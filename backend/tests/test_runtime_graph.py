"""Runtime evidence is scoped to recorded runs and exact indexed source hashes."""

import copy
import json
import os
import subprocess
import sys
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
from src.db.models import Base, RepositoryGraphAnalysis
from src.graph.code_graph import build_code_graph
from src.graph.runtime_trace import RuntimeCallRecorder, apply_runtime_report
from src.storage.metadata.code_graph_mixin import CodeGraphStoreMixin


SOURCE = '''class Store:
    def save(self): return 42
    def unused(self): return 0

def run(obj, method):
    return getattr(obj, method)()

def choose(flag):
    if flag:
        return first()
    return second()

def first(): return 1
def second(): return 2
'''


class RuntimeGraphTests(unittest.TestCase):
    def fixture(self, source=SOURCE, max_events=100000):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        path = root / "sample.py"
        path.write_text(source, encoding="utf-8")
        namespace = {}
        exec(compile(source, str(path), "exec"), namespace)
        recorder = RuntimeCallRecorder(root, label="unit test", max_events=max_events)
        return root, namespace, recorder

    def report(self):
        root, namespace, recorder = self.fixture()
        before = sys.getprofile()
        with recorder:
            self.assertEqual(namespace["run"](namespace["Store"](), "save"), 42)
            namespace["choose"](True)
        self.assertIs(sys.getprofile(), before)
        return root, recorder.report()

    def test_dynamic_call_is_observed_without_claiming_unexecuted_branch(self):
        root, report = self.report()
        graph = build_code_graph(root)
        apply_runtime_report(graph, report, {"sample.py": SOURCE})
        tools = CodebaseTools(SimpleNamespace(indexed_chunks=[]), root, code_graph=graph,
                              source_files={"sample.py": SOURCE})
        observed = tools.find_callees("run", evidence="observed")
        self.assertEqual([n["symbol"] for n in observed["callees"]], ["Store.save"])
        self.assertEqual(tools.find_callees("run", evidence="static")["callees"], [])
        self.assertTrue(observed["relationships"][0]["runtime_observed"])
        self.assertEqual([n["symbol"] for n in tools.find_callees("choose", evidence="observed")["callees"]], ["first"])
        self.assertEqual({n["symbol"] for n in tools.find_callees("choose", evidence="static")["callees"]}, {"first", "second"})
        self.assertFalse(observed["proves_execution"])
        self.assertEqual(observed["analysis_kind"], "hybrid")

    def test_stale_source_and_changed_during_run_are_rejected_atomically(self):
        root, report = self.report()
        graph = build_code_graph(root)
        for invalid in ({**report, "sources_unchanged": False},
                        {**report, "source_hashes": {"sample.py": "invalid"}}):
            with self.assertRaises(ValueError):
                apply_runtime_report(graph, invalid, {"sample.py": SOURCE})
            self.assertFalse(graph.runtime_runs)
        with self.assertRaises(ValueError):
            apply_runtime_report(graph, report, {"sample.py": SOURCE + "# changed\n"})

    def test_report_validation_and_idempotency(self):
        root, report = self.report()
        graph = build_code_graph(root)
        invalid = copy.deepcopy(report)
        invalid["edges"][-1]["line"] = -1
        with self.assertRaises(ValueError):
            apply_runtime_report(graph, invalid, {"sample.py": SOURCE})
        self.assertFalse(any(e.observations for e in graph.edges))
        invalid = copy.deepcopy(report)
        invalid["edges"][0]["source_id"] = {}
        with self.assertRaises(ValueError):
            apply_runtime_report(graph, invalid, {"sample.py": SOURCE})
        self.assertTrue(apply_runtime_report(graph, report, {"sample.py": SOURCE})["imported"])
        self.assertFalse(apply_runtime_report(graph, report, {"sample.py": SOURCE})["imported"])
        with self.assertRaises(ValueError):
            apply_runtime_report(graph, {**report, "label": "different payload"}, {"sample.py": SOURCE})

    def test_profile_hook_is_restored_after_program_failure_and_event_limit_is_explicit(self):
        root, namespace, recorder = self.fixture(max_events=1)
        with self.assertRaises(RuntimeError):
            with recorder:
                namespace["choose"](True)
                raise RuntimeError("test error")
        self.assertIsNone(sys.getprofile())
        self.assertTrue(recorder.report()["truncated"])
        self.assertEqual(recorder.report()["exit_status"], "raised")
        self.assertEqual(recorder.report()["call_events"], 1)

    def test_does_not_replace_an_existing_profiler(self):
        root, namespace, recorder = self.fixture()
        original = sys.getprofile()
        hook = lambda frame, event, arg: None
        try:
            sys.setprofile(hook)
            with self.assertRaises(RuntimeError):
                with recorder:
                    pass
            self.assertIs(sys.getprofile(), hook)
        finally:
            sys.setprofile(original)

    def test_cli_records_a_real_subprocess_without_database_or_api(self):
        root, namespace, recorder = self.fixture(SOURCE + "\nif __name__ == '__main__':\n    run(Store(), 'save')\n")
        output = root / "trace.json"
        completed = subprocess.run([sys.executable, "-m", "scripts.record_runtime_calls", "--repo", str(root),
                                    "--script", str(root / "sample.py"), "--output", str(output)],
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(report["sources_unchanged"])
        self.assertTrue(report["edges"])
        self.assertEqual(report["scope"], "current_thread_python_call_events")

    def test_cli_clean_system_exit_is_reported_as_completed(self):
        source = "import sys\ndef run(): return 1\nif __name__ == '__main__':\n    run()\n    sys.exit(0)\n"
        root, namespace, recorder = self.fixture(source)
        output = root / "trace.json"
        completed = subprocess.run([sys.executable, "-m", "scripts.record_runtime_calls", "--repo", str(root),
                                    "--script", str(root / "sample.py"), "--output", str(output)],
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["exit_status"], "completed")

    def test_cli_target_namespace_app_is_not_shadowed_by_backend_debug_app(self):
        root, namespace, recorder = self.fixture("def placeholder(): pass\n")
        helper = root / "app" / "services" / "helper.py"
        helper.parent.mkdir(parents=True)
        helper.write_text("def save(): return 42\n", encoding="utf-8")
        entry = root / "main.py"
        entry.write_text("from app.services.helper import save\ndef run(): return save()\nif __name__ == '__main__':\n    assert run() == 42\n", encoding="utf-8")
        output = root / "trace.json"
        completed = subprocess.run([sys.executable, "-m", "scripts.record_runtime_calls", "--repo", str(root),
                                    "--script", str(entry), "--output", str(output)],
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["edges"])

    def test_db_round_trip_keeps_sites_runtime_only_edges_and_repo_isolation(self):
        root, report = self.report()
        graph = build_code_graph(root)
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.addCleanup(engine.dispose)

        @contextmanager
        def session_scope():
            with Session(engine) as session:
                with session.begin():
                    yield session

        store = CodeGraphStoreMixin()
        with patch("src.storage.metadata.code_graph_mixin.engine", engine), patch(
                "src.storage.metadata.code_graph_mixin.get_db_session", session_scope):
            store.replace_code_graph(repo_id="one", code_graph=graph)
            store.replace_code_graph(repo_id="two", code_graph=build_code_graph(root))
            loaded = store.load_code_graph("one")
            self.assertTrue(any(e.sites for e in loaded.edges))
            apply_runtime_report(loaded, report, {"sample.py": SOURCE})
            store.save_graph_analysis("one", loaded)
            reloaded = store.load_code_graph("one")
            self.assertEqual(len(reloaded.runtime_runs), 1)
            self.assertTrue(any(e.observations and not e.sites for e in reloaded.edges))
            self.assertFalse(store.load_code_graph("two").runtime_runs)
            store.replace_code_graph(repo_id="one", code_graph=build_code_graph(root))
            self.assertFalse(store.load_code_graph("one").runtime_runs)

    def test_old_database_without_analysis_table_remains_readable(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        RepositoryGraphAnalysis.__table__.drop(engine)
        self.addCleanup(engine.dispose)

        @contextmanager
        def session_scope():
            with Session(engine) as session:
                yield session

        with patch("src.storage.metadata.code_graph_mixin.engine", engine), patch(
                "src.storage.metadata.code_graph_mixin.get_db_session", session_scope):
            graph = CodeGraphStoreMixin().load_code_graph("old")
            self.assertEqual(graph.analysis_version, 0)


if __name__ == "__main__":
    unittest.main()
