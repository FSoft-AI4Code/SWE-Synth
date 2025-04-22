"""
This is a thin wrapper around `swebench.inference.make_datasets.create_text_dataset`
with 2 patches:
1. get_oracle_filenames
2. https://github.com/princeton-nlp/SWE-bench/pull/240
"""

import os
from pathlib import Path
import subprocess
from argparse import ArgumentParser
from tempfile import TemporaryDirectory

# --- patch ---
from git import Repo
from loguru import logger
import pandas as pd
from tqdm import tqdm
import unidiff
from datasets import load_from_disk, load_dataset, DatasetDict, Dataset
from swebench.inference.make_datasets.create_instance import add_lines_list, make_code_text, PATCH_EXAMPLE, add_text_inputs
from swebench.inference.make_datasets.create_text_dataset import PROMPT_FUNCTIONS, main, extract_fields
from swebench.inference.make_datasets.tokenize_dataset import TOKENIZER_FUNCS
from swebench.inference.make_datasets import utils
from transformers import AutoTokenizer

global DUMP_PARQUET
global CLONE_FROM_LOCAL


def shorten_log(row, tokenizer: AutoTokenizer, max_log_tokens: int = 14_000):
    original_log = row["problem_statement"]
    if not original_log:
        return {"problem_statement": original_log}
    tokens = tokenizer.encode(original_log, add_special_tokens=False)
    if len(tokens) > max_log_tokens:
        # Decode the first 14K tokens back to text
        truncated_log = tokenizer.decode(tokens[:max_log_tokens], skip_special_tokens=True)
        transformed_log = truncated_log + "\n[log truncated]"
    else:
        transformed_log = original_log
    return {"problem_statement": transformed_log}


def truncate_log(dataset: DatasetDict, tokenizer_name: str, max_log_tokens: int = 14_000) -> DatasetDict:
    assert tokenizer_name == "qwen2.5"
    tokenizer = AutoTokenizer.from_pretrained(f"Qwen/Qwen2.5-Coder-14B-Instruct")
    dataset = dataset.map(shorten_log, num_proc=48, fn_kwargs={"tokenizer": tokenizer, "max_log_tokens": max_log_tokens}, desc="Shortening logs")
    return dataset


def get_oracle_filenames(instance):
    """
    Returns the filenames that are changed in the patch
    """
    source_files = {patch_file.path for patch_file in unidiff.PatchSet(instance["patch"])}
    gold_docs = set()
    for source_file in source_files:
        gold_docs.add(source_file)
    return gold_docs


def make_code_text_edits_only(files_dict, patch, add_line_numbers=True):
    files = dict()
    patch = unidiff.PatchSet(patch)
    for patched_file in patch:
        source_file = patched_file.path
        files[source_file] = list()
        for hunk in patched_file:
            start = hunk.source_start - 15
            end = start + hunk.source_length + 15
            files[source_file].append((start, end))
    all_text = ""
    for filename, content in files_dict.items():
        all_text += f"[start of {filename}]\n"
        content_with_lines = add_lines_list(content)
        for start, end in files[filename]:
            if start > 0:
                all_text += "...\n"
            all_text += "\n".join(content_with_lines[start:end])
            all_text += "\n"
            if end < len(content_with_lines):
                all_text += "...\n"
        all_text = all_text.strip("\n")
        all_text += f"\n[end of {filename}]\n"
    return all_text.strip("\n")


