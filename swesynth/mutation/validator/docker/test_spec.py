import hashlib
import platform
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypedDict

import docker
from docker.models.containers import Container
from swebench.harness.run_evaluation import run_instance
from swebench.harness.test_spec import (
    get_dockerfile_base,
    get_dockerfile_env,
    get_dockerfile_instance,
    # make_env_script_list,
    make_repo_script_list,
    get_environment_yml,
    get_requirements,
    replace_uninstallable_packages_requirements_txt,
)

from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS, USE_X86, SWEbenchInstance

if TYPE_CHECKING:
    from swesynth.mutation.version_control.repository import RepositorySnapshot

from swesynth.mutation.version_control.get_version import RepoVersion


@dataclass
class TestSpec:
    """
    A dataclass that represents a test specification for a single instance of SWE-bench.
    """

    instance_id: str
    repo: str
    version: str
    arch: str

    base_commit: str

    repo_script_list: list[str]
    env_script_list: list[str]

    eval_script_list: list[str] | None = None

    _remote_image_name: str | None = None

    @property
    def setup_env_script(self):
        return "\n".join(["#!/bin/bash", "set -exo pipefail"] + self.env_script_list) + "\n"

    @property
    def eval_script(self):
        assert self.eval_script_list is not None
        return "\n".join(["#!/bin/bash", "set -xo pipefail"] + self.eval_script_list) + "\n"
        # Don't exit early because we need to revert tests at the end

    @property
    def install_repo_script(self):
        return "\n".join(["#!/bin/bash", "set -exo pipefail"] + self.repo_script_list) + "\n"

    @property
    def base_image_key(self):
        return f"sweb.base.{self.arch}:latest"

    @property
    def env_image_key(self):
        """
        The key for the environment image is based on the hash of the environment script list.
        If the environment script list changes, the image will be rebuilt automatically.

        Note that old images are not automatically deleted, so consider cleaning up old images periodically.
        """
        hash_object = hashlib.sha256()
        hash_object.update(str(self.env_script_list).encode("utf-8"))
        hash_value = hash_object.hexdigest()
        val = hash_value[:22]  # 22 characters is still very likely to be unique
        return f"sweb.env.{self.arch}.{val}:latest"

    @property
    def instance_image_key(self):
        return f"sweb.eval.{self.arch}.{self.instance_id}:latest"

    @property
    def remote_instance_image_name(self):
        if self._remote_image_name is not None:
            return self._remote_image_name

        res: str | None = RepoVersion.get_instance().mapping_from_repo_base_commit_to_docker_image[self.repo][self.base_commit]
        if res is None:
            raise Exception(f"Remote docker image for {self.repo} {self.base_commit} does not exist on Docker Hub")
        return res

    def get_instance_container_name(self, run_id=None):
        if not run_id:
            return f"swesynth.{self.instance_id}"
        return f"swesynth.{self.instance_id}.{run_id}"

    @property
    def base_dockerfile(self):
        return get_dockerfile_base(self.platform, self.arch)

    @property
    def env_dockerfile(self):
        return get_dockerfile_env(self.platform, self.arch)

    @property
    def instance_dockerfile(self):
        return get_dockerfile_instance(self.platform, self.env_image_key)

    @property
    def platform(self):
        if self.arch == "x86_64":
            return "linux/x86_64"
        elif self.arch == "arm64":
            return "linux/arm64/v8"
        else:
            raise ValueError(f"Invalid architecture: {self.arch}")


