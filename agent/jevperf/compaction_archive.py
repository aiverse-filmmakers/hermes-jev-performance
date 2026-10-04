"""Private, bounded output drawer. Live recovery references are never auto-deleted."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

from .store import PLUGIN_DATA_DIR, current_hermes_home


REFERENCE_RE = re.compile(r"[a-f0-9]{32}/[a-f0-9]{32}/[a-f0-9]{32}")
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_DRAWER_BYTES = 512 * 1024 * 1024


def archive_root() -> Path:
    return current_hermes_home() / "plugin-data" / PLUGIN_DATA_DIR / "compaction-archive"


class OutputArchive:
    def __init__(self, root: Path | None = None, *, max_bytes: int = MAX_DRAWER_BYTES):
        self.root = Path(root) if root is not None else archive_root()
        self.max_bytes = max_bytes

    @staticmethod
    def owns(reference: str, session_id: str) -> bool:
        return (bool(session_id) and isinstance(reference, str) and
                REFERENCE_RE.fullmatch(reference) is not None and
                reference.split("/", 1)[0] == hashlib.sha256(session_id.encode()).hexdigest()[:32])

    @staticmethod
    def _sync_directory(folder: Path) -> None:
        fd = os.open(folder, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def reference(self, session_id: str) -> str:
        owner = hashlib.sha256(session_id.encode()).hexdigest()[:32]
        return f"{owner}/{uuid.uuid4().hex}/{uuid.uuid4().hex}"

    def _directory(self, relative: str = "", *, create: bool = False) -> Path:
        # Check the full path rather than resolving a symlink into another profile.
        path = self.root.absolute()
        parts = list(reversed(path.parents)) + [path]
        if relative:
            for part in relative.split("/"):
                path = path / part
                parts.append(path)
        for part in parts:
            if create:
                try:
                    part.mkdir(mode=0o700)
                except FileExistsError:
                    pass
                else:
                    # Persist each newly linked ancestor, not just the final leaf.
                    self._sync_directory(part.parent)
            info = part.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("unsafe_archive_directory")
            if part == self.root.absolute() or self.root.absolute() in part.parents:
                if info.st_uid != os.getuid() or info.st_mode & 0o077:
                    raise ValueError("unsafe_archive_permissions")
        return path

    def write_batch(self, entries: list[tuple[str, str]], *, should_abort=None) -> None:
        import fcntl

        # Validate the entire batch before creating any content.
        prepared = []
        folders = set()
        for reference, text in entries:
            if not isinstance(reference, str) or REFERENCE_RE.fullmatch(reference) is None:
                raise ValueError("invalid_reference")
            raw = text.encode("utf-8")
            if len(raw) > MAX_ARCHIVE_BYTES:
                raise ValueError("archive_too_large")
            directory, name = reference.rsplit("/", 1)
            if directory in folders:
                raise ValueError("duplicate_archive_directory")
            folders.add(directory)
            prepared.append((reference, raw, directory, name, len(text)))
        self._directory(create=True)
        fd = os.open(self.root / "LOCK", os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "rb") as lock:
            info = os.fstat(lock.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError("unsafe_archive_lock")
            fcntl.flock(lock, fcntl.LOCK_EX)
            used = 0
            for folder, dirs, files in os.walk(self.root, followlinks=False):
                self._directory(str(Path(folder).relative_to(self.root)) if Path(folder) != self.root else "")
                if any((Path(folder) / d).is_symlink() for d in dirs):
                    raise ValueError("unsafe_archive_directory")
                for name in files:
                    info = (Path(folder) / name).lstat()
                    if not stat.S_ISREG(info.st_mode):
                        raise ValueError("unsafe_archive_file")
                    used += info.st_size
            # Budget includes conservative index overhead. Fail open on capacity;
            # never delete a still-recoverable output to make room.
            if used + sum(len(p[1]) + 1024 for p in prepared) > self.max_bytes:
                raise ValueError("archive_capacity")
            created = []
            try:
                for reference, raw, directory, name, characters in prepared:
                    if should_abort is not None and should_abort():
                        raise InterruptedError("stale_compaction")
                    owner = self._directory(directory.split("/")[0], create=True)
                    folder = owner / directory.split("/")[1]
                    folder.mkdir(mode=0o700)  # Refuse existing archives without touching them.
                    created.append(folder)
                    self._sync_directory(owner)
                    path = folder / (name + ".txt")
                    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                    fd = os.open(path, flags, 0o600)
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(stream.fileno())
                    self._write_index(folder, {"reference": reference, "characters": characters,
                                              "sha256": hashlib.sha256(raw).hexdigest()})
                if should_abort is not None and should_abort():
                    raise InterruptedError("stale_compaction")
            except BaseException:
                # Ordinary partial-batch failures cannot leave raw orphan output.
                for folder in reversed(created):
                    for path in folder.iterdir():
                        path.unlink()
                    folder.rmdir()
                    self._sync_directory(folder.parent)
                raise

    @staticmethod
    def _write_index(folder: Path, record: dict) -> None:
        fd = os.open(folder / "INDEX.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(record, stream)
            stream.flush()
            os.fsync(stream.fileno())
        OutputArchive._sync_directory(folder)

    def recover(self, reference: str, *, offset: int = 0, limit: int = 20000) -> dict:
        if not isinstance(reference, str) or REFERENCE_RE.fullmatch(reference) is None:
            raise ValueError("invalid_reference")
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 20000:
            raise ValueError("invalid_range")
        directory, name = reference.rsplit("/", 1)
        folder = self._directory(directory)
        def read_file(path: Path) -> bytes:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or info.st_mode & 0o077 or info.st_size > MAX_ARCHIVE_BYTES):
                    raise ValueError("unsafe_archive_file")
                return stream.read(MAX_ARCHIVE_BYTES + 1)
        raw = read_file(folder / (name + ".txt"))
        index = json.loads(read_file(folder / "INDEX.json"))
        if index.get("reference") != reference or hashlib.sha256(raw).hexdigest() != index.get("sha256"):
            raise ValueError("archive_integrity")
        text = raw.decode("utf-8")
        return {"reference": reference, "offset": offset, "text": text[offset:offset + limit],
                "total_characters": len(text), "next_offset": offset + limit if offset + limit < len(text) else None}
