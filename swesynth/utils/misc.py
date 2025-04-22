import subprocess
import os


def colordiff(patch: str) -> str:
    assert os.path.exists("/usr/bin/colordiff"), "colordiff is not installed, please install it by running 'sudo apt-get install colordiff'"
    return subprocess.run(["/usr/bin/colordiff"], input=patch, text=True, capture_output=True, check=True).stdout
