#!/usr/bin/env python
"""
Given a preds.jsonl file and a gold.jsonl file, this script will determine whether the predictions are correct or not using AST comparison.
python -m swesynth.scripts.correctness \
    --preds preds.jsonl \
    --dataset "princeton-nlp/SWE-bench_Lite" \
    --cache-dir .cache
"""

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path

from git import Repo
import pandas as pd
from datasets import load_dataset
from loguru import logger
from tqdm import tqdm

from swesynth import RepositorySnapshot
from swesynth.mutation.processing.program.correctness import check_ast_correctness
from swesynth.mutation.processing.program.extract import get_changed_code_files_from_minimized_diff
from swesynth.mutation.version_control.checkout import GitRemoteProgress
from swesynth.utils import read_jsonl
from swesynth.utils.misc import colordiff


def git_diff_strings(str1, str2, filename1="old.txt", filename2="new.txt"):
    """
    Compute a git-like diff representation between two strings.

    Args:
        str1 (str): The first string (old version)
        str2 (str): The second string (new version)
        filename1 (str, optional): Name for the first file in the diff output. Defaults to "old.txt".
        filename2 (str, optional): Name for the second file in the diff output. Defaults to "new.txt".

    Returns:
        str: A git-like diff representation
    """
    # Split the strings into lines
    lines1 = str1.splitlines(True)  # keepends=True to keep line endings
    lines2 = str2.splitlines(True)

    # Generate a unified diff
    diff = difflib.unified_diff(lines1, lines2, fromfile=filename1, tofile=filename2, n=3)  # Context lines (git default is 3)

    # Join the diff lines into a single string
    return "".join(diff)


def evaluate_prediction(row, cache_dir: Path):
    """
    Evaluate if a model prediction matches the gold solution using AST comparison.

    Args:
        row: DataFrame row containing prediction and gold data
        cache_dir: Directory to store repository clones

    Returns:
        dict: Result data including correctness information
    """
    instance_id = row["instance_id"]
    result = {"instance_id": instance_id, "correct": {}}

    logger.info(f"Evaluating instance: {instance_id}")

    # Check if prediction patch is empty
    prediction_patch = row["model_patch"]
    if not prediction_patch or prediction_patch.strip() == "":
        logger.info(f"Empty prediction patch for instance {instance_id}")
        result["empty_patch"] = True
        result["all_correct"] = False
        return result

    result["empty_patch"] = False

    # Create repository snapshot from the instance
    logger.debug(f"Creating repository snapshot for instance {instance_id}")
    instance = RepositorySnapshot.from_swebench_instance(row)
    path = cache_dir / instance.repo.replace("/", "_")
    if not path.exists():
        Repo.clone_from(f"https://github.com/{instance.repo}.git", path, progress=GitRemoteProgress())
    instance.origin._cached_origin = path

    with instance as repo_path:
        gold_patch = row["patch"]

        logger.debug(f"Gold patch for {instance_id}:\n{colordiff(gold_patch)}")
        logger.debug(f"Model prediction patch for {instance_id}:\n{colordiff(prediction_patch)}")

        # Get changed files from gold patch
        logger.debug(f"Extracting changed files from gold patch")
        changed_files = get_changed_code_files_from_minimized_diff(gold_patch)
        logger.debug(f"Changed files: {', '.join(changed_files)}")

        # Save original content
        logger.debug(f"Saving original content of changed files")
        changed_files_to_old_content = {}
        for file in changed_files:
            try:
                content = (repo_path / file).read_text_with_encoding_retry()
                changed_files_to_old_content[file] = content
                logger.debug(f"Saved original content for {file} ({len(content)} chars)")
            except Exception as e:
                logger.error(f"Error reading original content of {file}: {e}")

        # Apply gold patch and save content
        try:
            logger.debug(f"Applying gold patch to repository")
            apply_cmd = f"""git apply -v <<-"EOF"\n{gold_patch}\nEOF"""
            process = subprocess.run(apply_cmd, shell=True, check=True, cwd=repo_path, capture_output=True, text=True)
            logger.debug(f"Git apply output:\n{process.stdout}")

            logger.debug(f"Saving gold-patched content")
            changed_files_to_gold_content = {}
            for file in changed_files:
                try:
                    content = (repo_path / file).read_text_with_encoding_retry()
                    changed_files_to_gold_content[file] = content
                    logger.debug(f"Saved gold content for {file} ({len(content)} chars)")
                except Exception as e:
                    logger.error(f"Error reading gold content of {file}: {e}")

            # Reset to original state
            logger.debug(f"Resetting repository to original state")
            checkout_process = subprocess.run("git checkout .", shell=True, check=True, cwd=repo_path, capture_output=True, text=True)
            logger.debug(f"Git checkout output:\n{checkout_process.stdout}")

            # Apply prediction patch and save content
            logger.debug(f"Applying prediction patch to repository")
            pred_apply_cmd = f"""git apply -v <<-"EOF"\n{prediction_patch}\nEOF"""
            pred_process = subprocess.run(pred_apply_cmd, shell=True, check=True, cwd=repo_path, capture_output=True, text=True)
            logger.debug(f"Prediction patch git apply output:\n{pred_process.stdout}")

            logger.debug(f"Saving prediction-patched content")
            changed_files_to_pred_content = {}
            for file in changed_files:
                try:
                    content = (repo_path / file).read_text_with_encoding_retry()
                    changed_files_to_pred_content[file] = content
                    logger.debug(f"Saved prediction content for {file} ({len(content)} chars)")
                except Exception as e:
                    logger.error(f"Error reading prediction content of {file}: {e}")

            # Check AST correctness for each file
            logger.debug(f"Checking AST correctness for changed files")
            all_correct = True
            for file in changed_files:
                logger.debug(f"Comparing ASTs for file: {file}")
                is_correct = check_ast_correctness(changed_files_to_gold_content[file], changed_files_to_pred_content[file])

                result["correct"][file] = is_correct
                logger.info(f"File {file} AST match: {is_correct}")

                if not is_correct:
                    all_correct = False

                # Generate diff between gold and prediction
                diff = git_diff_strings(changed_files_to_gold_content[file], changed_files_to_pred_content[file], "gold", "pred")
                result[f"diff_{file}"] = diff

                logger.debug(f"Diff between gold and prediction for {file}:")
                logger.debug(colordiff(diff))

            result["all_correct"] = all_correct
            logger.info(f"Overall correctness for instance {instance_id}: {all_correct}")

        except Exception as e:
            logger.error(f"Error processing instance {instance_id}: {e}")
            result["error"] = str(e)
            result["all_correct"] = False
    return result


