"""
python -m swesynth.lib.swebench.scripts.utils.fix_jsonl *.jsonl
"""

import json
import argparse
import glob
import os


def fix_jsonl_file(file_path):
    valid_lines = []

    # Read the file and validate each line
    with open(file_path, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            try:
                json_obj = json.loads(line)
                valid_lines.append(json.dumps(json_obj))  # Store valid JSON line
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_number} in {file_path}: {e}\nLine content: {line.strip()}")

    # Write back only the valid lines
    with open(file_path, "w", encoding="utf-8") as file:
        file.write("\n".join(valid_lines) + "\n")

    print(f"Fixed JSONL file: {file_path}, valid lines: {len(valid_lines)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix corrupted lines in JSONL files.")
    parser.add_argument("files", nargs="+", help="Path to one or more JSONL files (wildcards supported)")
    args = parser.parse_args()

    file_list = []
    for pattern in args.files:
        file_list.extend(glob.glob(pattern))

    for file_path in file_list:
        if os.path.isfile(file_path):
            fix_jsonl_file(file_path)
        else:
            print(f"Skipping invalid file: {file_path}")
