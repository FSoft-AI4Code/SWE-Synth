from dataclasses import dataclass, field
from pathlib import Path

from contextlib import ExitStack
import shutil

from git import Repo
from loguru import logger
from tqdm import tqdm
from swesynth.mutation.validator.tester import Tester
from swesynth.mutation.version_control.repository import Repository, RepositorySnapshot
from swesynth.mutation.version_control.checkout import GitRemoteProgress
from swebench.harness.constants import SWEbenchInstance


@dataclass
class RepoManager:
    """
    If `repository.py` is `git clone`
    then this is `git worktree`
    """

    repo: str
    commits: list[str]
    cache_dir: Path
    """
    cache_dir / repo / commit
    """

    exit_stack: ExitStack = field(default_factory=ExitStack, init=False)
    commit_to_snapshot: dict[str, RepositorySnapshot] = field(default_factory=dict, init=False)
    commit_to_tester: dict[str, Tester] = field(default_factory=dict, init=False)
    in_context: bool = field(default=False, init=False)

    def __post_init__(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if not (self.cache_dir / "original").exists():
            Repo.clone_from(f"https://github.com/{self.repo}.git", self.cache_dir / "original", progress=GitRemoteProgress())
            logger.info(f"Cloned {self.repo} to {self.cache_dir}")

        for commit in self.commits:
            if (self.cache_dir / commit).exists():
                shutil.rmtree(self.cache_dir / commit)
            Repo.clone_from(self.cache_dir / "original", self.cache_dir / commit)
            repository: Repository = Repository(self.repo, self.cache_dir / commit)
            self.exit_stack.callback(repository.rmdir)
            self.exit_stack.enter_context(repository)
            snapshot: RepositorySnapshot = repository.checkout(commit)
            self.commit_to_snapshot[commit] = snapshot

    def get(self, commit: str) -> RepositorySnapshot:
        return self.commit_to_snapshot[commit]

    def get_mutation(self, instance: SWEbenchInstance) -> RepositorySnapshot:
        base_snapshot: RepositorySnapshot = self.get(instance["base_commit"])
        mutation: RepositorySnapshot = RepositorySnapshot.from_swebench_instance(instance)
        mutation.origin = base_snapshot.origin
        return mutation

    def get_tester(self, commit: str) -> Tester:
        assert self.in_context, "RepoManager must be used in a context"
        return self.commit_to_tester[commit]

    def build_images(self):
        for commit in tqdm(self.commits, desc=f"Building images for {self.repo}"):
            snapshot: RepositorySnapshot = self.get(commit)
            tester: Tester = Tester(snapshot).setup()
            self.commit_to_tester[commit] = tester

    def __enter__(self):
        """
        Start all the containers
        """
        self.in_context = True

        if not self.commit_to_tester:
            self.build_images()

        for commit in tqdm(self.commits, desc=f"Starting containers for {self.repo}"):
            tester: Tester = self.get_tester(commit)
            self.exit_stack.enter_context(tester)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Stop all the containers
        """
        self.in_context = False
        self.exit_stack.close()
