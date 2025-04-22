import os
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--exp_path", type=str, required=True)
args = parser.parse_args()
exp_path = args.exp_path

# Define the directory containing the JSON-L files
directory_path = exp_path + "/preds"
output_file = exp_path + "/preds.jsonl"

# Initialize a list to store all JSON lines
all_lines = []

# Iterate through each file in the directory
for filename in os.listdir(directory_path):
    if filename.endswith(".jsonl"):  # Check for JSON-L files
        file_path = os.path.join(directory_path, filename)
        with open(file_path, "r") as f:
            all_lines.extend(f.readlines())  # Read and append each line

# Write all lines to the output file
with open(output_file, "w") as out_f:
    out_f.writelines(all_lines)

print(f"Successfully merged files into {output_file}")
