"""
python -m swesynth.mutation.version_control.get_version
"""

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
import threading

from loguru import logger
from tqdm import tqdm
from tqdm.contrib.concurrent import thread_map

from .fixes import PYLINT_DEV_ASTROID_CORRUPTED_COMMITS, ASTROPY_CORRUPTED_COMMITS
from ..validator.docker.utils import check_if_remote_docker_image_exist

# from swebench.harness.constants import RUN_EVALUATION_LOG_DIR, SWEbenchInstance

repo_nameT = str
base_commit_hashT = str


@dataclass
class RepoVersion:
    path_to_file: Path = Path("logs/repo_version_mapping.json.gz")

    mapping_from_repo_base_commit_to_version: dict[repo_nameT, dict[base_commit_hashT, str]] | None = None

    mapping_from_repo_base_commit_to_env_setup_commit: dict[repo_nameT, dict[base_commit_hashT, str]] | None = None

    mapping_from_repo_base_commit_to_docker_image: dict[repo_nameT, dict[base_commit_hashT, str]] | None = None

    # singleton
    instance: "RepoVersion | None" = None

    @staticmethod
    def get_all_known_commits_of_repo(repo_name: repo_nameT) -> list[base_commit_hashT]:
        instance: RepoVersion = RepoVersion.get_instance()
        all_known_commits: set[base_commit_hashT] = set(instance.mapping_from_repo_base_commit_to_version[repo_name].keys())

        if repo_name == "pylint-dev/astroid":
            all_known_commits -= PYLINT_DEV_ASTROID_CORRUPTED_COMMITS

        if repo_name == "astropy/astropy":
            all_known_commits -= ASTROPY_CORRUPTED_COMMITS

        return all_known_commits

    @staticmethod
    def get_instance() -> "RepoVersion":
        if RepoVersion.instance is None:
            RepoVersion()
        return RepoVersion.instance

    def __post_init__(self):
        if self.__class__.instance is not None:
            return
        if not self.path_to_file.exists():
            logger.warning(f"File {self.path_to_file} does not exist")
            logger.warning(f"Creating a new instance of RepoVersion")
            RepoVersion.create_mapping(RepoVersion.path_to_file)

        assert ".json.gz" in "".join(self.path_to_file.suffixes), f"Invalid file extension: {self.path_to_file.suffixes}"
        with gzip.open(self.path_to_file, "rt") as f:
            data = json.load(f)
            self.mapping_from_repo_base_commit_to_version = data["mapping_from_repo_commit_to_version"]
            self.mapping_from_repo_base_commit_to_env_setup_commit = data["mapping_from_repo_base_commit_to_env_setup_commit"]
            self.mapping_from_repo_base_commit_to_docker_image = data["mapping_from_repo_base_commit_to_docker_image"]
            logger.info(f"Loaded version mapping from {self.path_to_file}")

        RepoVersion.instance = self

    @staticmethod
    def get_version_from_base_commit(repo_name: repo_nameT, base_commit_hash: base_commit_hashT) -> str:
        # assert RepoVersion.instance is not None, "RepoVersion instance is not initialized"
        if RepoVersion.instance is None:
            logger.warning("RepoVersion instance is not initialized")
            RepoVersion()

        if RepoVersion.instance.mapping_from_repo_base_commit_to_version is not None:
            try:
                return RepoVersion.instance.mapping_from_repo_base_commit_to_version[repo_name][base_commit_hash]
            except KeyError:
                logger.warning(f"Cannot find version for {repo_name} and {base_commit_hash}")

        # from swebench.versioning.get_versions import get_versions
        # TODO: fetch online here | extract version from git tags/setup.py/ check how swe-bench crawl them
        raise NotImplementedError

    @staticmethod
    def get_env_setup_commit_from_base_commit(repo_name: repo_nameT, base_commit_hash: base_commit_hashT) -> str:
        # assert RepoVersion.instance is not None, "RepoVersion instance is not initialized"
        if RepoVersion.instance is None:
            logger.warning("RepoVersion instance is not initialized")
            RepoVersion()

        if RepoVersion.instance.mapping_from_repo_base_commit_to_env_setup_commit is not None:
            try:
                return RepoVersion.instance.mapping_from_repo_base_commit_to_env_setup_commit[repo_name][base_commit_hash]
            except KeyError:
                logger.warning(f"Cannot find env setup commit for {repo_name} and {base_commit_hash}")

        raise NotImplementedError

    @staticmethod
    def create_mapping(path_to_file: Path) -> None:
        """
        Create a mapping from repo base commit to version and environment setup commit
        from the SWE-bench dataset

        This is a one-time operation
        """
        from datasets import load_dataset
        import pandas as pd
        from collections import defaultdict

        logger.info(f"Creating version mapping ...")

        ds = load_dataset("princeton-nlp/SWE-bench")
        dev_df = pd.DataFrame(ds["dev"])
        test_df = pd.DataFrame(ds["test"])

        swebench_df = pd.concat([dev_df, test_df])
        # https://github.com/swe-bench/SWE-bench/blob/ee09c356410a330bbdceef14313ab60e9081dc1f/swebench/harness/test_spec/test_spec.py#L85
        swebench_df["remote_docker_image_name"] = (
            "swebench/sweb.eval.x86_64." + swebench_df["instance_id"].str.lower().str.replace("__", "_1776_") + ":latest"
        )

        ds_gym = load_dataset("SWE-Gym/SWE-Gym")
        swegym_df = pd.DataFrame(ds_gym["train"])
        # SWE-Gym does not have `environment_setup_commit`
        swegym_df["environment_setup_commit"] = swegym_df["base_commit"]
        swegym_df["instance_id"] = swegym_df["instance_id"].str.lower()
        swegym_df["repo"] = swegym_df["repo"].str.lower()

        # NOTE: SWE-Gym release all docker images under `xingyaoww/sweb.eval.x86_64` prefix at docker hub.
        swegym_df["remote_docker_image_name"] = "xingyaoww/sweb.eval.x86_64." + swegym_df["instance_id"].str.replace("__", "_s_") + ":latest"

        df = pd.concat([swebench_df, swegym_df])
        # df = pd.concat([swegym_df])

        df[["repo", "base_commit", "environment_setup_commit", "version", "remote_docker_image_name"]]

        mapping_from_repo_base_commit_to_version: dict[repo_nameT, dict[base_commit_hashT, str]] = defaultdict(dict)

        mapping_from_repo_base_commit_to_env_setup_commit: dict[repo_nameT, dict[base_commit_hashT, str]] = defaultdict(dict)

        mapping_from_repo_base_commit_to_docker_image: dict[repo_nameT, dict[base_commit_hashT, str | None]] = defaultdict(dict)

        # mapping_from_repo_version_to_docker_image: dict[repo_nameT, dict[base_commit_hashT, str | None]] = defaultdict(dict)

        lock = threading.Lock()

        def process_row(row):
            """Process a single row of the dataframe."""
            repo = row["repo"]
            base_commit = row["base_commit"]
            environment_setup_commit = row["environment_setup_commit"]
            version = row["version"]

            # if check_if_remote_docker_image_exist(row["remote_docker_image_name"].split(":")[0]):
            #     row['remote_docker_image_name'] = row['remote_docker_image_name']
            # elif check_if_remote_docker_image_exist(row["remote_docker_image_name"].split(":")[0], tag='v1'):
            #     row['remote_docker_image_name'] = row['remote_docker_image_name'].replace(":latest", ":v1")
            # else:
            #     logger.error(f"Remote docker image '{row['remote_docker_image_name']}' `v1` and `latest` does not exist")
            #     row['remote_docker_image_name'] = None

            with lock:
                # check if mapping_from_repo_base_commit_to_env_setup_commit[repo][base_commit] docker image exist, if not, then replace it.
                mapping_from_repo_base_commit_to_env_setup_commit[repo][base_commit] = environment_setup_commit
                mapping_from_repo_base_commit_to_version[repo][base_commit] = version

                mapping_from_repo_base_commit_to_docker_image[repo][base_commit] = row["remote_docker_image_name"]
            return row

        rows = [row for _, row in df.iterrows()]
        thread_map(process_row, rows, desc="Creating version mapping", total=len(rows), max_workers=5)

        path_to_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "mapping_from_repo_commit_to_version": mapping_from_repo_base_commit_to_version,
            "mapping_from_repo_base_commit_to_env_setup_commit": mapping_from_repo_base_commit_to_env_setup_commit,
            "mapping_from_repo_base_commit_to_docker_image": mapping_from_repo_base_commit_to_docker_image,
        }

        with gzip.open(path_to_file, "wt") as f:
            json.dump(data, f)

        logger.info(f"Saved version mapping for {len(mapping_from_repo_base_commit_to_version)} repos to {path_to_file}")


if __name__ == "__main__":
    # python -m swesynth.mutation.version_control.get_version
    RepoVersion.create_mapping(RepoVersion.path_to_file)
