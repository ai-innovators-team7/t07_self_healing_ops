"""Evaluation runner and golden test loader for the AI Innovators Expedition Starter.

Discovers `.test.json` / `.evalset.json` files from `seed_packs/<SEED_PACK>/eval/`
(or falls back to `eval/hello_fallback.test.json`), validates them against ADK's
`EvalSet` schema, executes each case against `app.agent.build_agent`, and prints
a clear pass/fail summary table.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from dotenv import load_dotenv
from google.adk.evaluation.eval_set import EvalSet
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agent import build_agent
from app.loader import REPO_ROOT, SEED_PACKS_DIR, resolve_pack_directory
from app.preflight import check_adc, format_error, require_project

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = EVAL_DIR / "test_config.json"
FALLBACK_EVAL_FILE = EVAL_DIR / "hello_fallback.test.json"


@dataclass
class NormalizedEvalTurn:
    """Single user->agent evaluation turn."""

    invocation_id: str
    user_text: str
    expected_tools: list[dict[str, Any]] = field(default_factory=list)
    reference_response: str = ""


@dataclass
class NormalizedEvalCase:
    """Normalized evaluation case supporting ADK EvalSet and simplified JSON formats."""

    eval_id: str
    source_file: str
    turns: list[NormalizedEvalTurn] = field(default_factory=list)


def discover_eval_files(
    pack_id: str | None = None,
    *,
    seed_packs_dir: Path = SEED_PACKS_DIR,
    fallback_file: Path = FALLBACK_EVAL_FILE,
) -> list[Path]:
    """Return all `.test.json` / `.evalset.json` files for `pack_id` (or fallback)."""
    resolved_id = (
        pack_id if pack_id is not None else os.environ.get("SEED_PACK", "")
    ).strip()

    if not resolved_id or resolved_id.lower() in {"none", "null", "hello"}:
        return [fallback_file] if fallback_file.exists() else []

    pack_dir = resolve_pack_directory(resolved_id, seed_packs_dir=seed_packs_dir)
    pack_eval_dir = pack_dir / "eval"
    if not pack_eval_dir.is_dir():
        # The hello fallback cases expect `hello_expedition_status`, which a real
        # pack does not have, so falling back would only produce confusing FAILs.
        raise FileNotFoundError(
            f"Seed Pack '{pack_dir.name}' has no eval/ folder. Create "
            f"{pack_eval_dir / 'golden.test.json'} (copy seed_packs/t00_example/eval/golden.test.json)."
        )

    files = sorted(
        list(pack_eval_dir.glob("*.test.json"))
        + list(pack_eval_dir.glob("*.evalset.json"))
    )
    return files


def load_eval_cases(file_path: Path) -> tuple[EvalSet | None, list[NormalizedEvalCase]]:
    """Parse an eval file into an ADK `EvalSet` (when compliant) and normalized cases."""
    raw_text = file_path.read_text(encoding="utf-8")
    raw_data = json.loads(raw_text)

    validated_eval_set: EvalSet | None = None
    if isinstance(raw_data, dict) and "eval_cases" in raw_data:
        try:
            validated_eval_set = EvalSet.model_validate(raw_data)
        except ValueError as exc:  # pydantic.ValidationError subclasses ValueError
            validated_eval_set = None
            first_error = str(exc).splitlines()[:4]
            print(
                f"[eval] WARNING: {file_path.name} is not a valid ADK EvalSet; using the lenient "
                f"parser instead. First validation errors: {' | '.join(first_error)}",
                file=sys.stderr,
            )

    cases: list[NormalizedEvalCase] = []
    if validated_eval_set is not None:
        for ec in validated_eval_set.eval_cases:
            turns: list[NormalizedEvalTurn] = []
            for inv in ec.conversation or []:
                user_parts = (inv.user_content.parts if inv.user_content else None) or []
                user_text = " ".join(p.text for p in user_parts if p.text)
                ref_parts = (inv.final_response.parts if inv.final_response else None) or []
                ref_text = " ".join(p.text for p in ref_parts if p.text)
                tool_uses: list[dict[str, Any]] = []
                if inv.intermediate_data and inv.intermediate_data.tool_uses:
                    for tu in inv.intermediate_data.tool_uses:
                        tool_uses.append({
                            "name": tu.name,
                            "args": dict(tu.args or {}),
                        })
                turns.append(
                    NormalizedEvalTurn(
                        invocation_id=inv.invocation_id or ec.eval_id,
                        user_text=user_text,
                        expected_tools=tool_uses,
                        reference_response=ref_text,
                    )
                )
            cases.append(
                NormalizedEvalCase(
                    eval_id=ec.eval_id,
                    source_file=file_path.name,
                    turns=turns,
                )
            )
        return validated_eval_set, cases

    # Fallback parser for simplified list/dict test files
    raw_cases = (
        raw_data.get("eval_cases") or raw_data.get("cases") or raw_data.get("tests")
        if isinstance(raw_data, dict)
        else raw_data
    )
    if isinstance(raw_cases, list):
        for idx, item in enumerate(raw_cases, start=1):
            if not isinstance(item, dict):
                continue
            eval_id = str(item.get("eval_id") or item.get("id") or f"case_{idx:02d}")
            if "conversation" in item and isinstance(item["conversation"], list):
                turns = []
                for t_idx, turn in enumerate(item["conversation"], start=1):
                    u_parts = turn.get("user_content", {}).get("parts", [])
                    u_text = " ".join(p.get("text", "") for p in u_parts if isinstance(p, dict))
                    f_parts = turn.get("final_response", {}).get("parts", [])
                    f_text = " ".join(p.get("text", "") for p in f_parts if isinstance(p, dict))
                    t_uses = turn.get("intermediate_data", {}).get("tool_uses", [])
                    turns.append(
                        NormalizedEvalTurn(
                            invocation_id=str(turn.get("invocation_id") or f"{eval_id}_{t_idx}"),
                            user_text=u_text,
                            expected_tools=list(t_uses),
                            reference_response=f_text,
                        )
                    )
                cases.append(NormalizedEvalCase(eval_id=eval_id, source_file=file_path.name, turns=turns))
            else:
                user_text = str(item.get("query") or item.get("prompt") or item.get("user_input") or "")
                exp_tool = item.get("expected_tool") or item.get("tool")
                exp_tools = [{"name": exp_tool, "args": item.get("expected_args", {})}] if exp_tool else []
                ref_resp = str(item.get("expected_response") or item.get("reference") or "")
                cases.append(
                    NormalizedEvalCase(
                        eval_id=eval_id,
                        source_file=file_path.name,
                        turns=[
                            NormalizedEvalTurn(
                                invocation_id=f"{eval_id}_1",
                                user_text=user_text,
                                expected_tools=exp_tools,
                                reference_response=ref_resp,
                            )
                        ],
                    )
                )
    return None, cases


def score_tool_trajectory(
    expected_tools: list[dict[str, Any]],
    actual_tools: list[dict[str, Any]],
) -> float:
    """Compute tool trajectory match score in [0.0, 1.0]."""
    if not expected_tools:
        return 1.0
    actual_names = [t.get("name") for t in actual_tools]
    matched = 0
    for exp in expected_tools:
        exp_name = exp.get("name")
        if exp_name in actual_names:
            matched += 1
    return round(matched / len(expected_tools), 4)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def score_response_match(reference: str, candidate: str) -> float:
    """Compute token-overlap recall/F1 score against reference response."""
    ref_tokens = _tokenize(reference)
    cand_tokens = _tokenize(candidate)
    if not ref_tokens:
        return 1.0 if cand_tokens else 0.0
    if not cand_tokens:
        return 0.0
    ref_set = set(ref_tokens)
    cand_set = set(cand_tokens)
    overlap = len(ref_set & cand_set)
    recall = overlap / len(ref_set)
    precision = overlap / len(cand_set)
    if recall + precision == 0:
        return 0.0
    f1 = 2 * recall * precision / (recall + precision)
    return round(max(recall, f1), 4)


async def run_live_evaluation(
    pack_id: str | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    """Execute all golden eval cases for `pack_id` against the live ADK agent."""
    criteria = {"tool_trajectory_avg_score": 0.8, "response_match_score": 0.25}
    if config_path.exists():
        loaded_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        criteria.update(loaded_cfg.get("criteria", {}))

    eval_files = discover_eval_files(pack_id=pack_id)
    if not eval_files:
        raise FileNotFoundError(
            f"No *.test.json / *.evalset.json files found for pack_id={pack_id!r}."
        )

    # Run evaluation with plain Python function tools for deterministic speed & reliability
    agent, pack = build_agent(pack_id=pack_id, enable_mcp_stdio=False)
    runner = InMemoryRunner(agent=agent, app_name="app")

    results: list[dict[str, Any]] = []
    for file_path in eval_files:
        _, cases = load_eval_cases(file_path)
        for case in cases:
            session = await runner.session_service.create_session(
                app_name="app",
                user_id="eval_runner",
            )
            case_tool_scores: list[float] = []
            case_resp_scores: list[float] = []
            actual_tool_names: list[str] = []
            expected_tool_names: list[str] = []
            last_reply = ""

            for turn in case.turns:
                turn_tools: list[dict[str, Any]] = []
                turn_texts: list[str] = []
                content = types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=turn.user_text)],
                )
                async for event in runner.run_async(
                    user_id="eval_runner",
                    session_id=session.id,
                    new_message=content,
                ):
                    if not event.content or not event.content.parts:
                        continue
                    for part in event.content.parts:
                        if part.function_call is not None:
                            fc = part.function_call
                            turn_tools.append({
                                "name": fc.name,
                                "args": dict(fc.args or {}),
                            })
                        if part.text:
                            turn_texts.append(part.text)

                reply_text = "\n".join(turn_texts).strip()
                last_reply = reply_text
                t_score = score_tool_trajectory(turn.expected_tools, turn_tools)
                r_score = score_response_match(turn.reference_response, reply_text)
                case_tool_scores.append(t_score)
                case_resp_scores.append(r_score)
                expected_tool_names.extend(t.get("name", "") for t in turn.expected_tools)
                actual_tool_names.extend(t.get("name", "") for t in turn_tools)

            avg_tool = round(sum(case_tool_scores) / max(len(case_tool_scores), 1), 4)
            avg_resp = round(sum(case_resp_scores) / max(len(case_resp_scores), 1), 4)
            passed = (
                avg_tool >= float(criteria.get("tool_trajectory_avg_score", 0.8))
                and avg_resp >= float(criteria.get("response_match_score", 0.25))
                and bool(last_reply)
            )
            results.append({
                "eval_id": case.eval_id,
                "file": case.source_file,
                "expected_tools": expected_tool_names,
                "actual_tools": actual_tool_names,
                "tool_score": avg_tool,
                "response_score": avg_resp,
                "passed": passed,
                "reply_excerpt": last_reply[:160].replace("\n", " "),
            })

    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    return {
        "pack_id": pack.pack_id,
        "pack_title": pack.title,
        "passed": passed_count,
        "total": total_count,
        "results": results,
    }


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Run ADK Golden Evaluations for the active Seed Pack.")
    parser.add_argument("--pack", default=None, help="Override SEED_PACK id (e.g. t08 or t00_example).")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate .test.json schema without making live Gemini LLM calls.",
    )
    args = parser.parse_args()

    try:
        files = discover_eval_files(pack_id=args.pack)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    if not files:
        print("ERROR: No evaluation files found.", file=sys.stderr)
        raise SystemExit(1)

    if args.validate_only:
        total_cases = 0
        for f in files:
            eval_set, cases = load_eval_cases(f)
            schema_tag = "ADK EvalSet" if eval_set is not None else "Normalized JSON"
            print(f"[eval:validate] {f.relative_to(REPO_ROOT)} -> {len(cases)} cases ({schema_tag})")
            total_cases += len(cases)
        print(f"EVAL_VALIDATE_SUMMARY: {len(files)} file(s), {total_cases} case(s) valid.")
        return

    try:
        project = require_project()
        check_adc(project)
        summary = asyncio.run(run_live_evaluation(pack_id=args.pack))
    except Exception as exc:
        print(format_error(exc), file=sys.stderr)
        raise SystemExit(1) from None
    print("=" * 88)
    print(f"ADK Evaluation Summary — Pack: {summary['pack_id']} ({summary['pack_title']})")
    print("=" * 88)
    for r in summary["results"]:
        status = "PASS" if r["passed"] else "FAIL"
        exp_t = ",".join(r["expected_tools"]) or "(none)"
        act_t = ",".join(r["actual_tools"]) or "(none)"
        print(
            f"[{status}] {r['eval_id']:<26} | tools: {act_t:<26} (exp: {exp_t}) "
            f"| tool_score={r['tool_score']:.2f} | resp_score={r['response_score']:.2f}"
        )
    print("-" * 88)
    pct = (summary["passed"] / summary["total"] * 100.0) if summary["total"] else 0.0
    print(f"EVAL_SUMMARY: {summary['passed']}/{summary['total']} cases passed ({pct:.1f}%)")
    if summary["total"] == 0:
        print("ERROR: 0 evaluation cases were executed; check your .test.json files.", file=sys.stderr)
        raise SystemExit(1)
    if summary["passed"] < summary["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
