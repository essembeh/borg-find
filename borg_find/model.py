"""
borg model: repository, archive, file
"""
import hashlib
from dataclasses import dataclass
from datetime import datetime
from functools import total_ordering
from os import utime
from pathlib import Path
from typing import Dict, Tuple

from cached_property import cached_property

from .borg import borg_archive_list, borg_extract_file, borg_repo_info, borg_repo_list
from .utils import compute_fingerprint

LATEST = object()


@dataclass
class BorgRepository:
    source: str

    def borg_info(self) -> Dict:
        return borg_repo_info(self.source)

    def borg_list(self) -> Dict:
        return borg_repo_list(self.source)

    @cached_property
    def archives(self) -> Tuple:
        return tuple(sorted(BorgArchive(self, a) for a in self.borg_list()["archives"]))

    @cached_property
    def archives_map(self) -> Dict:
        return {a.name: a for a in self.archives}

    @cached_property
    def latest_archive(self):
        return self.archives[-1]

    @cached_property
    def borg_name(self):
        return self.source

    def __str__(self):
        return self.borg_name

    def __getitem__(self, name):
        if name == LATEST:
            return self.archives[-1]
        if name in self.archives_map:
            return self.archives_map[name]
        raise ValueError(f"Cannot find archive {name}")


@total_ordering
@dataclass
class BorgArchive:
    repo: BorgRepository
    description: dict

    def borg_list(self):
        return borg_archive_list(self.borg_name)

    @cached_property
    def uid(self):
        return self.description["id"]

    @cached_property
    def name(self):
        return self.description["name"]

    @cached_property
    def date(self):
        return datetime.fromisoformat(self.description["time"])

    @cached_property
    def files(self):
        return tuple(BorgFile(self, f) for f in self.borg_list())

    @cached_property
    def borg_name(self):
        return f"{self.repo.borg_name}::{self.name}"

    def __str__(self):
        return self.borg_name

    def __eq__(self, other):
        if not isinstance(other, BorgArchive):
            return NotImplemented
        return self.uid == other.uid

    def __lt__(self, other):
        if not isinstance(other, BorgArchive):
            return NotImplemented
        return self.date < other.date

    def find(self, path: str):
        for file in self.files:
            if file.path == path:
                return file


@dataclass
@total_ordering
class BorgFile:
    archive: BorgArchive
    description: dict

    def __lt__(self, other):
        if not isinstance(other, BorgFile):
            return NotImplemented
        return self.path < other.path

    @cached_property
    def mode(self) -> str:
        return self.description["mode"]

    @cached_property
    def user(self) -> str:
        return self.description["user"]

    @cached_property
    def group(self) -> str:
        return self.description["group"]

    @cached_property
    def path(self) -> str:
        return self.description["path"]

    @cached_property
    def as_path(self) -> Path:
        return Path(self.path)

    @cached_property
    def size(self) -> int:
        return int(self.description["size"])

    @cached_property
    def date(self):
        return datetime.fromisoformat(self.description["mtime"])

    @cached_property
    def md5sum(self):
        return compute_fingerprint(self.read(), hashlib.md5)

    @cached_property
    def sha1sum(self):
        return compute_fingerprint(self.read(), hashlib.sha1)

    def is_executable(self):
        return self.mode[3] == "x"

    def is_file(self) -> bool:
        return self.description["type"] == "-"

    def is_dir(self) -> bool:
        return self.description["type"] == "d"

    def is_link(self) -> bool:
        return self.description["type"] == "l"

    def __eq__(self, other):
        if not isinstance(other, BorgFile):
            return NotImplemented
        return (
            self.path == other.path
            and self.size == other.size
            and self.date == other.date
        )

    def read(self):
        return borg_extract_file(self.archive.borg_name, self.path)

    def extract(
        self, output: Path, mkdir_parents: bool = True, update_times: bool = True
    ):
        if mkdir_parents:
            output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as fp:
            fp.write(self.read())
        if update_times:
            mtime_secs = self.date.timestamp()
            utime(output, (mtime_secs, mtime_secs))
