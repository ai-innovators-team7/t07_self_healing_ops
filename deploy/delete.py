"""Delete the deployed Vertex AI Agent Runtime (Reasoning Engine) instance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines

from app.loader import REPO_ROOT
from app.preflight import format_error, parse_reasoning_engine_name
from deploy.deploy import STATE_FILE
from deploy.test_remote import resolve_deployed_resource_name


def _saved_resource_name(state_file: Path) -> str | None:
    if not state_file.exists():
        return None
    try:
        return str(json.loads(state_file.read_text(encoding="utf-8")).get("resource_name") or "").strip()
    except (OSError, ValueError):
        return None


def delete_remote_agent(
    resource_name: str | None = None,
    *,
    state_file: Path | None = None,
) -> str:
    """Force-delete exactly one ReasoningEngine (and its sessions).

    The target is the explicit `resource_name`, `AGENT_ENGINE_RESOURCE_NAME`, or
    the resource saved by `make deploy`; nothing else is ever deleted. The state
    file is removed only when it records the resource that was just deleted.
    """
    load_dotenv(REPO_ROOT / ".env")
    state_path = state_file or STATE_FILE
    target_resource = resolve_deployed_resource_name(resource_name, state_file=state_path)
    parts = parse_reasoning_engine_name(target_resource)

    print(f"[delete] Deleting Agent Runtime instance: {target_resource} ...")
    vertexai.init(project=parts["project"], location=parts["location"])
    remote = agent_engines.get(target_resource)
    remote.delete(force=True)

    if _saved_resource_name(state_path) == target_resource:
        state_path.unlink()
    print(f"DELETED_RESOURCE_NAME: {target_resource}")
    return target_resource


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete the deployed Agent Runtime agent.")
    parser.add_argument(
        "--resource-name",
        default=None,
        help="Full projects/.../reasoningEngines/... name (default: the one saved by make deploy).",
    )
    args = parser.parse_args()
    try:
        delete_remote_agent(resource_name=args.resource_name)
    except Exception as exc:
        print(format_error(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
