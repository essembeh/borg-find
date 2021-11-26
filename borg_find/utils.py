"""
some useful functions
"""
import hashlib
from typing import Callable

from colorama import Cursor
from colorama.ansi import clear_line


def sizeof_fmt(num: float, suffix: str = ""):
    """
    simply display a human readable size
    """
    for unit in ("", "K", "M", "G"):
        if abs(num) < 1024:
            if isinstance(num, float):
                return f"{num:0.1f}{unit}{suffix}"
            return f"{num}{unit}{suffix}"
        num /= 1024.0
    raise ValueError()


def print_temp_message(msg: str):
    """
    print a message and reset the cursor to the begining of the line
    """
    print(clear_line(), msg, Cursor.BACK(len(msg)), sep="", end="", flush=True)


def compute_fingerprint(content, func: Callable = hashlib.md5):
    """
    compute fingerprint given the algo function (sha1, md5 ...)
    """
    algo = func()
    algo.update(content)
    return algo.hexdigest()
