"""
python -m swesynth.scripts.mutation.export_cache logs logs-exported
"""

from pathlib import Path
import shutil
import argparse
from tqdm import tqdm
import yaml


# Function to check if a directory meets the criteria
def should_keep_dir(directory):
    dir_path = Path(directory)
    has_test2function_mapping = (dir_path / "test2function_mapping.json.zst").is_file()
    has_test_status = (dir_path / "test_status.json").is_file()
    has_reversed_patch = (dir_path / "reversed_patch.diff").is_file()

    # Check if mutated_source_code.yml exists and has non-empty mutation_info
    mutated_source_code_path = dir_path / "mutated_source_code.yml"
    has_mutation_info = False
    if mutated_source_code_path.is_file():
        with open(mutated_source_code_path, "r") as f:
            try:
                data = yaml.safe_load(f)
                has_mutation_info = bool(data.get("mutation_info"))
            except yaml.YAMLError as e:
                print(f"[ERROR] Failed to parse {mutated_source_code_path}: {e}")

    return has_test2function_mapping or (has_test_status and not has_reversed_patch and not has_mutation_info)


# Function to scan directories and filter them
def filter_directories(root_dir):
    directories_to_keep = []

    for subdir in tqdm(Path(root_dir).rglob("*"), desc="Scanning directories", unit="dir"):
        if subdir.is_dir():
            if should_keep_dir(subdir):
                directories_to_keep.append(subdir)
                print(f"[INFO] Keeping directory: {subdir}")
            else:
                print(f"[INFO] Skipping directory: {subdir}")

    return directories_to_keep


# Function to copy directories to another location
# Preserve entire nested tree structure
def copy_directories(directories, root_dir, destination_root, dry_run):
    destination_root = Path(destination_root)
    root_dir = Path(root_dir)

    if not destination_root.exists():
        print(f"[INFO] Creating destination directory: {destination_root}")
        destination_root.mkdir(parents=True, exist_ok=True)

    for directory in tqdm(directories, desc="Copying directories", unit="dir"):
        relative_path = directory.relative_to(root_dir)
        destination_dir = destination_root / relative_path

        if dry_run:
            print(f"[DRY RUN] Would copy {directory} to {destination_dir}")
        else:
            print(f"[INFO] Copying {directory} to {destination_dir}")
            destination_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(directory, destination_dir, dirs_exist_ok=True, ignore_dangling_symlinks=True)


# Main function to parse arguments and execute
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter and copy directories based on specific criteria.")
    parser.add_argument("root_directory", type=str, help="Root directory to scan.")
    parser.add_argument("destination_directory", type=str, help="Destination directory to copy the filtered directories.")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without actually copying directories.")

    args = parser.parse_args()

    # Get the list of directories to keep
    directories = filter_directories(args.root_directory)

    # Print the directories to keep
    print("Directories to keep:")
    for directory in directories:
        print(directory)

    # Copy the directories to the destination
    copy_directories(directories, args.root_directory, args.destination_directory, args.dry_run)
