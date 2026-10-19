"""Self-check validator for all 10 Hackathon Seed Packs (t01..t10)."""

from __future__ import annotations

import csv
import importlib
import inspect
import json
from pathlib import Path
import sys
from typing import Any

import yaml

_SEED_PACKS_DIR = Path(__file__).resolve().parent
_STARTER_ROOT = _SEED_PACKS_DIR.parent
if str(_STARTER_ROOT) not in sys.path:
    sys.path.insert(0, str(_STARTER_ROOT))

EXPECTED_PACKS = [
    ("t01", 1, "t01_campaign_orchestrator"),
    ("t02", 2, "t02_dynamic_storefronts"),
    ("t03", 3, "t03_catalog_discovery"),
    ("t04", 4, "t04_b2b_sourcing"),
    ("t05", 5, "t05_financial_auditor"),
    ("t06", 6, "t06_climate_risk"),
    ("t07", 7, "t07_self_healing_ops"),
    ("t08", 8, "t08_travel_concierge"),
    ("t09", 9, "t09_mobility_energy"),
    ("t10", 10, "t10_retention_matcher"),
]

REQUIRED_YAML_KEYS = {
    "id",
    "table",
    "title",
    "tribe",
    "short_description",
    "instruction",
    "bigquery_dataset",
    "gcs_prefix",
    "mcp_server",
}

# Tribe of each Table (2 Tables per Tribe); the sister Table is the other one.
EXPECTED_TRIBES = {
    1: "Creative AI & AdTech",
    2: "Creative AI & AdTech",
    3: "Content Intelligence",
    4: "Content Intelligence",
    5: "FinTech & Analytics",
    6: "FinTech & Analytics",
    7: "Cross-functional Ops & CX",
    8: "Cross-functional Ops & CX",
    9: "Smart Mobility & UX",
    10: "Smart Mobility & UX",
}

# Terms that must never appear in participant-facing pack docs.
BANNED_TERMS = (
    "claude",
    "anthropic",
    "agent builder",
    "imagen",
    "genkit",
    "gemini 3.8 pro",
    "gemini-3.8-pro",
)


def _sister_table(table_num: int) -> int:
    return table_num + 1 if table_num % 2 else table_num - 1


def _slug_for_table(table_num: int) -> str:
    return next(slug for _, num, slug in EXPECTED_PACKS if num == table_num)


def _check_golden_tool_uses(
    slug: str, eval_data: dict[str, Any], tool_fns: dict[str, Any]
) -> list[str]:
    """Every expected tool call must name a real tool with valid argument names."""
    errors: list[str] = []
    for case in eval_data.get("eval_cases", []):
        for turn in case.get("conversation", []):
            uses = (turn.get("intermediate_data") or {}).get("tool_uses") or []
            for use in uses:
                name = use.get("name")
                fn = tool_fns.get(name)
                if fn is None:
                    errors.append(
                        f"{slug}: eval case {case.get('eval_id')} expects unknown tool '{name}'"
                    )
                    continue
                params = inspect.signature(fn).parameters
                args = set((use.get("args") or {}).keys())
                unknown = sorted(args - set(params))
                required = sorted(
                    p for p, v in params.items()
                    if v.default is inspect.Parameter.empty and p not in args
                )
                if unknown or required:
                    errors.append(
                        f"{slug}: eval case {case.get('eval_id')} {name} has unknown args "
                        f"{unknown} / missing required args {required}"
                    )
    return errors


