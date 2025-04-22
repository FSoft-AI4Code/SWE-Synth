"""
python -m swesynth.scripts.create_logs.create_swegym_log_trace_multiprocessing \
    --dataset SWE-Gym/SWE-Gym \
    --output_dir ./swegym_logs \
    --num_workers 24
"""

import argparse
import json
import os
from pathlib import Path

import pandas as pd
from datasets import Dataset, DatasetDict, load_dataset
from loguru import logger
from multiprocessing import Pool
from tqdm.auto import tqdm
from functools import partial

from swesynth import RepositorySnapshot
from swesynth.mutation.validator.tester import Tester
from typing import TYPE_CHECKING

from swesynth.mutation.version_control.get_version import RepoVersion

if TYPE_CHECKING:
    from swebench.harness.constants import SWEbenchInstance


# We define this at top-level so it can be pickled by multiprocessing on Windows.
def get_log_trace(sample: pd.Series) -> str | None:
    """
    Generate log trace from a single sample. Returns the log trace or None if it fails.
    """
    try:
        d: "SWEbenchInstance" = sample.to_dict()
        obj: RepositorySnapshot = RepositorySnapshot.from_swebench_instance(d)
        log_trace: str = Tester.get_test_case_log(obj)
        logger.debug(f"Generated log trace for sample ID: {d.get('instance_id', 'N/A')}")
        return log_trace
    except Exception as e:
        logger.error(f"Failed to generate log trace for sample {sample.get('instance_id')} with error: {e}")
        logger.exception(e)
        return None


def process_sample(sample_dict: dict, tmp_dir: Path) -> None:
    """
    Called by Pool workers for each sample dict.
    Skips certain repos, checks if log file already exists, otherwise generates the log file.
    """
    instance_id = sample_dict["instance_id"]
    repo_name = sample_dict["repo"].lower()

    # Skip special repos
    # if repo_name in ["modin-project/modin", "pandas-dev/pandas"]:
    #     logger.warning(f"Skipping sample with Modin/Pandas repo: {instance_id}")
    #     return

    out_file = tmp_dir / f"{instance_id}.json"
    if out_file.exists():
        # Attempt to read it. If valid, skip generation
        try:
            with open(out_file, "r") as f:
                a = json.load(f)

            if a is not None:
                return

        except json.JSONDecodeError:
            # If file is corrupted, re-generate
            logger.warning(f"Log file {out_file} is corrupted; regenerating...")

    # Generate and save the log trace
    sample_series = pd.Series(sample_dict)
    log_trace: str | None = get_log_trace(sample_series)
    with open(out_file, "w") as f:
        json.dump(log_trace, f)


@logger.catch(BaseException, reraise=True)
def main(dataset_name: str, output_dir: str, num_workers: int = 1):
    # Prepare output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logger.add(f"{output_dir}/create_log_trace.log", level="DEBUG")
    logger.info("====== Starting log trace creation process ======")

    # Load dataset
    logger.info(f"Loading dataset: {dataset_name}")
    ds = load_dataset(dataset_name)
    logger.debug(f"Dataset loaded with splits: {list(ds.keys())}")

    train_df = pd.DataFrame(ds["train"])
    logger.debug(f"Train split shape: {train_df.shape}")

    # Prepare a directory for the JSON logs
    tmp_dir = Path(output_dir) / "train_logs"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    RepoVersion()

    # Multiprocessing setup
    logger.info(f"Spawning Pool with {num_workers} workers for log trace generation...")
    partial_fn = partial(process_sample, tmp_dir=tmp_dir)
    with Pool(num_workers) as pool:
        list(tqdm(pool.imap(partial_fn, train_df.to_dict("records")), total=len(train_df), desc="Generating log traces"))

    logger.info("Completed generating log traces, now consolidating results.")

    # Now collect and store results in a final dataset
    output = []
    for _, sample in tqdm(train_df.iterrows(), total=len(train_df), desc="Reading log traces"):
        instance_id = sample["instance_id"]
        out_file = tmp_dir / f"{instance_id}.json"
        if out_file.exists():
            with open(out_file, "r") as f:
                try:
                    log_trace: str | None = json.load(f)
                    sample["problem_statement"] = log_trace
                except json.JSONDecodeError:
                    logger.error(f"Cannot read JSON for {instance_id}, skipping.")
                    sample["problem_statement"] = None
        else:
            sample["problem_statement"] = None
        output.append(sample)

    train_df = pd.DataFrame(output)
    logger.info("Completed reading log traces from the train split.")

    # Convert back to Hugging Face dataset format
    logger.info("Converting dataframes to Hugging Face DatasetDict format.")
    dataset = DatasetDict(
        {
            "train": Dataset.from_pandas(train_df),
        }
    )

    logger.info(f"Saving dataset with log traces to disk at: {output_dir}")
    dataset.save_to_disk(output_dir)
    logger.info("Dataset saved successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create SWEbench dataset with log traces using CPU multiprocessing.")
    parser.add_argument("--dataset", default="SWE-Gym/SWE-Gym", help="Name of the dataset to load from Hugging Face.")
    parser.add_argument("--output_dir", required=True, help="Directory where the output dataset with log traces will be saved.")
    parser.add_argument("--num_workers", type=int, default=24, help="Number of CPU workers to use for parallel processing.")
    args = parser.parse_args()

    main(args.dataset, args.output_dir, args.num_workers)
