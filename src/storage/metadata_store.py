import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.db.models import (
    Chunk,
    CodeEdge as DBCodeEdge,
    CodeNode as DBCodeNode,
    Repository,
)
from src.code_graph import CodeGraph, CodeNode as GraphCodeNode
from src.db.session import get_db_session


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_stable_chunk_id(
    repo_id: str,
    relative_path: str,
    start_line: int | None,
    end_line: int | None,
    text: str,
) -> str:
    raw = f"{repo_id}:{relative_path}:{start_line}:{end_line}:{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def get_chunk_text(chunk: Any) -> str:
    """
    Support multiple possible chunk shapes:
    - chunk.text
    - chunk.content
    - chunk.code
    """
    return (
        getattr(chunk, "text", None)
        or getattr(chunk, "content", None)
        or getattr(chunk, "code", None)
        or ""
    )


def get_chunk_metadata(chunk: Any) -> dict[str, Any]:
    metadata = getattr(chunk, "metadata", None)

    if isinstance(metadata, dict):
        return metadata

    return {}


def get_metadata_value(
    metadata: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    for key in keys:
        value = metadata.get(key)

        if value is not None:
            return value

    return default


class MetadataStore:
    """
    PostgreSQL metadata store.

    Stores:
    - repositories
    - chunks metadata/text
    - code graph nodes
    - code graph edges

    Embeddings are still stored in Chroma for now.
    Qdrant will be added in the next phase.
    """

    def upsert_repository(
        self,
        *,
        repo_id: str,
        name: str,
        source_type: str,
        visibility: str,
        is_persistent: bool,
        collection_name: str,
        status: str,
        file_count: int,
        doc_count: int,
        ignored_file_count: int,
        chunk_count: int,
        local_path: str | None = None,
        github_url: str | None = None,
        branch: str | None = None,
        commit_hash: str | None = None,
        owner_session_id: str | None = None,
        owner_user_id: str | None = None,
        indexed_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        with get_db_session() as session:
            stmt = insert(Repository).values(
                repo_id=repo_id,
                name=name,
                source_type=source_type,
                visibility=visibility,
                is_persistent=is_persistent,
                owner_session_id=owner_session_id,
                owner_user_id=owner_user_id,
                local_path=local_path,
                github_url=github_url,
                branch=branch,
                commit_hash=commit_hash,
                collection_name=collection_name,
                status=status,
                file_count=file_count,
                doc_count=doc_count,
                ignored_file_count=ignored_file_count,
                chunk_count=chunk_count,
                indexed_at=indexed_at,
                expires_at=expires_at,
            )

            update_columns = {
                "name": stmt.excluded.name,
                "source_type": stmt.excluded.source_type,
                "visibility": stmt.excluded.visibility,
                "is_persistent": stmt.excluded.is_persistent,
                "owner_session_id": stmt.excluded.owner_session_id,
                "owner_user_id": stmt.excluded.owner_user_id,
                "local_path": stmt.excluded.local_path,
                "github_url": stmt.excluded.github_url,
                "branch": stmt.excluded.branch,
                "commit_hash": stmt.excluded.commit_hash,
                "collection_name": stmt.excluded.collection_name,
                "status": stmt.excluded.status,
                "file_count": stmt.excluded.file_count,
                "doc_count": stmt.excluded.doc_count,
                "ignored_file_count": stmt.excluded.ignored_file_count,
                "chunk_count": stmt.excluded.chunk_count,
                "indexed_at": stmt.excluded.indexed_at,
                "expires_at": stmt.excluded.expires_at,
                "updated_at": utc_now(),
            }

            stmt = stmt.on_conflict_do_update(
                index_elements=[Repository.repo_id],
                set_=update_columns,
            )

            session.execute(stmt)

    def replace_chunks(
        self,
        *,
        repo_id: str,
        chunks: Iterable[Any],
    ) -> None:
        with get_db_session() as session:
            session.execute(
                delete(Chunk).where(Chunk.repo_id == repo_id)
            )

            chunk_rows: list[Chunk] = []

            for chunk in chunks:
                metadata = get_chunk_metadata(chunk)
                text = get_chunk_text(chunk)

                relative_path = get_metadata_value(
                    metadata,
                    "relative_path",
                    "file_path",
                    "path",
                    default="",
                )

                start_line = get_metadata_value(
                    metadata,
                    "start_line",
                    "line_start",
                )

                end_line = get_metadata_value(
                    metadata,
                    "end_line",
                    "line_end",
                )

                chunk_id = (
                    getattr(chunk, "chunk_id", None)
                    or metadata.get("chunk_id")
                    or make_stable_chunk_id(
                        repo_id=repo_id,
                        relative_path=str(relative_path),
                        start_line=start_line,
                        end_line=end_line,
                        text=text,
                    )
                )

                source_type = get_metadata_value(
                    metadata,
                    "source_type",
                    "type",
                )

                symbol_name = get_metadata_value(
                    metadata,
                    "symbol_name",
                    "name",
                )

                qualified_name = get_metadata_value(
                    metadata,
                    "qualified_name",
                    "symbol",
                )

                symbol_type = get_metadata_value(
                    metadata,
                    "symbol_type",
                    "type",
                )

                heading = get_metadata_value(
                    metadata,
                    "heading",
                    "title",
                )

                chunk_rows.append(
                    Chunk(
                        chunk_id=str(chunk_id),
                        repo_id=repo_id,
                        source_type=source_type,
                        relative_path=str(relative_path),
                        start_line=start_line,
                        end_line=end_line,
                        symbol_name=symbol_name,
                        qualified_name=qualified_name,
                        symbol_type=symbol_type,
                        heading=heading,
                        text=text,
                    )
                )

            session.add_all(chunk_rows)

    def replace_code_graph(
        self,
        *,
        repo_id: str,
        code_graph: Any,
    ) -> None:
        """
        Store code graph nodes/edges from the in-memory CodeGraph.

        Expected current graph shape:
        - code_graph.nodes: dict[node_id, node]
        - code_graph.edges: list[edge]
        - node has node_id/name/qualified_name/node_type/relative_path/start_line/end_line/parent
        - edge has source_id/target_id/edge_type
        """
        with get_db_session() as session:
            session.execute(
                delete(DBCodeEdge).where(DBCodeEdge.repo_id == repo_id)
            )
            session.execute(
                delete(DBCodeNode).where(DBCodeNode.repo_id == repo_id)
            )

            node_rows: list[DBCodeNode] = []

            for node_id, node in code_graph.nodes.items():
                node_rows.append(
                    DBCodeNode(
                        repo_id=repo_id,
                        node_id=str(getattr(node, "node_id", None) or node_id),
                        name=str(getattr(node, "name", "")),
                        qualified_name=str(getattr(node, "qualified_name", "")),
                        node_type=str(
                            getattr(node, "node_type", None)
                            or getattr(node, "type", "")
                        ),
                        relative_path=str(getattr(node, "relative_path", "")),
                        start_line=int(getattr(node, "start_line", 0)),
                        end_line=int(getattr(node, "end_line", 0)),
                        parent=getattr(node, "parent", None),
                    )
                )

            edge_rows: list[DBCodeEdge] = []

            for edge in code_graph.edges:
                edge_rows.append(
                    DBCodeEdge(
                        repo_id=repo_id,
                        source_node_id=str(
                            getattr(edge, "source_node_id", None)
                            or getattr(edge, "source_id", "")
                        ),
                        target_node_id=str(
                            getattr(edge, "target_node_id", None)
                            or getattr(edge, "target_id", "")
                        ),
                        edge_type=str(getattr(edge, "edge_type", "")),
                    )
                )

            session.add_all(node_rows)
            session.add_all(edge_rows)

    def get_repository(self, repo_id: str) -> dict[str, Any] | None:
        with get_db_session() as session:
            repo = session.get(Repository, repo_id)

            if repo is None:
                return None

            return {
                "repo_id": repo.repo_id,
                "name": repo.name,
                "source_type": repo.source_type,
                "visibility": repo.visibility,
                "is_persistent": repo.is_persistent,
                "collection_name": repo.collection_name,
                "status": repo.status,
                "file_count": repo.file_count,
                "doc_count": repo.doc_count,
                "ignored_file_count": repo.ignored_file_count,
                "chunk_count": repo.chunk_count,
                "indexed_at": repo.indexed_at,
                "expires_at": repo.expires_at,
            }

    def list_repositories(self) -> list[dict[str, Any]]:
        with get_db_session() as session:
            repos = session.execute(
                select(Repository).order_by(Repository.updated_at.desc())
            ).scalars().all()

            return [
                {
                    "repo_id": repo.repo_id,
                    "name": repo.name,
                    "source_type": repo.source_type,
                    "visibility": repo.visibility,
                    "is_persistent": repo.is_persistent,
                    "collection_name": repo.collection_name,
                    "status": repo.status,
                    "file_count": repo.file_count,
                    "doc_count": repo.doc_count,
                    "ignored_file_count": repo.ignored_file_count,
                    "chunk_count": repo.chunk_count,
                    "indexed_at": repo.indexed_at,
                    "expires_at": repo.expires_at,
                }
                for repo in repos
            ]

    def count_chunks(self, repo_id: str) -> int:
        with get_db_session() as session:
            result = session.execute(
                select(Chunk).where(Chunk.repo_id == repo_id)
            ).scalars().all()

            return len(result)

    def count_code_nodes(self, repo_id: str) -> int:
        with get_db_session() as session:
            result = session.execute(
                select(DBCodeNode).where(DBCodeNode.repo_id == repo_id)
            ).scalars().all()

            return len(result)

    def count_code_edges(self, repo_id: str) -> int:
        with get_db_session() as session:
            result = session.execute(
                select(DBCodeEdge).where(DBCodeEdge.repo_id == repo_id)
            ).scalars().all()

            return len(result)
    
    def load_code_graph(self, repo_id: str) -> CodeGraph:
        """
        Reconstruct CodeGraph from PostgreSQL code_nodes/code_edges.

        Important:
        Use graph.add_node() and graph.add_edge() instead of assigning
        graph.nodes / graph.edges directly, because CodeGraph also maintains:
        - name_to_ids
        - qualified_name_to_id
        - incoming
        - outgoing
        """
        with get_db_session() as session:
            node_rows = session.execute(
                select(DBCodeNode).where(DBCodeNode.repo_id == repo_id)
            ).scalars().all()

            edge_rows = session.execute(
                select(DBCodeEdge).where(DBCodeEdge.repo_id == repo_id)
            ).scalars().all()

            graph = CodeGraph()

            for row in node_rows:
                node = GraphCodeNode(
                    node_id=row.node_id,
                    name=row.name,
                    qualified_name=row.qualified_name,
                    node_type=row.node_type,
                    relative_path=row.relative_path,
                    start_line=row.start_line,
                    end_line=row.end_line,
                    parent=row.parent or "",
                )

                graph.add_node(node)

            for row in edge_rows:
                graph.add_edge(
                    source_id=row.source_node_id,
                    target_id=row.target_node_id,
                    edge_type=row.edge_type,
                )

            return graph