from __future__ import annotations

import os
import zipfile
from datetime import datetime
from pathlib import Path

from nielsen_config import ENCODING


class RunLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            self.handle.close()
            self.handle = None
            raise RuntimeError("Exista deja un export Nielsen in executie") from exc
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def archive_export(export_dir: Path, zip_path: Path) -> int:
    if not export_dir.exists():
        raise FileNotFoundError(f"Nu exista folderul de export: {export_dir}")
    files = [path for path in export_dir.iterdir() if path.is_file()]
    if not files:
        raise RuntimeError("Exportul nu a generat niciun fisier; ZIP-ul nu este considerat valid")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, arcname=path.name)
    return len(files)


def rename_existing_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.stem}_vechi_{timestamp}{path.suffix}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_vechi_{timestamp}_{counter}{path.suffix}")
        counter += 1
    path.rename(candidate)
    return candidate


def append_log(base_dir: Path, job_name: str, message: str = "null") -> None:
    log_path = base_dir / "Log.csv"
    timestamp = datetime.now().strftime(" %d/%m/%Y  %H:%M:%S")
    with log_path.open("a", encoding=ENCODING, errors="replace", newline="") as handle:
        handle.write(f"{timestamp}{job_name} {message} \n")
