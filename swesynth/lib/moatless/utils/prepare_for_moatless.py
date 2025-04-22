#!/usr/bin/env python3
"""
python -m swesynth.lib.moatless.utils.prepare_for_moatless \
    --input-file swesynth17-5-2-2025.parquet \
    --output-file swesynth17-5-2-2025-shortened.parquet

Or to load from Hugging Face datasets:
python -m swesynth.lib.moatless.utils.prepare_for_moatless \
    --dataset hf_dataset_name \
    --split train \
    --output-file swesynth17-5-2-2025-shortened.parquet
"""

import argparse
import pandas as pd
from datasets import Dataset, load_dataset, load_from_disk
from loguru import logger
from transformers import AutoTokenizer


def load_dataframe(input_file=None, dataset=None, split=None):
    if dataset:
        logger.info(f"Loading dataset {dataset}, split {split} from Hugging Face")
        ds = load_from_disk(dataset)[split]
        df = ds.to_pandas()
        if "__index_level_0__" in df.columns:
            df.drop(columns=["__index_level_0__"], inplace=True)
    else:
        logger.info(f"Reading input file: {input_file}")
        df = pd.read_parquet(input_file)

    logger.info(f"Initial DataFrame size: {df.shape[0]} rows")
    return df


def main():
    parser = argparse.ArgumentParser(description="Shorten logs in a Parquet file or Hugging Face dataset.")
    parser.add_argument("--input-file", type=str, required=False, help="Path to the input Parquet file.")
    parser.add_argument("--dataset", type=str, required=False, help="Hugging Face dataset name.")
    parser.add_argument("--split", type=str, default="train", help="Dataset split to use (default: train).")
    parser.add_argument("--output-file", type=str, required=True, help="Path to save the shortened Parquet file.")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-Coder-32B-Instruct", help="Hugging Face model name to load the tokenizer from.")
    parser.add_argument("--max-tokens", type=int, default=16000, help="Max tokens for truncation.")
    parser.add_argument("--num-proc", type=int, default=40, help="Number of processes to use for dataset mapping.")
    args = parser.parse_args()

    if not args.input_file and not args.dataset:
        parser.error("Either --input-file or --dataset must be specified.")

    df = load_dataframe(input_file=args.input_file, dataset=args.dataset, split=args.split)

    logger.info("Initializing tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.model)

    def shorten_log(problem_statement: str, max_tokens: int = 16000) -> str:
        tokens = tokenizer.encode(problem_statement, add_special_tokens=False)
        if len(tokens) > max_tokens:
            truncated_log = tokenizer.decode(tokens[:max_tokens], skip_special_tokens=True)
            return truncated_log + "\n[log truncated]"
        return problem_statement

    logger.info("Filtering out rows with NaN in 'problem_statement'...")
    df = df[~df["problem_statement"].isna()]
    logger.info(f"DataFrame size after filtering: {df.shape[0]} rows")

    logger.info("Converting DataFrame to a Hugging Face Dataset...")
    ds = Dataset.from_pandas(df)

    logger.info("Truncating problem statements if needed...")

    def map_fn(x):
        return {"problem_statement": shorten_log(x["problem_statement"], args.max_tokens)}

    processed_ds = ds.map(map_fn, num_proc=args.num_proc)

    logger.info("Converting back to a Pandas DataFrame...")
    df_shortened = processed_ds.to_pandas()

    logger.info(f"Writing output Parquet to: {args.output_file}")
    df_shortened.to_parquet(args.output_file)
    logger.info("Processing complete.")


if __name__ == "__main__":
    main()
