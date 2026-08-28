# Headless Harness Datagen — Pipeline Guide

A standalone guide to the `datagen` pipeline: what's in this repo, how a task flows
through it end to end, and the exact commands to install and run it. For the full
CLI flag reference, result-status table, and output-path table, see
[`datagen/README.md`](datagen/README.md) — this file is the higher-level map.

## What this is

`datagen` runs tasks straight from a local, pre-forged task bank
(`artifacts/datagen_task_bank/`) through the Chakra coding-agent backend
(`ConversationRunner` — plan → implement → verify → repair), with independent
re-verification, checkpoint/resume, curation, and a versioned dataset manifest
layered on top. No per-domain Python is needed to add a task — the task bank is
the only input.

## Repository structure

```
headless_harness_datagen/
├── datagen/                  # The pipeline itself — CLI, orchestration, hardening
│   ├── cli.py                #   entry point: python -m datagen
│   ├── executor.py           #   runs one task end to end (run_task)
│   ├── bank_ingest.py        #   reads artifacts/datagen_task_bank/ into TaskSpec objects
│   ├── task_spec.py          #   the TaskSpec data model
│   ├── prompt_compose.py     #   assembles a task's PRD into the harness objective
│   ├── data_need.py          #   heuristic: does this task need input data?
│   ├── data_synth.py         #   generic LLM-schema-inference data generator
│   ├── domain_generators.py  #   prefers a hand-written real generator when one exists
│   ├── preflight.py          #   pre-run validation (task, generated data)
│   ├── independent_verify.py  #   re-runs the verification agent's claimed commands
│   ├── dataset_manifest.py    #   append-only ledger + versioned dataset snapshots
│   ├── checkpoint.py           #   crash-safe per-task resume state
│   ├── curation.py             #   durable "known-good, don't regenerate" list
│   └── README.md              #   full CLI reference
│
├── controller/                # ConversationRunner, supervisor policy, recovery,
│                               #   phase gates, tracing — the supervision layer
├── engine/                    # ExecutionEngine — turn/notification plumbing
├── adapter/chakra/            # Translates the harness interface to Chakra's gRPC API
├── interface/                 # Harness contract: events, models, capabilities
├── client/                    # Low-level Chakra gRPC client (chakra_client.py)
├── verification/              # Unified objective prompt, verdict parsing, artifacts
├── scripts/
│   ├── start_chakra.sh        #   launches the Chakra backend
│   └── real_backend.py        #   env/config loading, connection setup
│
├── pipelines/                  # Hand-written, domain-accurate data generators
│   ├── finance/data_generator.py
│   └── cybersecurity/data_generator.py
│
├── artifacts/
│   ├── datagen_task_bank/     # THE INPUT — pre-forged tasks by category
│   ├── checkpoint/            # (runtime state, created on first run)
│   ├── curation/              # (runtime state)
│   ├── dataset_manifest/      # (runtime state — the output ledger)
│   ├── verification_reports/  # (runtime state)
│   └── task_cache/            # (runtime state — cached per-task decisions)
│
├── harness/chakra/            # The Chakra coding-agent backend (separate Bun/Node app)
├── tests/                     # Unit tests for every datagen/ module (offline, no live Chakra)
├── datagen_dims/              # Standalone dimension-taxonomy/cost-estimation tool (unrelated to datagen/)
├── prompt_forge/              # Optional: PRD expansion, only used by --llm-expand
├── prompt_stats/              # Optional: prompt/cost telemetry dashboard (soft dependency)
├── debugger/                  # Offline trace analysis, for diagnosing a run after the fact
├── docs/                      # Architecture reference, handover notes, journal
│
├── pyproject.toml
├── .example.env               # Copy to .env and fill in credentials
└── README.md                  # Original repo-level README (broader harness context)
```

`experiments/` (generated repos + benchmark reports) and `logs/` (run traces) are
created as you run the pipeline — they're output, not input.

## Workflow

```
 1. Start Chakra (separate terminal)
        │
 2. python -m datagen [filters]
        │
        ▼
 3. bank_ingest.py reads artifacts/datagen_task_bank/ → TaskSpec objects
        │
        ▼
 4. For each target task (executor.py::run_task):
        │
        ├─ Skip if curated-good or already checkpoint-done (unless --force-rerun)
        ├─ preflight.validate_task → skip as INPUT_INVALID if malformed
        ├─ data_need.py decides if input data is required
        │     └─ domain_generators.py prefers a real hand-written generator
        │        (pipelines/finance, pipelines/cybersecurity) over the generic
        │        LLM-schema-inference fallback (data_synth.py)
        ├─ prompt_compose.py wraps the task's platform_prompt.md with the
        │     harness's lifecycle contract (verification/prompts.py)
        │
        ├─ ConversationRunner.run(objective)  ◄── Chakra owns plan/implement/
        │     │                                    verify/repair from here
        │     └─ retries into the SAME workdir on a transient stall
        │        (wall_clock_timeout / inactivity_timeout / progress_timeout),
        │        up to --max-retries times
        │
        ├─ On self-reported VERDICT: PASS → independent_verify.py re-runs the
        │     claimed "Command run:" lines itself → PASSED or SELF_REPORTED_ONLY
        │
        └─ dataset_manifest.append_entry() + checkpoint.mark_done/failed
              (recorded for every outcome, including skips)
        │
        ▼
 5. experiments/<stem>_benchmark.{json,csv} + _by_domain.json written
        │
 6. (optional) --freeze-dataset → immutable, content-hashed snapshot
```

## Install

**1. Chakra backend** (Bun/Node — separate app under `harness/chakra/`):

```bash
cd headless_harness_datagen/harness/chakra
bun install
```

**2. Python environment:**

```bash
cd headless_harness_datagen
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**3. Credentials:**

```bash
cp .example.env .env
# edit .env — set at minimum OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
```

## Run

**Terminal 1 — start Chakra, and leave it running:**

```bash
cd headless_harness_datagen
./scripts/start_chakra.sh
# wait for: gRPC Server running at localhost:50051
```

**Terminal 2 — run the pipeline:**

```bash
cd headless_harness_datagen
source .venv/bin/activate

# Preview what would run — no Chakra connection needed
python -m datagen --dry-run

# Run everything in the task bank
python -m datagen

# Run one category
python -m datagen --category finance_ca_practice
python -m datagen --category cybersecurity_ops

# Run a single task by id (ids come from --dry-run's output)
python -m datagen --task-id gst_01_full-gst-purchase-reconciliation-with-gstr-2b-matc

# Run a slice by global index
python -m datagen --start 1 --end 10

# Resume a killed batch (already-done tasks are skipped automatically)
python -m datagen --checkpoint-status
python -m datagen

# Cut a versioned dataset snapshot after a batch
python -m datagen --freeze-dataset
```

Full flag reference, result-status meanings, and output-path table:
[`datagen/README.md`](datagen/README.md).

## Tests (offline, no live Chakra required)

```bash
cd headless_harness_datagen
python3 -m pytest tests/test_bank_ingest.py tests/test_domain_generators.py \
  tests/test_data_need.py tests/test_data_synth.py tests/test_independent_verify.py \
  tests/test_dataset_manifest.py tests/test_checkpoint.py \
  tests/test_curation.py -v
```
