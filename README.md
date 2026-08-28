# Headless Harness

Autonomous headless harness for the [Chakra](harness/chakra) gRPC coding backend.

One long-lived Chakra conversation owns **plan → implement → verify → repair → re-verify**.
Python does not write the project itself. It starts the session, auto-approves tools,
keeps the conversation alive, steers when the pipeline stalls, traces everything, and
stops on an authoritative verification outcome (or a configured safety limit).

| Doc | When to read it |
|-----|-----------------|
| This README | Setup, commands, runbook |
| [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md) | Full prose explanation of idea, flow, and every major component |
| [`docs/HANDOVER.md`](docs/HANDOVER.md) | Operator handover, layout, what not to delete |
| [`docs/DEBUGGER.md`](docs/DEBUGGER.md) | Offline log analysis after a run |
| [`docs/refactoring.md`](docs/refactoring.md) | Why Python is a supervisor, not a workflow engine |

---

## Idea in one paragraph

Chakra is a coding agent runtime (tools, subagents, context compaction). This repo wraps
it so a single natural-language objective becomes a real repository under `experiments/`,
with verification that must prove a real build or smoke run—not static file review alone.
Python watches lifecycle markers, denies out-of-order verification, recovers from stalls
and workspace confusion, and writes full traces under `logs/` so you can debug offline.

---

## Pipeline flow

```text
objective (main.py)
    → unified bootstrap prompt
    → ConversationRunner + one Chakra session
         → Plan (plan.md)
         → general-purpose (env + implement + IMPLEMENTATION_STATUS)
         → verification (RUNTIME_CHECK + VERDICT)
         → on FAIL/PARTIAL: Plan repair → GP repair → re-verify
    → artifacts under logs/<run-id>/pipeline/
```

**Ownership**

| Concern | Owner |
|---------|--------|
| Plan / implement / verify / repair decisions | Chakra (subagents) |
| Tool yes/no | Python auto-approver + phase / execution policy |
| Phase nudges and recovery | Python resume nudges + recovery effects |
| Chat history and compaction | Chakra |
| Traces and reports | Python |

**Lifecycle markers** (emitted in agent output; Python observes them)

| Marker | Who | Meaning |
|--------|-----|---------|
| `ENV_STATUS: READY` | general-purpose | Project-local env ready |
| `IMPLEMENTATION_STATUS: COMPLETE` | general-purpose | Implementation finished |
| `RUNTIME_CHECK: PASS` | verification | Real build/run evidence |
| `VERDICT: PASS / FAIL / PARTIAL` | verification only | Authoritative outcome |
| `REPAIR_STATUS: COMPLETE` | general-purpose | Repair cycle finished |

`VERDICT: PASS` without `RUNTIME_CHECK: PASS` is rejected. Verification Agents are denied
until `IMPLEMENTATION_STATUS: COMPLETE` is seen.

---

## Prompt forge (unique platform add-ons)

Optional mid-layer that sits **between** a short task seed and the harness bootstrap.
It classifies the seed into a category, expands a durable category template via LLM into
a unique PLATFORM ADD-ON PRD, then composes that onto the existing sandbox/lifecycle
prompt (add-on only — original harness rules stay).

```bash
python -m prompt_forge list
python main.py "Smart home dashboard with schedules" --forge-prompt
python main.py "Inventory for a bike shop" --forge-prompt --forge-category ecommerce
```

Details: [`prompt_forge/README.md`](prompt_forge/README.md). Category templates live in
`prompt_forge/templates/`.

### Prompt statistics (every Chakra prompt)

Durable ledger of prompt size, complexity, timing, and outcomes:

```bash
python -m prompt_stats refresh
python -m prompt_stats show
python -m prompt_stats serve        # graphs UI → http://127.0.0.1:8787/
```

Data lives in [`artifacts/prompt_stats/`](artifacts/prompt_stats/) (`ledger.jsonl`).
`serve` auto-syncs new interactive Chakra prompts. See [`prompt_stats/README.md`](prompt_stats/README.md).

---

## Prerequisites

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10+ | Harness and tests |
| Bun | latest | Start Chakra |
| Node.js | ≥ 20 | Chakra runtime |
| LLM provider | via `.env` | Real agent chat (OpenAI-compatible) |

Copy [`.example.env`](.example.env) to `.env` and set at least `OPENAI_API_KEY`,
`OPENAI_BASE_URL`, and `OPENAI_MODEL`.

---

## Setup

```bash
cd headless_harness_datagen
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .example.env .env               # then edit credentials
```

---

## Start Chakra (Terminal 1)

```bash
cd headless_harness_datagen
./scripts/start_chakra.sh
```

Wait for `gRPC Server running at localhost:50051` and registered subagents, for example:

