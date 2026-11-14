"""Conservative, repository-local name/receiver resolution. Never executes code."""

import ast
import hashlib
from dataclasses import dataclass

from src.graph.code_graph import CodeGraph, CodeNode


UNKNOWN = {("unknown", "")}


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


@dataclass
class Definition:
    node: CodeNode
    syntax: ast.AST
    scope: str
    class_id: str = ""


class Resolver:
    def __init__(self, sources: dict[str, str]):
        self.graph = CodeGraph()
        self.graph.analysis_version = 2
        self.sources = {p.replace("\\", "/"): s for p, s in sources.items() if p.endswith(".py")}
        self.modules = {}
        self.trees = {}
        self.definitions = {}
        self.scope_definitions = {}
        self.scopes = {}
        self.globals = {}
        self.bases = {}
        self.attributes = {}
        for path, source in sorted(self.sources.items()):
            self.graph.source_hashes[path] = source_hash(source)
            module = path[:-3].replace("/", ".")
            if module.endswith(".__init__"):
                module = module[:-9]
            self.modules[module] = path
            try:
                tree = ast.parse(source)
            except SyntaxError as exc:
                self.graph.diagnostics.append({"relative_path": path, "line": exc.lineno,
                                               "reason": "syntax_error"})
                continue
            self.trees[path] = tree
            self.collect(path, tree.body, "", "")
        # Re-exports and aliases can depend on a module discovered later.
        self.globals = {p: dict(self.scopes.get((p, ""), {})) for p in self.trees}
        for _ in range(8):
            changed = False
            for path, tree in self.trees.items():
                env = dict(self.globals[path])
                for statement in tree.body:
                    if isinstance(statement, (ast.Import, ast.ImportFrom)):
                        env.update(self.import_bindings(path, statement))
                    elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                        value = self.value(statement.value, path, env)
                        for target in targets:
                            if isinstance(target, ast.Name):
                                env[target.id] = value
                changed |= env != self.globals[path]
                self.globals[path] = env
            if not changed:
                break
        for node_id, definition in self.definitions.items():
            if isinstance(definition.syntax, ast.ClassDef):
                self.bases[node_id] = [target for base in definition.syntax.bases
                                       for kind, target in self.value(base, definition.node.relative_path, {})
                                       if kind == "node" and self.graph.nodes[target].node_type == "class"]

    def collect(self, path, statements, scope, class_id):
        bindings = self.scopes.setdefault((path, scope), {})
        for item in statements:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = f"{scope}.{item.name}" if scope else item.name
                end = item.end_lineno or item.lineno
                node_id = f"{path}:{qualified}:{item.lineno}-{end}"
                kind = "class" if isinstance(item, ast.ClassDef) else "method" if class_id else "function"
                node = CodeNode(node_id, item.name, qualified, kind, path, item.lineno, end,
                                self.graph.nodes[class_id].qualified_name if class_id else scope)
                self.graph.add_node(node)
                bindings[item.name] = {("node", node_id)}
                self.definitions[node_id] = Definition(node, item, scope, class_id)
                self.scope_definitions[(path, qualified)] = self.definitions[node_id]
                self.graph.node_info[node_id] = {
                    "docstring": (ast.get_docstring(item) or "")[:1000],
                    "is_async": isinstance(item, ast.AsyncFunctionDef),
                    "runtime_first_line": min([item.lineno] + [d.lineno for d in item.decorator_list]),
                }
                if class_id:
                    self.graph.add_edge(class_id, node_id, "contains", certainty="resolved")
                self.collect(path, item.body, qualified, node_id if kind == "class" else "")
            else:
                # Definitions in branches keep their lexical parent, not an ast.walk owner.
                for block in ("body", "orelse", "finalbody"):
                    body = getattr(item, block, None)
                    if isinstance(body, list):
                        self.collect(path, body, scope, class_id)
                for handler in getattr(item, "handlers", []):
                    self.collect(path, handler.body, scope, class_id)

    def import_bindings(self, path, node):
        result = {}
        if isinstance(node, ast.Import):
            for alias in node.names:
                result[alias.asname or alias.name.split(".")[0]] = {
                    ("module", alias.name if alias.asname else alias.name.split(".")[0])}
        else:
            module = path[:-3].replace("/", ".")
            package = module[:-9].split(".") if module.endswith(".__init__") else module.split(".")[:-1]
            prefix = package[:len(package) - node.level + 1] if node.level else []
            target_module = ".".join(prefix + ([node.module] if node.module else []))
            for alias in node.names:
                if alias.name == "*":
                    self.graph.diagnostics.append({"relative_path": path, "line": node.lineno,
                                                   "reason": "wildcard_import_not_resolved"})
                    continue
                result[alias.asname or alias.name] = self.export(target_module, alias.name)
        return result

    def export(self, module, name):
        path = self.modules.get(module)
        if path and name in self.globals.get(path, {}):
            return self.globals[path][name]
        child = f"{module}.{name}" if module else name
        if child in self.modules:
            return {("module", child)}
        return UNKNOWN

    def method(self, class_id, name, seen=None):
        seen = set() if seen is None else set(seen)
        if class_id in seen:
            return set()
        seen.add(class_id)
        node = self.graph.nodes[class_id]
        own = self.scopes.get((node.relative_path, node.qualified_name), {}).get(name)
        if own:
            return own
        values = set()
        for base in self.bases.get(class_id, []):
            values.update(self.method(base, name, seen))
        return values

    def subclasses(self, class_id):
        found = {class_id}
        while True:
            more = {child for child, bases in self.bases.items() if any(base in found for base in bases)}
            if more <= found:
                return found
            found |= more

    def annotation(self, annotation, path, env):
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                annotation = ast.parse(annotation.value, mode="eval").body
            except SyntaxError:
                return UNKNOWN
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            return self.annotation(annotation.left, path, env) | self.annotation(annotation.right, path, env)
        if isinstance(annotation, ast.Subscript):
            container = ast.unparse(annotation.value).split(".")[-1]
            if container in {"dict", "Dict", "Mapping", "MutableMapping"} and isinstance(annotation.slice, ast.Tuple):
                return {("dict_value", target) for kind, target in self.annotation(annotation.slice.elts[-1], path, env)
                        if kind == "typed_instance"} or UNKNOWN
            if container in {"Optional", "Union"}:
                members = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
                return set().union(*(self.annotation(member, path, env) for member in members))
        if not isinstance(annotation, (ast.Name, ast.Attribute)):
            return UNKNOWN
        return {("typed_instance", target) for kind, target in self.value(annotation, path, env)
                if kind == "node" and self.graph.nodes[target].node_type == "class"} or UNKNOWN

    def value(self, expression, path, env, class_id="", depth=0):
        if expression is None or depth > 15:
            return UNKNOWN
        recurse = lambda expr: self.value(expr, path, env, class_id, depth + 1)
        if isinstance(expression, ast.Name):
            return env.get(expression.id, self.globals.get(path, {}).get(expression.id, UNKNOWN))
        if isinstance(expression, ast.IfExp):
            return recurse(expression.body) | recurse(expression.orelse)
        if isinstance(expression, ast.Subscript):
            return {("typed_instance", target) for kind, target in recurse(expression.value)
                    if kind == "dict_value"} or UNKNOWN
        if isinstance(expression, ast.Attribute):
            result = set()
            for kind, target in recurse(expression.value):
                if kind == "module":
                    result.update(self.export(target, expression.attr))
                elif kind in {"instance", "typed_instance", "super", "node"} and target in self.graph.nodes:
                    if self.graph.nodes[target].node_type != "class":
                        continue
                    classes = self.subclasses(target) if kind == "typed_instance" else {target}
                    for candidate in classes:
                        values = self.attributes.get((candidate, expression.attr)) or self.method(candidate, expression.attr)
                        if kind == "typed_instance":
                            values = {("candidate" if k == "node" else k, v) for k, v in values}
                        result.update(values)
            return result or UNKNOWN
        if isinstance(expression, ast.Call):
            if isinstance(expression.func, ast.Attribute) and expression.func.attr == "get":
                mapped = {("typed_instance", target) for kind, target in recurse(expression.func.value)
                          if kind == "dict_value"}
                if mapped:
                    return mapped | UNKNOWN
            if isinstance(expression.func, ast.Name):
                if expression.func.id == "super" and class_id and not expression.args:
                    return {("super", base) for base in self.bases.get(class_id, [])} or UNKNOWN
                if expression.func.id == "getattr" and len(expression.args) == 2:
                    name = expression.args[1]
                    if isinstance(name, ast.Constant) and isinstance(name.value, str):
                        return recurse(ast.Attribute(value=expression.args[0], attr=name.value))
            result = set()
            for kind, target in recurse(expression.func):
                if kind not in {"node", "candidate"}:
                    continue
                if self.graph.nodes[target].node_type == "class":
                    result.add(("instance", target))
                else:
                    definition = self.definitions.get(target)
                    annotation = getattr(definition.syntax, "returns", None) if definition else None
                    if annotation:
                        # Resolve return hints in the callee's module, not the caller's.
                        result.update(self.annotation(annotation, definition.node.relative_path, {}))
            return result or UNKNOWN
        return UNKNOWN

    def build(self):
        # Initializer fields improve self.service.method() without guessing by suffix.
        definitions = sorted(self.definitions.values(), key=lambda d: d.node.name != "__init__")
        for definition in definitions:
            if definition.node.node_type == "class":
                continue
            path = definition.node.relative_path
            env = {}
            scope = definition.scope
            while scope:
                # Python method bodies do not inherit class namespace as bare names.
                scope_node = self.scope_definitions.get((path, scope))
                if scope_node and scope_node.node.node_type != "class":
                    for name, values in self.scopes.get((path, scope), {}).items():
                        env.setdefault(name, values)
                scope = scope.rpartition(".")[0]
            args = definition.syntax.args
            for name in local_bindings(definition.syntax.body):
                env[name] = UNKNOWN
            for parameter in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                env[parameter.arg] = self.annotation(parameter.annotation, path, env)
            for parameter in (args.vararg, args.kwarg):
                if parameter:
                    env[parameter.arg] = UNKNOWN
            decorators = [ast.unparse(d) for d in definition.syntax.decorator_list]
            positional = [*args.posonlyargs, *args.args]
            if definition.class_id and positional and "staticmethod" not in decorators:
                env[positional[0].arg] = {("typed_instance", definition.class_id)}
            BodyAnalyzer(self, definition, env).statements(definition.syntax.body)
        return self.graph


