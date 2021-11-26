"""
borg wrapper
"""
import os
import subprocess
from dataclasses import dataclass
from json import loads
from pathlib import Path
from typing import List, Optional

EXTENSION = ".borg-cache"


@dataclass
class Borg:
    binary: str
    cache_folder: Optional[Path] = None
    lock_wait: int = 10

    def __post_init__(self):
        if self.cache_folder:
            self.cache_folder.mkdir(exist_ok=True, parents=True)

    @property
    def _env(self):
        # Avoid interactive question when accessing repository
        out = dict(os.environ)
        out["BORG_RELOCATED_REPO_ACCESS_IS_OK"] = "yes"
        return out

    @property
    def _command(self) -> List[str]:
        return [self.binary, "--lock-wait", str(self.lock_wait)]

    def _cached_file(self, uid: Optional[str]) -> Optional[Path]:
        if self.cache_folder and uid:
            return self.cache_folder / f"{uid}{EXTENSION}"

    def _read_cache(self, uid: Optional[str]) -> Optional[bytes]:
        cached = self._cached_file(uid)
        if cached and cached.is_file():
            return cached.read_bytes()

    def _write_cache(self, uid: Optional[str], data: bytes):
        cached = self._cached_file(uid)
        if cached and data:
            cached.write_bytes(data)
            return True
        return False

    def repo_info(self, repo: str) -> dict:
        command = self._command + ["info", repo, "--json"]
        process = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            check=True,
            capture_output=True,
            env=self._env,
        )
        return loads(process.stdout)

    def repo_list(self, repo: str) -> dict:
        command = self._command + ["list", str(repo), "--json"]
        process = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            check=True,
            capture_output=True,
            env=self._env,
        )
        return loads(process.stdout)

    def archive_list(self, archive: str, uid: str = None) -> List[dict]:
        data = self._read_cache(uid)
        if data is None:
            command = self._command + ["list", archive, "--json-lines"]
            process = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                check=True,
                capture_output=True,
                env=self._env,
            )
            data = process.stdout
            self._write_cache(uid, data)
        return [loads(line) for line in data.decode().splitlines()]

    def extract_file(self, archive: str, path: str) -> bytes:
        command = self._command + ["extract", "--stdout", archive, path]
        process = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            check=True,
            capture_output=True,
            env=self._env,
        )
        return process.stdout
