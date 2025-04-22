from argparse import ArgumentParser
from collections import defaultdict
import json
import logging
import os
from pathlib import Path
import subprocess
import traceback
from contextvars import ContextVar
from typing import Any
from concurrent.futures import Future, ThreadPoolExecutor

from swebench.inference.make_datasets.bm25_retrieval import (
    ContextManager,
    clone_repo,
    make_index,
    DOCUMENT_ENCODING_FUNCTIONS,
    string_to_bool,
    main,
    logger,
)
from swebench.inference.make_datasets.utils import is_test
from tqdm import tqdm
from .create_text_dataset import load_from_disk_patched, MockedAutoContextManager
from . import create_text_dataset

instance_var: ContextVar[dict] = ContextVar("instance_var")


def list_files(root_dir, include_tests=False):
    # breakpoint()
    files = []
    for filename in Path(root_dir).rglob("*.py"):
        name = filename.relative_to(root_dir).as_posix()
        if not include_tests and is_test(name):
            continue
        files.append(name)
    return files


def build_documents(repo_dir, commit, document_encoding_func):
    """
    Builds a dictionary of documents from a given repository directory and commit.

    Args:
        repo_dir (str): The path to the repository directory.
        commit (str): The commit hash to use.
        document_encoding_func (function): A function that takes a filename and a relative path and returns the encoded document text.

    Returns:
        dict: A dictionary where the keys are the relative paths of the documents and the values are the encoded document text.
    """
    documents = dict()

    # --- patched
    repo: str = repo_dir
    # with ContextManager(repo_dir, commit) as cm:
    with MockedAutoContextManager(
        {
            "repo": repo,
            "base_commit": commit,
            "test_patch": instance_var.get()["test_patch"],
        }
    ) as cm:
        # instance = instance_var.get()

        #         subprocess.run(f"""git apply -v <<-"EOF18923727"
        # {instance["test_patch"]}
        # EOF18923727""", shell=True, check=True, cwd=cm.repo_path)
        #         print(f"Applied test patch to {cm.repo_path}")

        # filenames = list_files(repo_dir, include_tests=False)
        # for relative_path in filenames:
        #     filename = os.path.join(repo_dir, relative_path)
        #     text = document_encoding_func(filename, relative_path)
        #     documents[relative_path] = text

        _repo_dir = cm.repo_path
        filenames = list_files(_repo_dir, include_tests=False)
        print(f"Got {len(filenames)} files")
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(document_encoding_func, os.path.join(_repo_dir, relative_path), relative_path): relative_path
                for relative_path in filenames
            }
            for future in futures:
                relative_path = futures[future]
                try:
                    text = future.result()
                    documents[relative_path] = text
                except Exception as e:
                    logger.error(f"Error processing {relative_path}: {e}")
    return documents


def make_index(
    repo_dir,
    root_dir,
    query,
    commit,
    document_encoding_func,
    python,
    instance_id,
):
    """
    Builds an index for a given set of documents using Pyserini.

    Args:
        repo_dir (str): The path to the repository directory.
        root_dir (str): The path to the root directory.
        query (str): The query to use for retrieval.
        commit (str): The commit hash to use for retrieval.
        document_encoding_func (function): The function to use for encoding documents.
        python (str): The path to the Python executable.
        instance_id (int): The ID of the current instance.

    Returns:
        index_path (Path): The path to the built index.
    """
    index_path = Path(root_dir, f"index__{str(instance_id)}", "index")
    if index_path.exists():
        # return index_path
        return ThreadPoolExecutor().submit(lambda: index_path)
    thread_prefix = f"(pid {os.getpid()}) "
    documents_path = Path(root_dir, instance_id, "documents.jsonl")
    if not documents_path.parent.exists():
        documents_path.parent.mkdir(parents=True)
    documents = build_documents(repo_dir, commit, document_encoding_func)
    with open(documents_path, "w") as docfile:
        for relative_path, contents in documents.items():
            print(
                json.dumps({"id": relative_path, "contents": contents}),
                file=docfile,
                flush=True,
            )
    cmd = [
        python,
        "-m",
        "pyserini.index",
        "--collection",
        "JsonCollection",
        "--generator",
        "DefaultLuceneDocumentGenerator",
        "--threads",
        "2",
        "--input",
        documents_path.parent.as_posix(),
        "--index",
        index_path.as_posix(),
        "--storePositions",
        "--storeDocvectors",
        "--storeRaw",
    ]

    def build_index(index_path):
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            output, error = proc.communicate()
        except KeyboardInterrupt:
            proc.kill()
            raise KeyboardInterrupt
        except Exception as e:
            logger.error(f"Exception occurred: {e}")
            return None
        if proc.returncode == 130:
            logger.warning(thread_prefix + f"Process killed by user")
            raise KeyboardInterrupt
        if proc.returncode != 0:
            logger.error(f"return code: {proc.returncode}")
            logger.error(f"Failed to build index for {instance_id} with error {error}")
            return None
        return index_path

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(build_index, index_path)
    return future


