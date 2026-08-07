from __future__ import annotations

from dataclasses import dataclass


class JobCancelled(Exception):
    """Raised when the user cancels a running conversion job."""


@dataclass
class JobProgress:
    """Shared mutable progress state for a running conversion job."""

    total: int = 0
    done: int = 0
