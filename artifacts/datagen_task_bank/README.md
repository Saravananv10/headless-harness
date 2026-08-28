# Datagen task bank (13 × 10)

Generated seeds for forge categories. **Completed prior runs are excluded**
(whiteboard, smart home, Tidewatch/tower defense, PalletLens/image-class API,
Snake, social platform, gaming platform, Django blog, thin ecom_test, flask todos, etc.).

## Layout

- `by_category/<category>/*.json` — machine-readable task + dimension hints
- `by_category/<category>/*.md` — same with run command
- `by_category/<category>/SEEDS.txt` — all 10 seeds for that category
- `manifest.json` / `manifest.jsonl` — full index

## Counts

- categories: 13
- tasks: 130

## Dimension hints

Each task has `dimensions_hint` (`complexity`/`value` low|medium|hard, language,
artifact, task_family, business_domain, …). These are **targets for diversity**;
forge/LLM expansion should deepen the PRD later.

## Run one category through Chakra (example)

```bash
# start Chakra gRPC first
python main.py "$(cat artifacts/datagen_task_bank/by_category/games/01_*.md | ...)" \
  --forge-prompt --forge-category games --workdir task_games_01
```

Or use the `pipeline_cmd` field inside each JSON.

## Archive reuse

Seeds marked `archive:*` come from `docs/archive/project_prompts.md` items that
were never fully implemented in this workspace.
