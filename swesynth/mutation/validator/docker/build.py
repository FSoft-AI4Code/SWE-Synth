import logging
import re
import traceback
import docker
import docker.errors

from swebench.harness.constants import (
    DOCKER_USER,
    MAP_REPO_VERSION_TO_SPECS,
)
from swebench.harness.docker_utils import cleanup_container, remove_image
from swebench.harness.docker_build import build_instance_image, BuildImageError

from swesynth.mutation.validator.docker.test_spec import TestSpec

ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def build_container(
    test_spec: TestSpec,
    client: docker.DockerClient,
    run_id: str,
    logger: logging.Logger,
    nocache: bool,
    force_rebuild: bool = False,
    num_cpus: int | None = None,
):
    """
    Builds the instance image for the given test spec and creates a container from the image.

    Args:
        test_spec (TestSpec): Test spec to build the instance image and container for
        client (docker.DockerClient): Docker client for building image + creating the container
        run_id (str): Run ID identifying process, used for the container name
        logger (logging.Logger): Logger to use for logging the build process
        nocache (bool): Whether to use the cache when building
        force_rebuild (bool): Whether to force rebuild the image even if it already exists
    """
    # Build corresponding instance image
    if force_rebuild:
        remove_image(client, test_spec.instance_image_key, "quiet")
    # build_instance_image(test_spec, client, logger, nocache)

    img_name = test_spec.remote_instance_image_name
    try:
        client.images.get(img_name)
    except docker.errors.ImageNotFound:
        try:
            client.images.pull(img_name)
        except docker.errors.NotFound as e:
            logger.error(f"Error pulling image {test_spec.remote_instance_image_name}: {e}\n Retrying with another tag...")
            if img_name.endswith(":latest"):
                img_name = img_name.replace(":latest", f":v1")
            elif img_name.endswith(":v1"):
                img_name = img_name.replace(":v1", f":latest")
            else:
                logger.warning(f"Unknown tag for image {img_name}, skipping retry...")
            try:
                client.images.pull(img_name)
            except docker.errors.NotFound as e:
                raise BuildImageError(test_spec.instance_id, str(e), logger) from e

    container = None
    try:
        # Get configurations for how container should be created
        config = MAP_REPO_VERSION_TO_SPECS[test_spec.repo][test_spec.version]
        user = DOCKER_USER if not config.get("execute_test_as_nonroot", False) else "nonroot"
        nano_cpus = config.get("nano_cpus")

        if nano_cpus is None and num_cpus is not None:
            nano_cpus = int(num_cpus * 1e9)

        # Create the container
        logger.info(f"Creating container for {test_spec.instance_id}...")
        container = client.containers.create(
            # image=test_spec.instance_image_key,
            image=img_name,
            name=test_spec.get_instance_container_name(run_id),
            user=user,
            detach=True,
            command="tail -f /dev/null",
            nano_cpus=nano_cpus,
            platform=test_spec.platform,
            mem_limit="100g",  # patch
        )
        logger.info(f"Container for {test_spec.instance_id} created: {container.id}")
        return container
    except Exception as e:
        # If an error occurs, clean up the container and raise an exception
        logger.error(f"Error creating container for {test_spec.instance_id}: {e}")
        logger.info(traceback.format_exc())
        cleanup_container(client, container, logger)
        raise BuildImageError(test_spec.instance_id, str(e), logger) from e
