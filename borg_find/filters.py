from argparse import Namespace
from dataclasses import dataclass
from functools import cached_property
from typing import Optional

from .model import BorgArchive, BorgFile


def find_previous_archive(archive: BorgArchive) -> Optional[BorgArchive]:
    """
    retrieve previous archive
    """
    out = None
    for other in archive.repo.archives:
        if other.uid != archive.uid and other.date < archive.date:
            if out is None or other.date > out.date:
                out = other
    return out


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
            # also check is file is new or modified
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
