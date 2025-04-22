import io
import tarfile
import threading
import time
from pathlib import Path
from typing import Callable
from loguru import logger

from docker.models.containers import Container


def exec_run_with_timeout(
    container: Container,
    cmd: str,
    timeout: int | None = 60,
    log_func: Callable[[str], None] | None = None,
):
    """
    Run a command in a container with a timeout.

    Args:
        container (docker.Container): Container to run the command in.
        cmd (str): Command to run.
        timeout (int): Timeout in seconds.
    """
    # Local variables to store the result of executing the command
    exec_result = ""
    exec_id = None
    exception = None
    timed_out = False

    # Wrapper function to run the command
    def run_command():
        nonlocal exec_result, exec_id, exception
        try:
            exec_id = container.client.api.exec_create(container.id, cmd)["Id"]
            exec_stream = container.client.api.exec_start(exec_id, stream=True)
            for chunk in exec_stream:
                try:
                    l = chunk.decode(errors="ignore")
                except UnicodeDecodeError as e:
                    logger.error(f"UnicodeDecodeError: {e}")
                    logger.error(f"Chunk: {chunk}")
                    l = ""
                exec_result += l
                if log_func:
                    log_func(l)
        except Exception as e:
            exception = e

    # Start the command in a separate thread
    thread = threading.Thread(target=run_command)
    start_time = time.time()
    thread.start()
    thread.join(timeout)

    if exception:
        raise exception

    # If the thread is still alive, the command timed out
    if thread.is_alive():
        if exec_id is not None:
            exec_pid = container.client.api.exec_inspect(exec_id)["Pid"]
            container.exec_run(f"kill -TERM {exec_pid}", detach=True)
        timed_out = True
    end_time = time.time()
    return exec_result, timed_out, end_time - start_time


def copy_file_from_container(container: Container, docker_path: Path, host_path: Path) -> None:
    """
    Copy a file from a container to the host.
    https://stackoverflow.com/questions/39903822/docker-py-getarchive-destination-folder

    Args:
        container (docker.Container): Container to copy the file from.
        docker_path (Path): Path to the file in the container.
        host_path (Path): Path to save the file on the host.
    """
    with host_path.open("wb") as f:
        bits, stat = container.get_archive(str(docker_path))
        for chunk in bits:
            f.write(chunk)


def read_file_from_container(container: Container, docker_path: Path) -> str:
    """
    Read a file from a container. This assumes the file is a text file.

    Args:
        container (docker.Container): Container to read the file from.
        docker_path (Path): Path to the file in the container.

    Returns:
        str: Contents of the file.
    """
    bits, stat = container.get_archive(str(docker_path))
    with io.BytesIO() as f:
        for chunk in bits:
            f.write(chunk)
        output: bytes = f.getvalue()

    with tarfile.open(fileobj=io.BytesIO(output)) as tar:
        member = tar.getmembers()[0]
        f = tar.extractfile(member)
        return f.read().decode("utf-8")
