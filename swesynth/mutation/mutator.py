from dataclasses import dataclass, field
from typing import Iterable

from langchain_community.callbacks.manager import get_openai_callback
from loguru import logger

from .strategy import EmptyClassStrategy, EmptyFunctionStrategy, PriorityAwareMutationStrategy, Strategy
from .validator.tester import Tester, TestStatus
from .version_control.repository import Repository, RepositorySnapshot


@dataclass
class Mutator:
    source_code: RepositorySnapshot
    strategy: Strategy = field(default_factory=PriorityAwareMutationStrategy)

    MAX_ITERATION: int = 10_000

    def __post_init__(self) -> None:
        assert self.source_code.unstaged_changes is None

    @logger.log_exception()
    def mutate(
        self,
        number_of_mutations: int = 100,
        max_cost: float = 1000.0,
    ) -> Iterable[RepositorySnapshot]:
        """
        Mutate the source code and return the mutated source codes

        Args:
            number_of_mutations_per_commit: number of mutations per commit
            max_cost: maximum cost (in USD)
        Returns:
            list[RepositorySnapshot]: list of mutated source codes
        """
        if number_of_mutations > self.MAX_ITERATION:
            logger.warning(f"number_of_mutations_per_commit is greater than {self.MAX_ITERATION}")

        generated_mutant_counter: int = 0
        usable_mutant_counter: int = 0
        with get_openai_callback() as cost, Tester(self.source_code).setup() as tester:

            original_test_status: TestStatus = tester.test()
            tester.original_test_status = original_test_status
            logger.info(f"Original test status: {original_test_status}")
            if not original_test_status:
                logger.error("Failed to test original source code, skip this commit")
                return
            self.strategy.load(tester.test_targeter)

            mutant_count: int = 0
            mutated_repo: RepositorySnapshot
            for mutated_repo in self.strategy.mutate(self.source_code):
                tester.docker_manager.set_log_dir(mutated_repo)

                generated_mutant_counter += 1
                if generated_mutant_counter >= self.MAX_ITERATION:
                    logger.info(f"Reached max iteration {self.MAX_ITERATION}")
                    break

                logger.info(f"Current cost: {cost}")
                if cost.total_cost > max_cost:
                    logger.warning(f"Reached max cost {cost.total_cost} > {max_cost}")
                    break

                test_subset: set[str] = tester.get_related_test_cases(original_test_status, mutated_repo)
                original_test_subset_status: TestStatus = original_test_status.shrink_to(test_subset)
                logger.info(f"Original test subset status: {original_test_subset_status}")

                if len(test_subset) == 0:
                    logger.info("No test cases to test, skip this mutant")
                    continue

                mutated_test_status: TestStatus = tester.test(mutated_repo, test_subset)

                if original_test_subset_status == mutated_test_status:
                    logger.info("All tests passed, skip this mutant")  # test status doesn't change
                    continue

                if not mutated_test_status:
                    logger.error("Something went wrong, skip this mutant")
                    if mutated_repo.test_log_traces is not None:
                        logger.error(f"Raw test logs:\n====== Raw test logs ======\n{mutated_repo.test_log_traces[-3000:]}\n========================")
                    continue

                if len(mutated_test_status.failed_test_cases) == 0:
                    logger.info(
                        "All tests passed, skip this mutant. "
                        "Note that this mutant is likely to fix some additional bug, but we are looking for causing a bug."
                    )
                    logger.info(f"Test status diff: {original_test_subset_status >> mutated_test_status}")
                    continue

                expected_test_status_diff = original_test_subset_status >> mutated_test_status
                test_files: set[str] = expected_test_status_diff.get_related_test_files()
                logger.info(f"Re-validate {len(test_files)} test files: {test_files}")
                related_test_cases: set[str] = original_test_status.get_all_tests_from_files(test_files)
                expected_original_test_status: TestStatus = original_test_status.shrink_to(related_test_cases)
                mutant_test_status: TestStatus = tester.test(mutated_repo, related_test_cases)
                real_test_status_diff = expected_original_test_status >> mutant_test_status
                if real_test_status_diff != expected_test_status_diff:
                    logger.info(f"Fixed test status diff from {expected_test_status_diff} to {real_test_status_diff}")

                if len(real_test_status_diff.PASS_TO_FAIL) == 0:
                    logger.info("All tests passed, skip this mutant")
                    continue

                mutated_repo.test_status_diff = real_test_status_diff
                mutated_repo.score = self.strategy.score(mutated_repo)
                try:
                    mutated_repo.save_reversed_diff()
                except Exception as e:
                    logger.error(f"Failed to save reversed diff: {e}")
                    logger.exception(e)
                    continue

                tester.log(mutated_repo)

                mutant_count += 1
                usable_mutant_counter += 1
                logger.info(f"Found mutant with test status: {mutant_test_status}")
                logger.info(f"Test status diff: {mutated_repo.test_status_diff}")
                logger.info(f"Mutant diff: {mutated_repo.relative_log_dir / 'patch.diff'}")
                logger.info(f"Usable mutant count: {usable_mutant_counter} | Generated mutant count: {generated_mutant_counter}")

                yield mutated_repo

                if mutant_count >= number_of_mutations:
                    logger.info(f"Found {mutant_count} mutants")
                    break


if __name__ == "__main__":
    with Repository("astropy/astropy") as repo:
        snapshot = repo.checkout("3832210580d516365ddae1a62071001faf94d416")
        mutator = Mutator(snapshot, strategy=EmptyFunctionStrategy())
        gen = mutator.mutate()
        mutant = next(gen)
        print(mutant)
