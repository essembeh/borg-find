"""
borg wrapper
"""

from os import environ, getenv
import subprocess
from json import loads
from typing import List

# Avoid interactive question when accessing repository
environ["BORG_RELOCATED_REPO_ACCESS_IS_OK"] = "yes"
DEFAULT_LOCK_WAIT = 10


def borg_command(lock_wait: int = DEFAULT_LOCK_WAIT) -> List[str]:
    return [getenv("BORG_BIN", "borg"), "--lock-wait", str(lock_wait)]


def borg_repo_info(repo: str):
    command = borg_command() + ["info", str(repo), "--json"]
    process = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        check=True,
        capture_output=True,
    )
    return loads(process.stdout)


def borg_repo_list(repo: str):
    command = borg_command() + ["list", str(repo), "--json"]
    process = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        check=True,
        capture_output=True,
    )
    return loads(process.stdout)


def borg_archive_list(archive: str):
    command = borg_command() + ["list", str(archive), "--json-lines"]
    process = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        check=True,
        capture_output=True,
    )
    return tuple(loads(line) for line in process.stdout.decode().splitlines())


def borg_extract_file(archive: str, path: str):
    command = borg_command() + ["extract", "--stdout", str(archive), str(path)]
    process = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        check=True,
        capture_output=True,
    )
    return process.stdout
