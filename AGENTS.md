# AGENTS.md — Antigravity & Coding Agent Instructions

This repository is the **Common Starter** for the **AI Innovators Expedition Hackathon** (Google London, 29–30 October 2026). Every Table forks this repository and activates its assigned **Seed Pack** (`t01`..`t10`, or `t00_example`).

## 1. Hackathon Must-Haves (Gate Criteria)
Your bonus points only count once all 5 Must-Haves are shown working; otherwise your Table keeps its core score (max 14):
1. **Google ADK (`google-adk`)**: Root agent defined in `app/agent.py` (`root_agent`).
2. **Vertex AI Agent Runtime (Reasoning Engine)**: Deployed via `make deploy` (`deploy/deploy.py`) to `europe-west1` or `europe-west2`.
3. **Google Antigravity**: Used by all Table members in parallel (each participant has a pre-configured `@gcplab.me` sandbox account with Agent Platform Pay-As-You-Go, collaborating via a shared private GitHub repository created by the Table's **Repo Captain**).
4. **Gemini Model**: Configured via `GEMINI_MODEL` in `.env` (default `gemini-3.8-flash` on `GOOGLE_CLOUD_LOCATION=global`).
5. **Evaluation Pipeline**: Golden `.test.json` evaluation suite executed via `make eval` (`eval/run_eval.py`).

## 2. Non-Negotiable Coding Rules

### Read Model & Location from Environment Only
- **Never hardcode a model version string** (such as `"gemini-..."`) anywhere in Python source files.
- Always read `GEMINI_MODEL` and `GOOGLE_CLOUD_LOCATION` via `resolve_env_config(...)` or `os.environ`.
- **Never use `-latest` model aliases** (`gemini-flash-latest` is rejected by `app/agent.py` because aliases fail on regional endpoints and Provisioned Throughput).
- Keep `GOOGLE_CLOUD_LOCATION=global` for `gemini-3.8-flash`, while `AGENT_RUNTIME_LOCATION=europe-west1` is used for Vertex AI Agent Runtime deployment.

### How to Add or Modify an ADK Tool
1. **Never raise unhandled exceptions inside a tool body.** In ADK on Agent Runtime, an uncaught exception crashes the execution node and kills the response stream. Always wrap tool logic in `try...except Exception as exc:` and return a `json.dumps({"status": "ERROR", "error": str(exc)})` string.
2. **Resolve config at call time (inside the function), never at module import time.** The Agent Runtime container does not have your workstation `.env` file and sets `AGENT_ENGINE_PROJECT` / `GOOGLE_CLOUD_PROJECT` at runtime:
   ```python
   def my_new_tool(customer_id: str) -> str:
       """Look up customer details by ID.

       Args:
           customer_id: Unique customer identifier (e.g. 'CUST-101').

       Returns:
           JSON string with the customer profile or error status.
       """
       try:
           project = (
               os.environ.get("GOOGLE_CLOUD_PROJECT")
               or os.environ.get("AGENT_ENGINE_PROJECT")
               or ""
           ).strip()
           # ... query BigQuery or run domain logic ...
           return json.dumps({"status": "SUCCESS", "customer_id": customer_id})
       except Exception as exc:
           return json.dumps({"status": "ERROR", "error": str(exc)})
   ```
3. **Register the tool**: Append your function to `TOOLS` in `seed_packs/<your_pack>/tools.py` (or pass it to `LlmAgent(tools=...)` in `app/agent.py`). For a mock action in `mcp_server.py`, decorate it with `@mcp.tool()` **and** add it to `MCP_TOOLS = [...]` at the bottom of that file; the loader only reads this explicit list (needed for `make eval` and Agent Runtime).
4. **No raw `{braces}` in agent instructions**: ADK treats `{identifier}` inside `instruction` strings as session-state variable lookups and raises `KeyError` if missing. Use square brackets `[identifier]` instead. `assert_no_state_tokens()` in `app/loader.py` guards against this automatically.

### Python 3.12 & Cloudpickle Parity
- Vertex AI Agent Runtime containers run **Python 3.12**. Always run commands through `.venv/bin/python` (created with `uv venv --python 3.12 .venv`).
- Do not add unpinned packages without adding them to both `pyproject.toml` and `PINNED_REQUIREMENTS` in `deploy/deploy.py`.
- In Agent Runtime, local stdio MCP subprocesses are disabled (`ENABLE_MCP_STDIO=0`), and mock action functions from `mcp_server.py` are automatically exposed as plain Python function tools so local and cloud behavior match.

### Deployment Safety
- Use only `make deploy`, `make test-remote` and `make delete`. `make deploy` updates the agent saved in `.deployed_agent.json`; never edit deploy scripts to delete or recreate agents automatically.
- `make delete` removes exactly one agent (the saved one, or `RESOURCE=projects/.../reasoningEngines/<id>`). Never delete Google Cloud resources you did not create.
- After any change to `.env`, tools or instructions: `make test`, `make eval`, then `make deploy` + `make test-remote` (the container has no `.env`; config is baked in at deploy time).

### Secrets & Git Hygiene
- **Never commit secrets**: `.env`, `.deployed_agent.json`, `*.key.json`, and `*credentials*.json` are gitignored. Never stage or hardcode API keys, service account JSON keys, or customer PII.

## 3. Key Commands
```bash
make setup               # Create Python 3.12 .venv and install pinned dependencies
make seed PACK=t08       # Create BigQuery dataset & load synthetic Seed Pack tables
make test                # Run fast offline pytest suite (loader, agent build, eval schema)
make dev                 # Start local ADK Web UI on http://127.0.0.1:8000
make eval                # Run ADK golden evaluations (.test.json) and print pass/fail summary
make eval-validate       # Validate eval JSON only (no Gemini calls)
make deploy              # Deploy (or update) agent on Vertex AI Agent Runtime (europe-west1)
make test-remote         # Stream a live verification query to the deployed Agent Runtime agent
make delete              # Delete the deployed Agent Runtime agent saved in .deployed_agent.json
```

## 4. Agentic SDLC & CI/CD Bonus Practices (+1 pt Each)
Tables can unlock two dedicated engineering-rigor Bonus points (`+1 pt` each once all 5 Must-Haves are met):
1. **Agentic SDLC Practices (`+1 pt` — demonstrate at least 2 of 3 pillars)**:
   - **Custom Primitives & Context**: Extend this `AGENTS.md` with Table-specific domain rules, or add custom Antigravity rules, skills, or subagents under `.agents/`.
   - **Spec / Eval-First Loop (Plan-Act-Verify & TDD)**: Draft a brief plan and add golden test cases in `seed_packs/<pack>/eval/golden.test.json` or unit tests in `tests/test_starter.py` *before* implementing new tools or prompts, then verify with `make test` and `make eval`.
   - **Parallel Git Collaboration**: Use feature branches, `git worktree` isolation, and Pull Requests across the 5 Table members rather than pushing untested code directly to `main`.
2. **Automated CI/CD Pipeline (`+1 pt`)**:
   - Wire GitHub Actions and/or Google Cloud Build (`cloudbuild.yaml`) to run automated quality gates (`make test` + `make eval-validate`/`make eval`) and deploy to Vertex AI Agent Runtime (`make deploy`). Note: `@gcplab.me` sandbox projects forbid exporting Service Account JSON keys, so use Cloud Build (native GCP service agent) or Workload Identity Federation for cloud steps. See `docs/STARTER.md` for copy-paste templates.
