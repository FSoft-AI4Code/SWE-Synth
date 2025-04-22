"""
Randomly pick a function, remove its body, ask LLM to re-implement it, then run
test until FAIL, if not then repeat
"""

import ast
from dataclasses import dataclass, field
import os
import pathlib
import random
from typing import Iterable, Iterator, TYPE_CHECKING

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from loguru import logger
from tqdm import tqdm
from typing_extensions import override

from swesynth.mutation.processing.model_output import extract_code
from swesynth.mutation.processing.program import empty_function_body, replace_function_body
from swesynth.mutation.processing.program.extract import get_all_functions
from swesynth.mutation.processing.program.transform import hint_function
from swesynth.mutation.validator.entities.mutation_info import MutationInfo, Target
from swesynth.mutation.validator.test_mapper.simple import SimpleTestTargeter
from swesynth.typing import FilePath, diff

from .base import Strategy, mutation_llm

if TYPE_CHECKING:
    from swesynth.mutation.version_control.repository import RepositorySnapshot


@dataclass
class EmptyFunctionStrategy(Strategy):
    MUTATION_PER_FUNCTION: int = 1

    chain = (
        ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a senior python developer. You always explain your intention before writing code that you are sure of.""",
                ),
                (
                    "user",
                    """Given the code below, please implement the body of the function `{entrypoint}`. \
Do not change the function's signature, which includes the function name, parameters, return type, and the function's docstring. \
Do not add any additional import statements. \
Please implement the function directly without changing the surrounding context.

```python
{file_content}
```

Answer in the following format:

<explain your implementation>

```python
{function_signature}
```
""",
                ),
            ]
        )
        | mutation_llm
        | StrOutputParser()
        | {"raw_output": RunnablePassthrough(), "code": extract_code}
    )

    previous_mutated_functions: set[Target] | None = field(default=None, init=False)

    def _filter_not_tested_functions(self, all_functions: list[Target]) -> list[Target]:
        if self.test_targeter is None:
            logger.warning("No test targeter is provided")
            return all_functions

        remaining_functions: list[Target] = []
        for target in tqdm(all_functions, desc="Filtering functions with no test impact"):
            approximated_related_test_cases = self.test_targeter.get_related_test_cases({target})

            if len(approximated_related_test_cases) == 0:
                # logger.warning(f"Function `{target.ast_obj.name}` has no related test cases.")
                continue

            remaining_functions.append(target)

        return remaining_functions

    @override
    def _mutate(self, path_to_repo: pathlib.Path) -> Iterator[tuple[diff, MutationInfo]]:
        self.path_to_repo = path_to_repo
        all_functions: list[Target] = list(self._get_all_functions(path_to_repo))

        if len(all_functions) == 0:
            logger.warning(f"No functions found in {path_to_repo}")
            return

        logger.info(f"Found {len(all_functions)} functions in {path_to_repo}")
        all_functions = self._filter_not_tested_functions(all_functions)
        logger.info(f"Remaining {len(all_functions)} functions after filtering out untested functions")

        if self.previous_mutated_functions is not None:
            all_functions = [f for f in all_functions if not any(f == prev_f for prev_f in self.previous_mutated_functions)]
            logger.info(f"Remaining {len(all_functions)} functions after filtering out previously mutated functions")

        while len(all_functions) > 0:
            # Randomly pick a function
            function: ast.FunctionDef
            # target = random.choice(all_functions)
            random_idx = random.randint(0, len(all_functions) - 1)
            target = all_functions.pop(random_idx)

            abs_function_path, relative_path, function = target.abs_path_to_file, target.relative_path, target.ast_obj

            try:
                yield from self._process_function(abs_function_path, function, target, path_to_repo)
            except Exception as e:
                logger.error(f"Failed to process function: {e}")
                logger.error(f"Function: {function.name} ({abs_function_path})")
                logger.exception(e)
                continue

    def _process_function(
        self,
        function_path: pathlib.Path,
        function: ast.FunctionDef,
        target: Target,
        path_to_repo: pathlib.Path,
    ) -> Iterator[tuple[diff, MutationInfo]]:
        file_content = function_path.read_text_with_encoding_retry()

        file_content_after_empty_function = self._empty_function(file_content, function)

        function_signature_hint: str = hint_function(file_content, function)

        empty_function_diff = self._get_diff(
            file_content_after_empty_function,
            function_path,
            path_to_repo,
        )

        approximated_related_test_cases = self.test_targeter.get_related_test_cases({target})

        # Filter out functions that do not change test status
        true_related_test_cases = SimpleTestTargeter(
            self.test_targeter.tester, self.test_targeter.tester.original_test_status
        ).get_related_test_cases(MutationInfo(metadata={"empty_function_diff": empty_function_diff}), test_subset=approximated_related_test_cases)

        if len(true_related_test_cases) == 0:
            logger.warning(
                f"Function `{function.name}` does not change test results despite having {len(approximated_related_test_cases)} related test cases."
            )
            return

        logger.info(f"Empty function: `{function.name}` ({function_path})")

        __generated_output_diff: set[diff] = set()
        for _ in range(self.MUTATION_PER_FUNCTION):
            # Generate model output for the emptied function
            model_output: dict[str, str] = self.llm_implement(
                {
                    "entrypoint": function.name,
                    "file_content": file_content_after_empty_function,
                    "function_signature": function_signature_hint,
                }
            )

            model_raw_output: str = model_output["raw_output"]
            model_processed_output: str = model_output["code"]
            logger.info(f"Model processed output:\n{model_processed_output}")

            # Replace the old function body with the new one
            try:
                new_file_content = self._replace_function(file_content, function, model_processed_output)
                output_diff = self._get_diff(new_file_content, function_path, path_to_repo)
            except Exception as e:
                logger.error(f"Failed to replace function body: {e}")
                logger.error(f"Function: {function.name} ({function_path})")
                logger.error(f"=== Model output ===\n{model_raw_output}\n========")
                logger.exception(e)
                continue

            # Skip duplicates
            if output_diff in __generated_output_diff:
                continue
            __generated_output_diff.add(output_diff)

            # Yield mutation information
            yield output_diff, MutationInfo(
                {target},
                {
                    "empty_function_diff": empty_function_diff,
                    "function_signature_hint": function_signature_hint,
                    "original_file_content": file_content,
                },
                model_raw_output=model_raw_output,
                strategy=self.__class__.__name__,
                mutator_model_name=mutation_llm.model_name,
            )

    @staticmethod
    def _get_all_functions(path_to_repo: FilePath) -> Iterable[Target]:
        _path_to_repo = pathlib.Path(path_to_repo)
        if _path_to_repo.is_dir():
            for root, _, files in os.walk(_path_to_repo):
                for file in files:
                    # check if this is test file
                    if "test" in file:
                        continue
                    if file.endswith(".py"):
                        abs_path: pathlib.Path = pathlib.Path(root) / file
                        relative_path: str = abs_path.relative_to(_path_to_repo).as_posix()
                        if relative_path.startswith("tests/") or relative_path.startswith("test/") or relative_path.startswith("testing/"):
                            continue
                        file_content: str = abs_path.read_text_with_encoding_retry()
                        for node in get_all_functions(file_content):
                            yield Target(node, relative_path, abs_path.absolute())
        else:
            assert _path_to_repo.is_file()
            # NOTE: this is for debug only purpose
            relative_path: str = _path_to_repo.relative_to(pathlib.Path(_path_to_repo)).as_posix()
            for node in get_all_functions(_path_to_repo.read_text_with_encoding_retry()):
                yield Target(node, relative_path, _path_to_repo)

    @staticmethod
    def _empty_function(file_content: str, function: ast.FunctionDef) -> str:
        """
        Empty the function body, keeping the function signature.
        """
        return empty_function_body(file_content, function)

    @staticmethod
    def _replace_function(file_content: str, function: ast.FunctionDef, model_processed_output: str) -> str:
        """
        Replace the old function body with the new one, while keeping everything outside the function the same.
        """
        modified_file_content: str = replace_function_body(file_content, function, model_processed_output)
        return modified_file_content

    @override
    def load_checkpoint(self, existing_mutations: list["RepositorySnapshot"]) -> None:
        self.previous_mutated_functions = {target for mutation in existing_mutations for target in mutation.mutation_info.changed_targets}
        logger.info(f"Loaded {len(self.previous_mutated_functions)} previously mutated functions")


if __name__ == "__main__":
    strategy = EmptyFunctionStrategy()
    for mutant in strategy._mutate("/home/anonymous/Workspace/Code/swesynth/phase-2/class-mutation"):
        print(mutant)
        input("Press Enter to continue...")
