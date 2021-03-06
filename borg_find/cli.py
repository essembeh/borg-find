"""
entry point
"""
import concurrent
import os
import re
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from datetime import datetime
from os import getenv
from pathlib import Path
from traceback import print_stack

from cached_property import cached_property
from colorama import Fore, Style

from . import __version__
from .model import BorgArchive, BorgFile, BorgRepository
from .ui import dumpproc, label
from .utils import print_temp_message, sizeof_fmt


@dataclass
class ArchiveFilter:
    args: Namespace

    def __call__(self, archive: BorgArchive):
        if self.args.after and self.args.after > archive.date:
            return False
        if self.args.before and self.args.before < archive.date:
            return False
        if self.args.prefix and not archive.name.startswith(self.args.prefix):
            return False
        return True


@dataclass
class FileFilter:
    args: Namespace
    archive: BorgArchive

    @cached_property
    def previous_archive(self):
        return find_previous_archive(self.archive)

    def __call__(self, file: BorgFile):
        out = False
        if self.args.names is None and self.args.patterns is None:
            out = True
        if not out and self.args.names:
            for name in self.args.names:
                if name.lower() in file.path.lower():
                    out = True
        if not out and self.args.patterns:
            for pattern in self.args.patterns:
                if pattern.search(file.path):
                    out = True
        if (
            out
            and (self.args.new or self.args.modified)
            and self.previous_archive is not None
        ):
            # also check is file is noew or modified
            out = False
            previous_file = self.previous_archive.find(file.path)
            if self.args.new and previous_file is None:
                out = True

            if (
                not out
                and self.args.modified
                and previous_file is not None
                and file != previous_file
            ):
                out = True
        return out


def find_previous_archive(archive: BorgArchive) -> BorgArchive:
    """
    retrieve previous archive
    """
    out = None
    for a in archive.repo.archives:
        if a.uid != archive.uid and a.date < archive.date:
            if out is None or a.date > out.date:
                out = a
    return out


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
    kwargs = {}
    if getenv("BORG_REPO"):
        kwargs["nargs"] = "?"
    parser.add_argument(
        "repository",
        default=getenv("BORG_REPO"),
        help="borg repository, mandatory is BORG_REPO is not set",
        **kwargs,
    )

    # Parse command line
    args = parser.parse_args()
    try:
        repo = BorgRepository(args.repository)
        archives = list(filter(ArchiveFilter(args), repo.archives))
        if args.reverse:
            archives = reversed(archives)
        if args.last:
            archives = archives[args.last * -1 :]
        elif args.first:
            archives = archives[0 : args.first]

        if args.jobs > 0:
            print_temp_message(
                f"Reading {len(archives)} archive(s) from {label(repo)} with {args.jobs} thread(s) ..."
            )
            # preload archives
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=args.jobs
            ) as executor:

                def load(a: BorgArchive):
                    a.files
                    return a

                count = 1
                for job in concurrent.futures.as_completed(
                    [executor.submit(load, a) for a in archives]
                ):
                    archive = job.result()
                    print_temp_message(
                        f"[{count}/{len(archives)}] Reading archive {label(archive)} ..."
                    )
                    count += 1

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
                            user_process = (
                                subprocess.run(  # pylint: disable=subprocess-run-check
                                    args.exec,
                                    shell=True,
                                    input=file.read(),
                                    capture_output=True,
                                )
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
    except BaseException as exception:  # pylint: disable=broad-except
        print(f"{Fore.RED}{exception.__class__.__name__}: {exception}")
        if getenv("DEBUG"):
            print_stack(exception)
        print(Style.RESET_ALL, end="")
        sys.exit(1)
