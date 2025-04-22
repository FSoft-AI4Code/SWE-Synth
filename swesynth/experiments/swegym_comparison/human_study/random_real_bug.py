import re
import json
import difflib
import tempfile
import subprocess
from pathlib import Path

import pandas as pd
from loguru import logger
from git import Repo

from swesynth import RepositorySnapshot
from swesynth.mutation.processing.program.extract import get_changed_code_files_from_minimized_diff
from swesynth.utils.misc import colordiff


def git_diff_strings(str1, str2, filename1="old.txt", filename2="new.txt", n=3):
    """
    Compute a git-like diff representation between two strings.
    """
    lines1 = str1.splitlines(True)
    lines2 = str2.splitlines(True)
    diff = difflib.unified_diff(lines1, lines2, fromfile=filename1, tofile=filename2, n=n)
    return "".join(diff)


def main():
    gym = pd.read_parquet("SWE-Gym-logs-shortened.parquet")
    sample_gym = gym[["instance_id", "patch", "problem_statement", "test_patch"]].sample(200, random_state=42)
    sample_gym.to_json("rq8_all_real_bug_sample200.jsonl.zst", orient="records", lines=True)
    allowed_gym_ids = set(sample_gym["instance_id"].unique())

    cache_dir = "/tmp/swesynth/cache/eval"

    for idx, row in gym.iterrows():
        if row["instance_id"] not in allowed_gym_ids:
            continue

        logger.info(f"Processing row index {idx}")
        instance = RepositorySnapshot.from_swebench_instance(row)
        path = Path(cache_dir) / instance.repo.replace("/", "_")
        logger.info(f"Repository path set to {path}")

        if not path.exists():
            logger.info(f"Cloning repository {instance.repo}")
            Repo.clone_from(f"https://github.com/{instance.repo}.git", path)

        instance.origin._cached_origin = path

        with instance as repo_path:
            model_patch = row.get("model_patch", row["patch"])
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

            with tempfile.NamedTemporaryFile() as f:
                f.write(model_patch.encode())
                f.flush()
                pred_apply_cmd = f"git apply -v {f.name}"
                subprocess.run(pred_apply_cmd, shell=True, cwd=repo_path, capture_output=True)
                logger.info("Applied model patch to repository")

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
                try:
                    old_file = changed_files_to_old_content[file]
                    pred_file = changed_files_to_pred_content[file]
                    diff = git_diff_strings(old_file, pred_file, n=5)
                    result["diffs"][file] = diff
                    result["color_diffs"][file] = colordiff(diff)
                    logger.info(f"Generated diff for {file}")

                    long_diff = git_diff_strings(old_file, pred_file, n=200)
                    result["long_diffs"][file] = long_diff
                    result["long_color_diffs"][file] = colordiff(long_diff)
                    logger.info(f"Generated long diff for {file}")

                    result["full_file_content_old"][file] = old_file
                    result["full_file_content_after"][file] = pred_file
                except Exception as e:
                    logger.error(f"Error processing {file}: {e}")

            with open("swesynth/output/human-study-real-bug.jsonl", "a") as f:
                f.write(json.dumps(result) + "\n")

            logger.info(f"Finished processing index {idx}")


if __name__ == "__main__":
    main()
