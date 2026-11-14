# OpenAI repository agent

[Back to README](../README.md)

The project uses OpenAI GPT-6 Luna. Set `OPENAI_API_KEY`,
`OPENAI_MODEL=gpt-6-luna`, and `LLM_BACKEND=openai`.
Credentials belong in `backend/.env` or the deployment's secret environment,
never in source control.

Paste the key directly after `OPENAI_API_KEY=` in `backend/.env`.
The selected model is `gpt-6-luna`, using the OpenAI Responses API with
`OPENAI_REASONING_EFFORT=low`. Model access depends on the API account.

## Upgrade an existing installation

1. Install backend dependencies from [requirements](../backend/requirements.txt).
2. Update your environment from [the example](../backend/.env.example).
3. From `backend/`, run `python -m scripts.init_db` to create missing tables,
   including `repository_files` and `repository_graph_analysis`. This adds tables;
   it does not restore deleted data or migrate arbitrary existing column changes.
4. If source snapshots are missing or the source changed, re-index company repositories:
   `python -m scripts.index_company_repo taskflow_api` and
   `python -m scripts.index_company_repo inventory_api`.
   These commands replace the repository's old index in the configured DB.
   If snapshots already exist and only the graph needs upgrading, use
   `python -m scripts.refresh_code_graph taskflow_api` (and the corresponding
   command for `inventory_api`) instead. This keeps embeddings and clears imported
   runtime observations; see [the graph guide](./call-graph.md).
5. Restart the API after code/configuration changes and load a repository into a new session.

Old indexes can still load. If original source snapshots are absent, the API
returns a re-index warning; source reads use legacy chunk reconstruction and may
omit unindexed lines. Re-indexing captures full supported-file content. Chat never
reads source files from the server filesystem.

Embeddings continue to use the local sentence-transformers model. Switching the
LLM to OpenAI does not change the local embedding model.

## Agent execution

[The loop](../backend/src/agent_core/agent_loop.py) sends the question and bounded
recent exchanges to OpenAI. [The registry](../backend/src/agent_core/tool_registry.py)
exposes `search_code`, `find_definitions`, `read_file`, `find_references`,
`find_callers`, `find_callees`, `impact_analysis`, `trace_flow`, `count_symbols`,
`count_files`, and `finish_answer`.

Arguments are validated with Pydantic. Tools are scoped to the loaded repository.
`read_file` returns up to 80 source lines; long tool results are explicitly
truncated so the model can narrow its query. Tools return structured errors for
recovery. Identical successful calls are cached within the run; a third identical
attempt stops the run. OpenAI Responses output items and call IDs are preserved,
including encrypted reasoning items when returned. Private reasoning is not added to traces.

`finish_answer` must select source IDs issued by tools during the current turn.
Unknown IDs and unsupported source-free completion are rejected. Count queries
may complete with an exact tool count and no source IDs, including a zero count.
Source validation checks indexed paths and ranges; it cannot prove that every
sentence follows from the sources. Static graph relationships remain approximate.

Graph tools now expose static/observed evidence filters, unresolved call sites,
potential impact paths and test candidates. Existing graph indexes should be
refreshed from DB snapshots; [the call graph guide](./call-graph.md) describes the
additive storage change and opt-in runtime recording/import workflow.

If OpenAI is disabled or cannot be constructed, the previous deterministic
workflow is used and missing configuration is reported. If OpenAI fails mid-run,
the loop returns a failure status and available evidence without claiming success.
This does not silently rerun an unbounded second investigation.

## Limits and response contract

| Setting | Default | Meaning |
| --- | --- | --- |
| `AGENT_MAX_STEPS` | 8 | Model turns |
| `AGENT_MODE` | loop | `loop` for the agent, `workflow` for baseline comparison |
| `AGENT_MAX_TOOL_CALLS` | 16 | Attempted calls, including finish and invalid calls |
| `AGENT_TIMEOUT_SECONDS` | 90 | Run deadline; remaining time is given to OpenAI |
| `AGENT_MAX_CONTEXT_CHARS` | 100000 | Conservative serialized-context size guard |
| `AGENT_TOOL_RESULT_CHARS` | 12000 | Tool payload compaction threshold |
| `AGENT_HISTORY_TURNS` | 4 | Retained recent exchanges per session |

The deadline is checked between operations; an already running synchronous local
tool is allowed to return. It is not forcibly interrupted. These are operational
bounds, not an exact currency budget. Model usage is recorded when returned.

`POST /chat` keeps `answer`, `query_type`, `tools_used`, `sources`, `raw_results`,
and `warnings`, and adds `status`. Loop statuses are `completed`,
`insufficient_evidence`, `budget_exhausted`, `stalled`, and `model_error`.
Initialization fallback may return `fallback`. `raw_results` includes `steps`,
`stop_reason`, usage, elapsed time, and source excerpts. Both UIs show the trace.

History is bounded, process-local, and reset on repository changes. A restart or
multiple API workers require loading a session again; distributed session storage
is outside this change. Prior conversation supplies context, not current evidence.

## Validation

From `backend/`, run:

```sh
python -m unittest discover -s tests -v
```

The tests require the declared Python dependencies but no API key, downloaded
embedding model, or external database. They use scripted model decisions, a real
OpenAI Responses adapter with local HTTP transport, and SQLite for snapshot storage.

Live evaluation uses the configured database and OpenAI API:

```sh
python -m scripts.run_eval --repo taskflow_api --repo inventory_api
python -m scripts.run_eval --repo taskflow_api --repo inventory_api --agent-mode workflow
```

The historical 100-case benchmark references three fixture repositories absent
from this checkout, and some expectations refer to files/symbols absent from the
current fixtures. The runner reports missing repositories before indexing; use
`--skip-missing-repos` explicitly if desired. The [historical evaluation scores](./evaluation.md#historical-deepseek-reference)
are not results for this agent. Compare baseline and new runs on corrected, identical
fixtures, including multi-step retrieval, ambiguous symbols, errors, abstention,
follow-up questions, latency, and tool-call costs. Summary output also records
completion rate, mean tool calls, model turns, and token usage. A completed status
describes execution, not a guarantee that the answer is correct.
