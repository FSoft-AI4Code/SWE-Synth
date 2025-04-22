from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from swesynth.mutation.validator.entities.mutation_info import MutationInfo
from swesynth.mutation.validator.entities.status import TestStatus, TestStatusDiff

if TYPE_CHECKING:
    from swesynth.mutation.validator.tester import Tester
    from swesynth.mutation.version_control.repository import RepositorySnapshot


@dataclass
class SimpleTestTargeter:
    """
    Get related test cases for a given mutation, by simply running the test with empty function body
    i.e. adding `raise NotImplementedError` to the function
    """

    tester: "Tester"
    original_test_status: TestStatus

    def get_related_test_cases(
        self,
        mutation_info: MutationInfo,
        test_subset: set[str] | None = None,
    ) -> set[str]:
        emptied_function_body_diff: str = mutation_info.metadata.get("empty_function_diff") or mutation_info.metadata.get("empty_class_diff") or ""
        if not emptied_function_body_diff:
            logger.warning(f"Mutation {mutation_info} does not have empty function diff")
            return set()
        source_code_with_empty_function_body: "RepositorySnapshot" = self.tester.source_code.copy_with_changes(emptied_function_body_diff)
        logger.info(f"Running test with empty function diff: {source_code_with_empty_function_body.relative_log_dir / 'patch.diff'}")
        empty_function_test_status: TestStatus = self.tester.test(source_code_with_empty_function_body, test_subset=test_subset)
        test_status_diff: TestStatusDiff = self.original_test_status >> empty_function_test_status
        if len(test_status_diff.FAIL_TO_PASS) > 0:
            logger.warning(f"Test cases FAIL_TO_PASS only by empty function: {test_status_diff.FAIL_TO_PASS}")
        need_to_test: set[str] = test_status_diff.PASS_TO_FAIL | test_status_diff.FAIL_TO_PASS
        if len(need_to_test) == 0:
            logger.warning(f"Test status does not change by emptying function body.")
            logger.warning(f"Original test status: {self.original_test_status}")
            logger.warning(f"Empty body test status: {empty_function_test_status}")

        if not empty_function_test_status:
            logger.warning("Something seems went wrong")
            if source_code_with_empty_function_body.test_log_traces is not None:
                logger.warning(
                    f"Raw test logs:\n====== Raw test logs ======\n{source_code_with_empty_function_body.test_log_traces[-3000:]}\n========================"
                )

        return need_to_test

    def get_first_test_command(self) -> str:
        return self.tester.docker_manager.get_test_command(self.tester.source_code)

    def train(self) -> None:
        pass

    def parse_test_output(
        self,
        raw_test_output: str,
    ) -> TestStatus:
        return self.tester.parse_test_output(raw_test_output)
