# datagen

Runs tasks straight from the local task bank (`artifacts/datagen_task_bank/by_category/`)
through the existing Chakra harness (`ConversationRunner` — plan → implement → verify → repair),
with independent re-verification, checkpoint/resume, curation, and a versioned dataset manifest
layered on top. No per-domain Python needed to add a task — the task bank is the input.

## Prerequisites

1. **Chakra running** — in a separate terminal:
   ```bash
   cd headless_harness_datagen
   ./scripts/start_chakra.sh
   ```
   Wait for `gRPC Server running at localhost:50051`.
2. **`.env` configured** — copy `.example.env` → `.env` and set at least `OPENAI_API_KEY`,
   `OPENAI_BASE_URL`, `OPENAI_MODEL`. `GRPC_HOST`/`GRPC_PORT` default to `localhost:50051`.
3. **A task bank to run against** — `artifacts/datagen_task_bank/by_category/<category>/`.
   Run `python -m datagen --dry-run` any time to see what's currently there without connecting
   to Chakra.

## Quickstart

```bash
cd headless_harness_datagen

# See what would run — no Chakra connection
python -m datagen --dry-run

# Run everything in the bank
python -m datagen

# Run one category
python -m datagen --category finance_ca_practice

# Run a single task by id (ids come from --dry-run's output)
python -m datagen --task-id gst_01_full-gst-purchase-reconciliation-with-gstr-2b-matc

# Run a slice by global index
python -m datagen --start 1 --end 10
```

## What one task run does

1. Skip if curated-good or already checkpointed done (unless `--force-rerun`).
2. Validate the task; skip as `INPUT_INVALID` if malformed.
3. If the task needs input data: prefer a hand-written realistic generator
   (`pipelines/finance/data_generator.py`, `pipelines/cybersecurity/data_generator.py`) over the
   generic LLM-schema-inference fallback.
4. Compose the objective from the task's pre-forged `platform_prompt.md` and hand it to
   `ConversationRunner` — Chakra owns plan/implement/verify/repair from here.
5. Retry into the **same workdir** (not from scratch) on a transient stall
   (`wall_clock_timeout` / `inactivity_timeout` / `progress_timeout`), up to `--max-retries`
   times. A genuine outcome (repair iterations exhausted, stuck-in-explore, denial loop) is
   never retried.
6. On a self-reported `VERDICT: PASS`: independently re-run the exact commands the verification
   subagent claimed it ran. Only counts as `PASSED` if that agrees — otherwise `SELF_REPORTED_ONLY`.
7. Record the outcome to the dataset manifest (`artifacts/dataset_manifest/entries.jsonl`) and
   the checkpoint store, regardless of pass/fail/skip.

## Result statuses

| Status | Meaning |
|---|---|
| `PASSED` | Self-reported PASS, independently confirmed |
| `SELF_REPORTED_ONLY` | Agent claimed PASS but the independent re-check didn't confirm it |
| `FAILED` | No PASS claimed, or claim rejected by the harness's own evidence rules |
| `INPUT_INVALID` | Task or its synthesized input data failed preflight |
| `CURATED_SKIP` | Manually marked good via `--mark-good`; not regenerated |
| `CHECKPOINT_SKIP` | Already `done` in a prior batch run of the same task |
| `ERROR` | Crashed on every retry attempt (e.g. dropped connection) |

## Resuming a killed batch

```bash
python -m datagen --checkpoint-status     # see done/failed/running counts
python -m datagen --reset-failed          # clear failed entries so they're retried
python -m datagen                          # re-run the same command — done tasks are skipped
python -m datagen --force-rerun            # ignore checkpoint + curation, rerun everything
```

## Curating known-good examples

```bash
python -m datagen --mark-good gst_01_full-gst-purchase-reconciliation-with-gstr-2b-matc \
  --mark-reason "clean demo, keep as-is"
python -m datagen --unmark-good gst_01_full-gst-purchase-reconciliation-with-gstr-2b-matc
```
Marked tasks are skipped on every future run (across sessions) until unmarked or `--force-rerun`.

