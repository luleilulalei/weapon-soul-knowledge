from __future__ import annotations

from pathlib import Path


def package_root() -> Path:
    return Path(__file__).resolve().parent


def project_root() -> Path:
    return package_root().parent


def resolve_project_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = project_root() / resolved
    return resolved
