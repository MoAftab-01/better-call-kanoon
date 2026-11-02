"""Portable path checks for local manifests and a flat, generated output namespace."""

import os
import re
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath


def validate_relative_path(value: str) -> None:
    parts = value.split("/")
    if (
        not value or "\\" in value or ":" in value
        or PurePosixPath(value).is_absolute() or PureWindowsPath(value).drive
        or any(part in {"", ".", ".."} for part in parts)
        or any(part.endswith((" ", ".")) for part in parts)
        or any(ord(c) < 32 or c in '<>"|?*' for c in value)
        or any(re.fullmatch(r"(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", p) for p in parts)
    ):
        raise ValueError("file_path must be a safe relative path using forward slashes, without traversal.")


def checked_path(path: Path) -> Path:
    """Reject symlinks/junctions in every existing component, including ancestors."""
    if ".." in path.parts:
        raise ValueError("Parent traversal is not allowed in configured paths.")
    absolute = Path(os.path.abspath(path))
    for component in [*reversed(absolute.parents), absolute]:
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Symlinks and filesystem reparse points are not allowed.")
    return absolute.resolve()


def source_path(root: Path, relative: str) -> Path:
    validate_relative_path(relative)
    root = checked_path(root)
    candidate = checked_path(root / relative)
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError("Source must be a regular file inside the source root.")
    return candidate


def output_path(root: Path, document_id: str) -> Path:
    if not re.fullmatch(r"doc_[0-9a-f]{64}", document_id):
        raise ValueError("Invalid generated document ID.")
    root = checked_path(root)
    target = checked_path(root / f"{document_id}.json")
    if target.parent != root:
        raise ValueError("Output target escaped the configured output directory.")
    return target