## Freezing a dataset version

```bash
python -m datagen --freeze-dataset
```
Content-hashes the current `artifacts/dataset_manifest/entries.jsonl` into an immutable snapshot
at `artifacts/dataset_manifest/snapshots/<dataset_id>.json` — same input entries always produce
the same `dataset_id`.

## All flags

| Flag | Default | Purpose |
|---|---|---|
| `--category` | every category | Bank category to include (repeatable) |
| `--start` / `--end` | `1` / unbounded | Global task index range |
| `--task-id` | — | Run a single task by id |
| `--data-seed` | `42` | Base random seed for synthesized input data |
| `--max-turns` | `25` | Safety cap on backend turns |
| `--max-decisions` | `25` | Safety cap on resume cycles |
| `--max-repair-iterations` | `3` | Verify↔repair rounds before giving up |
| `--llm-detect-data-need` | off | LLM fallback when the data-need heuristic is ambiguous |
| `--llm-expand` | off | One extra LLM pass to deepen the composed PRD (needs `prompt_forge`) |
| `--dry-run` | off | Ingest + data-need only, no Chakra connection |
| `--max-retries` | `1` | Retries into the same workdir on a transient stall |
| `--force-rerun` | off | Ignore checkpoint and curation skips |
| `--mark-good TASK_ID` | — | Mark a task known-good and exit |
| `--unmark-good TASK_ID` | — | Remove a task from the curation list and exit |
| `--mark-reason` | `""` | Note stored alongside `--mark-good` |
| `--reset-failed` | — | Clear failed checkpoint entries and exit |
| `--checkpoint-status` | — | Print checkpoint summary and exit |
| `--report-name` | category list, or `datagen_task_bank` | Report file stem under `experiments/` |
| `--freeze-dataset` | off | Cut an immutable dataset snapshot after the batch |

## Outputs

| Path | Contents |
|---|---|
| `experiments/<origin>/task_<idx>_<id>/` | The generated repository for one task |
| `experiments/<stem>_benchmark.{json,csv}` | Per-task results for the batch |
| `experiments/<stem>_by_domain.json` | Pass rate / avg turns / avg tool calls per category |
| `logs/<run-id>/pipeline/` | Full trace (`trace.jsonl`, `raw_events.jsonl`), verdict, report |
| `artifacts/dataset_manifest/entries.jsonl` | Append-only ledger of every attempted task |
| `artifacts/dataset_manifest/snapshots/<id>.json` | Frozen dataset versions |
| `artifacts/verification_reports/<run_id>.json` | Independent re-verification result |
| `artifacts/checkpoint/checkpoint.json` | Per-task done/failed/running state |
| `artifacts/curation/skip_done.json` | Manually curated known-good task ids |
| `artifacts/task_cache/<origin>/<task_id>/` | Cached data-need/schema decisions per task |

## Running the tests

```bash
cd headless_harness_datagen
python3 -m pytest tests/test_bank_ingest.py tests/test_domain_generators.py \
  tests/test_data_need.py tests/test_data_synth.py tests/test_independent_verify.py \
  tests/test_dataset_manifest.py tests/test_checkpoint.py tests/test_curation.py -v
```
All offline — no live Chakra/LLM connection required to validate the logic itself. A real
end-to-end run still needs Chakra running per the Prerequisites above.

## Known limitations

- No live-Chakra run has validated the full chain end to end in this repo — every subsystem is
  unit-tested in isolation.
- Retry only covers `wall_clock_timeout` / `inactivity_timeout` / `progress_timeout`; other
  transient failure modes aren't auto-retried.
- The checkpoint/curation JSON stores have no file locking; don't run two batches
  concurrently against the same `artifacts/`.
- `domain_generators.py`'s realistic-generator registry only covers `finance_ca_practice`/
  `cybersecurity_ops`; any other category uses the generic synthesis engine.
