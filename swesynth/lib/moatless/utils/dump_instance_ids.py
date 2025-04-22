#!/usr/bin/env python3
"""
python -m swesynth.lib.moatless.utils.dump_instance_ids \
    --input-file swesynth17-5-2-2025.parquet \
    --output-file swesynth17-5-2-2025.txt

Or to load from Hugging Face datasets:
python -m swesynth.lib.moatless.utils.dump_instance_ids \
    --dataset hf_dataset_name \
    --split train \
    --output-file swesynth17-5-2-2025.txt
"""

import argparse
import pandas as pd
from loguru import logger
from datasets import load_dataset, load_from_disk


def load_dataframe(input_file=None, dataset=None, split=None):
    if dataset:
        logger.info(f"Loading dataset {dataset}, split {split} from Hugging Face")
        # ds = load_dataset(dataset, split=split)
        ds = load_from_disk(dataset)[split]
        df = pd.DataFrame(ds)
    else:
        logger.info(f"Loading DataFrame from {input_file}")
        df = pd.read_parquet(input_file)

    logger.info(f"DataFrame loaded with {len(df)} rows")
    return df


def main():
    parser = argparse.ArgumentParser(description="Read instance_id from a Parquet file or Hugging Face dataset and write to a text file.")
    parser.add_argument("--input-file", type=str, required=False, help="Path to the input Parquet file.")
    parser.add_argument("--dataset", type=str, required=False, help="Hugging Face dataset name.")
    parser.add_argument("--split", type=str, default="train", help="Dataset split to use (default: train).")
    parser.add_argument("--output-file", type=str, required=True, help="Path to the output text file.")
    args = parser.parse_args()

    if not args.input_file and not args.dataset:
        parser.error("Either --input-file or --dataset must be specified.")

    df = load_dataframe(input_file=args.input_file, dataset=args.dataset, split=args.split)

    logger.info(f"Writing instance_id column to {args.output_file}")
    with open(args.output_file, "w") as f:
        for instance_id in df["instance_id"]:
            f.write(f"{instance_id}\n")

    logger.info("Completed writing instance_id values.")


if __name__ == "__main__":
    main()
