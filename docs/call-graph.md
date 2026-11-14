# Call graph evidence

[Back to README](../README.md)

The graph separates **static candidate calls** from **runtime observations**. Neither proves a function's business meaning or that a future edit will introduce a bug.

## Static resolution

[The resolver](../backend/src/graph/static_analysis.py) analyzes Python source without importing or executing it:

- Resolves lexical/module names, explicit imports, aliases, relative imports and bounded re-export chains instead of globally matching short names.
- Separates nested function bodies and preserves recursive edges.
- Tracks simple callable/instance aliases, rebinding and unions of possible values across branches.
- Uses simple receiver/return annotations, typed mapping values, initializer fields, inheritance/override candidates, zero-argument `super()` and literal `getattr` targets.
- Retains call-site lines, expressions and conditions. Unknown/external targets and parse errors remain visible.
- Reports potential impact paths and test candidates, without automatically executing tests.

`resolved` describes a static name binding, not certainty of execution. `inferred` describes a candidate. `observed_only` identifies a runtime relationship without a static call site. Old indexes use `legacy_unknown` until refreshed.

## Record and import runtime evidence

[The recorder](../backend/src/graph/runtime_trace.py) uses Python's [`sys.setprofile`](https://docs.python.org/3.10/library/sys.html#sys.setprofile) events to map executing code objects to indexed definitions. It records direct caller/callee pairs, caller lines and call-event counts, without collecting arguments, locals, return values or API keys.

The collector covers **Python calls in the current thread**. It excludes child threads/processes, native C calls, module-level calls and unmapped/generated functions. Coroutine/generator resumptions can add call events, so counts are not guaranteed to equal distinct invocations. The result aggregates relationships; it is not an execution timeline.

This is opt-in local instrumentation for **trusted code**. The recording CLI executes the selected program with normal user permissions and is not a sandbox. Chat and uploaded repositories never trigger program execution automatically.

### 1. Refresh an old graph

From `backend/`, with the project virtual environment:

```sh
python -m scripts.refresh_code_graph taskflow_api
python -m scripts.refresh_code_graph inventory_api
```

This rebuilds from PostgreSQL source snapshots, without regenerating embeddings or reading local source. It creates the additive `repository_graph_analysis` sidecar table if needed, and clears previous runtime observations. Fresh indexing also stores the new evidence automatically.

### 2. Record a trusted script or test module

Replace the example paths with your own repository and entry point:

```sh
python -m scripts.record_runtime_calls --repo ../company_repos/my_repo --script ../company_repos/my_repo/smoke_test.py --output data/runtime/my_repo-trace.json --label smoke-test
```

For a test runner, pass its arguments after `--`:

```sh
python -m scripts.record_runtime_calls --repo ../company_repos/my_repo --module unittest --output data/runtime/my_repo-tests.json --label unit-tests -- discover -s ../company_repos/my_repo/tests
```

Reports are written even if the target raises or exits with a failure; the command still propagates that failure. `SystemExit(0)` counts as completed. A default cap of 100,000 matched call events records truncation explicitly. Existing profiler hooks are not replaced. Run with your normal isolated environment and test timeouts; the collector does not impose a program timeout.

The CLI puts the target repo on the import path and removes the tooling backend root for external repos, so a target namespace such as `app/` is not shadowed by the backend's Streamlit package. The original path is restored after execution. Broader collisions with already-loaded tooling modules still require an appropriately isolated target environment.

### 3. Import into the indexed repo

```sh
python -m scripts.import_runtime_calls my_repo data/runtime/my_repo-tests.json
```

The report must match the graph and indexed Python source hashes. Stale versions, unknown nodes and invalid caller lines are rejected before mutation. Re-importing the same report is idempotent. A graph stores at most 100 runs; refresh to reset evidence. Reload the repo session after importing.

Reports are user-supplied local observations, not cryptographically authenticated attestations. Import does not independently repeat the run. Keep artifacts in the ignored runtime directory.

## Agent tools

`find_callers`, `find_callees`, `impact_analysis` and `trace_flow` accept:

| `evidence` | Meaning |
|---|---|
| `all` (default) | Static candidates plus imported runtime relationships |
| `static` | Static call sites, including legacy edges before refresh |
| `observed` | Relationships observed in the imported runs |

Results include `relationships` with `sites` and per-run `observations`, unresolved calls, diagnostics, run provenance and definition/docstring context. `analysis_kind` is `static` or `hybrid`. `runtime_observed=true` applies to that relationship in those runs only. Top-level `proves_execution=false` means there is no general execution guarantee; `proves_breakage=false` is always explicit.

Impact results include dependency paths and `tests_to_review`. Traversal has depth and node limits. Neither a missing static edge nor an unobserved runtime edge establishes impossibility. The agent is instructed to read implementations and tests for business behavior, and to avoid claiming that dependency paths prove a regression.

To establish a regression, reproduce a failure on the changed version and compare with the same test/input on the baseline. This graph does not automatically perform that experiment.

## Remaining limits and research basis

Complex return-value flow, callback parameters, framework injection, dictionary dispatch, monkey patching, descriptors, custom metaclasses, complex multiple-inheritance MRO, closures and module initialization can still be incomplete. Docstrings express intent and can disagree with implementation.

[CodeQL's model](https://codeql.github.com/codeql-standard-libraries/python/semmle/python/pointsto/CallGraph.qll/type.CallGraph%24FunctionInvocation.html) describes a static approximation to dynamic calls. Python's profiler supplies observed events for a particular execution, with [thread-specific profiling semantics](https://docs.python.org/3.10/library/sys.html#sys.setprofile). Combining them expands evidence without making either complete proof.

Regression tests cover import collisions, nested scopes, recursion, rebinding, branches, annotations, inheritance, unresolved calls, profiler cleanup, stale reports, DB round trips and runtime-only dynamic calls:

```sh
python -m unittest discover -s tests -v
```
