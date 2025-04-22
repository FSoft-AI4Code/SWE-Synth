import json
import time
import pathlib
from swesynth.typing import FilePath
from typing import Iterator
import zstandard as zstd


def tail_jsonl(file_path: FilePath, wait_forever: bool = True) -> Iterator[dict]:
    """
    An infinite generator that reads from a JSON Lines (.jsonl) file.

    Args:
        file_path (str): The path to the .jsonl file to read from.

    Yields:
        dict: The parsed JSON object from each line in the file.

    Examples:
        >>> for line in tail_jsonl('data.jsonl'):
        ...     print(line)
    """
    # Open the file in read mode
    with open(file_path, "r") as file:
        # Read existing lines
        lines = file.readlines()

        # If there are existing lines, yield them first
        for line in lines:
            if line.strip():
                yield json.loads(line)

        if not wait_forever:
            return

        # Continuously check for new lines
        while True:
            # Get the current position of the file pointer
            current_position = file.tell()
            # Read new lines
            new_lines: list[str] = file.readlines()
            new_lines = [line for line in new_lines if line.strip()]  # Remove empty lines
            if new_lines:
                for line in new_lines:
                    yield json.loads(line)
            else:
                # If no new lines, wait before checking again
                file.seek(current_position)  # Go back to the saved position
                time.sleep(1)  # Wait for a second before checking again


def read_jsonl(file_path: FilePath) -> list[dict]:
    """
    Reads a JSON Lines (.jsonl) file and returns a list of parsed JSON objects.

    Args:
        file_path (str): The path to the .jsonl file to read from.

    Returns:
        list[dict]: A list of parsed JSON objects from the file.

    Examples:
        >>> read_jsonl('data.jsonl')
        >>> read_jsonl('data.jsonl.zst')
    """
    file_path = pathlib.Path(file_path)
    if file_path.suffixes[-2:] == [".jsonl", ".zst"]:
        output = []
        with zstd.open(file_path, "rt") as file:
            for line in file:
                if line.strip():
                    output.append(json.loads(line))
        return output
    elif file_path.suffix == ".jsonl":
        return list(tail_jsonl(file_path, wait_forever=False))
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffixes}")
