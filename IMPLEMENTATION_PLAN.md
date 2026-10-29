# Implementation Plan — Table 7: Self-Healing Infrastructure & Security Copilot (`t07_self_healing_ops`)

> [!IMPORTANT]
> **Current Status (`expedition-dn26lon-5923`)**
> - **BigQuery (`seed_t07`) & GCS**: Seeded in `EU` (`service_incidents`: 100 rows, `deployment_releases`: 80 rows, `slo_runbooks`: 60 rows) and uploaded to `gs://expedition-dn26lon-5923-hackathon-staging/seed/t07/`.
> - **Baseline Golden Eval (`gemini-3.8-flash`)**: **5/5 cases passing (100%)** with `tool_score=1.00`.
> - **Antigravity Skill Installed**: `.agents/skills/council/SKILL.md` is configured as an Antigravity workspace skill (also fulfilling the `AGENTS.md` `.agents/skills/` **Agentic SDLC Bonus**).
> - **Local Dev Server**: `make dev` is live at `http://127.0.0.1:8000`.

---

## 1. Runtime Architecture (Pure Google ADK + FastMCP + BigQuery + Table 8 A2A)

- **Phase 1**: Credential & Environment Hardening (`app/preflight.py` & `seed_packs/t07_self_healing_ops/tools.py`)
- **Phase 2**: Deterministic Blast-Radius, Allowlist & Security Guardrails (`mcp_server.py` & `tools.py`)
  - `query_active_incidents`: Prompt-injection detection on `recent_log_snippet` (`INC-0019`).
  - `execute_canary_rollback`: Enforces `rollback_safe == True` and `target_stable_version == previous_stable_version` allowlist.
  - `scale_service_replicas`: Enforces global `[3, 40]` corridor AND service runbook `[min_safe_replicas, max_safe_replicas]`.
  - `annotate_incident_timeline`: Structured before/after remediation & security refusal audit trail.
- **Phase 3**: Tribe A2A Handshake with Sister Table 8 (`t08_travel_concierge`) for customer-facing services (`checkout-payment-svc`, `auth-token-gateway`).
- **Phase 4**: Prompt & Persona Hardening (`seed_packs/t07_self_healing_ops/pack.yaml`).
- **Phase 5**: Unit Tests (`tests/test_starter.py`), Live Golden Evals (`make eval PACK=t07`), `AGENTS.md` & `cloudbuild.yaml`.
- **Phase 6**: Live Cloud Deployment (`make deploy PACK=t07` & `make test-remote`) to Vertex AI Agent Runtime (`europe-west1`).
