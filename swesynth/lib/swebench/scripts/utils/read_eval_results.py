"""
python -m swesynth.lib.swebench.scripts.utils.read_eval_results '*.json'
"""

import json
import sys
import glob
from pathlib import Path


def filter_json(file_path):
    if Path(file_path).name == "args.json":
        return
    # Load the JSON file
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        print(f"Error: {file_path} is not a valid JSON file.")
        return

    # Filter keys containing "instances"
    filtered_data = {key: value for key, value in data.items() if "instances" in key}

    # Print the file name and filtered JSON
    print(f"--- {file_path} ---")
    if filtered_data:
        print(json.dumps(filtered_data, indent=4))
        print(f"Submitted instances: {filtered_data["submitted_instances"]}/{filtered_data["total_instances"]}")
        print(
            f"Resolved instances: {filtered_data["resolved_instances"]}/{filtered_data["total_instances"]} ({(filtered_data["resolved_instances"] / filtered_data["total_instances"]) * 100:.2f}%)"
        )
        print(
            f"Empty patch instances: {filtered_data["empty_patch_instances"]}/{filtered_data["total_instances"]} ({(filtered_data["empty_patch_instances"] / filtered_data["total_instances"]) * 100:.2f}%)"
        )
        print(
            f"Error instances: {filtered_data["error_instances"]}/{filtered_data["total_instances"]} ({(filtered_data["error_instances"] / filtered_data["total_instances"]) * 100:.2f}%)"
        )
        # check if there is correctness result beside it

    if (Path(file_path).parent / "correct_result.json").exists():
        with open(Path(file_path).parent / "correct_result.json", "r") as file:
            correct_data = json.load(file)
        print("Correctness result:")
        # print(json.dumps(correct_data, indent=4))
        num_total_task = int(correct_data["correct_count"] / correct_data["correct_percentage"])
        print(f"Submitted patches: {correct_data['total_count']}/{num_total_task}")
        print(f"Empty patches: {correct_data['empty_patches']}/{num_total_task} ({correct_data['empty_patch_percentage'] * 100:.2f}%)")
        print(f"Correct patches: {correct_data['correct_count']}/{num_total_task} ({correct_data['correct_percentage'] * 100:.2f}%)")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python filter_instances.py <input_json_files>")
    else:
        # Expand the glob pattern and process each file
        file_paths = glob.glob(sys.argv[1])
        if not file_paths:
            print("No files matched the given pattern.")
        else:
            for file_path in file_paths:
                try:
                    filter_json(file_path)
                except:
                    print(f"Error: Could not process {file_path}.")
                    continue