def _check_pack(pack_id: str, table_num: int, slug: str) -> list[str]:
    errors: list[str] = []
    pack_dir = _SEED_PACKS_DIR / slug
    if not pack_dir.is_dir():
        return [f"{slug}: directory missing at {pack_dir}"]

    # 1. Check pack.yaml
    data: Any = None
    yaml_path = pack_dir / "pack.yaml"
    if not yaml_path.is_file():
        errors.append(f"{slug}: missing pack.yaml")
    else:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            errors.append(f"{slug}: pack.yaml is not a mapping")
        else:
            missing = REQUIRED_YAML_KEYS - set(data.keys())
            if missing:
                errors.append(f"{slug}: pack.yaml missing keys {sorted(missing)}")
            if data.get("id") != pack_id:
                errors.append(f"{slug}: pack.yaml id={data.get('id')} != {pack_id}")
            if data.get("table") != table_num:
                errors.append(f"{slug}: pack.yaml table={data.get('table')} != {table_num}")
            if data.get("bigquery_dataset") != f"seed_{pack_id}":
                errors.append(
                    f"{slug}: pack.yaml bigquery_dataset={data.get('bigquery_dataset')} != seed_{pack_id}"
                )
            if data.get("gcs_prefix") != f"seed/{pack_id}/":
                errors.append(f"{slug}: pack.yaml gcs_prefix={data.get('gcs_prefix')} != seed/{pack_id}/")
            instruction = str(data.get("instruction", ""))
            if "{" in instruction or "}" in instruction:
                errors.append(f"{slug}: pack.yaml instruction contains curly braces")
            if data.get("tribe") != EXPECTED_TRIBES[table_num]:
                errors.append(
                    f"{slug}: pack.yaml tribe={data.get('tribe')!r} != {EXPECTED_TRIBES[table_num]!r}"
                )

    # 2. Check data/*.csv (at least 2 CSVs, 50-500 rows each)
    data_dir = pack_dir / "data"
    csv_files = sorted(data_dir.glob("*.csv")) if data_dir.is_dir() else []
    if len(csv_files) < 2:
        errors.append(f"{slug}: expected >=2 CSV files in data/, found {len(csv_files)}")
    for csv_path in csv_files:
        with csv_path.open("r", encoding="utf-8") as fp:
            rows = list(csv.reader(fp))
        if len(rows) < 2:
            errors.append(f"{slug}: {csv_path.name} has no data rows")
            continue
        header = rows[0]
        data_rows = rows[1:]
        if not (50 <= len(data_rows) <= 500):
            errors.append(
                f"{slug}: {csv_path.name} has {len(data_rows)} rows (expected 50..500)"
            )
        for idx, row in enumerate(data_rows, start=2):
            if len(row) != len(header):
                errors.append(
                    f"{slug}: {csv_path.name} line {idx} has {len(row)} cols != header {len(header)}"
                )
                break

    # 3. Check tools.py
    tool_fns: dict[str, Any] = {}
    try:
        tools_mod = importlib.import_module(f"seed_packs.{slug}.tools")
        tools_list = vars(tools_mod).get("TOOLS")
        if not isinstance(tools_list, list) or len(tools_list) < 2:
            errors.append(f"{slug}: tools.py TOOLS must be a list of >=2 callables")
        else:
            for fn in tools_list:
                if not callable(fn):
                    errors.append(f"{slug}: non-callable in TOOLS: {fn}")
                    continue
                tool_fns[fn.__name__] = fn
                if not (inspect.getdoc(fn) or "").strip():
                    errors.append(f"{slug}: tool {fn.__name__} missing docstring")
                sig = inspect.signature(fn)
                for param_name, param in sig.parameters.items():
                    if param.annotation is inspect.Parameter.empty:
                        errors.append(
                            f"{slug}: tool {fn.__name__} param '{param_name}' missing type annotation"
                        )
                if sig.return_annotation is inspect.Signature.empty:
                    errors.append(f"{slug}: tool {fn.__name__} missing return type annotation")
    except Exception as exc:
        errors.append(f"{slug}: failed importing tools.py: {exc}")

    # 4. Check mcp_server.py
    try:
        mcp_mod = importlib.import_module(f"seed_packs.{slug}.mcp_server")
        if vars(mcp_mod).get("mcp") is None:
            errors.append(f"{slug}: mcp_server.py missing 'mcp' FastMCP instance")
        # app/loader.py only reads MCP_TOOLS (ACTION_TOOLS is an optional alias).
        mcp_tools = vars(mcp_mod).get("MCP_TOOLS")
        if not isinstance(mcp_tools, list) or len(mcp_tools) < 2:
            errors.append(f"{slug}: mcp_server.py missing MCP_TOOLS list of >=2 callables")
        else:
            for fn in mcp_tools:
                if not callable(fn):
                    errors.append(f"{slug}: non-callable in MCP_TOOLS: {fn}")
                    continue
                if not (inspect.getdoc(fn) or "").strip():
                    errors.append(f"{slug}: MCP tool {fn.__name__} missing docstring")
                tool_fns[fn.__name__] = fn
    except Exception as exc:
        errors.append(f"{slug}: failed importing mcp_server.py: {exc}")

    # 5. Check load.py
    try:
        load_mod = importlib.import_module(f"seed_packs.{slug}.load")
        if not callable(vars(load_mod).get("main")):
            errors.append(f"{slug}: load.py missing callable main()")
    except Exception as exc:
        errors.append(f"{slug}: failed importing load.py: {exc}")

    # 6. Check eval/golden.test.json
    eval_path = pack_dir / "eval" / "golden.test.json"
    if not eval_path.is_file():
        errors.append(f"{slug}: missing eval/golden.test.json")
    else:
        try:
            eval_data: dict[str, Any] = json.loads(eval_path.read_text(encoding="utf-8"))
            for key in ("eval_set_id", "name", "description", "eval_cases"):
                if key not in eval_data:
                    errors.append(f"{slug}: eval/golden.test.json missing '{key}'")
            cases = eval_data.get("eval_cases", [])
            if not isinstance(cases, list) or len(cases) < 5:
                errors.append(
                    f"{slug}: eval/golden.test.json has {len(cases) if isinstance(cases, list) else 0} cases (expected >=5)"
                )
            else:
                for case in cases:
                    if "eval_id" not in case or "conversation" not in case or "session_input" not in case:
                        errors.append(f"{slug}: eval case missing required keys: {case.get('eval_id')}")
                errors.extend(_check_golden_tool_uses(slug, eval_data, tool_fns))
        except Exception as exc:
            errors.append(f"{slug}: invalid JSON in eval/golden.test.json: {exc}")

    # Docs must describe the tools that actually ship (instruction, card).
    if isinstance(data, dict) and tool_fns:
        instruction = str(data.get("instruction", ""))
        for name in sorted(tool_fns):
            if f"`{name}`" not in instruction:
                errors.append(f"{slug}: pack.yaml instruction does not mention tool `{name}`")

    # 7. Check CHALLENGE_CARD.md
    card_path = pack_dir / "CHALLENGE_CARD.md"
    if not card_path.is_file():
        errors.append(f"{slug}: missing CHALLENGE_CARD.md")
    else:
        card_text = card_path.read_text(encoding="utf-8")
        if "This challenge is a starting point - adapt it." not in card_text:
            errors.append(f"{slug}: CHALLENGE_CARD.md missing required footer")
        for marker in (
            "GEMINI_MODEL",
            "Gemini 3.8 Flash",
            "A2A",
            "Verifiable Agent Readiness",
            "Attack Vector",
            "Defence Hint",
            f"Table {table_num}",
            f"**Tribe**: {EXPECTED_TRIBES[table_num]}",
        ):
            if marker not in card_text:
                errors.append(f"{slug}: CHALLENGE_CARD.md missing section/marker '{marker}'")
        sister = _sister_table(table_num)
        sister_line = next(
            (line for line in card_text.splitlines() if line.startswith("- **Sister Table**")), ""
        )
        if f"Table {sister} " not in sister_line or _slug_for_table(sister) not in sister_line:
            errors.append(
                f"{slug}: CHALLENGE_CARD.md Sister Table must be Table {sister} "
                f"(`{_slug_for_table(sister)}`), found {sister_line!r}"
            )
        for name in sorted(tool_fns):
            if f"`{name}`" not in card_text:
                errors.append(f"{slug}: CHALLENGE_CARD.md does not mention tool `{name}`")
        for csv_path in csv_files:
            if f"`seed_{pack_id}.{csv_path.stem}`" not in card_text:
                errors.append(
                    f"{slug}: CHALLENGE_CARD.md does not list table `seed_{pack_id}.{csv_path.stem}`"
                )
        lowered = card_text.lower()
        if isinstance(data, dict):
            lowered += " " + str(data.get("instruction", "")).lower()
            lowered += " " + str(data.get("short_description", "")).lower()
        for term in BANNED_TERMS:
            if term in lowered:
                errors.append(f"{slug}: banned term '{term}' in CHALLENGE_CARD.md or pack.yaml")

    return errors


