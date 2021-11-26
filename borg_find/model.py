"""
borg model: repository, archive, file
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property, total_ordering
from os import utime
from pathlib import Path
from typing import Dict, List, Optional

from .borg import Borg
from .utils import compute_fingerprint

LATEST = object()


@dataclass
class BorgRepository:
    borg: Borg
    source: str

    @property
    def borg_info(self) -> dict:
        return self.borg.repo_info(self.source)

    @property
    def borg_list(self) -> dict:
        return self.borg.repo_list(self.source)

    @cached_property
    def archives(self) -> List[BorgArchive]:
        return sorted(BorgArchive(self, a) for a in self.borg_list["archives"])

    @cached_property
    def archives_map(self) -> Dict[str, BorgArchive]:
        return {a.name: a for a in self.archives}

    @cached_property
    def latest_archive(self) -> BorgArchive:
        return self.archives[-1]

    @cached_property
    def borg_name(self) -> str:
        return self.source

    def __str__(self):
        return self.borg_name

    def __getitem__(self, name):
        if name == LATEST:
            return self.archives[-1]
        if name in self.archives_map:
            return self.archives_map[name]
        raise KeyError(f"Cannot find archive {name}")


@total_ordering
@dataclass
class BorgArchive:
    repo: BorgRepository
    description: dict

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

    @property
    def borg(self) -> Borg:
        return self.repo.borg

    @property
    def borg_list(self):
        return self.borg.archive_list(self.borg_name, self.uid)

    @cached_property
    def uid(self) -> str:
        return self.description["id"]

    @cached_property
    def name(self) -> str:
        return self.description["name"]

    @cached_property
    def date(self) -> datetime:
        return datetime.fromisoformat(self.description["time"])

    @cached_property
    def files(self) -> List[BorgFile]:
        return [BorgFile(self, f) for f in self.borg_list]

    @cached_property
    def borg_name(self) -> str:
        return f"{self.repo.borg_name}::{self.name}"

    def find(self, path: str) -> Optional[BorgFile]:
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

    def __eq__(self, other):
        if not isinstance(other, BorgFile):
            return NotImplemented
        return (
            self.path == other.path
            and self.size == other.size
            and self.date == other.date
        )

    @property
    def borg(self) -> Borg:
        return self.archive.borg

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
    def date(self) -> datetime:
        return datetime.fromisoformat(self.description["mtime"])

    @cached_property
    def md5sum(self) -> str:
        return compute_fingerprint(self.read(), hashlib.md5)

    @cached_property
    def sha1sum(self) -> str:
        return compute_fingerprint(self.read(), hashlib.sha1)

    def is_executable(self) -> bool:
        return self.mode[3] == "x"

    def is_file(self) -> bool:
        return self.description["type"] == "-"

    def is_dir(self) -> bool:
        return self.description["type"] == "d"

    def is_link(self) -> bool:
        return self.description["type"] == "l"

    def read(self) -> bytes:
        return self.borg.extract_file(self.archive.borg_name, self.path)

    def extract(
        self, output: Path, mkdir_parents: bool = True, update_times: bool = True
    ):
        if mkdir_parents:
            output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(self.read())
        if update_times:
            mtime_secs = self.date.timestamp()
            utime(output, (mtime_secs, mtime_secs))
