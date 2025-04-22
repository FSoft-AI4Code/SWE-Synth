import requests
import tenacity
import docker
from loguru import logger


def check_local_docker_image_exist(image_name: str, tag: str = "latest") -> bool:
    """Check if the Docker image exists locally."""
    client = docker.from_env()
    try:
        client.images.get(f"{image_name}:{tag}")
        return True
    except docker.errors.ImageNotFound:
        return False
    except docker.errors.APIError as e:
        logger.warning(f"Docker API error: {e}")
        raise e


@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=30),
    stop=tenacity.stop_after_attempt(100),
    retry=tenacity.retry_if_exception_type(ValueError),
)
def check_if_remote_docker_image_exist(image_name: str, tag: str = "latest", check_local_only: bool = False) -> bool:
    """
    Check if the Docker image exists locally or remotely.

    Args:
        image_name (str): The name of the image.
        tag (str): The tag of the image.
        check_local_only (bool): Whether to check only locally using docker-py.

    Returns:
        bool: Whether the image exists.
    """
    if check_local_only:
        return check_local_docker_image_exist(image_name, tag)

    image_name = image_name.split(":")[0]
    url = f"https://hub.docker.com/v2/repositories/{image_name}/tags/{tag}/"
    response = requests.get(url)

    if response.status_code == 200:
        return True
    elif response.status_code == 404:
        return False

    logger.warning(f"Unexpected status code: {response.status_code} for url: {url}")
    raise ValueError(f"Unexpected status code: {response.status_code} for url: {url}")
