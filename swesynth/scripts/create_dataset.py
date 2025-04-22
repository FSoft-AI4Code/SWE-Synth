import json
from dataclasses import dataclass
from multiprocessing import Manager, Pool, Value, Process
import threading
from pathlib import Path
from time import sleep

from tempfile import TemporaryDirectory
import rich_argparse
import simple_parsing
from tqdm import tqdm
import yaml
from git import Repo
from loguru import logger
from swebench.harness.constants import RUN_EVALUATION_LOG_DIR

from swesynth.mutation.mutator import Mutator
from swesynth.mutation.strategy import EmptyClassStrategy, EmptyFunctionStrategy, PriorityAwareMutationStrategy, Strategy
from swesynth.mutation.version_control.checkout import GitRemoteProgress
from swesynth.mutation.version_control.repository import Repository, RepositorySnapshot
from swesynth.mutation.validator.docker.multiprocessing_utils import (
    docker_max_semaphore,
    get_test_mapping_lock,
    concurrent_waiting_mutator_counter_semaphores,
    is_locked,
    test_log_stream_dict,
    num_semaphores,
    num_mutator_semaphores,
)
from swesynth.utils import sample_with_seed, read_jsonl

num_generated_bug_so_far = Value("i", 0)
finished_commits = Value("i", 0)
error_commits = Value("i", 0)

NUM_SAMPLE_COMMITS = 5


@dataclass
class Config:
    """Mutation Configuration"""

    repo: str
    repo_clone_cache_dir: str = "cache"
    """"""
    # 50K / 16 repo = 3125 mutation per repo
    stop_mutation_at: int = 6250
    """Stop mutation at this number of mutants"""
    output_dir: str = "./output_dir"
    """Output directory to store the mutants and logs"""
    max_cost: float = 1000.0
    """
    Maximum cost for mutation, in USD
    This will be divided by the number of known commits
    # this is just in case
    """
    seed: int = 42
    """Random seed for sampling commits"""


MUTATION_RATIO: dict[type[Strategy], float] = {
    PriorityAwareMutationStrategy: 0.1,
    EmptyClassStrategy: 0.1,
    EmptyFunctionStrategy: 0.8,
}


@logger.catch(BaseException)
def process_commit(args):
    (
        repo_cache_dir,
        commit_hash,
        config,
        output_path,
        max_cost_per_commit,
        max_mutation_per_commit,
    ) = args

    repo_name: str = config.repo.replace("/", "_")
    log_file_path: Path = output_path / f"{repo_name}_{commit_hash}.log"
    logger.add(log_file_path, level="INFO", enqueue=True)
    logger.info(f"===== Logging to {log_file_path} =====")
    logger.info(f"=== Begin mutation at commit {commit_hash} ===")

    try:
        with TemporaryDirectory(dir=repo_cache_dir) as path_to_tmp_dir:
            path_to_tmp_dir = Path(path_to_tmp_dir)
            Repo.clone_from(repo_cache_dir / "original", path_to_tmp_dir)
            logger.info(f"Cloned {config.repo} to `{path_to_tmp_dir}`")

            with Repository(config.repo, path_to_tmp_dir) as repo:

                snapshot: RepositorySnapshot = repo.checkout(commit_hash)

                for strategy_class, ratio in MUTATION_RATIO.items():
                    output_file_path: Path = output_path / f"{repo_name}_{commit_hash}_{strategy_class.__name__}.jsonl"
                    num_existing_mutations: int = output_file_path.read_text().count("\n") if output_file_path.exists() else 0

                    num_mutations: int = int(max_mutation_per_commit * ratio) - num_existing_mutations
                    max_cost_per_strategy: float = max_cost_per_commit * ratio

                    if num_mutations <= 0:
                        logger.info(
                            f"Skip commit {commit_hash} for strategy `{strategy_class.__name__}` as it already has {num_existing_mutations} mutations"
                        )
                        continue

                    strategy: Strategy = strategy_class()
                    if num_existing_mutations > 0:
                        logger.warning(
                            f"Found {num_existing_mutations} existing mutations in {output_file_path} , will generate {num_mutations} more mutations"
                        )
                        existing_mutations: list[RepositorySnapshot] = [
                            RepositorySnapshot.from_dict(mutation) for mutation in read_jsonl(output_file_path)
                        ]
                        strategy.load_checkpoint(existing_mutations)

                    with output_file_path.open("a") as f:
                        mutator = Mutator(snapshot, strategy=strategy)
                        for mutant in mutator.mutate(number_of_mutations=num_mutations, max_cost=max_cost_per_strategy):
                            f.write(json.dumps(mutant.to_dict(), skipkeys=True) + "\n")

                            with num_generated_bug_so_far.get_lock():
                                num_generated_bug_so_far.value += 1
                                logger.success(f"Generated total {num_generated_bug_so_far.value} bugs so far")

                                if num_generated_bug_so_far.value >= config.stop_mutation_at:
                                    # It should never reach here, but just in case
                                    return

    except Exception as e:
        logger.error(f"Commit finished with error '{commit_hash}': {e}")
        with error_commits.get_lock():
            error_commits.value += 1
            logger.error(f"Error {error_commits.value} commits so far")
        raise e
    finally:
        with finished_commits.get_lock():
            finished_commits.value += 1
            logger.success(f"Finished {finished_commits.value} commits so far")


