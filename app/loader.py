"""Seed Pack plugin loader for the AI Innovators Expedition Starter repo.

Loads `seed_packs/<pack_id>/pack.yaml`, imports `TOOLS` from `tools.py`, and
optionally attaches `mcp_server.py` via ADK `McpToolset` (stdio) for local runs
while falling back to plain Python function tools for Vertex AI Agent Runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PACKS_DIR = REPO_ROOT / "seed_packs"


def _sanitize_google_application_credentials() -> None:
    """Remove stale or external GOOGLE_APPLICATION_CREDENTIALS so ADC is used."""
    gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if gac and ("docdigitizer" in gac.lower() or not Path(gac).is_file()):
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)


_sanitize_google_application_credentials()

# Regex to catch accidental `{identifier}` tokens in ADK instructions, which ADK
# interprets as session-state lookups (raising KeyError and blanking the reply).
_STATE_TOKEN_RE = re.compile(r"{+[^{}]*}+")
_ALLOWED_STATE_PREFIXES = ("{app:", "{user:", "{temp:")


def assert_no_state_tokens(instruction: str) -> None:
    """Raise ValueError if `instruction` contains raw `{...}` ADK session-state tokens."""
    bad = [
        tok
        for tok in _STATE_TOKEN_RE.findall(instruction or "")
        if not tok.startswith(_ALLOWED_STATE_PREFIXES)
    ]
    if bad:
        raise ValueError(
            f"Instruction contains unescaped ADK session-state tokens {bad[:5]}. "
            "Remove curly braces or use square brackets instead."
        )


def _replace_state_token(match: re.Match[str]) -> str:
    tok = match.group(0)
    if tok.startswith(_ALLOWED_STATE_PREFIXES):
        return tok
    inner = tok.strip("{}")
    return f"[{inner}]"


def sanitize_instruction(instruction: str) -> str:
    """Replace accidental `{identifier}` tokens with `[identifier]` so ADK never crashes."""
    return _STATE_TOKEN_RE.sub(_replace_state_token, instruction or "")


_PLACEHOLDER_MARKERS = ("your-gcp-project-id", "your-project-id")


def is_placeholder(value: str | None) -> bool:
    """Return True for template values copied verbatim from `.env.example`."""
    lowered = (value or "").strip().lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def resolve_env_config(key: str, default: str = "") -> str:
    """Read a config key from os.environ, falling back to .env or .env.example.

    Template placeholders such as `your-gcp-project-id` are treated as unset so
    that a half-edited `.env` never sends requests to a non-existent project or
    bucket.
    """
    val = os.environ.get(key, "").strip()
    if val and not is_placeholder(val):
        return val
    for env_file in (REPO_ROOT / ".env", REPO_ROOT / ".env.example"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                k, v = stripped.split("=", 1)
                if k.strip() == key:
                    parsed = v.strip().strip("'").strip('"')
                    if parsed and not is_placeholder(parsed):
                        return parsed
    return default


def hello_expedition_status(table_name: str = "Unassigned Table") -> str:
    """Return a status check for the AI Innovators Expedition Starter agent when no Seed Pack is set.

    Args:
        table_name: Name or number of the hackathon Table (e.g., 'Table 8').

    Returns:
        JSON string confirming the Starter agent is online and explaining how to activate a Seed Pack.
    """
    try:
        project = (
            os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("AGENT_ENGINE_PROJECT")
            or "unset"
        )
        return json.dumps({
            "status": "ONLINE",
            "mode": "hello_fallback",
            "table_name": table_name,
            "project": project,
            "hint": "Set SEED_PACK=t01..t10 (or t00_example) in .env and run `make seed PACK=<id>`.",
        })
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})


@dataclass
class LoadedSeedPack:
    """Resolved Seed Pack configuration and assembled ADK tool list."""

    pack_id: str
    table: int | str | None
    title: str
    tribe: str
    short_description: str
    instruction: str
    bigquery_dataset: str | None
    gcs_prefix: str | None
    mcp_server: str | None
    pack_dir: Path | None
    tools: list[Any] = field(default_factory=list)
    mcp_stdio_attached: bool = False


def resolve_pack_directory(pack_id: str, seed_packs_dir: Path = SEED_PACKS_DIR) -> Path:
    """Locate `seed_packs/<pack_id>` (exact match or `<pack_id>_*` prefix match)."""
    clean_id = pack_id.strip()
    exact = seed_packs_dir / clean_id
    if exact.is_dir() and (exact / "pack.yaml").exists():
        return exact

    matches = sorted(
        p for p in seed_packs_dir.glob(f"{clean_id}_*")
        if p.is_dir() and (p / "pack.yaml").exists()
    )
    if matches:
        return matches[0]

    raise FileNotFoundError(
        f"Seed Pack '{clean_id}' not found under {seed_packs_dir}. "
        f"Expected '{exact / 'pack.yaml'}' or '{clean_id}_*/pack.yaml'."
    )


def _tool_name(tool_obj: Any) -> str | None:
    if callable(tool_obj):
        try:
            return str(tool_obj.__name__)
        except AttributeError:
            return None
    return None


def _extract_mcp_module_functions(mcp_module_path: str) -> list[Callable[..., Any]]:
    """Import the pack's `mcp_server` module and return its explicit `MCP_TOOLS` list.

    Seed Pack contract: every `mcp_server.py` exports `MCP_TOOLS = [fn, ...]`
    (the same functions decorated with `@mcp.tool()`). Only this public list is
    used; FastMCP internals are never inspected, so MCP SDK upgrades cannot
    silently drop tools.

    Raises:
        ImportError: if the module declared in `pack.yaml` cannot be imported.
    """
    try:
        mod = importlib.import_module(mcp_module_path)
    except Exception as exc:
        raise ImportError(
            f"pack.yaml declares mcp_server '{mcp_module_path}' but it failed to import "
            f"({type(exc).__name__}: {exc}). Fix the module or remove `mcp_server` from pack.yaml."
        ) from exc

    explicit = vars(mod).get("MCP_TOOLS")
    if isinstance(explicit, (list, tuple)) and explicit:
        return [fn for fn in explicit if callable(fn)]

    logger.warning(
        "mcp_server '%s' does not export a non-empty MCP_TOOLS list; its mock actions "
        "will NOT be available in Agent Runtime or `make eval`. Add "
        "`MCP_TOOLS = [your_tool, ...]` at the bottom of mcp_server.py.",
        mcp_module_path,
    )
    return []


def _build_mcp_stdio_toolset(mcp_module_path: str) -> Any | None:
    """Create an ADK McpToolset connected to `python -m <mcp_module_path>` over stdio."""
    try:
        from google.adk.tools.mcp_tool import McpToolset
        from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
        from mcp import StdioServerParameters

        env = dict(os.environ)
        python_path = str(REPO_ROOT)
        if env.get("PYTHONPATH"):
            python_path = f"{python_path}{os.pathsep}{env['PYTHONPATH']}"
        env["PYTHONPATH"] = python_path

        return McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=["-m", mcp_module_path],
                    env=env,
                ),
            )
        )
    except Exception as exc:
        logger.warning(
            "Optional MCP stdio toolset for '%s' could not be initialized (%s); "
            "falling back to plain Python function tools.",
            mcp_module_path,
            exc,
        )
        return None


def _should_use_mcp_stdio(explicit_flag: bool | None) -> bool:
    """Determine whether to attach McpToolset (stdio) vs plain Python function tools.

    Inside Vertex AI Agent Runtime containers (or during `deploy/deploy.py`
    packaging where `ENABLE_MCP_STDIO=0`), stdio subprocesses are disabled and
    mock actions run as direct Python function tools.
    """
    if explicit_flag is not None:
        return explicit_flag
    env_flag = os.environ.get("ENABLE_MCP_STDIO", "").strip().lower()
    if env_flag in {"0", "false", "no", "off"}:
        return False
    if env_flag in {"1", "true", "yes", "on"}:
        return True
    # Detect cloud container runtime environments where workstation sys.executable is invalid
    if os.environ.get("AGENT_RUNTIME_DEPLOY") == "1" or os.environ.get("K_SERVICE"):
        return False
    return True


def load_seed_pack(
    pack_id: str | None = None,
    *,
    seed_packs_dir: Path = SEED_PACKS_DIR,
    enable_mcp_stdio: bool | None = None,
    strict_state_tokens: bool = False,
) -> LoadedSeedPack:
    """Load a Seed Pack by ID, or return the generic fallback pack when `pack_id` is unset."""
    resolved_id = (
        pack_id if pack_id is not None else os.environ.get("SEED_PACK", "")
    ).strip()

    if not resolved_id or resolved_id.lower() in {"none", "null", "hello"}:
        fallback_instruction = (
            "You are the AI Innovators Expedition Starter Agent running in fallback mode "
            "(no SEED_PACK selected). Use `hello_expedition_status` to check system readiness "
            "and guide the user to configure SEED_PACK in their .env file."
        )
        return LoadedSeedPack(
            pack_id="hello_fallback",
            table=0,
            title="AI Innovators Expedition — Hello Starter Agent",
            tribe="Common Starter",
            short_description="Fallback starter agent used when SEED_PACK is unset.",
            instruction=fallback_instruction,
            bigquery_dataset=None,
            gcs_prefix=None,
            mcp_server=None,
            pack_dir=None,
            tools=[hello_expedition_status],
            mcp_stdio_attached=False,
        )

    pack_dir = resolve_pack_directory(resolved_id, seed_packs_dir=seed_packs_dir)
    yaml_path = pack_dir / "pack.yaml"
    raw_cfg: dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

    raw_instruction = str(raw_cfg.get("instruction") or "").strip()
    if strict_state_tokens:
        assert_no_state_tokens(raw_instruction)
    safe_instruction = sanitize_instruction(raw_instruction)

    bq_dataset = raw_cfg.get("bigquery_dataset")
    if bq_dataset:
        os.environ.setdefault("SEED_BQ_DATASET", str(bq_dataset).strip())

    # Import TOOLS from seed_packs.<dir_name>.tools
    module_prefix = f"seed_packs.{pack_dir.name}"
    tools_mod = importlib.import_module(f"{module_prefix}.tools")
    raw_tools = list(vars(tools_mod).get("TOOLS", []))

    mcp_server_mod = raw_cfg.get("mcp_server")
    mcp_server_str = str(mcp_server_mod).strip() if mcp_server_mod else None
    mcp_funcs = _extract_mcp_module_functions(mcp_server_str) if mcp_server_str else []
    mcp_func_names = {fn.__name__ for fn in mcp_funcs}

    use_stdio = _should_use_mcp_stdio(enable_mcp_stdio)
    final_tools: list[Any] = []
    mcp_attached = False

    if mcp_server_str and use_stdio:
        mcp_toolset = _build_mcp_stdio_toolset(mcp_server_str)
        if mcp_toolset is not None:
            # Avoid duplicate FunctionDeclaration names when tools.py also re-exports MCP functions
            final_tools = [
                fn for fn in raw_tools
                if _tool_name(fn) not in mcp_func_names
            ]
            final_tools.append(mcp_toolset)
            mcp_attached = True

    if not mcp_attached:
        # Plain function mode (Agent Runtime or fallback): ensure all MCP functions are present
        existing_names = {_tool_name(fn) for fn in raw_tools}
        final_tools = list(raw_tools)
        for fn in mcp_funcs:
            if fn.__name__ not in existing_names:
                final_tools.append(fn)

    return LoadedSeedPack(
        pack_id=str(raw_cfg.get("id") or pack_dir.name),
        table=raw_cfg.get("table"),
        title=str(raw_cfg.get("title") or pack_dir.name),
        tribe=str(raw_cfg.get("tribe") or ""),
        short_description=str(raw_cfg.get("short_description") or ""),
        instruction=safe_instruction,
        bigquery_dataset=str(bq_dataset) if bq_dataset else None,
        gcs_prefix=str(raw_cfg.get("gcs_prefix")) if raw_cfg.get("gcs_prefix") else None,
        mcp_server=mcp_server_str,
        pack_dir=pack_dir,
        tools=final_tools,
        mcp_stdio_attached=mcp_attached,
    )
