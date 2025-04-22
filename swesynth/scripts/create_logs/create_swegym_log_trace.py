"""
python -m swesynth.scripts.create_logs.create_swegym_log_trace \
    --dataset SWE-Gym/SWE-Gym \
    --output_dir ./swegym_logs \
    --shard_id 0 \
    --total_num_shard 4

# collect all shards
python -m swesynth.scripts.create_logs.create_swegym_log_trace \
    --dataset SWE-Gym/SWE-Gym \
    --output_dir ./swegym_logs
"""

import argparse
import json
from pathlib import Path
import pandas as pd

from datasets import Dataset, DatasetDict, load_dataset
from tqdm.auto import tqdm
from swesynth import RepositorySnapshot
from swesynth.mutation.validator.tester import Tester
from loguru import logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swebench.harness.constants import SWEbenchInstance

tqdm.pandas()


@logger.catch(BaseException, reraise=True)
def main(dataset_name: str, output_dir: str, shard_id: int = None, total_num_shard: int = None):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logger.add(f"{output_dir}/create_log_trace.log", level="DEBUG")
    logger.info("====== Starting log trace creation process ======")

    # Load dataset
    logger.info(f"Loading dataset: {dataset_name}")
    ds = load_dataset(dataset_name)
    logger.debug(f"Dataset loaded with splits: {ds.keys()}")

    train_df = pd.DataFrame(ds["train"])
    logger.debug(f"train split shape: {train_df.shape}")

    # Apply sharding if applicable
    if shard_id is not None and total_num_shard is not None:
        train_df = train_df.iloc[shard_id::total_num_shard]
        logger.info(f"Processing shard {shard_id} out of {total_num_shard} shards, containing {len(train_df)} samples.")

    # Generate log traces
    def get_log_trace(sample: pd.Series) -> str | None:
        try:
            d: "SWEbenchInstance" = sample.to_dict()
            obj: RepositorySnapshot = RepositorySnapshot.from_swebench_instance(d)
            log_trace: str = Tester.get_test_case_log(obj)
            logger.debug(f"Generated log trace for sample ID: {d.get('instance_id', 'N/A')}")
            return log_trace
        except Exception as e:
            logger.error(f"Failed to generate log trace for sample: {sample} with error: {e}")
            logger.exception(e)
            return None

    logger.info("Generating log traces for the train split")
    tmp_dir = Path(output_dir) / "train_logs"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    pbar = tqdm(train_df.iterrows(), total=len(train_df), desc="Generating log traces")
    for _, sample in pbar:
        pbar.set_postfix_str(f"Processing {sample['instance_id']}")
        if sample["repo"].lower() == "modin-project/modin" or sample["repo"].lower() == "pandas-dev/pandas":
            logger.warning(f"Skipping sample with Modin repo: {sample['instance_id']}")
            continue
        if (tmp_dir / f"{sample['instance_id']}.json").exists() and (tmp_dir / f"{sample['instance_id']}.json").read_json():
            with open(tmp_dir / f"{sample['instance_id']}.json", "r") as f:
                log_trace = json.load(f)
        else:
            log_trace = get_log_trace(sample)
            with open(tmp_dir / f"{sample['instance_id']}.json", "w") as f:
                json.dump(log_trace, f)

    if shard_id is not None and total_num_shard is not None:
        logger.info(f"Completed log traces for shard {shard_id} out of {total_num_shard} shards")
        return

    output = []
    for _, sample in tqdm(train_df.iterrows(), total=len(train_df), desc="Reading log traces"):
        if (tmp_dir / f"{sample['instance_id']}.json").exists():
            with open(tmp_dir / f"{sample['instance_id']}.json", "r") as f:
                log_trace: str | None = json.load(f)
                sample["problem_statement"] = log_trace
                output.append(sample)

    train_df = pd.DataFrame(output)
    logger.info("Completed log traces for the train split")

    # Convert back to Hugging Face dataset format
    logger.info("Converting dataframes to Hugging Face DatasetDict format")
    dataset = DatasetDict(
        {
            "train": Dataset.from_pandas(train_df),
        }
    )

    logger.info("Saving dataset with log traces to disk")
    logger.info(f"Saving dataset to directory: {output_dir}")
    dataset.save_to_disk(output_dir)
    logger.info("Dataset saved successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create SWEbench dataset with log traces.")
    parser.add_argument("--dataset", default="SWE-Gym/SWE-Gym", help="Name of the dataset to load from Hugging Face.")
    parser.add_argument("--output_dir", required=True, help="Directory where the output dataset with log traces will be saved.")
    parser.add_argument("--shard_id", type=int, default=None, help="Shard ID (zero-based index) for processing a subset of data.")
    parser.add_argument("--total_num_shard", type=int, default=None, help="Total number of shards for parallel processing.")

    args = parser.parse_args()
    main(args.dataset, args.output_dir, args.shard_id, args.total_num_shard)
