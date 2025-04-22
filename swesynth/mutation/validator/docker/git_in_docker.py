from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from docker.models.containers import Container
from loguru import logger
from swebench.harness.constants import APPLY_PATCH_FAIL, APPLY_PATCH_PASS
from swebench.harness.docker_utils import copy_to_container
from swebench.harness.test_spec import *

if TYPE_CHECKING:
    from ..docker_manager import DockerManager


@dataclass
class GitInDocker:
    """
    Preserve all `git status` on enter and restore on exit
    """

    changes: str
    docker_manager: "DockerManager"

    current_diff: str | None = field(init=False, default=None)

    @property
    def container(self) -> Container:
        return self.docker_manager.container

    @property
    def instance_id(self) -> str:
        return self.docker_manager.test_spec.instance_id

    def __enter__(self) -> "GitInDocker":
        self.current_diff = self.get_current_container_diff()
        self.apply_patch_to_container(self.changes)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.reset_git(to=self.current_diff)

    def get_current_container_diff(self) -> str:
        return self.container.exec_run("git diff", workdir="/testbed").output.decode("utf-8").strip()

    def reset_git(self, to: str = "") -> str:
        HEREDOC_DELIMITER = "EOF_114329324912"
        assert self.container is not None, "Container is not initialized"
        cmd_output: str = self.container.exec_run("git reset --hard HEAD", workdir="/testbed").output.decode("utf-8").strip()
        # cmd_output += "\n" + (
        #     self.container.exec_run("git clean -fdxq", workdir="/testbed")
        #     .output.decode("utf-8")
        #     .strip()
        # )
        if to:
            cmd_output += "\n" + (self.docker_manager.exec(f"git apply -v - <<'{HEREDOC_DELIMITER}'\n{to}\n{HEREDOC_DELIMITER}", name="reset.sh"))
        logger.info(f"Reset git: {cmd_output}")
        return cmd_output

    def apply_patch_to_container(self, diff: str) -> None:
        # Copy model prediction as patch file to container
        assert diff
        patch_file = Path(self.docker_manager.log_dir / "patch.diff")
        patch_file.write_text(diff)
        logger.info(f"Intermediate patch for {self.instance_id} written to {patch_file}, now applying to container...")
        copy_to_container(self.container, patch_file, Path("/tmp/patch.diff"))

        # Attempt to apply patch to container
        val = self.container.exec_run(
            "git apply --allow-empty -v /tmp/patch.diff",
            workdir="/testbed",
            user="root",
        )
        if val.exit_code != 0:
            logger.info(f"Failed to apply patch to container, trying again...")

            # try "patch --batch --fuzz=5 -p1 -i {patch_path}" to try again
            val = self.container.exec_run(
                "patch --batch --fuzz=5 -p1 -i /tmp/patch.diff",
                workdir="/testbed",
                user="root",
            )
            if val.exit_code != 0:
                logger.info(f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}")
                raise Exception(
                    # self.instance_id,
                    f"Apply patch failed for {self.instance_id}:\n"
                    f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}"
                )
            else:
                logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")
        else:
            logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")
