import os
import pathlib
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
from loguru import logger

from swesynth.mutation.validator.entities.mutation_info import MutationInfo
from swesynth.mutation.version_control.checkout import UsingRepo
from swesynth.mutation.version_control.repository import RepositorySnapshot
from swesynth.typing import diff
from swesynth.mutation.validator.docker.multiprocessing_utils import concurrent_waiting_mutator_counter_semaphores
from swebench.inference.make_datasets.utils import extract_minimal_patch, repair_patch

if TYPE_CHECKING:
    from swesynth.mutation.validator.test_mapper.dynamic.targeter import DynamicCallGraphTestTargeter

# mutation_llm = ChatOpenAI(
#     model_name="deepseek-chat",
#     base_url="https://api.deepseek.com",
#     api_key=os.environ["DEEPSEEK_API_KEY"],
#     max_retries=100
# )

# mutation_llm = ChatTogether(
#     model_name="meta-llama/Llama-3.2-3B-Instruct-Turbo",
#     max_retries=100
# )

mutation_llm = ChatOpenAI(
    model_name=os.environ.get("SWESYNTH_MUTATION_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"),
    base_url=f"http://{os.environ.get('LLM_INFERENCE_API_ENDPOINT', 'localhost:27439')}/v1/",
    api_key="null",
    max_retries=100,
    timeout=1200,
)


class Strategy(ABC):
    test_targeter: "DynamicCallGraphTestTargeter | None" = None
    MAX_ITERATION: int = 2000

    def mutate(self, source_code: "RepositorySnapshot") -> Iterator["RepositorySnapshot"]:
        counter = 0
        for unstaged_changes, mutation_info in self._mutate(source_code.origin.path):
            counter += 1
            if counter >= self.MAX_ITERATION:
                logger.info(f"Reached max iteration {self.MAX_ITERATION}")
                break

            if not unstaged_changes:
                # this intentionally skips both empty and None
                logger.warning("Empty unstaged changes, skip this mutant")
                continue

            mutant: "RepositorySnapshot" = source_code.copy_with_changes(unstaged_changes, mutation_info)
            logger.info(f"Generated mutant: {mutant!r}")

            if "+import " in unstaged_changes or ("+from " in unstaged_changes and " import " in unstaged_changes):
                logger.warning("Import statement detected, skip this mutant")
                continue

            yield mutant  # return a modified copy

    @abstractmethod
    def _mutate(self, path_to_repo: Path) -> Iterator[tuple[diff, MutationInfo]]:
        raise NotImplementedError

    @staticmethod
    def _get_diff(
        new_file_content: str,
        function_path: pathlib.Path,
        repo_path: pathlib.Path,
    ) -> str:
        """
        Get the diff between the old and new file content by writing and reverse
        """
        with UsingRepo(repo_path):
            assert function_path.exists()
            if function_path.read_text().endswith("\n") and not new_file_content.endswith("\n"):
                new_file_content += "\n"
            elif not function_path.read_text().endswith("\n") and new_file_content.endswith("\n"):
                # rare case, since new_file_content should already be stripped
                new_file_content = new_file_content.rstrip("\n")

            function_path.write_text(new_file_content)

            # git diff
            res: str = subprocess.run(["git", "diff"], stdout=subprocess.PIPE, check=True).stdout.decode("utf-8")

            if res.strip() == "":
                logger.warning(f"Empty diff for this mutation: {function_path}")
                return res

            res_repaired: str = repair_patch(res)
            if not res_repaired:
                logger.error(f"Failed to repair patch: {res}")
                return res
        return res_repaired

    def load(self, test_targeter: "DynamicCallGraphTestTargeter") -> None:
        self.test_targeter = test_targeter

    def score(self, mutated_repo: "RepositorySnapshot") -> float:
        logger.warning("Scoring not implemented")
        return 0.0

    def llm_implement(self, *args, **kwargs):
        assert hasattr(self, "chain"), "Chain not implemented"
        with concurrent_waiting_mutator_counter_semaphores:
            return self.chain.invoke(*args, **kwargs)

    def load_checkpoint(self, existing_mutations: list[RepositorySnapshot]) -> None:
        logger.warning(f"Loading checkpoint not implemented in {self.__class__.__name__}")
        pass
