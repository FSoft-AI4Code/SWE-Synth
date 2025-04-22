import json
import os
import random
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from git import Repo
from loguru import logger
import numpy as np
from swebench.harness.constants import RUN_EVALUATION_LOG_DIR, SWEbenchInstance

from swesynth.mutation.validator.docker.test_log_extractor import LogExtractor
from swesynth.mutation.validator.entities.mutation_info import MutationInfo
from swesynth.mutation.validator.entities.status import TestStatusDiff
from swesynth.mutation.version_control.checkout import GitRemoteProgress, UsingRepo
from swesynth.mutation.version_control.get_version import RepoVersion
from swesynth.mutation.version_control.utils import hash_to_n_chars
from swesynth.mutation.processing.program.diff import swap_a_b_of_patch_and_clean
from swesynth.typing import diff
from swesynth.utils.compression import compress, decompress, sample_with_seed

from .fixes import CORRUPTED_COMMITS


@dataclass
class Repository:
    repo: str
    path: Path | None = None

    _repo: Repo | None = field(init=False, default=None)
    _temp_dir: TemporaryDirectory | None = field(init=False, default=None)

    _all_known_commits: list[str] | None = field(init=False, default=None)
    _cached_origin: str | None = field(init=False, default=None)

    def __post_init__(self):
        self.repo = self.repo.lower()

    @property
    def all_known_commits(self) -> list[str]:
        if self._all_known_commits is None:
            self._all_known_commits = list(RepoVersion.get_all_known_commits_of_repo(self.repo))
        return self._all_known_commits

    def sample_known_commit(self, k: int = 5, seed: int = 42) -> list[str]:
        all_known_commits: list[str] = self.all_known_commits
        logger.info(f"Known commits: {len(all_known_commits)}")
        all_known_commits: list[str] = list(sample_with_seed(all_known_commits, k=k, seed=seed))
        # all_known_commits = list(set(all_known_commits) - CORRUPTED_COMMITS.get(self.repo.lower(), set()))
        logger.info(f"Sampled {len(all_known_commits)} commits: {all_known_commits}")
        return all_known_commits

    def __enter__(self) -> "Repository":
        if self.path is None:
            self._temp_dir = TemporaryDirectory()
            self.path = Path(self._temp_dir.name)

            logger.info(f"Cloning {self.repo} to {self.path}")
            if self._cached_origin is None:
                if os.environ.get("GITHUB_TOKEN"):
                    self._repo = Repo.clone_from(
                        f"https://{os.environ.get('GITHUB_TOKEN')}@github.com/{self.repo}.git", self.path, progress=GitRemoteProgress()
                    )
                else:
                    self._repo = Repo.clone_from(f"https://github.com/{self.repo}.git", self.path, progress=GitRemoteProgress())
            else:
                self._repo = Repo.clone_from(self._cached_origin, self.path)
            logger.info(f"Cloned {self.repo} to {self.path}")

        assert len(list(self.path.iterdir())) > 0, f"Repo {self.repo} at {self.path} is empty"
        self._repo = Repo(self.path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            logger.info(f"Deleted {self.path}")

    def checkout_random_commit(self) -> "RepositorySnapshot":
        assert self._repo
        # latest commit for now
        commit = random.choice(self.all_known_commits)
        # commit = '3832210580d516365ddae1a62071001faf94d416'
        # commit: Commit = self._repo.head.commit
        return self.checkout(commit)

    _pointer: int = 0

    def checkout_next_known_commit(self) -> "RepositorySnapshot":
        """Round robin to checkout all known commits"""
        assert self._repo
        if self._pointer >= len(self.all_known_commits):
            self._pointer = 0
        commit = self.all_known_commits[self._pointer]
        self._pointer += 1
        return self.checkout(commit)

    def checkout(self, commit: str) -> "RepositorySnapshot":
        assert self._repo
        self._repo.git.checkout(commit)
        logger.info(f"Checked out {commit}")
        return RepositorySnapshot(commit, self)

    def __repr__(self) -> str:
        return f"Repository(repo={self.repo}, path={self.path})"

    def rmdir(self) -> None:
        if self.path is not None:
            shutil.rmtree(self.path)
            logger.info(f"Deleted {self.path}")


@dataclass
class RepositorySnapshot:
    base_commit: str
    origin: Repository

    unstaged_changes: diff | None = None
    """this is the mutation diff to cause the bug, from the base commit (already working code)"""

    test_status_diff: TestStatusDiff | None = None

    mutation_info: MutationInfo | None = None

    score: float | None = None

    reversed_diff: diff | None = None
    """this is the diff to revert the mutation, which is the **gold patch** to fix the bug"""

    test_log_traces: str | None = None
    """this is similar to problem statement, but in the form of test logs"""

    def __enter__(self) -> Path:
        """
        Git clone the repo and checkout to the base commit, and discard all changes on exit
        also change the working directory to the repo during the context
        """
        self.origin.__enter__()
        self.origin._repo.git.checkout(self.base_commit)
        self._using_repo = UsingRepo(self.origin.path)
        _path: Path = self._using_repo.__enter__()
        self.__apply_diff()
        return _path

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._using_repo.__exit__(exc_type, exc_val, exc_tb)
        self.origin.__exit__(exc_type, exc_val, exc_tb)

    def copy_with_changes(self, changes: diff, mutation_info: MutationInfo | None = None) -> "RepositorySnapshot":
        assert self.unstaged_changes is None
        return self.__class__(base_commit=self.base_commit, origin=self.origin, unstaged_changes=changes, mutation_info=mutation_info)

    @property
    def repo(self) -> str:
        return self.origin.repo

    _version: str | None = None

    @property
    def version(self) -> str:
        if self._version is None:
            self._version = RepoVersion.get_version_from_base_commit(self.repo, self.base_commit)
        return self._version

    @property
    def hash_of_diff(self) -> str:
        try:
            return "swebench_" + self.mutation_info.metadata["instance_id"].lower()
        except:
            pass

        if self.unstaged_changes is None:
            hash_of_diff = "original"
        else:
            # hash diff
            hash_of_diff = self._hash_of_diff
        return hash_of_diff

    @property
    def _hash_of_diff(self) -> str:
        return hash_to_n_chars(self.unstaged_changes)

    @property
    def instance_id(self) -> str:
        return f"{self.origin.repo.replace('/', '_').lower()}-{self.base_commit}-{self.hash_of_diff}"

    @staticmethod
    def parse_instance_id(instance_id: str) -> tuple[str, str, str]:
        _ = instance_id.split("-")
        # repo, commit, hash_of_diff = [:3]
        hash_of_diff = _.pop()
        commit = _.pop()
        repo = "-".join(_)
        return repo, commit, hash_of_diff

    def __repr__(self) -> str:
        return f"""RepositorySnapshot(
    base_commit={self.base_commit},
    origin={self.origin},
    version={self._version},
    instance_id={self.instance_id},
    test_status_diff={self.test_status_diff},
    score={self.score},
    mutation_info={self.mutation_info},
    unstaged_changes='''
{self.unstaged_changes}
''',
    log_dir={self.log_dir},
)"""

    def to_dict(self) -> dict:
        return {
            "base_commit": self.base_commit,
            "origin": self.origin.repo,
            "version": self.version,
            "instance_id": self.instance_id,
            "unstaged_changes": self.unstaged_changes,
            "reversed_diff": self.reversed_diff,
            "test_status_diff": (self.test_status_diff is not None)
            and self.test_status_diff.to_dict(),  # equivalent to self.test_status_diff?.to_dict()
            "mutation_info": self.mutation_info and self.mutation_info.to_dict(),
            "score": self.score,
            "test_log_traces": self.test_log_traces and compress(self.test_log_traces),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RepositorySnapshot":
        return cls(
            base_commit=data["base_commit"],
            origin=Repository(repo=data["origin"]),
            unstaged_changes=data["unstaged_changes"],
            reversed_diff=data.get("reversed_diff"),
            test_status_diff=TestStatusDiff.from_dict(data["test_status_diff"]),
            mutation_info=MutationInfo.from_dict(data["mutation_info"]),
            score=data["score"],
            test_log_traces=data.get("test_log_traces") and decompress(data["test_log_traces"]),
            _version=data.get("version"),
        )

    @classmethod
    def from_swebench_instance(cls, instance: SWEbenchInstance) -> "RepositorySnapshot":
        def _get_status_diff(instance: SWEbenchInstance) -> TestStatusDiff:
            pass_to_pass = instance["PASS_TO_PASS"]
            fail_to_pass = instance["FAIL_TO_PASS"]

            if isinstance(pass_to_pass, str):
                pass_to_pass = json.loads(pass_to_pass)
            if isinstance(fail_to_pass, str):
                fail_to_pass = json.loads(fail_to_pass)

            if isinstance(pass_to_pass, np.ndarray):
                pass_to_pass = pass_to_pass.tolist()
            if isinstance(fail_to_pass, np.ndarray):
                fail_to_pass = fail_to_pass.tolist()

            assert isinstance(pass_to_pass, list), f"Expected list, got {type(pass_to_pass)}: {pass_to_pass}"
            assert isinstance(fail_to_pass, list), f"Expected list, got {type(fail_to_pass)}: {fail_to_pass}"

            test_status_diff = TestStatusDiff(
                # NOTE: key difference here
                FAIL_TO_PASS=set(),
                PASS_TO_PASS=set(pass_to_pass),
                FAIL_TO_FAIL=set(),
                PASS_TO_FAIL=set(fail_to_pass),
            )
            return test_status_diff

        try:
            test_status_diff = _get_status_diff(instance)
        except KeyError:
            test_status_diff = None
        environment_setup_commit: str | None = instance.get("environment_setup_commit")

        if isinstance(environment_setup_commit, str):
            pass
        elif environment_setup_commit is None or np.isnan(environment_setup_commit):
            environment_setup_commit = instance["base_commit"]

        return cls(
            base_commit=instance["base_commit"],
            origin=Repository(repo=instance["repo"]),
            unstaged_changes=instance["test_patch"],
            reversed_diff=instance["patch"],
            test_status_diff=test_status_diff,
            mutation_info=MutationInfo(
                metadata={"instance_id": instance["instance_id"], "environment_setup_commit": environment_setup_commit},
                # NOTE: environment_setup_commit is only be used for retrieving requirements.txt in SWE-Bench
                # this is not used for git checkout
            ),
            _version=instance.get("version", None),
        )

    def to_swebench_instance(self) -> SWEbenchInstance:
        try:
            environment_setup_commit = self.mutation_info.metadata["environment_setup_commit"]
        except (KeyError, AttributeError):
            environment_setup_commit = RepoVersion.get_env_setup_commit_from_base_commit(self.repo, self.base_commit)

        return SWEbenchInstance(
            instance_id=self.instance_id,
            repo=self.origin.repo,
            base_commit=self.base_commit,
            version=self.version,
            test_patch=self.unstaged_changes,
            patch=self.reversed_diff,
            environment_setup_commit=environment_setup_commit,
            # NOTE: key difference here
            FAIL_TO_PASS=self.test_status_diff is not None and json.dumps(list(self.test_status_diff.PASS_TO_FAIL)),
            PASS_TO_PASS=self.test_status_diff is not None and json.dumps(list(self.test_status_diff.PASS_TO_PASS)),
            problem_statement=self.test_log_traces,
            hints_text="",
            created_at="",
        )

    @property
    def log_dir(self) -> Path:
        return Path(self.repo.replace("/", "_")) / self.version / self.base_commit / self.hash_of_diff

    @property
    def relative_log_dir(self) -> Path:
        return RUN_EVALUATION_LOG_DIR / self.log_dir

    def parse_test_log_traces(self, logs: str) -> str:
        """
        Extract the test log traces from the total raw logs in order to be used as **problem statement**
        """
        return LogExtractor(self.repo).parse_log(logs)

    def save_reversed_diff(self) -> None:
        if self.reversed_diff is None:
            assert self.unstaged_changes is not None
            self.reversed_diff = self.get_reversed_diff_of(self.unstaged_changes)
        (self.relative_log_dir / "reversed_patch.diff").write_text(self.reversed_diff)
        logger.info(f"Saved reversed diff to {self.relative_log_dir / 'reversed_patch.diff'}")

    def get_reversed_diff_of(self, changes: diff) -> diff:
        """
        NOTE: this will discard all current changes and clean the repo
        """
        assert self.origin.path is not None

        # git apply patch.diff && git diff -R
        with UsingRepo(self.origin.path):
            subprocess.run(
                f"""git apply -v <<-"EOF"
{changes}
EOF""",
                shell=True,
                check=True,
            )
            reversed_diff = subprocess.run(["git", "diff", "-R"], stdout=subprocess.PIPE, check=True).stdout.decode("utf-8")

            reversed_diff_cleaned = swap_a_b_of_patch_and_clean(reversed_diff)

        # logger.info(f"Diff:\n{changes}\nReversed diff:\n{reversed_diff}")

        return reversed_diff_cleaned

    def __apply_diff(self) -> None:
        assert self.unstaged_changes is not None
        if self.unstaged_changes.strip() == "":
            logger.warning(f"Empty diff for {self.instance_id}")
            return
        subprocess.run(
            f"""git apply -v <<-"EOF"
{self.unstaged_changes}
EOF""",
            shell=True,
            check=True,
        )

        subprocess.run(f"""git add -u""", shell=True, check=True)

    def get_current_diff(self) -> diff:
        assert self.origin.path is not None
        diff = subprocess.run(["git", "diff"], stdout=subprocess.PIPE, check=True).stdout.decode("utf-8")
        return diff
