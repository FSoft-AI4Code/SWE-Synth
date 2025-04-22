from git import Repo
import pandas as pd
from swesynth.mutation.processing.program.extract import get_changed_code_files_from_minimized_diff
import json
import difflib
from swesynth.utils.misc import colordiff
import subprocess

from loguru import logger
from swesynth import RepositorySnapshot
from pathlib import Path
from datasets import load_dataset


def git_diff_strings(str1, str2, filename1="old.txt", filename2="new.txt", n=3):
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
    diff = difflib.unified_diff(lines1, lines2, fromfile=filename1, tofile=filename2, n=n)  # Context lines (git default is 3)

    # Join the diff lines into a single string
    return "".join(diff)


if __name__ == "__main__":
    df = load_dataset("swesynth/SWE-Synth", split="train").to_pandas()
    rollout_result = load_dataset("swesynth/SWE-Synth_Moatless-SFT-Trajectories", split="train").to_pandas()
    rollout_result
    rollout_result.instance_id.nunique()
    run_df = (
        (
            df.drop_duplicates("instance_id")
            .set_index("instance_id")
            .join((rollout_result.groupby("instance_id").agg({"model_patch": list})))
            .dropna()
            .reset_index()
        )
        .explode("model_patch")
        .reset_index(drop=True)
    )

    cache_dir = "/tmp/swesynth/cache/eval"

    # all these are success fix
    (run_df[["instance_id", "model_patch", "problem_statement"]].to_json("rq8_all_fake_bug.jsonl.zst", orient="records", lines=True))
    (
        run_df[["instance_id", "model_patch", "problem_statement"]]
        .sample(200, random_state=42)
        .to_json("rq8_all_fake_bug_sample200.jsonl.zst", orient="records", lines=True)
    )
    gym = pd.read_parquet("SWE-Gym-logs-shortened.parquet")
    (
        gym[["instance_id", "patch", "problem_statement"]]
        .sample(200, random_state=42)
        .to_json("rq8_all_real_bug_sample200.jsonl.zst", orient="records", lines=True)
    )

    allowed_ids: set[str] = set(pd.read_json("rq8_all_fake_bug_sample200.jsonl.zst", lines=True).instance_id)
    # diff between buggy -> rollout
    #
    for idx, row in run_df.iterrows():
        # break
        # idx, row, cache_dir, jsonl_file = payload
        if row["instance_id"] not in allowed_ids:
            continue
        logger.info(f"Processing row index {idx}")
        instance = RepositorySnapshot.from_swebench_instance(row)
        path = Path(cache_dir) / instance.repo.replace("/", "_")
        logger.info(f"Repository path set to {path}")

        if not path.exists():
            logger.info(f"Cloning repository {instance.repo}")
            Repo.clone_from(f"https://github.com/{instance.repo}.git", path)
        instance.origin._cached_origin = path

        # with instance as repo_path:
        # %cd swesynth/

        with instance as repo_path:
            model_patch = row["model_patch"]
            logger.info(f"Applying model patch for index {idx}")
            changed_files = get_changed_code_files_from_minimized_diff(model_patch)
            logger.info(f"Changed files: {changed_files}")

            changed_files_to_old_content = {}
            for file in changed_files:
                try:
                    content = (repo_path / file).read_text()
                    changed_files_to_old_content[file] = content
                    logger.info(f"Read original content of {file} ({len(content)} chars)")
                except Exception as e:
                    logger.error(f"Error reading {file}: {e}")

            pred_apply_cmd = f"""git apply -v <<-"EOF"\n{model_patch}\nEOF"""
            subprocess.run(pred_apply_cmd, shell=True, cwd=repo_path, capture_output=True)
            logger.info(f"Applied model patch to repository")

            changed_files_to_pred_content = {}
            for file in changed_files:
                try:
                    content = (repo_path / file).read_text()
                    changed_files_to_pred_content[file] = content
                    logger.info(f"Read prediction-patched content of {file} ({len(content)} chars)")
                except Exception as e:
                    logger.error(f"Error reading {file}: {e}")

            result = {
                "index": idx,
                "instance_id": row["instance_id"],
                "patch": model_patch,
                "test_patch": row["test_patch"],
                "diffs": {},
                "color_diffs": {},
                "full_file_content_old": {},
                "full_file_content_after": {},
                "long_diffs": {},
                "long_color_diffs": {},
            }
            for file in changed_files:
                old_file = changed_files_to_old_content[file]
                pred_file = changed_files_to_pred_content[file]
                diff = git_diff_strings(old_file, pred_file, n=5)
                result["diffs"][file] = diff
                result["color_diffs"][file] = colordiff(diff)
                logger.info(f"Generated diff for {file}: {colordiff(diff)}")

                long_diff = git_diff_strings(old_file, pred_file, n=200)
                result["long_diffs"][file] = long_diff
                result["long_color_diffs"][file] = colordiff(long_diff)
                logger.info(f"Generated long diff for {file}: {colordiff(long_diff)}")

                result["full_file_content_old"][file] = old_file
                result["full_file_content_after"][file] = pred_file

            # save_to_jsonl(jsonl_file, result)
            with open("swesynth/output/human-study.jsonl", "a") as f:
                f.write(json.dumps(result) + "\n")

            logger.info(f"Finished processing index {idx}")

        result
