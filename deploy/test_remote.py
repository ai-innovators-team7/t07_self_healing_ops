"""Send a live verification query to the deployed Agent Runtime (Reasoning Engine) agent."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines

from app.loader import REPO_ROOT
from app.preflight import format_error, parse_reasoning_engine_name
from deploy.deploy import STATE_FILE

GENERIC_PROMPT = "Briefly introduce yourself, then use one of your tools to show what you can do."


def resolve_deployed_resource_name(
    explicit_name: str | None = None,
    *,
    state_file: Path | None = None,
) -> str:
    """Resolve the deployed ReasoningEngine resource name from args, env, or `.deployed_agent.json`."""
    state_path = state_file or STATE_FILE
    if explicit_name and explicit_name.strip():
        return explicit_name.strip()
    env_name = os.environ.get("AGENT_ENGINE_RESOURCE_NAME", "").strip()
    if env_name:
        return env_name
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"{state_path.name} is unreadable ({exc}). Pass --resource-name explicitly."
            ) from exc
        if data.get("resource_name"):
            return str(data["resource_name"]).strip()
    raise RuntimeError(
        "No deployed agent resource name found. Run `make deploy` first or pass --resource-name."
    )


def default_prompt_for_deployment(state_file: Path | None = None) -> str:
    """Use the first golden eval question of the deployed Seed Pack as the probe prompt."""
    state_path = state_file or STATE_FILE
    try:
        pack_id = json.loads(state_path.read_text(encoding="utf-8")).get("pack_id") or ""
    except (OSError, ValueError):
        pack_id = ""
    if not pack_id or pack_id == "hello_fallback":
        return GENERIC_PROMPT
    try:
        from eval.run_eval import discover_eval_files, load_eval_cases

        for file_path in discover_eval_files(pack_id):
            for case in load_eval_cases(file_path)[1]:
                if case.turns and case.turns[0].user_text:
                    return case.turns[0].user_text
    except (FileNotFoundError, ValueError) as exc:
        print(f"[test-remote] Could not read golden evals for '{pack_id}' ({exc}); using a generic prompt.")
    return GENERIC_PROMPT


def query_remote_agent(
    *,
    resource_name: str | None = None,
    message: str | None = None,
) -> str:
    """Create a remote session, stream a query, and return the assembled text reply."""
    load_dotenv(REPO_ROOT / ".env")
    target_resource = resolve_deployed_resource_name(resource_name)
    name_parts = parse_reasoning_engine_name(target_resource)
    project_id = name_parts["project"]

    prompt = (
        message or os.environ.get("TEST_REMOTE_PROMPT") or default_prompt_for_deployment()
    ).strip()

    print(f"[test-remote] Connecting to {target_resource} ...")
    vertexai.init(project=project_id, location=name_parts["location"])
    remote = agent_engines.get(target_resource)

    session = remote.create_session(user_id="hackathon-probe")
    session_id = session.get("id") if isinstance(session, dict) else session.id
    print(f"[test-remote] Session created: {session_id}")
    print(f"[test-remote] Sending query: {prompt!r}")

    text_chunks: list[str] = []
    tool_calls: list[str] = []
    for event in remote.stream_query(
        user_id="hackathon-probe",
        session_id=session_id,
        message=prompt,
    ):
        if isinstance(event, dict):
            content = event.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else event.get("parts", [])
            for part in parts:
                if not isinstance(part, dict):
                    continue
                if "function_call" in part and isinstance(part["function_call"], dict):
                    tool_calls.append(str(part["function_call"].get("name", "")))
                if "text" in part and part["text"]:
                    text_chunks.append(str(part["text"]))

    full_reply = "".join(text_chunks).strip()
    if not full_reply:
        raise RuntimeError(
            "Deployed agent returned an empty stream. Inspect logs with:\n"
            f'  gcloud logging read \'resource.type="aiplatform.googleapis.com/ReasoningEngine"\' '
            f"--project={project_id} --limit=30 --freshness=15m"
        )

    print(f"[test-remote] Tool calls observed: {tool_calls}")
    print(f"REMOTE_REPLY: {full_reply}")
    return full_reply


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the deployed Agent Runtime agent.")
    parser.add_argument("--resource-name", default=None, help="ReasoningEngine resource name.")
    parser.add_argument("--message", default=None, help="Query message to send.")
    args = parser.parse_args()
    try:
        query_remote_agent(resource_name=args.resource_name, message=args.message)
    except Exception as exc:
        print(format_error(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
