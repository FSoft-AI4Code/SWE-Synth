"""
python -m swesynth.scripts.create_logs.create_swebench_log_trace \
    --dataset "princeton-nlp/SWE-bench_Lite" \
    --output_dir "./output/SWE-bench_Lite_with_test_logs"
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


@logger.catch
def main(dataset_name: str, output_dir: str):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logger.add(f"{output_dir}/create_log_trace.log", level="DEBUG")
    logger.info("====== Starting log trace creation process ======")

    # Load dataset
    logger.info(f"Loading dataset: {dataset_name}")
    ds = load_dataset(dataset_name)
    logger.debug(f"Dataset loaded with splits: {ds.keys()}")

    dev_df = pd.DataFrame(ds["dev"])
    test_df = pd.DataFrame(ds["test"])
    logger.debug(f"Dev split shape: {dev_df.shape}")
    logger.debug(f"Test split shape: {test_df.shape}")

    # Generate log traces
    def get_log_trace(sample: pd.Series):
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

    logger.info("Generating log traces for the dev split")
    if (Path(output_dir) / "dev_df.gz").exists():
        dev_df = pd.read_pickle(Path(output_dir) / "dev_df.gz", compression="gzip")
    else:
        dev_df["problem_statement"] = dev_df.progress_apply(get_log_trace, axis=1)
        dev_df.to_pickle(Path(output_dir) / "dev_df.gz", compression="gzip")
    logger.info("Completed log traces for the dev split")

    logger.info("Generating log traces for the test split")
    if (Path(output_dir) / "test_df.gz").exists():
        test_df = pd.read_pickle(Path(output_dir) / "test_df.gz", compression="gzip")
    else:
        test_df["problem_statement"] = test_df.progress_apply(get_log_trace, axis=1)
        test_df.to_pickle(Path(output_dir) / "test_df.gz", compression="gzip")
    logger.info("Completed log traces for the test split")

    # Convert back to Hugging Face dataset format
    logger.info("Converting dataframes to Hugging Face DatasetDict format")
    dataset = DatasetDict({"dev": Dataset.from_pandas(dev_df), "test": Dataset.from_pandas(test_df)})

    logger.info("Saving dataset with log traces to disk")
    logger.info(f"Saving dataset to directory: {output_dir}")
    dataset.save_to_disk(output_dir)
    logger.info("Dataset saved successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create SWEbench dataset with log traces.")
    parser.add_argument("--dataset", default="princeton-nlp/SWE-bench_Lite", help="Name of the dataset to load from Hugging Face.")
    parser.add_argument("--output_dir", required=True, help="Directory where the output dataset with log traces will be saved.")
    args = parser.parse_args()
    main(args.dataset, args.output_dir)
