"""Ensure both indexing and DB loading wire exact sources into the agent tools."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from src.indexing.codebase_indexer import build_codebase_agent
from src.indexing.codebase_loader import load_existing_codebase_agent


class IndexingWiringTests(unittest.TestCase):
    def test_indexing_persists_original_files_and_scopes_chunk_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.py"
            source = "LIMIT = 1\n\ndef task():\n    return LIMIT\n"
            path.write_text(source, encoding="utf-8")
            with patch("src.indexing.codebase_indexer.SupabaseCodeVectorStore"), patch("src.indexing.codebase_indexer.MetadataStore") as metadata:
                first = build_codebase_agent(directory, repo_id="first", use_llm=False, use_llm_router=False)
                metadata.return_value.replace_files.assert_called_with("first", {"tasks.py": source})
                second = build_codebase_agent(directory, repo_id="second", save_metadata=False, use_llm=False, use_llm_router=False)
            first_ids = {chunk.chunk_id for chunk in first.retriever.indexed_chunks}
            second_ids = {chunk.chunk_id for chunk in second.retriever.indexed_chunks}
            self.assertFalse(first_ids & second_ids)
            self.assertEqual(first.tools.read_file("tasks.py", 1, 1)["content"], "1: LIMIT = 1")

    def test_loading_reads_only_database_snapshots(self):
        repo = SimpleNamespace(repo_id="company", is_persistent=True, local_path="/absent/source",
                               repo_name="Company", source_type="company")
        chunks = [{"chunk_id": "one", "text": "return 1", "metadata": {"source_type": "code"}}]
        with patch("src.indexing.codebase_loader.get_repository_snapshot", return_value=repo), patch("src.indexing.codebase_loader.MetadataStore") as metadata, patch("src.indexing.codebase_loader.SupabaseCodeVectorStore"), patch.object(Path, "read_text", side_effect=AssertionError("filesystem read")):
            metadata.return_value.load_chunks.return_value = chunks
            metadata.return_value.load_files.return_value = {"config.py": "PORT = 8000\n"}
            loaded = load_existing_codebase_agent("company", "fast", False, False)
        self.assertEqual(loaded.tools.read_file("config.py")["content"], "1: PORT = 8000")


if __name__ == "__main__":
    unittest.main()
