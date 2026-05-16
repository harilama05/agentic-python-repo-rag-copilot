"""
Permission filter — applies access policies to search results.
"""

from typing import Any, Dict, List

from src.metadata.access_policy import AccessPolicy


class PermissionFilter:
    """
    Filters search results based on an ``AccessPolicy``.
    """

    def __init__(self, policy: AccessPolicy | None = None):
        self.policy = policy or AccessPolicy()

    def filter_results(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove results whose file path is denied by the policy."""
        return [
            r
            for r in results
            if self.policy.is_allowed(r.get("file_path", r.get("relative_path", "")))
        ]