class BodyAnalyzer(ast.NodeVisitor):
    def __init__(self, resolver, definition, env):
        self.resolver = resolver
        self.definition = definition
        self.env = dict(env)
        self.conditions = []

    def value(self, node):
        return self.resolver.value(node, self.definition.node.relative_path, self.env,
                                   self.definition.class_id)

    def statements(self, statements):
        for statement in statements:
            self.visit(statement)
            if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                break

    def bind(self, target, values):
        if isinstance(target, ast.Name):
            self.env[target.id] = values
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self.bind(item, UNKNOWN)
        elif isinstance(target, ast.Attribute) and self.definition.node.name == "__init__":
            if isinstance(target.value, ast.Name) and target.value.id == "self" and self.definition.class_id:
                self.resolver.attributes[(self.definition.class_id, target.attr)] = values

    def visit_Assign(self, node):
        self.visit(node.value)
        values = self.value(node.value)
        for target in node.targets:
            self.bind(target, values)

    def visit_AnnAssign(self, node):
        if node.value:
            self.visit(node.value)
        values = self.value(node.value) if node.value else self.resolver.annotation(
            node.annotation, self.definition.node.relative_path, self.env)
        if values == UNKNOWN:
            values = self.resolver.annotation(node.annotation, self.definition.node.relative_path, self.env)
        self.bind(node.target, values)

    def visit_NamedExpr(self, node):
        self.visit_Assign(ast.Assign(targets=[node.target], value=node.value))

    def visit_AugAssign(self, node):
        self.visit(node.value)
        self.bind(node.target, UNKNOWN)

    def visit_Delete(self, node):
        for target in node.targets:
            self.bind(target, UNKNOWN)

    def visit_Import(self, node):
        self.env.update(self.resolver.import_bindings(self.definition.node.relative_path, node))

    visit_ImportFrom = visit_Import

    def visit_FunctionDef(self, node):
        values = self.resolver.scopes.get((self.definition.node.relative_path,
                                          self.definition.node.qualified_name), {}).get(node.name, UNKNOWN)
        self.env[node.name] = values
        # Only definition-time expressions execute in this scope, never its body.
        for expression in [*node.decorator_list, *node.args.defaults,
                           *(d for d in node.args.kw_defaults if d is not None)]:
            self.visit(expression)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.env[node.name] = self.resolver.scopes.get(
            (self.definition.node.relative_path, self.definition.node.qualified_name), {}).get(node.name, UNKNOWN)

    def visit_Lambda(self, node):
        # Lambda bodies require their own invocation context; leave dynamic targets unresolved.
        for default in node.args.defaults:
            self.visit(default)

    def branch(self, statements, label, initial):
        self.env = dict(initial)
        self.conditions.append(label[:500])
        self.statements(statements)
        self.conditions.pop()
        return dict(self.env)

    def merge(self, branches):
        self.env = {name: set().union(*(branch.get(name, UNKNOWN) for branch in branches))
                    for name in set().union(*(branch.keys() for branch in branches))}

    def visit_If(self, node):
        self.visit(node.test)
        if isinstance(node.test, ast.Constant) and isinstance(node.test.value, bool):
            self.statements(node.body if node.test.value else node.orelse)
            return
        initial = dict(self.env)
        yes = self.branch(node.body, f"if {ast.unparse(node.test)}", initial)
        no = self.branch(node.orelse, f"else of line {node.lineno}", initial)
        self.merge([yes, no])

    def visit_For(self, node):
        self.visit(node.iter)
        initial = dict(self.env)
        self.bind(node.target, UNKNOWN)
        body = self.branch(node.body, f"loop at line {node.lineno}", self.env)
        self.merge([initial, body])
        self.statements(node.orelse)

    visit_AsyncFor = visit_For

    def visit_With(self, node):
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars:
                self.bind(item.optional_vars, UNKNOWN)
        self.statements(node.body)

    visit_AsyncWith = visit_With

    def visit_ListComp(self, node):
        initial = dict(self.env)
        for generator in node.generators:
            self.visit(generator.iter)
            self.bind(generator.target, UNKNOWN)
            for condition in generator.ifs:
                self.visit(condition)
        self.conditions.append("comprehension: candidate execution only")
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.conditions.pop()
        self.env = initial

    visit_SetComp = visit_ListComp
    visit_DictComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def visit_While(self, node):
        self.visit(node.test)
        initial = dict(self.env)
        body = self.branch(node.body, f"while {ast.unparse(node.test)}", initial)
        self.merge([initial, body])
        self.statements(node.orelse)

    def visit_Try(self, node):
        initial = dict(self.env)
        success = self.branch([*node.body, *node.orelse], f"try at line {node.lineno}", initial)
        branches = [success]
        for handler in node.handlers:
            handler_env = {**initial, **({handler.name: UNKNOWN} if handler.name else {})}
            branches.append(self.branch(handler.body, f"except at line {handler.lineno}", handler_env))
        self.merge(branches)
        self.statements(node.finalbody)

    def visit_Call(self, node):
        values = self.value(node.func)
        targets = [(kind, target) for kind, target in values if kind in {"node", "candidate"}]
        path = self.definition.node.relative_path
        site = {"relative_path": path, "line": node.lineno,
                "expression": ast.unparse(node)[:500], "conditions": list(self.conditions),
                "resolution": "inferred" if len(values) > 1 or any(k == "candidate" for k, _ in targets) else "resolved"}
        if not targets:
            self.resolver.graph.unresolved_calls.append({**site, "source_id": self.definition.node.node_id,
                                                        "reason": "external_or_dynamic_target"})
        for _, target in targets:
            self.resolver.graph.add_edge(self.definition.node.node_id, target, "calls",
                                         certainty=site["resolution"], sites=[site])
            if self.resolver.graph.nodes[target].node_type == "class":
                for _, initializer in self.resolver.method(target, "__init__"):
                    self.resolver.graph.add_edge(self.definition.node.node_id, initializer, "calls",
                                                 certainty="inferred", sites=[{**site, "resolution": "constructor_init_candidate"}])
        self.generic_visit(node)