class MockedAutoContextManager(utils.ContextManager):
    def __init__(self, instance, root_dir=None, verbose=False, token=None):
        if token is None:
            token = os.environ.get("GITHUB_TOKEN", "git")
        self.tempdir = None
        if root_dir is None:
            self.tempdir = TemporaryDirectory()
            root_dir = self.tempdir.name
        self.root_dir = root_dir
        if CLONE_FROM_LOCAL:
            self.root_dir = "/dev/shm/user2/swesynth/create_text_dataset"
            Path(self.root_dir).mkdir(parents=True, exist_ok=True)

        verbose = True
        repo_dir = os.path.join(self.root_dir, instance["repo"].replace("/", "__"))
        if not os.path.exists(repo_dir):
            if CLONE_FROM_LOCAL:
                repo_url = f"/cm/archive/user2/swesynth/git_repos/{instance['repo'].replace('/', '__')}"

                if not os.path.exists(repo_url):
                    raise FileNotFoundError(
                        f"""Directory {repo_dir} does not exist, please run
```
git clone https://github.com/swe-bench/{instance["repo"].replace("/", "__")}.git {repo_url}
```"""
                    )
            else:
                repo_url = f"https://{token}@github.com/swe-bench/" + instance["repo"].replace("/", "__") + ".git"

            if verbose:
                print(f"Cloning {instance['repo']} to {self.root_dir}")
            Repo.clone_from(repo_url, repo_dir)
        super().__init__(repo_dir, instance["base_commit"], verbose=verbose)
        self.instance = instance

    def __enter__(self):
        p = super().__enter__()
        # patch with `test_patch`
        subprocess.run(
            f"""git apply -v <<-"EOF981273"
{self.instance["test_patch"]}
EOF981273""",
            shell=True,
            check=True,
            cwd=self.repo_path,
        )
        print(f"Applied test patch to {self.repo_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tempdir is not None:
            self.tempdir.cleanup()
        return super().__exit__(exc_type, exc_val, exc_tb)


# class MockedDatasetDict(DatasetDict):
#     def save_to_disk(self, path, *args, **kwargs):
#         if DUMP_PARQUET:
#             for split, dataset in self.items():
#                 dataset.to_parquet(Path(path) / f"{split}.parquet")
#         else:
#             super().save_to_disk(str(path), *args, **kwargs)


def load_from_disk_patched(dataset_path: str) -> DatasetDict:
    dataset_path = Path(dataset_path)
    if not dataset_path.is_dir() and dataset_path.suffix == ".parquet":
        return load_dataset("parquet", data_files={"dev": str(dataset_path)})

    data_files = {split: str(dataset_path / f"{split}.parquet") for split in ["train", "dev", "test"] if (dataset_path / f"{split}.parquet").exists()}
    if not data_files:
        # raise FileNotFoundError(f"No dataset files found in {dataset_path}")
        logger.warning(f"No parquet files found in {dataset_path}")
        return load_from_disk(dataset_path)
    return load_dataset("parquet", data_files=data_files)


def prompt_style_3(instance):
    premise = "You will be provided with a partial code base and a test error log trace that need to be resolved."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    example_explanation = (
        f"Here is an example of a patch file. It consists of changes to the code base. "
        + f"It specifies the file names, the line numbers of each change, and the removed and added lines. "
        + f"A single patch file can contain changes to multiple files."
    )
    final_instruction = (
        f"I need you to solve the provided test error trace by generating a single patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the format shown above."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<test_log>",
        problem_statement,
        "</test_log>",
        "",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        "",
        example_explanation,
        "<patch>",
        PATCH_EXAMPLE,
        "</patch>",
        "",
        final_instruction,
        "Respond below:",
    ]
    final_text = "\n".join(final_text)
    return final_text


# --- main ---
def main(
    dataset_name_or_path,
    splits,
    validation_ratio,
    output_dir,
    retrieval_file,
    prompt_style,
    file_source,
    k,
    max_context_len,
    tokenizer_name,
    push_to_hub_user,
    max_log_length,
):
    if push_to_hub_user is not None:
        hub_token = os.environ.get("HUGGING_FACE_HUB_TOKEN", None)
        assert hub_token is not None, "Must provide HUGGING_FACE_HUB_TOKEN to push to the Hub"
        assert output_dir is None, "Cannot provide output_dir if pushing to the Hub"
    if max_context_len is not None:
        assert tokenizer_name is not None
    if push_to_hub_user is None and not Path(output_dir).exists():
        Path(output_dir).mkdir(parents=True)
    output_file = f"SWE-bench__{prompt_style}__fs-{file_source}"
    if k is not None:
        assert file_source not in {
            "all",
            "oracle",
        }, "Cannot use max_context_len with oracle or all file sources"
        output_file += f"__k-{k}"
    if max_context_len is not None:
        assert file_source not in {
            "all",
            "oracle",
        }, "Cannot use max_context_len with oracle or all file sources"
        assert tokenizer_name is not None, "Must provide tokenizer_name if max_context_len is not None"
        output_file += f"__mcc-{max_context_len}-{tokenizer_name}"
    if push_to_hub_user is None:
        output_file = Path(output_dir, output_file)
        if output_file.exists():
            logger.info(f"{output_file.absolute().as_posix()} already exists. Aborting")
            return
        output_file = str(output_file)
    if Path(dataset_name_or_path).exists():
        # dataset = load_from_disk(dataset_name_or_path)
        dataset = load_from_disk_patched(dataset_name_or_path)
    else:
        dataset = load_dataset(dataset_name_or_path)

    dataset = truncate_log(dataset, tokenizer_name, max_log_length)

    split_instances = dict()
    logger.info(f"Found {set(dataset.keys())} splits")
    if set(splits) - set(dataset.keys()) != set():
        raise ValueError(f"Unknown splits {set(splits) - set(dataset.keys())}")
    for split in splits:
        split_instances[split] = {x["instance_id"]: x for x in dataset[split]}
        add_text_inputs(
            split_instances[split],
            retrieval_file,
            k,
            prompt_style,
            file_source,
            max_context_len=max_context_len,
            tokenizer_name=tokenizer_name,
        )
    columns = [
        "instance_id",
        "text",
        "repo",
        "base_commit",
        "problem_statement",
        "hints_text",
        "created_at",
        "patch",
        "test_patch",
        "version",
        "FAIL_TO_PASS",
        "PASS_TO_PASS",
        "environment_setup_commit",
    ]
    split_data = dict()
    assert DUMP_PARQUET, "Only support DUMP_PARQUET"
    for split in split_instances:
        split_data[split] = {key: list() for key in columns}
        for instance in tqdm(
            split_instances[split].values(),
            total=len(split_instances[split]),
            desc=f"Processing {split} instances",
        ):
            datum = extract_fields(instance)
            if datum is None:
                continue
            for key in columns:
                split_data[split][key].append(datum[key] if key in datum else "")
        logger.info(f"Found {len(split_data[split]['instance_id'])} {split} ids")

        df = pd.DataFrame(split_data[split])
        Path(output_file).mkdir(parents=True, exist_ok=True)
        df.to_parquet(Path(output_file) / f"{split}.parquet")

        # split_data[split] = Dataset.from_dict(split_data[split])
    # dataset = DatasetDict(split_data)
    # if validation_ratio > 0 and "train" in dataset:
    #     train_val = dataset["train"].train_test_split(
    #         test_size=validation_ratio,
    #         seed=42,
    #     )
    #     dataset["train"] = train_val["train"]
    #     dataset["validation"] = train_val["test"]
    # for split in dataset:
    #     logger.info(f"Found {len(dataset[split])} {split} instances")

    # --- patch ---
    # if push_to_hub_user is not None:
    #     dataset.push_to_hub(f'{push_to_hub_user}/{output_file}', use_auth_token=hub_token)
    # else:
    # if DUMP_PARQUET:
    #     for split, _dataset in dataset.items():
    #         _dataset.to_parquet(Path(output_file) / f"{split}.parquet")
    # else:
    #     dataset.save_to_disk(str(output_file))
    # ---
    logger.info(f"Finsihed saving to {output_file}")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset_name_or_path",
        type=str,
        default="princeton-nlp/SWE-bench",
        help="Dataset to use for test set from HuggingFace Datasets or path to a save_to_disk directory.",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "test"],
        help="Splits to use from the dataset.",
    )
    parser.add_argument(
        "--validation_ratio",
        type=float,
        # default=0.01,
        default=0.0,
        help="Ratio of the training set to use for validation.",
    )
    parser.add_argument("--output_dir", type=str, help="Path to the output directory.")
    parser.add_argument(
        "--retrieval_file",
        type=str,
        help="Path to the file where the retrieval results are stored.",
    )
    parser.add_argument(
        "--prompt_style",
        type=str,
        default="style-3",
        choices=PROMPT_FUNCTIONS.keys(),
        help="Prompt style to use. See create_instance.PROMPT_FUNCTIONS for details.",
    )
    parser.add_argument(
        "--file_source",
        type=str,
        default="oracle",
        choices=["oracle", "bm25", "all"],
        help="How to select the files to use in context.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="Maximum number of files to use for retrieval.",
    )
    parser.add_argument(
        "--max_context_len",
        type=int,
        default=None,
        help="Maximum number of tokens to use for context.",
    )
    parser.add_argument(
        "--tokenizer_name",
        type=str,
        default=None,
        choices={*TOKENIZER_FUNCS.keys(), "qwen2.5"},
        help="Tokenizer to use for max_context_len. Only needed if max_context_len is specified.",
    )
    parser.add_argument(
        "--push_to_hub_user",
        type=str,
        help="Username to use for pushing to the Hub. If not provided, will save to disk.",
    )
    parser.add_argument(
        "--dump_parquet",
        action="store_true",
        help="If set, save the dataset as parquet files instead of the default format.",
    )
    parser.add_argument(
        "--clone_from_local",
        action="store_true",
        help=".",
    )
    parser.add_argument(
        "--max_log_length",
        type=int,
        default=14_000,
        help="Maximum number of tokens to use for logs context (problem statement).",
    )
    args = parser.parse_args()
    DUMP_PARQUET = args.dump_parquet
    CLONE_FROM_LOCAL = args.clone_from_local
    del args.dump_parquet
    del args.clone_from_local

    from unittest.mock import patch

    # patch("swebench.inference.make_datasets.create_text_dataset.DatasetDict", MockedDatasetDict), \
    with patch("swebench.inference.make_datasets.create_instance.make_code_text_edits_only", make_code_text_edits_only), patch(
        "swebench.inference.make_datasets.create_instance.get_oracle_filenames", get_oracle_filenames
    ), patch("swebench.inference.make_datasets.create_instance.AutoContextManager", MockedAutoContextManager), patch(
        "swebench.inference.make_datasets.create_text_dataset.load_from_disk", load_from_disk_patched
    ), patch(
        "swebench.inference.make_datasets.create_instance.prompt_style_3", prompt_style_3
    ):

        from swebench.inference.make_datasets import create_instance, tokenize_dataset

        create_instance.PROMPT_FUNCTIONS["style-3"] = prompt_style_3

        tokenize_dataset.TOKENIZER_FUNCS["qwen2.5"] = (
            AutoTokenizer.from_pretrained(f"Qwen/Qwen2.5-Coder-14B-Instruct"),
            lambda text, tokenizer: tokenizer(text, add_special_tokens=False, return_attention_mask=False)["input_ids"],
        )

        main(**vars(args))
