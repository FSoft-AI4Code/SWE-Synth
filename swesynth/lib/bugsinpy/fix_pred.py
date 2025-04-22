"""
python -m swesynth.lib.bugsinpy.fix_pred preds.jsonl
"""

import argparse
import pandas as pd
from pathlib import Path


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Filter predictions based on allowed instance IDs.")
    parser.add_argument("jsonl_file", type=str, help="Path to the input JSONL file")
    parser.add_argument("--output", type=str, help="Path to the output JSONL file (default: inplace replacement)")
    args = parser.parse_args()

    # Set output file to input file if not provided
    output_file = args.output if args.output else args.jsonl_file

    # Get the directory of the current script
    script_dir = Path(__file__).resolve().parent
    ids_file = script_dir / "reproducable_ids.txt"

    # Read allowed IDs from the text file
    with ids_file.open("r") as f:
        allowed_ids = {line.strip() for line in f}

    # Read JSONL file
    preds = pd.read_json(args.jsonl_file, lines=True)
    input_rows = len(preds)
    print(f"Loaded {input_rows} rows from {args.jsonl_file}")

    # Process and filter data
    filtered_preds = (
        preds.assign(instance_id=lambda x: x["instance_id"].str.replace("spaCy", "spacy"))
        .assign(id=lambda x: x["instance_id"].str.split("__").str[-1])
        .query("id in @allowed_ids")
        .drop(columns=["id"])
    )
    output_rows = len(filtered_preds)
    print(f"Filtered down to {output_rows} rows")

    # Save to output file
    filtered_preds.to_json(output_file, orient="records", lines=True)
    print(f"Saved output to {output_file}")


if __name__ == "__main__":
    main()