def get_index_paths_worker(
    instance,
    root_dir_name,
    document_encoding_func,
    python,
    token,
):
    index_path = None
    repo = instance["repo"]
    commit = instance["base_commit"]
    instance_id = instance["instance_id"]
    try:
        # repo_dir = clone_repo(repo, root_dir_name, token)

        # ---
        instance_var.set(instance)
        # ---

        query = instance["problem_statement"]
        index_path = make_index(
            repo_dir=repo,
            root_dir=root_dir_name,
            query=query,
            commit=commit,
            document_encoding_func=document_encoding_func,
            python=python,
            instance_id=instance_id,
        )
    except:
        logger.error(f"Failed to process {repo}/{commit} (instance {instance_id})")
        logger.error(traceback.format_exc())
    return instance_id, index_path


def get_index_paths(
    remaining_instances: list[dict[str, Any]],
    root_dir_name: str,
    document_encoding_func: Any,
    python: str,
    token: str,
    output_file: str,
) -> dict[str, str]:
    """
    Retrieves the index paths for the given instances using multiple processes.

    Args:
        remaining_instances: A list of instances for which to retrieve the index paths.
        root_dir_name: The root directory name.
        document_encoding_func: A function for encoding documents.
        python: The path to the Python executable.
        token: The token to use for authentication.
        output_file: The output file.
        num_workers: The number of worker processes to use.

    Returns:
        A dictionary mapping instance IDs to index paths.
    """
    # all_index_paths = dict()
    all_index_paths = defaultdict(list)
    for instance in tqdm(remaining_instances, desc="Indexing"):
        instance_id, index_path_promise = get_index_paths_worker(
            instance=instance,
            root_dir_name=root_dir_name,
            document_encoding_func=document_encoding_func,
            python=python,
            token=token,
        )
        # all_index_paths[instance_id] = index_path_promise
        all_index_paths[instance_id].append(index_path_promise)

    output_index_paths = dict()
    for instance_id, index_path_promise in tqdm(all_index_paths.items(), desc="Waiting for results"):
        for p in index_path_promise:
            index_path = p.result()
            if index_path is None:
                continue
            output_index_paths[instance_id] = index_path

    logger.info(f"{len(output_index_paths)}/{len(all_index_paths)} instances indexed")
    return output_index_paths


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--dataset_name_or_path",
        type=str,
        default="princeton-nlp/SWE-bench",
        help="Dataset to use for test set from HuggingFace Datasets or path to a save_to_disk directory.",
    )
    parser.add_argument(
        "--document_encoding_style",
        choices=DOCUMENT_ENCODING_FUNCTIONS.keys(),
        default="file_name_and_contents",
    )
    parser.add_argument("--output_dir", default="./retreival_results")
    parser.add_argument("--splits", nargs="+", default=["train", "test"])
    parser.add_argument("--shard_id", type=int)
    parser.add_argument("--num_shards", type=int, default=20)
    parser.add_argument("--leave_indexes", type=string_to_bool, default=True)
    parser.add_argument("--clone_from_local", action="store_true")
    args = parser.parse_args()

    from unittest.mock import patch

    with patch("swebench.inference.make_datasets.bm25_retrieval.get_index_paths_worker", get_index_paths_worker), patch(
        "swebench.inference.make_datasets.bm25_retrieval.build_documents", build_documents
    ), patch("swebench.inference.make_datasets.bm25_retrieval.load_from_disk", load_from_disk_patched), patch(
        "swebench.inference.make_datasets.bm25_retrieval.get_index_paths", get_index_paths
    ):

        create_text_dataset.CLONE_FROM_LOCAL = args.clone_from_local
        del args.clone_from_local

        main(**vars(args))
