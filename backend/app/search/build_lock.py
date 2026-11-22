"""Kunci antarproses: memastikan hanya satu pembangunan indeks berjalan, baik dari server maupun dari CLI.

Memakai kunci file milik sistem operasi (msvcrt di Windows, fcntl di Linux/macOS). Bila proses yang memegang
kunci mati (mis. dihentikan paksa), sistem operasi otomatis melepas kuncinya, sehingga tidak ada kunci "basi".
"""

import os
from pathlib import Path
from typing import IO


class BuildLock:
    def __init__(self, path: Path):
        self.path = path
        self._handle: IO | None = None

    def acquire(self) -> bool:
        """Ambil kunci tanpa menunggu. False bila sedang dipegang proses lain."""
        if self._handle is not None:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+")
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle, fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None

    def held_by_other_process(self) -> bool:
        if self._handle is not None:
            return False  # dipegang proses ini sendiri
        if self.acquire():
            self.release()
            return False
        return True