def make_env_script_list(instance: SWEbenchInstance, specs: dict, env_name: str) -> list[str]:
    """
    Creates the list of commands to set up the conda environment for testing.
    This is the setup script for the environment image.

    Returns:
        list[str]: List of commands to set up the conda environment
    """
    HEREDOC_DELIMITER = "EOF_59812759871"
    reqs_commands = [
        "source /opt/miniconda3/bin/activate",
    ]
    # Create conda environment according to install instructinos
    pkgs = specs.get("packages", "")
    if pkgs == "requirements.txt":
        # Create environment
        cmd = f"conda create -n {env_name} python={specs['python']} -y"
        reqs_commands.append(cmd)

        # Install dependencies
        reqs = replace_uninstallable_packages_requirements_txt(get_requirements(instance))
        path_to_reqs = "$HOME/requirements.txt"
        reqs_commands.append(f"cat <<'{HEREDOC_DELIMITER}' > {path_to_reqs}\n{reqs}\n{HEREDOC_DELIMITER}")
        cmd = f"conda activate {env_name} && python -m pip install -r {path_to_reqs}"
        reqs_commands.append(cmd)
        reqs_commands.append(f"rm {path_to_reqs}")
    elif pkgs == "environment.yml":
        # Create environment from yml
        reqs = get_environment_yml(instance, env_name)
        path_to_reqs = "environment.yml"
        reqs_commands.append(f"cat <<'{HEREDOC_DELIMITER}' > {path_to_reqs}\n{reqs}\n{HEREDOC_DELIMITER}")
        if "no_use_env" in specs and specs["no_use_env"]:
            # `conda create` based installation
            cmd = f"conda create -c conda-forge -n {env_name} python={specs['python']} -y"
            reqs_commands.append(cmd)

            # Install dependencies
            cmd = f"conda env update -f {path_to_reqs}"
            reqs_commands.append(cmd)
        else:
            # `conda env create` based installation
            cmd = f"conda env create --file {path_to_reqs}"
            reqs_commands.append(cmd)

            if "python" in specs:  # swe-gym patching
                cmd = f"conda activate {env_name} && conda install python={specs['python']} -y"
            else:
                cmd = f"conda activate {env_name}"

            reqs_commands.append(cmd)

        # Remove environment.yml
        reqs_commands.append(f"rm {path_to_reqs}")
    else:
        # Create environment + install dependencies
        cmd = f"conda create -n {env_name} python={specs['python']} {pkgs} -y"
        reqs_commands.append(cmd)

    reqs_commands.append(f"conda activate {env_name}")

    # Install additional packages if specified
    if "pip_packages" in specs:
        pip_packages = " ".join(specs["pip_packages"])
        cmd = f"python -m pip install {pip_packages}"
        reqs_commands.append(cmd)
    return reqs_commands


def make_test_spec(instance: "RepositorySnapshot") -> TestSpec:
    instance_id = instance.instance_id
    repo = instance.origin.repo
    version = instance.version
    base_commit = instance.base_commit

    env_name = "testbed"
    repo_directory = f"/{env_name}"
    specs = MAP_REPO_VERSION_TO_SPECS[repo][version]

    repo_script_list = make_repo_script_list(specs, repo, repo_directory, base_commit, env_name)
    repo_script_list = [
        # https://stackoverflow.com/questions/59282476/error-rpc-failed-curl-92-http-2-stream-0-was-not-closed-cleanly-protocol-erro
        "git config --global http.version HTTP/1.1",
        "git config --global http.postBuffer 157286400",
    ] + repo_script_list

    # NOTE: this will fetch online data
    env_script_list = make_env_script_list(instance.to_swebench_instance(), specs, env_name)

    # delay this
    # eval_script_list = make_eval_script_list(
    #     instance, specs, env_name, repo_directory, base_commit, test_patch
    # )

    if platform.machine() in {"aarch64", "arm64"}:
        # use arm64 unless explicitly specified
        arch = "arm64" if instance_id not in USE_X86 else "x86_64"
    else:
        arch = "x86_64"

    _remote_image_name: str | None = None
    try:
        __swebench_instance_id: str = instance.mutation_info.metadata["instance_id"].lower()
        _remote_image_name = "swebench/sweb.eval.x86_64." + __swebench_instance_id.lower().replace("__", "_1776_") + ":latest"
    except:
        pass

    return TestSpec(
        instance_id=instance_id,
        base_commit=base_commit,
        repo=repo,
        env_script_list=env_script_list,
        repo_script_list=repo_script_list,
        version=version,
        arch=arch,
        _remote_image_name=_remote_image_name,
    )
