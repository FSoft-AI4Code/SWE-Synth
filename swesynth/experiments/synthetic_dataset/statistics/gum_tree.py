import os
from tqdm import tqdm
import json
import pandas as pd
from pathlib import Path
from swesynth import RepositorySnapshot
import subprocess
from swesynth.mutation.processing.program.correctness import check_ast_correctness
from swesynth.mutation.processing.program.extract import get_changed_code_files_from_minimized_diff
from swesynth.utils.misc import colordiff
from loguru import logger
from git import Repo
from collections import Counter
import hashlib
import os
import random
import string
import tempfile
import json
import subprocess
import difflib
import os
import json
import pandas as pd
from pathlib import Path
from swesynth import RepositorySnapshot
import subprocess
from swesynth.mutation.processing.program.extract import get_changed_code_files_from_minimized_diff
from swesynth.utils.misc import colordiff
from loguru import logger
from git import Repo
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm.contrib.concurrent import process_map
from datasets import load_dataset


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


def create_temp_file(content: str, base_dir: str = None) -> str:
    # Compute hash of content
    hasher = hashlib.sha256()
    hasher.update(content.encode("utf-8"))
    file_hash = hasher.hexdigest()

    # Generate random string
    random_suffix = "".join(random.choices(string.ascii_letters + string.digits, k=6))
    filename = f"{file_hash}_{random_suffix}.py"

    # Determine base directory
    if base_dir is None:
        base_dir = tempfile.gettempdir()
    os.makedirs(base_dir, exist_ok=True)

    file_path = os.path.join(base_dir, filename)

    # Write content to file
    with open(file_path, "w") as f:
        f.write(content)

    return file_path


def gum_tree(file1: str, file2: str, base_cache_dir: str = None) -> dict:
    file1_path = create_temp_file(file1, base_cache_dir)
    file2_path = create_temp_file(file2, base_cache_dir)

    try:
        command = f"/home/user1/temp/gumtree.sh {file1_path} {file2_path}"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
        output = result.stdout.decode("utf-8")
        return json.loads(output)
    finally:
        os.remove(file1_path)
        os.remove(file2_path)


def count_ast_changes(json_data, counting_parent: bool = False):
    counter = Counter()

    for action in json_data.get("actions", []):
        tree = action.get("tree", "")
        node_type = tree.split(":")[0].split(" ")[0]  # Extracting node type
        counter[node_type] += 1

        # get parent also
        parent = action.get("parent", "")
        parent_node_type = parent.split(":")[0].split(" ")[0]
        if counting_parent:
            if parent_node_type:
                counter[parent_node_type] += 1
    return counter


def resume_from_last_checkpoint(jsonl_file):
    processed_ids = set()
    if os.path.exists(jsonl_file):
        with open(jsonl_file, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    processed_ids.add(data["index"])
                except json.JSONDecodeError:
                    continue
        logger.info(f"Resuming processing. Found {len(processed_ids)} completed entries.")
    return processed_ids


def save_to_jsonl(jsonl_file, data):
    with open(jsonl_file, "a") as f:
        f.write(json.dumps(data) + "\n")


if __name__ == "__main__":
    logger.add("gum_tree.log", level="DEBUG")

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

    # def process_row(idx, row, cache_dir, jsonl_file):
    def process_row(payload):
        idx, row, cache_dir, jsonl_file = payload
        logger.info(f"Processing row index {idx}")
        instance = RepositorySnapshot.from_swebench_instance(row)
        path = Path(cache_dir) / instance.repo.replace("/", "_")
        logger.info(f"Repository path set to {path}")

        if not path.exists():
            logger.info(f"Cloning repository {instance.repo}")
            Repo.clone_from(f"https://github.com/{instance.repo}.git", path)
        instance.origin._cached_origin = path

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

            result = {"index": idx, "diffs": {}, "changes": {}, "changes_without_parent": {}}
            for file in changed_files:
                old_file = changed_files_to_old_content[file]
                pred_file = changed_files_to_pred_content[file]
                diff = git_diff_strings(old_file, pred_file)
                result["diffs"][file] = diff
                logger.info(f"Generated diff for {file}: {colordiff(diff)}")

                # Run GumTree analysis
                logger.info(f"Running GumTree analysis for {file}")
                gum_tree_result = gum_tree(old_file, pred_file)
                result["gum_tree"] = gum_tree_result
                logger.info(f"GumTree result for {file}: {gum_tree_result['actions']}")
                changed_statements = count_ast_changes(gum_tree_result, counting_parent=True)
                logger.info(f"AST changes for {file}: {changed_statements}")
                result["changes"][file] = changed_statements
                changed_statements_without_parent = count_ast_changes(gum_tree_result, counting_parent=False)
                logger.info(f"AST changes for {file} (without parent): {changed_statements_without_parent}")
                result["changes_without_parent"][file] = changed_statements_without_parent

            save_to_jsonl(jsonl_file, result)
            logger.info(f"Finished processing index {idx}")
        return idx

    # Main execution
    jsonl_file = "swesynth/results.jsonl"
    processed_ids = resume_from_last_checkpoint(jsonl_file)
    cache_dir = "/tmp/swesynth/cache/eval"
    # run_df = pd.read_csv("data.csv")  # Ensure correct file path

    tasks = [(idx, row, cache_dir, jsonl_file) for idx, row in run_df.iterrows() if idx not in processed_ids]

    def rr(x):
        return process_row(x)

    results = process_map(rr, tasks, max_workers=80, chunksize=1)
