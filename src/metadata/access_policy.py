"""
Access policy — controls which files or chunks are visible to a user.

This is a placeholder for multi-tenant / RBAC scenarios. For single-user
setups everything is allowed.
"""

from pathlib import Path
from typing import List, Optional, Set


class AccessPolicy:
    """
    Determines whether a given file or chunk should be visible.

    In the default (open) policy, everything is allowed.
    """

    def __init__(
        self,
        allowed_paths: Optional[List[str]] = None,
        denied_paths: Optional[List[str]] = None,
    ):
        self._allowed: Optional[Set[str]] = (
            set(allowed_paths) if allowed_paths else None
        )
        self._denied: Set[str] = set(denied_paths) if denied_paths else set()

    def is_allowed(self, file_path: str | Path) -> bool:
        path_str = str(Path(file_path).resolve())

        # Deny list takes precedence
        for denied in self._denied:
            if denied in path_str:
                return False

        # If allow list exists, file must match
        if self._allowed is not None:
            return any(allowed in path_str for allowed in self._allowed)

        return True