```text
gRPC built-in subagents: Plan, general-purpose, verification, Explore
```

The script loads `.env` and defaults `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=55` so long runs
compact mid-window. Do not set `DISABLE_AUTO_COMPACT=1` for long pipelines.
**Restart Chakra** after changing Chakra-side env or files under `harness/chakra/src/grpc/`.

### Smoke checks (Terminal 2)

```bash
source .venv/bin/activate
python tests/test_connectivity.py
python scripts/smoke_chakra_subagents.py   # Explore spawn; ~1–3 minutes
python tests/test_minimal_chat.py
```

---

## Run the production pipeline (Terminal 2)

```bash
cd headless_harness_datagen
source .venv/bin/activate

# Full lifecycle in one conversation
python main.py "Create a recipe management web app with React, TypeScript, and Vite"

# Custom project folder under experiments/
python main.py "Build a personal finance tracker API" --workdir personal-finance-tracker

# Named logs + higher limits
python main.py "Build a todo app with tests" \
  --workdir todo_app \
  --run-id my_todo_run \
  --max-turns 60 \
  --max-decisions 60 \
  --max-repair-iterations 10

# Generation only (complete on IMPLEMENTATION_STATUS, no verify/repair)
python main.py "Prototype a CLI tool" --skip-verification

# From a prompt file
python main.py "$(cat prompt.txt)" --workdir my_project --run-id my_run
```

### CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--workdir` | `autonomous_run` | Repo under `experiments/<workdir>/` |
| `--run-id` | auto timestamp | Logs under `logs/<run-id>/` |
| `--max-turns` | `40` | Safety cap on backend turns |
| `--max-decisions` | `40` | Safety cap on resume cycles |
| `--max-repair-iterations` | `15` | Stop after this many failed verification rounds |
| `--skip-verification` | off | Complete on implementation marker |
| `--no-trace` | off | Disable JSONL tracing |

Exit code `0` = success (`VERDICT: PASS`, or generation complete with `--skip-verification`).
Exit code `1` = incomplete, limits, health stop, or missing authoritative PASS.

---

## Outputs

| Path | Contents |
|------|----------|
| `experiments/<workdir>/` | Generated repository |
| `logs/<run-id>/pipeline/report.md` | Final assistant / verdict summary |
| `logs/<run-id>/pipeline/verdict.json` | Parsed verdict |
| `logs/<run-id>/pipeline/summary.json` | Run metadata + lifecycle snapshot |
| `logs/<run-id>/pipeline/trace.jsonl` | Normalized orchestration trace |
| `logs/<run-id>/pipeline/raw_events.jsonl` | Raw harness / Chakra events |
| `logs/<run-id>/pipeline/working/` | Live traces during the run |
| `logs/<run-id>/pipeline/debug/` | Offline debugger reports (after analyze) |

### After a run

```bash
cat logs/<run-id>/pipeline/verdict.json
cat logs/<run-id>/pipeline/report.md
cat logs/<run-id>/pipeline/summary.json
ls -la experiments/<workdir>/
```

### Run the generated project (stack-dependent)

```bash
cd experiments/<workdir>

# Node / TypeScript
npm install && npm test && npm run build

# Python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # if present
pytest                            # if tests exist

# Static / built frontend
python3 -m http.server 8000       # open http://localhost:8000
```

Re-run against the same repo with a new log folder:

```bash
python main.py "Same objective" --workdir <workdir> --run-id <new-run-id>
```

---

## Offline debugger

Analyze artifacts under `logs/<run-id>/pipeline/` (writes `pipeline/debug/report.md`):

```bash
python -m debugger analyze logs/<run-id>
python -m debugger analyze logs/<run-id> --stall-cycles 5
python -m debugger compare logs/run_a logs/run_b
python scripts/debug_run.py analyze logs/<run-id>
```

Accepts `logs/<run-id>`, `logs/<run-id>/pipeline`, or `…/pipeline/working`.
Full guide: [`docs/DEBUGGER.md`](docs/DEBUGGER.md).

---

## Controller behavior (short)

Python is progress-aware. Soft continues and tool chatter alone do not count as
forward progress—only phase transitions and completed milestones reset the stall
counter. When stalled, recovery may:

- force Plan / implement (and deny further Explore spawns),
- soft-reset workspace after repeated out-of-repo / harness path denials,
- escalate repair after rejected verification,
- terminate with a causal reason (`no_forward_progress`, `stuck_in_explore`,
  `denial_loop`, `phase_budget_exceeded:<phase>`, …).

Defaults: up to **3** recovery attempts (`HARNESS_MAX_RECOVERY_ATTEMPTS`),
**5** stall cycles (`HARNESS_STALL_CYCLES`). Phase budgets cover turns, tool calls,
and reads (no per-phase wall-clock timers). Details in the project guide and debugger doc.