def load_existing_results(output_path):
    """
    Load existing results from output file if available.

    Args:
        output_path: Path to the output file

    Returns:
        dict: Map of instance_id to result entry
    """
    existing_results = {}
    if Path(output_path).exists():
        try:
            with open(output_path, "r") as f:
                for line in f:
                    try:
                        result = json.loads(line.strip())
                        if "instance_id" in result:
                            existing_results[result["instance_id"]] = result
                    except json.JSONDecodeError:
                        continue
            logger.info(f"Loaded {len(existing_results)} existing results from {output_path}")
        except Exception as e:
            logger.warning(f"Error loading existing results from {output_path}: {e}")
    return existing_results


def main():
    parser = argparse.ArgumentParser(description="Evaluate model predictions against gold solutions using AST comparison")
    parser.add_argument("--preds", type=str, required=True, help="Path to predictions JSONL file")
    parser.add_argument("--dataset", type=str, default="princeton-nlp/SWE-bench_Lite", help="HuggingFace dataset name or path to a .parquet file")
    parser.add_argument("--output", type=str, default="results.jsonl", help="Path to output JSONL file (default: results.jsonl)")
    parser.add_argument("--cache-dir", type=str, default=".cache", help="Directory to store repository clones (default: .cache)")

    args = parser.parse_args()

    # Ensure cache directory exists
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting SWE-bench correctness evaluation")
    logger.info(f"Parameters: preds={args.preds}, dataset={args.dataset}, output={args.output}, cache_dir={args.cache_dir}")

    # Load existing results to avoid recomputing
    existing_results = load_existing_results(args.output)

    # Load predictions
    logger.info(f"Loading predictions from {args.preds}")
    predictions = read_jsonl(args.preds)
    pred_df = pd.DataFrame(predictions)
    logger.info(f"Loaded {len(pred_df)} predictions")

    # Load dataset (check if it's a .parquet file or Hugging Face dataset)
    if args.dataset.endswith(".parquet"):
        logger.info(f"Loading dataset from .parquet file: {args.dataset}")
        ds_df = pd.read_parquet(args.dataset)
    else:
        logger.info(f"Loading dataset {args.dataset} from HuggingFace")
        ds = load_dataset(args.dataset)
        ds_df = ds["test"].to_pandas()

    logger.info(f"Loaded {len(ds_df)} dataset instances")
    total_tasks = len(ds_df)

    # Merge predictions with dataset
    df = ds_df.merge(pred_df, on="instance_id")
    logger.info(f"Found {len(df)} instances to evaluate after merging")

    # Filter out already evaluated instances
    to_evaluate = []
    for _, row in df.iterrows():
        instance_id = row["instance_id"]
        if instance_id not in existing_results:
            to_evaluate.append(row)

    logger.info(f"Skipping {len(df) - len(to_evaluate)} already evaluated instances")
    logger.info(f"Evaluating {len(to_evaluate)} new instances")

    # Evaluate each prediction and stream results to file
    results = list(existing_results.values())  # Start with existing results

    with open(args.output, "a") as f:
        for row in tqdm(to_evaluate, desc="Evaluating predictions"):
            result = evaluate_prediction(row, cache_dir)
            # Write the result immediately to file
            f.write(json.dumps(result) + "\n")
            f.flush()  # Ensure it's written to disk
            results.append(result)

    # Count empty patches
    empty_patches = sum(1 for r in results if r.get("empty_patch", False))
    empty_patch_percentage = (empty_patches / total_tasks) * 100 if results else 0
    logger.info(f"Empty patches: {empty_patches}/{total_tasks} ({empty_patch_percentage:.2f}%)")

    # Print summary
    correct_count = sum(1 for r in results if r.get("all_correct", False))
    logger.info(f"Results: {correct_count}/{total_tasks} correct ({correct_count/total_tasks*100:.2f}%)")

    # # Detailed summary
    # file_results = {}
    # for result in results:
    #     for file, is_correct in result.get("correct", {}).items():
    #         if file not in file_results:
    #             file_results[file] = {"correct": 0, "total": 0}
    #         file_results[file]["total"] += 1
    #         if is_correct:
    #             file_results[file]["correct"] += 1

    # logger.info("Per-file correctness:")
    # for file, stats in file_results.items():
    #     pct = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
    #     logger.info(f"  {file}: {stats['correct']}/{stats['total']} ({pct:.2f}%)")

    # write result to result.json
    with open("correct_result.json", "w") as f:
        json.dump(
            {
                "total_count": len(results),
                "correct_count": correct_count,
                "correct_percentage": correct_count / total_tasks,
                "empty_patches": empty_patches,
                "empty_patch_percentage": empty_patches / total_tasks,
            },
            f,
            indent=4,
        )

    logger.info(f"Evaluation complete. Full results written to {args.output}")


if __name__ == "__main__":
    main()
