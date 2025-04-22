from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import TYPE_CHECKING, overload

import yaml
from loguru import logger
from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS

from swesynth.mutation.validator.test_mapper.dynamic import DynamicCallGraphTestTargeter
from swesynth.mutation.validator.test_mapper.simple import SimpleTestTargeter

from .entities.status import TestStatus
from .docker_manager import DockerManager
from .docker.multiprocessing_utils import get_test_mapping_lock

if TYPE_CHECKING:
    from ..version_control.repository import Repository, RepositorySnapshot


@dataclass
class Tester:
    source_code: "RepositorySnapshot"
    docker_manager: DockerManager = field(init=False)
    test_targeter: DynamicCallGraphTestTargeter = field(init=False)

    original_test_status: TestStatus | None = None

    @property
    def test_status_file(self) -> Path:
        return self.docker_manager.log_dir / "test_status.json"

    def __post_init__(self):
        """
        Initialize needed metadata for testing
        """
        self.docker_manager = DockerManager(self.source_code)
        self.test_targeter = DynamicCallGraphTestTargeter(self)

    def setup(self, remove_image_after_container_exit: bool = False) -> "Tester":
        # self.docker_manager.build_docker_image(remove_image_after_container_exit)
        return self

    @overload
    def test(self) -> TestStatus:
        """Test the source code without applying any patch"""

    @overload
    def test(self, mutated_repo: "RepositorySnapshot") -> TestStatus:
        """Test the mutated source code with all test cases"""

    @overload
    def test(self, mutated_repo: "RepositorySnapshot", test_subset: set[str]) -> TestStatus:
        """Test the mutated source code with specific test cases"""

    @logger.log_exception()
    def test(self, mutated_repo: "RepositorySnapshot | None" = None, test_subset: set[str] | None = None) -> TestStatus:
        """
        Side Effects:
            1. write test status to file
            2. mutated_repo.test_log_traces will be updated
        """
        assert self.docker_manager.container is not None, "Container is not initialized, call `with tester` first"

        self.docker_manager.set_log_dir(mutated_repo)
        if self.test_status_file.exists():
            logger.info(f"Test status already exists: {self.test_status_file}")
            return TestStatus.from_json_file(self.test_status_file)

        self.log(mutated_repo or self.source_code)

        if mutated_repo is None:
            assert test_subset is None, "Test subset is only applicable for mutated repo"
            return self._test_original_source_code()

        assert mutated_repo.unstaged_changes, "Diff is should not empty"
        try:
            with self.docker_manager.using_git_with(change=mutated_repo.unstaged_changes):
                test_command: str = self.docker_manager.get_test_command(mutated_repo, test_subset or set())
                raw_output: str = self.docker_manager.exec(test_command)
                test_result: TestStatus = self.parse_test_output(raw_output)
                mutated_repo.test_log_traces = mutated_repo.parse_test_log_traces(raw_output)

                if test_subset is not None:
                    test_result = test_result.shrink_to(test_subset)

                return test_result
        except Exception as e:
            logger.error(f"Failed to test: {e}")
            logger.exception(e)
            return TestStatus(set(), set())

    def _test_original_source_code(self) -> TestStatus:
        test_command: str = self.docker_manager.get_test_command(self.source_code)
        raw_test_output: str = self.docker_manager.exec(test_command)

        test_command: str = self.test_targeter.get_first_test_command()
        with get_test_mapping_lock:
            raw_output: str = self.docker_manager.exec(
                test_command, name="get_mapping.sh", timeout=3600 * int(os.environ.get("SWESYNTH_GET_REPO_MAPPING_TIMEOUT", 15))
            )
        self.test_targeter.parse_test_output(raw_output, self.docker_manager.container)
        self.test_targeter.train()

        test_result: TestStatus = self.parse_test_output(raw_test_output)
        self.source_code.test_log_traces = self.source_code.parse_test_log_traces(raw_test_output)
        return test_result

    def log(self, mutated_repo: "RepositorySnapshot") -> None:
        data = mutated_repo.to_dict()
        data.pop("test_log_traces")  # visual
        (self.docker_manager.log_dir / "mutated_source_code.yml").write_text(yaml.dump_nice_yaml(data))

    def __enter__(self) -> "Tester":
        """Manage container lifetime"""
        self.docker_manager.create_docker_container()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.docker_manager.cleanup()

    def parse_test_output(
        self,
        raw_test_output: str,
        test_subset: set[str] | None = None,
    ) -> TestStatus:
        # Get report from test output
        logger.info(f"Grading answer ...")
        report: TestStatus = TestStatus.parse_test_output(raw_test_output, self.source_code.repo)
        if report == TestStatus(set(), set()):
            logger.warning("Test status is empty, something seems went wrong")
            return report

        if test_subset is not None:
            report = report.shrink_to(test_subset)
        report.to_json_file(self.test_status_file)
        logger.info(f"Output written to {self.test_status_file}")
        logger.info(f"Test status: {report}")
        return report

    def get_related_test_cases(self, original_source_code_test_status: TestStatus, mutated_repo: "RepositorySnapshot") -> set[str]:
        if mutated_repo.unstaged_changes is None:
            logger.warning("No unstaged changes")
            return set()

        """
        This is over-estimated related test cases, because it includes all setup-teardown functions
        """
        approximated_related_test_cases = self.test_targeter.get_related_test_cases(mutated_repo.mutation_info.changed_targets)
        # approx is correct

        if len(approximated_related_test_cases) == 0:
            logger.error("This mutation does not have any related test cases")
            return set()

        # OPTIONAL: this is only minor optimization, should have almost no affect on the score
        logger.info(f"Original test status: {original_source_code_test_status}")
        original_source_code_test_status = original_source_code_test_status.shrink_to(approximated_related_test_cases)
        logger.info(f"Original test status after shrink to approximated related test cases: {original_source_code_test_status}")

        # Get the true related test cases
        true_related_test_cases = SimpleTestTargeter(self, original_source_code_test_status).get_related_test_cases(
            mutated_repo.mutation_info, test_subset=approximated_related_test_cases
        )

        if len(true_related_test_cases) == 0:
            logger.warning("This mutation does not have any related test cases")
            return set()

        return true_related_test_cases

    @staticmethod
    def get_test_case_log(swebench_converted_instance: "RepositorySnapshot") -> str:
        if swebench_converted_instance.test_log_traces is not None:
            logger.warning(f"Test log traces already exists for {swebench_converted_instance}")

        assert swebench_converted_instance.test_status_diff is not None and swebench_converted_instance.unstaged_changes is not None

        with Tester(swebench_converted_instance).setup(remove_image_after_container_exit=True) as tester:
            # test_files: set[str] = swebench_converted_instance.test_status_diff.get_related_test_files()
            test_files = {test_file.split("::")[0] for test_file in swebench_converted_instance.test_status_diff.all_tests}
            test_command: str = tester.docker_manager.get_test_command(swebench_converted_instance, test_files)
            with tester.docker_manager.using_git_with(change=swebench_converted_instance.unstaged_changes):
                raw_output: str = tester.docker_manager.exec(test_command)

                # NOTE: these test_results status only used to check if the test status is equal to the expected (reproduce), not used for returning the value
                test_result: TestStatus = tester.parse_test_output(raw_output, test_subset=swebench_converted_instance.test_status_diff.all_tests)

                expected_test_status: TestStatus = TestStatus(
                    passed_test_cases=swebench_converted_instance.test_status_diff.PASS_TO_PASS,
                    failed_test_cases=swebench_converted_instance.test_status_diff.PASS_TO_FAIL
                    | swebench_converted_instance.test_status_diff.FAIL_TO_PASS,
                )

                test_result = test_result.fill_missing_test_cases_from(expected_test_status, as_failed=True)

                if test_result != expected_test_status:
                    logger.warning(f"Test status is not equal to the expected: {swebench_converted_instance}")
                    logger.warning(f"Expected: {expected_test_status}")
                    logger.warning(f"Actual: {test_result}")
                else:
                    logger.success(f"Test status is equal to the expected!")

                if test_result.passed_test_cases != expected_test_status.passed_test_cases:
                    logger.warning(f"Passed test cases are not equal to the expected")
                    logger.warning(f"Expected {len(expected_test_status.passed_test_cases)}: {expected_test_status.passed_test_cases}")
                    logger.warning(f"Actual: {len(test_result.passed_test_cases)}: {test_result.passed_test_cases}")

                if test_result.failed_test_cases != expected_test_status.failed_test_cases:
                    logger.warning(f"Failed test cases are not equal to the expected")
                    logger.warning(f"Expected: {len(expected_test_status.failed_test_cases)}: {expected_test_status.failed_test_cases}")
                    logger.warning(f"Actual: {len(test_result.failed_test_cases)}: {test_result.failed_test_cases}")

                swebench_converted_instance.test_log_traces = swebench_converted_instance.parse_test_log_traces(raw_output)
                return swebench_converted_instance.test_log_traces


if __name__ == "__main__":
    pass
