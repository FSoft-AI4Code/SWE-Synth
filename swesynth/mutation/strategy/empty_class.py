"""
Randomly pick a class, remove all of its methods, and then ask LLM to re-implement them
"""

import ast
import os
import pathlib
import random
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Iterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from loguru import logger
from tqdm import tqdm
from typing_extensions import override

from swesynth.mutation.processing.model_output import extract_code
from swesynth.mutation.processing.program import empty_class, empty_function_body, replace_class_body
from swesynth.mutation.processing.program.transform import hint_class
from swesynth.mutation.processing.program.extract import get_all_classes, get_all_functions
from swesynth.mutation.validator.entities.mutation_info import MutationInfo, Target
from swesynth.mutation.validator.test_mapper.simple import SimpleTestTargeter
from swesynth.mutation.version_control.checkout import UsingRepo
from swesynth.typing import FilePath, diff

from .base import Strategy, mutation_llm

if TYPE_CHECKING:
    from swesynth.mutation.validator.test_mapper.dynamic.targeter import DynamicCallGraphTestTargeter


@dataclass
class EmptyClassStrategy(Strategy):
    MUTATION_PER_CLASS: int = 2
    path_to_repo: pathlib.Path | None = None

    chain = (
        ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a senior python developer. You always explain your intention before writing code that you are sure of.""",
                ),
                (
                    "user",
                    """Given the code below, please implement the body of the class `{entrypoint}`. \
Do not change the signature of the class, which includes all the methods name, parameters, return type, and the methods' docstring. \
Keep all the methods' signatures and their docstrings as they are. \
This also means you should not add new docstrings to the method if they are not already there. \
Do not add any additional import statements. \
Please implement the class directly without changing the surrounding context beyond the class body.

```python
{file_content}
```

Answer in the following format:

<explain your implementation>

```python
{class_signature}
```
""",
                ),
            ]
        )
        | mutation_llm
        | StrOutputParser()
        | {"raw_output": RunnablePassthrough(), "code": extract_code}
    )

    def _filter_no_tested_classes(self, all_classes: list[Target]) -> list[Target]:
        if self.test_targeter is None:
            logger.warning("No test targeter is provided")
            return all_classes

        # Filter out classes that have no related test cases
        remaining_classes: list[Target] = []
        with tqdm(all_classes, desc="Filtering out untested classes") as pbar:
            for target in pbar:
                changed_class_methods: set[ast.FunctionDef] = {node for node in target.ast_obj.body if isinstance(node, ast.FunctionDef)}
                changed_class_methods_targets: set[Target] = {
                    Target(node, target.relative_path, target.abs_path_to_file) for node in changed_class_methods
                }
                approximated_related_test_cases = self.test_targeter.get_related_test_cases(changed_class_methods_targets)

                if len(approximated_related_test_cases) == 0:
                    logger.warning(f"Class `{target.ast_obj.name}` does not have any approximated related test cases")
                    continue

                remaining_classes.append(target)
                pbar.set_postfix({"Collected": len(remaining_classes)})

        return remaining_classes

    @override
    def _mutate(self, path_to_repo: pathlib.Path) -> Iterator[tuple[diff, MutationInfo]]:
        self.path_to_repo = path_to_repo
        all_classes: list[Target] = list(self._get_all_classes(path_to_repo))

        if len(all_classes) == 0:
            logger.warning(f"No classes found in {path_to_repo}")
            return

        logger.info(f"Found {len(all_classes)} classes in {path_to_repo}")
        all_classes = self._filter_no_tested_classes(all_classes)
        logger.info(f"Remaining {len(all_classes)} classes after filtering out untested classes")

        while len(all_classes) > 0:
            # Randomly pick a class
            random_idx = random.randint(0, len(all_classes) - 1)
            target = all_classes.pop(random_idx)

            abs_path, relative_path, class_node = target.abs_path_to_file, target.relative_path, target.ast_obj

            try:
                yield from self._process_class(abs_path, class_node, target, path_to_repo)
            except Exception as e:
                logger.error(f"Failed to process class: {e}")
                logger.error(f"Class: {class_node.name} ({abs_path})")
                logger.exception(e)
                continue

    def _process_class(
        self, class_path: pathlib.Path, class_node: ast.ClassDef, target: Target, path_to_repo: pathlib.Path
    ) -> Iterator[tuple[diff, MutationInfo]]:
        # Read the file content
        file_content: str = class_path.read_text_with_encoding_retry()

        # Empty all methods in the selected class
        file_content_after_empty_methods: str = self._empty_class_methods(file_content, class_node)
        logger.info(f"Emptying methods of class: `{class_node.name}` ({class_path})")

        if file_content == file_content_after_empty_methods:
            # super rare case
            logger.warning(f"No method is emptied in class `{class_node.name}`")
            if len([node for node in class_node.body if isinstance(node, ast.FunctionDef)]) == 0:
                logger.warning(f"Because class `{class_node.name}` has no methods")
            return

        changed_class_methods: set[ast.FunctionDef] = {node for node in class_node.body if isinstance(node, ast.FunctionDef)}
        changed_class_methods_targets: set[Target] = {Target(node, target.relative_path, target.abs_path_to_file) for node in changed_class_methods}

        approximated_related_test_cases = self.test_targeter.get_related_test_cases(changed_class_methods_targets)

        # Generate the diff for the emptied methods
        empty_methods_diff: diff = self._get_diff(
            file_content_after_empty_methods,
            class_path,
            path_to_repo,
        )

        # Filter out classes that DO have related test cases, but emptying all methods does not change the test status
        true_related_test_cases = SimpleTestTargeter(
            self.test_targeter.tester, self.test_targeter.tester.original_test_status
        ).get_related_test_cases(MutationInfo(metadata={"empty_class_diff": empty_methods_diff}), test_subset=approximated_related_test_cases)

        if len(true_related_test_cases) == 0:
            logger.warning(
                f"Class `{target.ast_obj.name}` does not have any true related test cases after running tests with empty methods,"
                f" despite having approximated related test cases {approximated_related_test_cases if len(str(approximated_related_test_cases)) < 1000 else str(approximated_related_test_cases)[:1000] + '...' + str(approximated_related_test_cases)[-1000:]}"
            )
            return

        class_signature_hints: str = hint_class(file_content, class_node)

        __generated_output_diff: set[diff] = set()
        for _ in range(self.MUTATION_PER_CLASS):
            # Invoke the LLM to re-implement the methods
            model_output: dict[str, str] = self.llm_implement(
                {
                    "entrypoint": class_node.name,
                    "file_content": file_content_after_empty_methods,
                    "class_signature": class_signature_hints,
                }
            )

            model_raw_output: str = model_output["raw_output"]
            model_processed_output: str = model_output["code"]
            logger.info(f"Model raw output for class `{class_node.name}`:\n{model_raw_output}")
            logger.info(f"Model processed output for class `{class_node.name}`:\n{model_processed_output}")

            # Replace the old methods with the new implementations
            try:
                new_file_content: str = self._replace_class_methods(file_content, class_node, model_processed_output)
            except Exception as e:
                logger.error(f"Failed to replace class methods: {e}")
                logger.error(f"=== Model output ===\n{model_raw_output}\n========")
                logger.exception(e)
                continue

            if file_content_after_empty_methods.count("raise NotImplementedError") == new_file_content.count("raise NotImplementedError"):
                logger.warning(f"No method is replaced in class `{class_node.name}`")
                continue

            # Generate the diff for the mutation
            output_diff: diff = self._get_diff(new_file_content, class_path, path_to_repo)

            if output_diff in __generated_output_diff:
                continue
            else:
                __generated_output_diff.add(output_diff)

            yield output_diff, MutationInfo(
                {target, *changed_class_methods_targets},
                metadata={
                    "empty_class_diff": empty_methods_diff,
                    "class_signature_hints": class_signature_hints,
                    "original_file_content": file_content,
                    "class_name": class_node.name,
                },
                model_raw_output=model_raw_output,
                strategy=self.__class__.__name__,
                mutator_model_name=mutation_llm.model_name,
            )

    @staticmethod
    def _get_all_classes(path_to_repo: FilePath) -> Iterable[Target]:
        """
        Extract all classes from the repository excluding test files.
        """
        _path_to_repo: pathlib.Path = pathlib.Path(path_to_repo)
        if _path_to_repo.is_dir():
            for root, _, files in os.walk(_path_to_repo):
                for file in files:
                    # Skip test files
                    if "test" in file.lower():
                        continue
                    if file.endswith(".py"):
                        abs_path: pathlib.Path = pathlib.Path(root) / file
                        relative_path: str = abs_path.relative_to(_path_to_repo).as_posix()
                        if relative_path.startswith("tests/") or relative_path.startswith("test/") or relative_path.startswith("testing/"):
                            continue
                        file_content: str = abs_path.read_text_with_encoding_retry()
                        for node in get_all_classes(file_content):
                            yield Target(node, relative_path, abs_path.absolute())
        else:
            assert _path_to_repo.is_file()
            relative_path: str = _path_to_repo.relative_to(pathlib.Path(_path_to_repo)).as_posix()
            for node in get_all_classes(_path_to_repo.read_text_with_encoding_retry()):
                yield Target(node, relative_path, _path_to_repo)

    @staticmethod
    def _empty_class_methods(file_content: str, class_node: ast.ClassDef) -> str:
        """
        Empty all method bodies within the specified class, keeping method signatures.
        """
        if "Base" in class_node.name:
            logger.warning(f"We are emptying methods of a base class: {class_node.name}")

        return empty_class(file_content, class_node)

    @staticmethod
    def _replace_class_methods(file_content: str, class_node: ast.ClassDef, model_processed_output: str) -> str:
        """
        Replace the old method bodies with the new ones generated by the LLM.
        """
        modified_file_content: str = replace_class_body(file_content, class_node, model_processed_output)
        return modified_file_content


if __name__ == "__main__":
    strategy = EmptyClassStrategy()
    for mutant in strategy._mutate("/home/anonymous/Workspace/Code/swesynth/phase-2/class-mutation"):
        print(mutant)
        input("Press Enter to continue...")
