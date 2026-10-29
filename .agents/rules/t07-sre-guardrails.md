---
description: Table 7 SRE & SecOps Guardrails for Self-Healing Infrastructure Copilot
---

# Table 7 (`t07_self_healing_ops`) — SRE & SecOps Guardrails

1. **Tool Documentation Sync (`check_packs.py`)**:
   - Every tool in `seed_packs/t07_self_healing_ops/tools.py` (`TOOLS`) and `seed_packs/t07_self_healing_ops/mcp_server.py` (`MCP_TOOLS`) must have complete type annotations, a docstring, and be listed in backticks in:
     - `seed_packs/t07_self_healing_ops/pack.yaml`
     - `seed_packs/t07_self_healing_ops/CHALLENGE_CARD.md`
     - `challenges/T07-self_healing_ops.md`
     - `seed_packs/README.md` (on the `| **T07** |` row)
2. **Cloudpickle-Safe Callbacks**:
   - All ADK callbacks (`before_tool_callback`, `after_tool_callback`) in `app/agent.py` must be pure top-level functions with zero module-level unpicklable state (`Lock`, open files, or network clients) so `cloudpickle.dumps(root_agent)` succeeds for Vertex AI Agent Runtime deployment.
3. **Deterministic Golden Evaluation IDs**:
   - `eval/run_eval.py` must reset `.state.json` and `/tmp/t07_self_healing_ops_state.json` before starting `run_live_evaluation` so `case_04_execute_rollback` (`RB-1001`) and `case_05_scale_replicas_safely` (`SCALE-2001`) remain deterministic across repeated runs.
4. **Strict Environment Model Resolution**:
   - Never hardcode `"gemini-..."` strings in Python source files; always resolve `GEMINI_MODEL`, `GEMINI_IMAGE_MODEL`, and `GOOGLE_CLOUD_LOCATION` from environment variables at runtime.
