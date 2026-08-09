from __future__ import annotations

from dataclasses import dataclass


class JobCancelled(Exception):
    """Raised when the user cancels a running conversion job."""


@dataclass
class JobProgress:
    """Shared mutable progress state for a running conversion job."""

    total: int = 0
    done: int = 0
    total_accounts: int = 0
    processed_accounts: int = 0
    cancel_requested: bool = False



@dataclass
class AutoProfileProgress:
    """Shared mutable progress state for the auto profile generation job."""

    total: int = 0
    done: int = 0
    modified: int = 0
    failed: int = 0
    region: str = ""
    identifier: str = "-"
    username: str = "-"
