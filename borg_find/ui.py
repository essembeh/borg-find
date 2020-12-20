"""
some utils for fancy stdout
"""
from pathlib import Path
import shlex
from subprocess import CompletedProcess
from colorama import Style, Fore
from .model import BorgArchive, BorgFile, BorgRepository


def label(item):
    """
    return a str with colors of the given object
    """
    if isinstance(item, Path):
        if not item.exists():
            return str(item)
        if item.is_dir():
            return f"{Fore.BLUE}{Style.BRIGHT}{item}/{Style.RESET_ALL}"
        return f"{Style.BRIGHT}{Fore.BLUE}{item.parent}/{Fore.MAGENTA}{item.name}{Style.RESET_ALL}"
    if isinstance(item, BorgFile):
        if item.is_dir():
            return f"{Fore.BLUE}{Style.BRIGHT}{item.as_path}/{Style.RESET_ALL}"
        color = Fore.MAGENTA
        if item.is_link():
            color = Fore.CYAN
        elif item.is_executable():
            color = Fore.GREEN
        return f"{Style.BRIGHT}{Fore.BLUE}{item.as_path.parent}/{color}{item.as_path.name}{Style.RESET_ALL}"
    if isinstance(item, BorgRepository):
        return f"{Fore.CYAN}{item.source}{Style.RESET_ALL}"
    if isinstance(item, BorgArchive):
        return (
            f"{label(item.repo)}::{Style.BRIGHT}{Fore.CYAN}{item.name}{Style.RESET_ALL}"
        )
    if isinstance(item, CompletedProcess):
        cmd = item.args
        if isinstance(cmd, list):
            cmd = " ".join(map(shlex.quote, cmd))
        return f"{Fore.YELLOW}{cmd}{Fore.RESET}"


def dumpproc(stdout, stderr=None):
    """
    print stdout/stderr of a process
    """
    if stdout is not None and len(stdout) > 0:
        print(" ", "=" * 20, "BEGIN STDOUT", "=" * 20)
        for line in stdout.decode().splitlines():
            print(" ", f"{Style.DIM}{line}{Style.RESET_ALL}")
        print(" ", "=" * 20, "END STDOUT", "=" * 20)
    if stderr is not None and len(stderr) > 0:
        print(" ", "=" * 20, "BEGIN STDERR", "=" * 20)
        for line in stderr.decode().splitlines():
            print(" ", f"{Fore.RED}{line}{Style.RESET_ALL}")
        print(" ", "=" * 20, "END STDERR", "=" * 20)
