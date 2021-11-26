"""
entry point
"""
import os
import re
import subprocess
import sys
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from os import getenv
from pathlib import Path

from colorama import Fore, Style

from borg_find.borg import Borg

from . import __version__
from .filters import ArchiveFilter, FileFilter
from .model import BorgRepository
from .ui import dumpproc, label
from .utils import print_temp_message, sizeof_fmt

DEFAULT_CACHE_FOLDER = Path.home() / ".cache" / "borg-find"


def run():
    parser = ArgumentParser("borg-find")
    parser.add_argument("--version", action="version", version=f"version {__version__}")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print more details",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=os.cpu_count() or 1,
        help="number of parallel threads to read archives",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help=f"disable caching archive content (default folder: {DEFAULT_CACHE_FOLDER})",
    )
    agroup = parser.add_argument_group("archive selection")
    agroup.add_argument(
        "-A",
        "--after",
        metavar="YYYY-MM-DD",
        type=datetime.fromisoformat,
        help="only consider archive created after given date",
    )
    agroup.add_argument(
        "-B",
        "--before",
        metavar="YYYY-MM-DD",
        type=datetime.fromisoformat,
        help="only consider archive created before given date",
    )
    agroup.add_argument(
        "-P",
        "--prefix",
        help="only consider archive names starting with this prefix.",
    )
    agroup.add_argument(
        "-R",
        "--reverse",
        action="store_true",
        help="reverse the archives order, default is oldest first",
    )
    agroup1 = agroup.add_mutually_exclusive_group()
    agroup1.add_argument(
        "-F",
        "--first",
        metavar="N",
        type=int,
        help="consider first N archives after other filters were applied",
    )
    agroup1.add_argument(
        "-L",
        "--last",
        metavar="N",
        type=int,
        help="consider last N archives after other filters were applied",
    )

    fgroup = parser.add_argument_group("file selection")
    fgroup.add_argument(
        "-n",
        "--name",
        metavar="MOTIF",
        dest="names",
        action="append",
        help="select files with path containing MOTIF (ignore case)",
    )
    fgroup.add_argument(
        "-r",
        "--regex",
        metavar="PATTERN",
        dest="patterns",
        action="append",
        type=re.compile,
        help="select files with path matching PATTERN",
    )
    fgroup.add_argument(
        "--new",
        action="store_true",
        help="select only *new* files, which were not present in previous archive",
    )
    fgroup.add_argument(
        "--modified",
        action="store_true",
        help="select only modified files, which were different in previous archive",
    )

    xgroup = parser.add_mutually_exclusive_group()
    xgroup.add_argument(
        "-x", "--exec", help="execute the command on every matching file"
    )
    xgroup.add_argument("--md5", action="store_true", help="also print file md5sum")
    xgroup.add_argument("--sha1", action="store_true", help="also print file sha1sum")
    xgroup.add_argument(
        "-o",
        "--output",
        metavar="FOLDER",
        type=Path,
        help="extract matching files to this folder",
    )
    parser.add_argument(
        "repository",
        default=getenv("BORG_REPO"),
        help="borg repository, mandatory is BORG_REPO is not set",
        **({"nargs": "?"} if getenv("BORG_REPO") else {}),
    )

    # Parse command line
    args = parser.parse_args()
    try:
        borg = Borg(
            getenv("BORG_BIN", "borg"),
            cache_folder=DEFAULT_CACHE_FOLDER,
        )
        repo = BorgRepository(borg, args.repository)
        archives = list(filter(ArchiveFilter(args), repo.archives))
        if args.reverse:
            archives = list(reversed(archives))
        if args.last:
            archives = archives[args.last * -1 :]
        elif args.first:
            archives = archives[0 : args.first]

        if args.jobs > 0:
            print_temp_message(
                f"Reading {len(archives)} archive(s) from {label(repo)} with {args.jobs} thread(s) ..."
            )
            # preload archives
            with ThreadPoolExecutor(max_workers=args.jobs) as executor:
                jobs = {executor.submit(lambda a: a.files, a): a for a in archives}
                for index, job in enumerate(as_completed(jobs.keys())):
                    archive = jobs[job]
                    print_temp_message(
                        f"[{index+1}/{len(jobs)}] Reading archive {label(archive)} ..."
                    )

        # process archives
        for archive in archives:
            matching_files = sorted(filter(FileFilter(args, archive), archive.files))
            if len(matching_files) == 0:
                print(f"Skip {label(archive)}, no matching file")
            else:
                print(
                    f"Inspect {label(archive)}, {len(matching_files)} matching file(s)"
                )

                if args.exec:
                    # Exec mode
                    for file in matching_files:
                        if file.is_dir():
                            print(
                                f"[{Fore.CYAN}SKIP{Fore.RESET}]",
                                label(file),
                                "is a directory",
                            )
                        else:
                            user_process = subprocess.run(
                                args.exec,
                                shell=True,
                                input=file.read(),
                                capture_output=True,
                            )
                            status = (
                                f"{Fore.GREEN}OK{Fore.RESET}"
                                if user_process.returncode == 0
                                else f"{Fore.RED}ERROR{Fore.RESET}"
                            )
                            print(
                                f"[{status}]",
                                label(user_process),
                                "on",
                                label(file),
                                "returned",
                                user_process.returncode,
                            )
                            if args.verbose:
                                dumpproc(user_process.stdout, user_process.stderr)
                elif args.output:
                    # Extract
                    count = 1
                    for file in matching_files:
                        if file.is_file():
                            target = args.output / archive.name / file.as_path
                            file.extract(target)
                            print(
                                " ",
                                f"[{count}/{len(matching_files)}]",
                                f"Extracted {label(file)} to {label(target)}",
                                f"({sizeof_fmt(file.size, 'B')})",
                            )
                        else:
                            print(
                                " ",
                                f"[{count}/{len(matching_files)}]",
                                f"Skip {label(file)}, not a regular file",
                            )
                        count += 1
                else:
                    # List mode
                    size = 0
                    for file in matching_files:
                        size += file.size
                        suffix = ""
                        if args.md5:
                            suffix = f"(md5:{Fore.YELLOW}{file.md5sum}{Fore.RESET})"
                        elif args.sha1:
                            suffix = f"(sha1:{Fore.YELLOW}{file.sha1sum}{Fore.RESET})"
                        if args.verbose:
                            user_group = f"{file.user}:{file.group}"
                            print(
                                " ",
                                file.mode,
                                f"{user_group:<12}",
                                f"{sizeof_fmt(file.size):>6}",
                                file.date.isoformat(sep=" ", timespec="seconds"),
                                label(file),
                                suffix,
                            )
                        else:
                            print(
                                " ",
                                label(file),
                                suffix,
                            )

                    print(f"  {len(matching_files)} file(s), {sizeof_fmt(size)}")
                    print("")

    except KeyboardInterrupt:
        pass
    except BaseException as e:
        print(f"{Fore.RED}{e.__class__.__name__}: {e}{Style.RESET_ALL}")
        if getenv("DEBUG"):
            raise e
        sys.exit(1)
