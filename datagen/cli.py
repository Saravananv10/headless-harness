"""cli.py — CLI entry point for the datagen batch runner.

Reads tasks straight from the local task bank under
artifacts/datagen_task_bank/by_category/ (datagen.bank_ingest) — the
harness's own native, already-forged task format.
Mirrors runner/batch_runner.py's flag names/behavior where they overlap.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapter.chakra import ChakraHarness
from controller import OpenAICompatibleClient
from scripts.real_backend import connection_config, load_project_env

from datagen import bank_ingest, checkpoint, curation, data_need, dataset_manifest
from datagen.executor import run_task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Headless harness datagen batch runner (local task bank)"
    )
    parser.add_argument(
        "--category", action="append", default=None,
        help="Bank category to include (repeatable; default: every category, "
             "e.g. finance_ca_practice, cybersecurity_ops)",
    )
    parser.add_argument("--start", type=int, default=1, help="Start global task index (inclusive)")
    parser.add_argument("--end", type=int, default=10**9, help="End global task index (inclusive)")
    parser.add_argument("--task-id", default=None, help="Run a single task by ID")
    parser.add_argument("--data-seed", type=int, default=42, help="Base random seed for data generation")
    parser.add_argument("--max-turns", type=int, default=25)
    parser.add_argument("--max-decisions", type=int, default=25)
    parser.add_argument("--max-repair-iterations", type=int, default=3)
    parser.add_argument(
        "--llm-detect-data-need", action="store_true",
        help="Use an LLM fallback when the data-need heuristic is ambiguous (cached per task)",
    )
    parser.add_argument(
        "--llm-expand", action="store_true",
        help="Run one extra LLM pass to deepen the composed PRD before sending it to Chakra",
    )
    parser.add_argument(
        "--report-name", default=None,
        help="Report file stem under experiments/ (default: the category list, or "
             "'datagen_task_bank' when running every category)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Ingest + data-need detection only; no Chakra connection, no harness run",
    )
    parser.add_argument(
        "--freeze-dataset", action="store_true",
        help="After the batch, cut an immutable dataset snapshot from artifacts/dataset_manifest/",
    )
    parser.add_argument(
        "--max-retries", type=int, default=1,
        help="Retries into the same workdir on a transient session-health stall "
             "(gRPC/inactivity/progress timeout) before giving up on a task",
    )
    parser.add_argument(
        "--force-rerun", action="store_true",
        help="Ignore checkpoint (already-done) and curation (marked-good) skips for this run",
    )
    parser.add_argument(
        "--mark-good", default=None, metavar="TASK_ID",
        help="Mark a task as a known-good example (never regenerate it again) and exit",
    )
    parser.add_argument(
        "--unmark-good", default=None, metavar="TASK_ID",
        help="Remove a task from the curation list and exit",
    )
    parser.add_argument(
        "--mark-reason", default="",
        help="Optional note to store alongside --mark-good",
    )
    parser.add_argument(
        "--reset-failed", action="store_true",
        help="Clear checkpoint entries marked 'failed' (they'll be attempted again) and exit",
    )
    parser.add_argument(
        "--checkpoint-status", action="store_true",
        help="Print a summary of the checkpoint store (done/failed/running counts) and exit",
    )
    args = parser.parse_args(argv)

    load_project_env()

    if args.mark_good:
        curation.CurationList().mark_good(args.mark_good, reason=args.mark_reason)
        print(f"Marked good: {args.mark_good}" + (f" ({args.mark_reason})" if args.mark_reason else ""))
        return 0
    if args.unmark_good:
        removed = curation.CurationList().unmark(args.unmark_good)
        print(f"{'Unmarked' if removed else 'Not marked'}: {args.unmark_good}")
        return 0
    if args.reset_failed:
        n = checkpoint.CheckpointStore().reset_failed()
        print(f"Reset {n} failed checkpoint entr{'y' if n == 1 else 'ies'} for retry.")
        return 0
    if args.checkpoint_status:
        summary = checkpoint.CheckpointStore().summary()
        print("Checkpoint status:", summary or "(empty)")
        return 0

    specs = bank_ingest.load_bank(args.category)
    default_report_stem = "_".join(args.category) if args.category else "datagen_task_bank"

    if not specs:
        print("No tasks found for the given source/filters.")
        return 0

    if args.task_id:
        target = [s for s in specs if s.id.upper() == args.task_id.upper()]
        if not target:
            print(
                f"Error: task ID '{args.task_id}' not found. "
                f"Available (first 20 of {len(specs)}): {[s.id for s in specs[:20]]}"
            )
            return 1
    else:
        target = [s for s in specs if args.start <= s.global_index <= args.end]

    if not target:
        print(f"No tasks match the filter (start={args.start}, end={args.end}). Exiting.")
        return 0

    report_stem = args.report_name or default_report_stem

    print(f"\n=== Datagen: {len(target)} task(s) from the local task bank ===\n")
    by_category: dict[str, int] = defaultdict(int)
    for spec in target:
        by_category[spec.category] += 1
    for cat, n in sorted(by_category.items()):
        print(f"  {cat}: {n}")
    print()

    if args.dry_run:
        for spec in target:
            needs, reason = data_need.needs_input_data(spec)
            print(f"[{spec.global_index:04d}] {spec.id}  needs_input_data={needs}  ({reason})")
        print(f"\nDry run: {len(target)} task(s) validated, no harness run performed.")
        return 0

    experiments_dir = REPO_ROOT / "experiments"
    logs_dir = REPO_ROOT / "logs"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    harness = ChakraHarness(default_timeout_seconds=3000)
    harness.connect(connection_config())
    llm = OpenAICompatibleClient.from_env()

    checkpoint_store = checkpoint.CheckpointStore()
    curation_list = curation.CurationList()

    results: list[dict] = []
    try:
        for spec in target:
            try:
                res = run_task(
                    spec,
                    harness=harness,
                    llm=llm,
                    experiments_dir=experiments_dir,
                    logs_dir=logs_dir,
                    data_seed=args.data_seed,
                    max_turns=args.max_turns,
                    max_decisions=args.max_decisions,
                    max_repair_iterations=args.max_repair_iterations,
                    llm_detect_data_need=args.llm_detect_data_need,
                    llm_expand=args.llm_expand,
                    checkpoint_store=checkpoint_store,
                    curation_list=curation_list,
                    force_rerun=args.force_rerun,
                    max_retries=args.max_retries,
                )
                results.append(res)
            except Exception as exc:
                print(f"[ERROR] Task {spec.id} failed with exception: {exc}")
                results.append(
                    {
                        "global_index": spec.global_index,
                        "task_id": spec.id,
                        "title": spec.title,
                        "category": spec.category,
                        "status": "ERROR",
                        "error": str(exc),
                    }
                )
    finally:
        harness.disconnect()

    _write_reports(results, experiments_dir, report_stem)

    if args.freeze_dataset:
        snapshot = dataset_manifest.freeze_dataset()
        print(
            f"Dataset frozen: {snapshot['dataset_id']} "
            f"({snapshot['entry_count']} entries, {snapshot['passed_count']} passed) "
            f"-> {snapshot['_path']}"
        )
    return 0


def _write_reports(results: list[dict], experiments_dir: Path, report_stem: str) -> None:
    report_json = experiments_dir / f"{report_stem}_benchmark.json"
    report_csv = experiments_dir / f"{report_stem}_benchmark.csv"
    report_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    if results:
        headers = sorted({k for r in results for k in r.keys()})
        with report_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)

    by_domain: dict[str, dict] = {}
    for r in results:
        cat = r.get("category") or "unknown"
        entry = by_domain.setdefault(cat, {"total": 0, "passed": 0, "turns": [], "tool_calls": []})
        entry["total"] += 1
        if r.get("status") == "PASSED":
            entry["passed"] += 1
        if "turn_count" in r:
            entry["turns"].append(r["turn_count"])
        if "tool_executions" in r:
            entry["tool_calls"].append(r["tool_executions"])

    domain_summary = {}
    for cat, entry in by_domain.items():
        turns = entry["turns"] or [0]
        tools = entry["tool_calls"] or [0]
        domain_summary[cat] = {
            "total": entry["total"],
            "passed": entry["passed"],
            "pass_rate": round(entry["passed"] / entry["total"], 3) if entry["total"] else 0.0,
            "avg_turns": round(sum(turns) / len(turns), 1),
            "avg_tool_calls": round(sum(tools) / len(tools), 1),
        }
    domain_path = experiments_dir / f"{report_stem}_by_domain.json"
    domain_path.write_text(json.dumps(domain_summary, indent=2), encoding="utf-8")

    passed = sum(1 for r in results if r.get("status") == "PASSED")
    print(f"\n{'='*75}")
    print(f"COMPLETE: {passed}/{len(results)} tasks passed")
    print(f"JSON report   -> {report_json}")
    print(f"CSV  report   -> {report_csv}")
    print(f"Domain rollup -> {domain_path}")
    print(f"{'='*75}\n")


if __name__ == "__main__":
    raise SystemExit(main())
