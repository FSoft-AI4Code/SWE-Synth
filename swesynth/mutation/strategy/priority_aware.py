import ast
import pathlib
import random
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from loguru import logger
from typing_extensions import override

from swesynth.mutation.validator.entities.mutation_info import MutationInfo, Target
from swesynth.mutation.validator.test_mapper.dynamic.parser import TestFunctionMap
from swesynth.mutation.validator.test_mapper.dynamic.scoring import FunctionScores, Scorer
from swesynth.typing import diff

from .empty_function import EmptyFunctionStrategy

if TYPE_CHECKING:
    from swesynth.mutation.validator.entities.status import TestStatusDiff
    from swesynth.mutation.validator.test_mapper.dynamic import DynamicCallGraphTestTargeter
    from swesynth.mutation.version_control.repository import RepositorySnapshot


@dataclass
class Scoring:
    # function_scores: FunctionScores | None = None
    """Function/Test cases importance scores"""

    test_function_map: TestFunctionMap | None = None

    function_to_node_degree: FunctionScores | None = None

    def load(self, test_targeter: "DynamicCallGraphTestTargeter") -> None:
        # self.function_scores = test_targeter.get_function_scores()
        self.test_function_map = test_targeter.test_function_map
        assert self.test_function_map is not None

        # optional, only for logging debug purpose
        self.function_to_node_degree = Scorer(self.test_function_map).compute_node_degree()

    def _calculate_passrate(self, function_nodeid: str, test_status_diff: "TestStatusDiff") -> float:
        num_total_passed_tests = len(test_status_diff.PASS_TO_PASS) + len(test_status_diff.PASS_TO_FAIL)
        num_total_failed_tests = len(test_status_diff.FAIL_TO_PASS) + len(test_status_diff.FAIL_TO_FAIL)
        true_related_tests: set[str] = (
            test_status_diff.PASS_TO_FAIL | test_status_diff.FAIL_TO_PASS | test_status_diff.FAIL_TO_FAIL | test_status_diff.PASS_TO_PASS
        )

        function_to_test_mapping = self.test_function_map.function_to_test_mapping
        assert function_to_test_mapping is not None

        # changed_status_tests: set[str] = test_status_diff.PASS_TO_FAIL | test_status_diff.FAIL_TO_PASS
        changed_status_tests: set[str] = test_status_diff.PASS_TO_FAIL

        all_related_tests_to_this_function: set[str] = set(function_to_test_mapping.get(function_nodeid, []))
        in_context_related_tests_to_this_function: set[str] = all_related_tests_to_this_function & true_related_tests

        logger.info(
            f"Function '{function_nodeid}' | Estimated related tests: {len(all_related_tests_to_this_function)} | In context: {len(in_context_related_tests_to_this_function)}"
        )

        if len(in_context_related_tests_to_this_function) == 0:
            logger.warning(f"No related tests found for {function_nodeid}")
            return 0

        changed_related_tests_to_this_function: set[str] = in_context_related_tests_to_this_function & changed_status_tests

        failrate = len(changed_related_tests_to_this_function) / len(in_context_related_tests_to_this_function)
        passrate = 1 - failrate

        if passrate == 1:
            passrate = 0

        logger.info(
            f"Function '{function_nodeid}' passrate: {passrate} ({len(changed_related_tests_to_this_function)}/{len(in_context_related_tests_to_this_function)} changed from pass to fail)"
        )

        return passrate

    def score(self, mutated_repo: "RepositorySnapshot") -> float:
        assert mutated_repo.test_status_diff is not None and self.test_function_map is not None

        related_functions = mutated_repo.mutation_info.changed_targets

        total_score = 0

        for func in related_functions:
            nodeid = func.nodeid
            # important_score = self.function_scores.function_to_scores.get(nodeid, 0)
            important_score = 0

            if important_score == 0:
                logger.warning(f"Function {func} has no importance score")

            passrate = self._calculate_passrate(nodeid, mutated_repo.test_status_diff)

            score = passrate * important_score

            logger.info(f"Function '{nodeid}' | Passrate={passrate} | Importance={important_score} | Score={passrate} x {important_score} = {score}")

            total_score += score

        logger.info(f"Total score: {total_score}")

        return total_score


class PriorityAwareMutationStrategy(EmptyFunctionStrategy, Scoring):
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

        weights = [self.function_to_node_degree.function_to_scores.get(func.nodeid, 0) for func in all_functions]

        while len(all_functions) > 0:
            # Randomly pick a function
            function: ast.FunctionDef

            # target: Target = self.get_next_target(all_functions)

            random_idx = random.choices(range(len(all_functions)), weights=weights, k=1)[0]
            target = all_functions.pop(random_idx)
            weights.pop(random_idx)

            logger.info(
                # f"Inspecting target: '{target.nodeid}' | Score={self.function_scores.function_to_scores.get(target.nodeid, -1)} "
                f"Inspecting target: '{target.nodeid}' "
                f"| Degree={self.function_to_node_degree.function_to_scores.get(target.nodeid, -1)}"
            )

            function_path, relative_path, function = target.abs_path_to_file, target.relative_path, target.ast_obj

            try:
                yield from self._process_function(function_path, function, target, path_to_repo)
            except Exception as e:
                logger.error(f"Failed to process function: {e}")
                logger.error(f"Function: {function.name} ({function_path})")
                logger.exception(e)
                continue

    def load(self, test_targeter: "DynamicCallGraphTestTargeter") -> None:
        EmptyFunctionStrategy.load(self, test_targeter)
        Scoring.load(self, test_targeter)
