"""Exact source preservation and DB-only reads across chunk boundaries."""

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from src.agent_core.tools import CodebaseTools
from src.chunking.code_chunker import build_code_chunks
from src.db.models import Base
from src.parsing.ast_parser import parse_python_file
from src.parsing.json_parser import parse_json_file
from src.storage.metadata.file_mixin import FileStoreMixin


class SourceSnapshotTests(unittest.TestCase):
    def test_module_imports_constants_and_decorators_are_indexed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.py"
            text = "import os\nLIMIT = 10\n\n@decorator\ndef task():\n    return LIMIT\n"
            path.write_text(text, encoding="utf-8")
            chunks = build_code_chunks(parse_python_file(path), directory)
            windows = [chunk.code for chunk in chunks if chunk.metadata["symbol_type"] == "module"]
            self.assertEqual("\n".join(windows), text.rstrip("\n"))

    def test_python_file_without_symbols_still_has_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.py"
            path.write_text("PORT = 8000\n", encoding="utf-8")
            self.assertTrue(build_code_chunks(parse_python_file(path), directory))

    def test_json_preserves_original_line_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            text = '{"z": 1, "a": 2}\n'
            path.write_text(text, encoding="utf-8")
            self.assertEqual(parse_json_file(path, directory)["text"], text)

    def test_exact_snapshot_is_used_even_without_chunks_or_local_source(self):
        tools = CodebaseTools(SimpleNamespace(indexed_chunks=[]), ".",
                              source_files={"settings.py": "import os\nPORT = 8000\n", "empty.py": ""})
        with patch.object(Path, "read_text", side_effect=AssertionError("filesystem read")):
            result = tools.read_file("settings.py", 1, 2)
            self.assertIn("1: import os", result["content"])
            self.assertEqual(tools.count_files("all")["count"], 2)
        with self.assertRaises(ValueError):
            tools.read_file("settings.py", 4, 5)

    def test_snapshot_storage_replacement_and_repo_isolation(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        @contextmanager
        def session_scope():
            with Session(engine) as session:
                with session.begin():
                    yield session

        store = FileStoreMixin()
        with patch("src.storage.metadata.file_mixin.engine", engine), patch("src.storage.metadata.file_mixin.get_db_session", session_scope):
            store.replace_files("one", {"a.py": "ONE\n", "stale.py": "old"})
            store.replace_files("two", {"a.py": "TWO\n"})
            store.replace_files("one", {"a.py": "UPDATED\n"})
            self.assertEqual(store.load_files("one"), {"a.py": "UPDATED\n"})
            self.assertEqual(store.load_files("two"), {"a.py": "TWO\n"})
        engine.dispose()

    def test_old_database_without_snapshot_table_stays_loadable(self):
        engine = create_engine("sqlite:///:memory:")
        with patch("src.storage.metadata.file_mixin.engine", engine):
            self.assertEqual(FileStoreMixin().load_files("old"), {})
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
