"""
https://qwen.readthedocs.io/en/latest/deployment/vllm.html#extended-context-support
"""

import argparse
import os
import json
from huggingface_hub import snapshot_download


def download_and_update_model_repo(model_name_or_path, output_dir):
    # Download the entire model repository
    print(f"Downloading model repository from {model_name_or_path}...")
    repo_path = snapshot_download(repo_id=model_name_or_path, local_dir=output_dir)
    print(f"Model repository downloaded to {repo_path}")

    # Path to the config.json
    config_path = os.path.join(repo_path, "config.json")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.json not found in {repo_path}")

    # Read the existing config.json
    with open(config_path, "r") as f:
        config_data = json.load(f)

    # Add the new rope_scaling parameters
    config_data["rope_scaling"] = {"factor": 4.0, "original_max_position_embeddings": 32768, "type": "yarn"}

    # Save the updated config.json
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=4)
    print(f"Updated config.json saved to {config_path}")

    return repo_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download model repository and update config.json.")
    parser.add_argument("--model_name_or_path", required=True, type=str, help="Model repository ID on Hugging Face Hub.")
    parser.add_argument("--output_dir", required=True, type=str, help="Directory to store the downloaded repository.")
    args = parser.parse_args()

    repo_path = download_and_update_model_repo(args.model_name_or_path, args.output_dir)
    print(f"Updated model repository is available at {repo_path}")

# CUDA_VISIBLE_DEVICES="" python -m swesynth.scripts.misc.yarn --model_name_or_path Qwen/Qwen2.5-Coder-0.5B-Instruct --output_dir ./output/models/Qwen2.5-Coder-0.5B-Instruct_128K
# CUDA_VISIBLE_DEVICES="" python -m swesynth.scripts.misc.yarn --model_name_or_path Qwen/Qwen2.5-Coder-3B-Instruct --output_dir ./output/models/Qwen2.5-Coder-3B-Instruct_128K
# CUDA_VISIBLE_DEVICES="" python -m swesynth.scripts.misc.yarn --model_name_or_path Qwen/Qwen2.5-Coder-14B-Instruct --output_dir ./output/models/Qwen2.5-Coder-14B-Instruct_128K
# CUDA_VISIBLE_DEVICES="" python -m swesynth.scripts.misc.yarn --model_name_or_path Qwen/Qwen2.5-Coder-32B-Instruct-AWQ --output_dir ./output/models/Qwen2.5-Coder-32B-Instruct-AWQ_128K
