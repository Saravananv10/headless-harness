# Run category marathons (forged, dimension-varied)

Each category folder has:

- `CHAKRA_PASTE_ALL_10_FORGED.md` — **paste this into Chakra** (full PRDs)
- `CHAKRA_PASTE_ALL_10.md` — short seeds only (not for real runs)
- `HOW_TO_RUN_ALL_10.md`
- JSON tasks with `dimensions_hint` + `forge_brief` (language, complexity, UI, …)

## Games (ready)

```powershell
cd C:\Users\anshg\.cursor\headless_harness_datagen\harness\chakra
chakra --dangerously-skip-permissions
```

Paste:

`artifacts/datagen_task_bank/by_category/games/CHAKRA_PASTE_ALL_10_FORGED.md`

Stats: `python -m prompt_stats serve` → http://127.0.0.1:8787/

## Regenerate dims / forge

```powershell
cd C:\Users\anshg\.cursor\headless_harness_datagen
python scripts/diversify_task_bank.py
python scripts/forge_category_batch.py games --force
python scripts/forge_all_categories.py          # all cats
python scripts/assemble_forged_paste.py games
```

## Dimension variety (per task)

Each of the 10 tasks locks a different mix of:

language_runtime, complexity, value, ui_surface, persistence,
verification_mode, testing_depth, tool_profile, user_persona,
agent_topology, session_shape, repo_state, delivery, novelty_hook

Plus time budgets: low≈8m / medium≈15m / hard≈25m.