@logger.log_exception()
def main(config: Config):
    global MUTATION_RATIO

    repo_name = config.repo.replace("/", "_").lower()
    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Configure logging for the specific repository and strategy
    logger.add(output_path / f"{repo_name}.log", level="INFO", enqueue=True)
    logger.add(RUN_EVALUATION_LOG_DIR / repo_name / "create_dataset.log", level="INFO", enqueue=True)
    logger.info(f"=============== Creating mutation dataset for {config.repo} ===============")
    logger.info(f"Config: {config}")
    (output_path / f"{repo_name}.yaml").write_text(yaml.dump_nice_yaml(config.__dict__))

    # Handle repository caching
    repo_cache_dir: Path = Path(config.repo_clone_cache_dir) / repo_name

    if not repo_cache_dir.exists():
        logger.warning(f"Cloning {config.repo} to {repo_cache_dir}")
        repo_cache_dir.mkdir(parents=True, exist_ok=True)
        Repo.clone_from(f"https://github.com/{config.repo}.git", repo_cache_dir / "original", progress=GitRemoteProgress())

    all_known_commits: list[str] = Repository(config.repo).sample_known_commit(k=NUM_SAMPLE_COMMITS, seed=config.seed)

    max_cost_per_commit = config.max_cost / len(all_known_commits)
    logger.info(f"Max cost per commit: {config.max_cost} / {len(all_known_commits)} = {max_cost_per_commit}")
    max_mutation_per_commit = config.stop_mutation_at // len(all_known_commits)
    logger.info(f"Max mutation per commit: {config.stop_mutation_at} // {len(all_known_commits)} = {max_mutation_per_commit}")

    for strategy_class, ratio in MUTATION_RATIO.items():
        num_mutations = int(max_mutation_per_commit * ratio)
        logger.info(f"Strategy `{strategy_class.__name__}`: {num_mutations} target mutations per commit")

    pool_args = [
        (repo_cache_dir, commit_hash, config, output_path, max_cost_per_commit, max_mutation_per_commit) for commit_hash in all_known_commits
    ]

    def get_report() -> str:
        l = f"""
--- Running Status ---
Generated total {num_generated_bug_so_far.value} bugs so far
Finished {finished_commits.value}/{len(all_known_commits)} commits ({error_commits.value} finished with errors)
Concurrent waiting mutator: {num_mutator_semaphores - concurrent_waiting_mutator_counter_semaphores.get_value()} (max: {num_mutator_semaphores})
Docker exec running test: {num_semaphores - docker_max_semaphore.get_value()} (max: {num_semaphores})
Docker get test mapping lock status: {is_locked(get_test_mapping_lock)} (max: 1)
----------------------"""
        for instance_id, test_log_stream_file in test_log_stream_dict.items():
            l += f"\nInstance '{instance_id}': '{test_log_stream_file}'"
        l += "\n======================"
        return l

    def monitor():
        # Create a tqdm instance without total to act as a status bar
        with tqdm(bar_format="{desc}", dynamic_ncols=True) as status_bar:
            counter = 0
            while True:
                counter += 1
                l = get_report()
                if counter == 30:
                    logger.info(l)
                    counter = 0
                # Update tqdm status bar description
                status_bar.set_description(l)
                sleep(10)
                if finished_commits.value >= len(all_known_commits):
                    break

    threading.Thread(target=monitor, daemon=True).start()

    # with Pool(processes=len(all_known_commits)) as pool:
    # try:
    #     pool.map(process_commit, pool_args)
    # except KeyboardInterrupt:
    #     logger.error("Interrupted by user")
    #     pool.close()
    #     pool.join()
    #     # pool.terminate()

    processes = []
    for args in pool_args:
        p = Process(target=process_commit, args=(args,))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()


if __name__ == "__main__":
    args: Config = simple_parsing.parse(
        Config,
        add_config_path_arg=False,
        formatter_class=rich_argparse.ArgumentDefaultsRichHelpFormatter,
    )
    main(args)