---

## Environment variables

| Variable | Typical default | Purpose |
|----------|-----------------|---------|
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | (required) | LLM for Chakra |
| `GRPC_HOST` / `GRPC_PORT` | `localhost` / `50051` | Chakra endpoint |
| `HARNESS_TURN_TIMEOUT` | large | Max idle seconds between gRPC events in a turn |
| `HARNESS_INACTIVITY_TIMEOUT_MINUTES` | `60` | Stop if no activity |
| `HARNESS_PROGRESS_TIMEOUT_MINUTES` | `20` | Session stagnation handling |
| `HARNESS_MAX_REPAIR_ITERATIONS` | `15` | Failed verification rounds |
| `HARNESS_STALL_CYCLES` | `5` | Resumes without workflow progress before recovery |
| `HARNESS_MAX_RECOVERY_ATTEMPTS` | `3` | Recoveries before causal terminate |
| `HARNESS_DENIAL_LOOP_THRESHOLD` | `3` | Identical denials → denial loop |
| `HARNESS_WORKSPACE_CONFUSION_THRESHOLD` | `3` | Out-of-repo / harness denials → workspace reset |
| `HARNESS_EXPLORE_MIN_READS` | `3` | Explore exit: unique in-repo reads after Explore completes |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | `55` via start script | When Chakra autocompacts |
| `CLAUDE_STREAM_IDLE_TIMEOUT_MS` | high | Max gap between stream chunks (restart Chakra) |
| `DISABLE_AUTO_COMPACT` | unset | Do **not** set for long pipelines |
| `ALLOW_AGENT_WORKTREE` | `1` | Allow worktree isolation on Agent spawn |
| `ENABLE_TOOL_SEARCH` | `false` | Chakra deferred tool schemas |

See [`.example.env`](.example.env) for a full template.

---

## Repository layout

```text
main.py                 Production pipeline entry
controller/             ConversationRunner, lifecycle, nudges, recovery, traces
verification/           Unified prompt, verdict parser, artifacts
debugger/               Offline analyze / compare
adapter/ engine/ interface/ client/   Harness stack (not Chakra source)
scripts/                start_chakra, smoke, test runner, helpers
tests/                  Automated tests
docs/                   Guides (this README points here)
experiments/            Generated project workdirs
logs/                   Run traces (safe to delete locally)
harness/chakra/         Chakra backend — do not “clean” casually
```

---

## Manual and helper CLIs

Single-turn / exploratory (not the full autonomous pipeline):

```bash
python scripts/run_query.py "Create a simple snake game in Python"
python scripts/run_query.py "Build a todo app in Flask" --workdir todo_app
python scripts/run_query.py "Create a calculator CLI" --approve manual
python scripts/run_autonomous.py "Create hello.py that prints Hello World"
```

---

## Testing

```bash
# Connectivity / smoke (Chakra running)
python tests/test_connectivity.py
python tests/test_minimal_chat.py

# Core orchestration (often no live LLM)
python tests/test_lifecycle.py
python tests/test_conversation_runner.py
python tests/test_phase_gate.py
python tests/test_progress_tracker.py
python tests/test_recovery_nudge.py
python tests/test_explore_exit.py
python tests/test_workspace_confusion.py
python tests/test_execution_policy.py

# Full real-backend suite (several minutes)
python scripts/run_all_real_tests.py

python -c "import main"
```

Historical Phase 1–6 validation tests still live under `tests/test_phase*.py` and exercise
the adapter, engine, and older controller surfaces. Production path is `main.py` +
`ConversationRunner`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Could not connect to Chakra` | Start `./scripts/start_chakra.sh` in another terminal |
| Provider error on Chakra start | Check `.env` LLM vars |
| Turn dies mid-work | Raise `HARNESS_TURN_TIMEOUT` |
| Stream aborts on slow models | Raise `CLAUDE_STREAM_IDLE_TIMEOUT_MS`, restart Chakra |
| Stuck in Explore / denials | Inspect debugger report; check workspace root and recovery |
| False `VERDICT: PASS` rejected | Need `RUNTIME_CHECK: PASS` + command evidence |
| Pipeline crash on recover log | Ensure frozenset/set JSON handling in `controller/trace.py` (already fixed) |

---

## Further reading

- [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md) — verbose plain-language project guide
- [`docs/HANDOVER.md`](docs/HANDOVER.md) — handover checklist and file ownership
- [`docs/DEBUGGER.md`](docs/DEBUGGER.md) — offline diagnosis
- [`docs/architecture_reference.md`](docs/architecture_reference.md) — harness contract detail
- [`docs/refactoring.md`](docs/refactoring.md) — design rationale for single-conversation supervision
