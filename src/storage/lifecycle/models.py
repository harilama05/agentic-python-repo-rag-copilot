from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.core.constants import TEMPORARY_REPO_SOURCE_TYPES

@dataclass
class RepositorySnapshot:
    repo_id: str
    repo_name: str
    source_type: str | None
    is_persistent: bool
    local_path: str | None
    collection_name: str | None
    file_count: int
    doc_count: int
    ignored_file_count: int
    chunk_count: int

@dataclass
class RepositoryListItem:
    repo_id: str
    repo_name: str
    source_type: str | None
    is_persistent: bool
    local_path: str | None
    collection_name: str | None
    chunk_count: int

@dataclass
class TemporaryRepositoryItem:
    repo_id: str
    repo_name: str
    source_type: str | None
    is_persistent: bool
    local_path: str | None
    expires_at: datetime | None

def is_temporary_repository(source_type: str | None, is_persistent: bool | None) -> bool:
    if is_persistent:
        return False
    return source_type in TEMPORARY_REPO_SOURCE_TYPES
