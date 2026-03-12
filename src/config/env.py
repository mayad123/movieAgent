"""
Locate the nearest .env file by walking up from cwd or the project root.

This module was previously expected at ``lib.env`` (a path that never existed
in the repository).  It now lives at ``config.env`` and is imported by
``config.__init__``.
"""
from pathlib import Path
from typing import Optional


def find_dotenv_path(
    filename: str = ".env",
    start: Optional[Path] = None,
    max_depth: int = 5,
) -> Optional[str]:
    """Walk up from *start* (default: cwd) looking for *filename*.

    Returns the absolute path as a string if found, otherwise ``None``.
    """
    current = Path(start) if start else Path.cwd()
    for _ in range(max_depth):
        candidate = current / filename
        if candidate.is_file():
            return str(candidate)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None
