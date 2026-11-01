from .utils import utc_now, make_stable_chunk_id, get_chunk_text, get_chunk_metadata, get_metadata_value
from .repository_mixin import RepositoryStoreMixin
from .chunk_mixin import ChunkStoreMixin
from .code_graph_mixin import CodeGraphStoreMixin
from .file_mixin import FileStoreMixin

class MetadataStore(RepositoryStoreMixin, ChunkStoreMixin, CodeGraphStoreMixin, FileStoreMixin):
    """
    PostgreSQL metadata store composed of domain-specific mixins.
    """
    pass

__all__ = [
    "MetadataStore",
    "utc_now",
    "make_stable_chunk_id",
    "get_chunk_text",
    "get_chunk_metadata",
    "get_metadata_value",
    "RepositoryStoreMixin",
    "ChunkStoreMixin",
    "CodeGraphStoreMixin",
]
