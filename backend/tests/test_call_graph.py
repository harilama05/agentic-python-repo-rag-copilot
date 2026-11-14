"""Regression cases for scope-aware static calls and honest graph evidence."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.graph.code_graph import build_code_graph
from src.agent_core.tools import CodebaseTools


class CallGraphTests(unittest.TestCase):
    def build(self, files):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name, source in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        return build_code_graph(root)

    def calls(self, graph, path, symbol):
        source = next(n for n in graph.nodes.values() if n.relative_path == path and n.qualified_name == symbol)
        return {(graph.nodes[e.target_id].relative_path, graph.nodes[e.target_id].qualified_name)
                for e in graph.outgoing.get(source.node_id, []) if e.edge_type == "calls"}

    def test_import_alias_does_not_connect_same_name_in_other_modules(self):
        graph = self.build({"a.py": "def save(): pass\n", "b.py": "def save(): pass\n",
                            "main.py": "from a import save as persist\ndef run(): persist()\n"})
        self.assertEqual(self.calls(graph, "main.py", "run"), {("a.py", "save")})

    def test_same_module_and_module_alias(self):
        graph = self.build({"a.py": "def save(): pass\n", "main.py":
                            "import a as storage\ndef save(): pass\ndef run():\n    save()\n    storage.save()\n"})
        self.assertEqual(self.calls(graph, "main.py", "run"), {("main.py", "save"), ("a.py", "save")})

    def test_relative_import_and_reexport(self):
        graph = self.build({"pkg/__init__.py": "from .impl import save\n", "pkg/impl.py": "def save(): pass\n",
                            "pkg/main.py": "from . import save as persist\ndef run(): persist()\n"})
        self.assertEqual(self.calls(graph, "pkg/main.py", "run"), {("pkg/impl.py", "save")})

    def test_nested_body_is_not_owned_by_outer_function(self):
        graph = self.build({"main.py": "def save(): pass\ndef outer():\n    def inner():\n        save()\n    return inner\n"})
        self.assertEqual(self.calls(graph, "main.py", "outer"), set())
        self.assertEqual(self.calls(graph, "main.py", "outer.inner"), {("main.py", "save")})

    def test_recursion_is_preserved_and_impact_excludes_the_target(self):
        graph = self.build({"main.py": "def recurse(): recurse()\n"})
        self.assertEqual(self.calls(graph, "main.py", "recurse"), {("main.py", "recurse")})
        self.assertEqual(graph.impact_analysis("recurse")["affected"], [])

    def test_unknown_receiver_does_not_match_unrelated_method_name(self):
        graph = self.build({"main.py": "class Store:\n    def save(self): pass\ndef run(client): client.save()\n"})
        self.assertEqual(self.calls(graph, "main.py", "run"), set())
        self.assertTrue(any(c["expression"] == "client.save()" for c in graph.unresolved_calls))
        self.assertFalse(graph.find_nodes("ore.save"))

    def test_local_callable_alias_and_rebinding(self):
        graph = self.build({"main.py": "def save(): pass\ndef run():\n    callback = save\n    callback()\n    callback = None\n    callback()\n"})
        edges = [e for e in graph.edges if e.edge_type == "calls"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(len(edges[0].sites), 1)
        self.assertTrue(any(c["line"] == 6 for c in graph.unresolved_calls))

    def test_instance_alias_inheritance_and_super(self):
        graph = self.build({"main.py": "class Base:\n    def save(self): pass\nclass Child(Base):\n    def save(self): super().save()\ndef run():\n    store = Child()\n    alias = store\n    alias.save()\n"})
        self.assertIn(("main.py", "Child.save"), self.calls(graph, "main.py", "run"))
        self.assertIn(("main.py", "Base.save"), self.calls(graph, "main.py", "Child.save"))

    def test_branches_preserve_both_possible_aliases_and_callsite_guards(self):
        graph = self.build({"main.py": "def a(): pass\ndef b(): pass\ndef run(flag):\n    if flag:\n        callback = a\n    else:\n        callback = b\n    callback()\n    if flag:\n        a()\n"})
        self.assertEqual(self.calls(graph, "main.py", "run"), {("main.py", "a"), ("main.py", "b")})
        self.assertTrue(any(site["conditions"] for e in graph.edges for site in e.sites))

    def test_parameter_annotation_is_a_candidate_not_runtime_proof(self):
        graph = self.build({"main.py": "class Base:\n    def save(self): pass\nclass Child(Base):\n    def save(self): pass\ndef run(store: Base): store.save()\n"})
        self.assertEqual(self.calls(graph, "main.py", "run"), {("main.py", "Base.save"), ("main.py", "Child.save")})
        self.assertTrue(all(e.certainty == "inferred" for e in graph.edges if e.edge_type == "calls"))

    def test_tools_report_limitations_unresolved_calls_and_call_sites(self):
        source = "def save(): pass\ndef run(client):\n    save()\n    client.save()\n"
        graph = self.build({"main.py": source})
        tools = CodebaseTools(SimpleNamespace(indexed_chunks=[]), ".", code_graph=graph,
                              source_files={"main.py": source})
        result = tools.find_callees("run")
        self.assertEqual(result["analysis_kind"], "static")
        self.assertFalse(result["proves_execution"])
        self.assertTrue(result["unresolved_calls"])
        self.assertEqual(result["relationships"][0]["sites"][0]["line"], 3)
        impact = tools.impact_analysis("save")
        self.assertFalse(impact["proves_breakage"])

    def test_parse_errors_are_visible_instead_of_silently_losing_files(self):
        graph = self.build({"broken.py": "def broken(\n", "ok.py": "def ok(): pass\n"})
        self.assertTrue(graph.diagnostics)
        self.assertEqual(graph.diagnostics[0]["relative_path"], "broken.py")

    def test_local_assignment_shadows_global_before_assignment(self):
        graph = self.build({"main.py": "def save(): pass\ndef run():\n    save()\n    save = None\n"})
        self.assertEqual(self.calls(graph, "main.py", "run"), set())

    def test_comprehension_and_with_bindings_do_not_leak_global_targets(self):
        graph = self.build({"main.py": "def save(): pass\ndef run(items, resource):\n    [save() for save in items]\n    with resource as save:\n        save()\n"})
        self.assertEqual(self.calls(graph, "main.py", "run"), set())

    def test_initializer_fields_and_literal_getattr_are_resolved(self):
        graph = self.build({"main.py": "class Store:\n    def save(self): pass\nclass Service:\n    def __init__(self): self.store = Store()\n    def run(self):\n        self.store.save()\n        getattr(self.store, 'save')()\n"})
        self.assertEqual(self.calls(graph, "main.py", "Service.run"), {("main.py", "Store.save")})

    def test_self_dispatch_includes_override_candidates(self):
        graph = self.build({"main.py": "class Base:\n    def save(self): pass\n    def run(self): self.save()\nclass Child(Base):\n    def save(self): pass\n"})
        self.assertEqual(self.calls(graph, "main.py", "Base.run"), {("main.py", "Base.save"), ("main.py", "Child.save")})

    def test_impact_returns_dependency_path_and_test_candidates(self):
        source = "def save(): pass\ndef service(): save()\ndef test_service(): service()\n"
        graph = self.build({"main.py": source})
        tools = CodebaseTools(SimpleNamespace(indexed_chunks=[]), ".", code_graph=graph,
                              source_files={"main.py": source})
        result = tools.impact_analysis("save")
        paths = {item["node_id"]: item["path_to_target"] for item in result["impact_paths"]}
        test_node = next(n for n in graph.nodes.values() if n.name == "test_service")
        self.assertEqual(len(paths[test_node.node_id]), 3)
        self.assertEqual(result["tests_to_review"][0]["symbol"], "test_service")

    def test_annotated_mapping_values_are_candidates_after_get(self):
        graph = self.build({"main.py": "class Item:\n    def check(self): pass\nclass Service:\n    def __init__(self): self.items: dict[str, Item] = {}\n    def run(self, key):\n        item = self.items.get(key)\n        if item is not None:\n            item.check()\n"})
        self.assertIn(("main.py", "Item.check"), self.calls(graph, "main.py", "Service.run"))

    def test_return_annotation_is_resolved_in_the_defining_module(self):
        graph = self.build({"models.py": "class Item:\n    def check(self): pass\ndef make() -> Item: return Item()\n",
                            "main.py": "from models import make\ndef run():\n    item = make()\n    item.check()\n"})
        self.assertIn(("models.py", "Item.check"), self.calls(graph, "main.py", "run"))

    def test_high_fanout_impact_obeys_node_limit_and_reports_truncation(self):
        source = "def save(): pass\n" + "".join(f"def caller_{i}(): save()\n" for i in range(250))
        graph = self.build({"main.py": source})
        tools = CodebaseTools(SimpleNamespace(indexed_chunks=[]), ".", code_graph=graph,
                              source_files={"main.py": source})
        result = tools.impact_analysis("save")
        self.assertLessEqual(len(result["affected"]), 199)
        self.assertTrue(result["truncated"])


if __name__ == "__main__":
    unittest.main()
