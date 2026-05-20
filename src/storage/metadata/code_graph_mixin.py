from typing import Any

from sqlalchemy import delete, select

from src.db.models import CodeEdge as DBCodeEdge, CodeNode as DBCodeNode
from src.db.session import get_db_session
from src.graph.code_graph import CodeGraph, CodeNode as GraphCodeNode


class CodeGraphStoreMixin:
    def replace_code_graph(
        self,
        *,
        repo_id: str,
        code_graph: Any,
    ) -> None:
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