def _check_readme(readme_text: str) -> list[str]:
    """README index rows must list each pack's real tools, tribe and sister Table."""
    errors: list[str] = []
    lines = readme_text.splitlines()
    for pack_id, table_num, slug in EXPECTED_PACKS:
        row = next((line for line in lines if line.startswith("| **") and f"./{slug}/" in line), "")
        if not row:
            errors.append(f"README.md: no index row for {slug}")
            continue
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if EXPECTED_TRIBES[table_num] not in row:
            errors.append(f"README.md: {slug} row does not show tribe {EXPECTED_TRIBES[table_num]!r}")
        if not cells or _slug_for_table(_sister_table(table_num)) not in cells[-1]:
            errors.append(f"README.md: {slug} row sister Table is not {_slug_for_table(_sister_table(table_num))}")
        try:
            names = [fn.__name__ for fn in importlib.import_module(f"seed_packs.{slug}.tools").TOOLS]
            names += [fn.__name__ for fn in importlib.import_module(f"seed_packs.{slug}.mcp_server").MCP_TOOLS]
        except Exception as exc:
            errors.append(f"README.md: cannot import {slug} tools to compare ({exc})")
            continue
        for name in names:
            if f"`{name}`" not in row:
                errors.append(f"README.md: {slug} row does not list tool `{name}`")
    for line in lines:
        lower_line = line.lower()
        if "gs://" in lower_line and "public" in lower_line and "not public" not in lower_line:
            errors.append("README.md: do not claim a gs:// bucket is public in seed_packs/README.md")
    return errors


def main() -> int:
    all_errors: list[str] = []
    for pack_id, table_num, slug in EXPECTED_PACKS:
        pack_errors = _check_pack(pack_id, table_num, slug)
        if pack_errors:
            all_errors.extend(pack_errors)
            print(f"[FAIL] {slug}: {len(pack_errors)} error(s)")
        else:
            print(f"[PASS] {slug} (Table {table_num}, dataset=seed_{pack_id})")

    readme_path = _SEED_PACKS_DIR / "README.md"
    if not readme_path.is_file():
        all_errors.append("seed_packs/README.md is missing")
    else:
        readme_errors = _check_readme(readme_path.read_text(encoding="utf-8"))
        all_errors.extend(readme_errors)
        print(
            "[PASS] seed_packs/README.md matches the packs"
            if not readme_errors
            else f"[FAIL] seed_packs/README.md: {len(readme_errors)} error(s)"
        )

    if all_errors:
        print("\nValidation failed with errors:")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("\nAll 10 Seed Packs (t01..t10) + README.md passed validation!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