def build_from_sources(sources: dict[str, str]) -> CodeGraph:
    """Build from saved snapshots as well as local source, without execution."""
    return Resolver(sources).build()


def local_bindings(statements) -> set[str]:
    """Python assignment shadows globals throughout a function, even before assignment."""
    class Bindings(ast.NodeVisitor):
        def __init__(self):
            self.names = set()
            self.nonlocal_names = set()

        def visit_Name(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                self.names.add(node.id)

        def visit_FunctionDef(self, node):
            self.names.add(node.name)

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef

        def visit_Import(self, node):
            self.names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

        def visit_ImportFrom(self, node):
            self.names.update(alias.asname or alias.name for alias in node.names)

        def visit_Global(self, node):
            self.nonlocal_names.update(node.names)

        visit_Nonlocal = visit_Global

        def visit_Lambda(self, node):
            pass

        def visit_ListComp(self, node):
            pass

        visit_SetComp = visit_ListComp
        visit_DictComp = visit_ListComp
        visit_GeneratorExp = visit_ListComp

        def visit_ExceptHandler(self, node):
            if node.name:
                self.names.add(node.name)
            self.generic_visit(node)

    visitor = Bindings()
    for statement in statements:
        visitor.visit(statement)
    return visitor.names - visitor.nonlocal_names
