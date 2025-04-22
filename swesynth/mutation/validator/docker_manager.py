import logging
from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path
from typing import TYPE_CHECKING

import docker
import zstandard as zstd
from docker.models.containers import Container
from loguru import logger
from swebench.harness.constants import (
    BASE_IMAGE_BUILD_DIR,
    ENV_IMAGE_BUILD_DIR,
    INSTANCE_IMAGE_BUILD_DIR,
    RUN_EVALUATION_LOG_DIR,
    MAP_REPO_VERSION_TO_SPECS,
)
from swebench.harness.docker_build import build_image, setup_logger
from swebench.harness.docker_utils import cleanup_container, copy_to_container
from swebench.harness.test_spec import *
from swebench.harness.utils import get_test_directives

from .docker.communication import exec_run_with_timeout
from .docker.git_in_docker import GitInDocker
from .docker.test_spec import TestSpec, make_test_spec
from .docker.test_log_parser import transform_django_test_directives
from .docker.multiprocessing_utils import docker_max_semaphore, test_log_stream_dict
from .docker.build import build_container
import multiprocessing

if TYPE_CHECKING:
    from ..version_control.repository import RepositorySnapshot

build_image_lock = multiprocessing.Lock()


@dataclass
class DockerManager:
    original_snapshot: "RepositorySnapshot"
    client: docker.DockerClient = field(default_factory=docker.from_env)
    test_spec: TestSpec = field(init=False)
    log_dir: Path = field(init=False)
    base_commit_log_dir: Path = field(init=False)

    container: Container | None = field(init=False, default=None)
    remove_image_after_container_exit: bool = False

    __last_parent_logger_id: int | None = field(init=False, default=None)
    __last_mutant_logger_id: int | None = field(init=False, default=None)

    def __post_init__(self):
        self.test_spec = make_test_spec(self.original_snapshot)
        self.set_log_dir(self.original_snapshot)

    def set_log_dir(self, mutated_repo: "RepositorySnapshot | None" = None) -> None:
        if mutated_repo is None:
            mutated_repo = self.original_snapshot
        self.log_dir = mutated_repo.relative_log_dir
        self.log_dir = self.log_dir.resolve()
        self.base_commit_log_dir = self.log_dir.parent
        self.log_dir.mkdir(parents=True, exist_ok=True)

        if self.__last_parent_logger_id is not None:
            logger.remove(self.__last_parent_logger_id)

        self.__last_parent_logger_id = logger.add(self.base_commit_log_dir / "tester.log", level="INFO", enqueue=True)

        if self.__last_mutant_logger_id is not None:
            logger.remove(self.__last_mutant_logger_id)

        self.__last_mutant_logger_id = logger.add(self.log_dir / "mutant.log", level="INFO")

    def build_docker_image(self, remove_image_after_container_exit: bool = False) -> None:
        """
        Exceptions:
            swebench.harness.docker_build.BuildImageError
        """
        self.remove_image_after_container_exit = remove_image_after_container_exit
        # build base image
        with build_image_lock:
            build_image(
                image_name=self.test_spec.base_image_key,
                setup_scripts={},
                dockerfile=self.test_spec.base_dockerfile,
                platform=self.test_spec.platform,
                client=self.client,
                build_dir=BASE_IMAGE_BUILD_DIR / self.test_spec.base_image_key.replace(":", "__"),
            )

            # build env image for repo-version-specific
            build_image(
                image_name=self.test_spec.env_image_key,
                setup_scripts={"setup_env.sh": self.test_spec.setup_env_script},
                dockerfile=self.test_spec.env_dockerfile,
                platform=self.test_spec.platform,
                client=self.client,
                build_dir=ENV_IMAGE_BUILD_DIR / self.test_spec.env_image_key.replace(":", "__"),
            )

    def create_docker_container(
        self,
        rm_image: bool = False,
        run_id: str | None = None,
        force_rebuild: bool = False,
    ) -> Container:

        _logger: logging.Logger = self.build_logger(self.test_spec)

        container: Container = build_container(
            test_spec=self.test_spec,
            client=self.client,
            run_id=f"swesynth_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}",
            logger=_logger,
            nocache=rm_image,
            force_rebuild=force_rebuild,
            num_cpus=int(os.cpu_count() // 10 * 6),
        )

        # docker run -d --tmpfs /run:rw,noexec,nosuid,size=65536k my_image
        # TODO: mount tmpfs to /testbed

        container.start()
        logger.info(f"Container for {self.test_spec.instance_id} started: {container.id}")

        self.container = container

        return container

    def using_git_with(self, change: str) -> GitInDocker:
        return GitInDocker(changes=change, docker_manager=self)

    def build_logger(self, test_spec: TestSpec) -> logging.Logger:
        # log_dir = RUN_EVALUATION_LOG_DIR / test_spec.instance_id
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Link the image build dir in the log dir
        build_dir = INSTANCE_IMAGE_BUILD_DIR / test_spec.instance_image_key.replace(":", "__")
        image_build_link = self.log_dir / "image_build_dir"
        if not image_build_link.exists():
            try:
                # link the image build dir in the log dir
                image_build_link.symlink_to(build_dir.absolute(), target_is_directory=True)
            except:
                # some error, idk why
                pass
        logger = setup_logger(test_spec.instance_id, self.log_dir / "build.log")

        return logger

    def cleanup(self) -> None:
        logger.info(f"Cleaning up container for {self.container.id}...")
        cleanup_container(self.client, self.container, logger=None)
        self.container = None

        if self.__last_parent_logger_id is not None:
            logger.remove(self.__last_parent_logger_id)

        if self.remove_image_after_container_exit:
            logger.info(f"Removing image {self.test_spec.instance_image_key}...")
            try:
                self.client.images.remove(self.test_spec.instance_image_key)
            except docker.errors.ImageNotFound:
                logger.warning(f"Image {self.test_spec.instance_image_key} not found.")

    def exec(
        self,
        command: str,
        name: str = "eval.sh",
        timeout: int | None = 7200,  # 2 hours
    ) -> str:
        """
        Execute command in container, return output
        """
        assert name.endswith(".sh"), "Name must end with .sh"
        with docker_max_semaphore:
            # Get git diff before running eval script
            git_diff_output_before = self.container.exec_run("git diff", workdir="/testbed").output.decode("utf-8").strip()

            eval_file = Path(self.log_dir / f"{name}")
            eval_file.write_text(command)

            test_output_path = self.log_dir / f"test_output_{name.replace('.sh', '')}.log.zst"
            stream_path = test_output_path.with_suffix(".stream")

            logger.info(f"Test output for {self.test_spec.instance_id} is streaming to {stream_path} ...")
            test_log_stream_dict[self.test_spec.instance_id] = stream_path

            with stream_path.open("a") as f:

                def _log(msg: str, end="\n") -> None:
                    print(msg, file=f, end=end, flush=True)

                _log(f"Git diff before:\n{git_diff_output_before}")
                _log(f"Eval script for {self.test_spec.instance_id} written to {eval_file}; copying to container...")
                copy_to_container(self.container, eval_file, Path(f"/{name}"))

                # Run eval script, write output to logs
                test_output, timed_out, total_runtime = exec_run_with_timeout(
                    self.container,
                    f"/bin/bash /{name}",
                    timeout,
                    log_func=lambda msg: _log(msg, end=""),
                )
                _log(f"Test runtime: {total_runtime:_.2f} seconds")

                if timed_out:
                    _log(f"\n\nTimeout error: {timeout} seconds exceeded.")
                    test_log_stream_dict.pop(self.test_spec.instance_id)
                    raise Exception(
                        f"Test timed out after {timeout} seconds for {self.test_spec.instance_id}.",
                    )

            if test_output_path.exists():
                logger.warning(f"Test output for {self.test_spec.instance_id} already exists: {test_output_path}")
                test_output_path = test_output_path.with_name(f"{test_output_path.stem}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log.zst")

            # !zstdcat test_output.log.zst
            test_output_path.write_bytes(zstd.compress(test_output.encode()))

            logger.info(f"Test output for {self.test_spec.instance_id} has been written to {test_output_path}")

            stream_path.unlink()
            test_log_stream_dict.pop(self.test_spec.instance_id)

            return test_output

    def get_test_command(self, mutated_repo: "RepositorySnapshot", test_subset: set[str] = set()) -> str:
        tests_to_run: set[str] = test_subset
        if mutated_repo.repo == "django/django":
            if os.environ.get("USE_SWEBENCH_DJANGO_TEST_DIRECTIVES", "false").lower() == "true":
                logger.warning("Using SWEBench test directives for Django tests")
                tests_to_run = set(get_test_directives(mutated_repo.to_swebench_instance()))
            else:
                # always test entire django repo by default
                tests_to_run = set()
                # might use this in the future
                # tests_to_run = transform_django_test_directives(tests_to_run)
        elif mutated_repo.repo == "sympy/sympy":
            if os.environ.get("USE_SWEBENCH_SYMPY_TEST_DIRECTIVES", "false").lower() == "true":
                logger.warning("Using SWEBench test directives for SymPy tests")
                tests_to_run = set(get_test_directives(mutated_repo.to_swebench_instance()))
            else:
                # always test entire sympy repo by default
                tests_to_run = set()
        else:
            tests_to_run = {test.split("[")[0] for test in tests_to_run}

        env_name = "testbed"
        repo_directory = f"/{env_name}"

        specs = MAP_REPO_VERSION_TO_SPECS[mutated_repo.repo][mutated_repo.version]

        HEREDOC_DELIMITER = "EOF_114329324912"
        # Reset test files to the state they should be in before the patch.
        test_command = " ".join(
            [
                specs["test_cmd"].replace("pytest", "pytest --continue-on-collection-errors --tb=long -vvv").replace("--tb=no", "--tb=long"),
                # NOTE: this is to only test the test that related to the patch, which is not applicable for us
                *tests_to_run,
            ]
        )
        logger.info(f"Running test command for {mutated_repo.instance_id}: {test_command[:50] if len(test_command) > 50 else test_command}")
        eval_commands: list[str] = [
            f"source /opt/miniconda3/bin/activate",
            f"conda activate {env_name}",
            f"cd {repo_directory}",
        ]
        if "eval_commands" in specs:
            eval_commands += specs["eval_commands"]
        eval_commands += [
            f"git config --global --add safe.directory {repo_directory}",  # for nonroot user
            f"cd {repo_directory}",
            # This is just informational, so we have a record
            f"git status",
            f"git show",
            f"git diff {mutated_repo.base_commit}",
            "source /opt/miniconda3/bin/activate",
            f"conda activate {env_name}",
        ]
        if "install" in specs:
            eval_commands.append(specs["install"])

        eval_commands.append(test_command),

        command = "\n".join(["#!/bin/bash", "set -xo pipefail"] + eval_commands) + "\n"
        return command
