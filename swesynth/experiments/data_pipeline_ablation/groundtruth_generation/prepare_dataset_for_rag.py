from pathlib import Path
from dotenv import load_dotenv
import argparse

load_dotenv()

import json
from datasets import load_from_disk, load_dataset
from transformers import AutoTokenizer
from trl.extras.dataset_formatting import conversations_formatting_function
import zstandard as zstd

model_name = "Qwen2.5-Coder-14B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(f"Qwen/{model_name}")


def get_messages(row):
    inputs = row["text"]
    system_messages = inputs.split("\n", 1)[0]
    user_message = inputs.split("\n", 1)[1]
    messages = [
        {"role": "system", "content": system_messages},
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": row["patch"]},
    ]
    messages_eval = [
        {"role": "system", "content": system_messages},
        {"role": "user", "content": user_message},
    ]
    return {"messages": messages, "messages_eval": messages_eval}


def conversations_formatting_function_generation(tokenizer: AutoTokenizer, messages_field):
    r"""
    return a callable function that takes in a "messages" dataset and returns a formatted dataset, based on the tokenizer
    apply chat template to the dataset
    """

    def format_dataset(examples):
        if isinstance(examples[messages_field][0], list):
            output_texts = []
            for i in range(len(examples[messages_field])):
                output_texts.append(tokenizer.apply_chat_template(examples[messages_field][i], tokenize=False, add_generation_prompt=True))
            return output_texts
        else:
            return tokenizer.apply_chat_template(examples[messages_field], tokenize=False, add_generation_prompt=True)

    return format_dataset


def count_tokens(row):
    return {"num_tokens": len(tokenizer(row["text"]).input_ids)}


def main(dataset_path, max_tokens, output_dir):
    # assert dataset_path.endswith("dev.parquet")
    try:
        dataset = load_from_disk(dataset_path)
    except:
        dataset = load_dataset(
            "parquet",
            data_files={
                # "dev": str(Path(dataset_path) / 'dev.parquet'),
                "test": str(Path(dataset_path) / "test.parquet"),
            },
        )
    # dataset = dataset.train_test_split(test_size=0.05, seed=42)
    dataset

    # global MAX_LOG_TOKENS
    # MAX_LOG_TOKENS = max_tokens

    print(f"Tokenizer max length: {tokenizer.model_max_length}")  # 131072
    # dataset = dataset.map(shorten_log, num_proc=48)
    transformed_dataset = dataset.map(get_messages, remove_columns=["text"])

    formatted_dataset = transformed_dataset.map(
        lambda x: {
            "text": conversations_formatting_function(tokenizer, "messages")(x),
            "eval_text": conversations_formatting_function_generation(tokenizer, "messages_eval")(x),
        }
    )

    formatted_dataset = formatted_dataset.map(count_tokens, num_proc=48)
    num_max_tokens = max_tokens
    len_before = len(formatted_dataset)
    formatted_dataset = formatted_dataset.filter(lambda x: x["num_tokens"] <= num_max_tokens)
    print(f"Removed {len_before - len(formatted_dataset)} rows with more than {num_max_tokens} tokens")
    # print(f"Max tokens in dev: {max(formatted_dataset['dev']['num_tokens'])}")
    print(f"Max tokens in test: {max(formatted_dataset['test']['num_tokens'])}")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    formatted_dataset.save_to_disk(f"{output_dir}/eval_log_q1_1_formatted_dataset_{max_tokens}")


if __name__ == "__main__":
    # Argument parser
    parser = argparse.ArgumentParser(description="Prepare dataset for benchmarking")
    parser.add_argument("--dataset_path", type=str, required=True, help="Path to the dataset")
    parser.add_argument("--max_tokens", type=int, default=64000, help="Max context length, will drop all rows beyond this")
    parser.add_argument("--output_dir", type=str, default="data", help="Output directory")

    args = parser.parse_args()
    main(args.dataset_path, args.max_tokens, args.output_dir)
