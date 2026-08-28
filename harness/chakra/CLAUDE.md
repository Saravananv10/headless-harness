# Datagen autonomy (overrides default “confirm first / pausing is cheap”)

You are instructed to work **fully autonomously** for harness datagen tasks.

## Hard rules
- **Never** ask for confirmation, approval, go-ahead, or “which phase next?”
- **Never** refuse for size, time, or “too big for one response”
- **No** wall-clock or turn budgets — ignore any Time budget language in prompts
- Keep calling tools until acceptance criteria pass; then print `DONE …`
- Do **not** stop after scaffolding, a phase plan, or “please confirm”
- Local file/shell/test work needs no confirmation
- If a tool/package is missing, work around it and keep going (stdlib / alternate stack)

## Demo quality (mandatory — not optional polish)
- A task is **not DONE** if the browser/API only shows a dead page, empty shell, or “upload that does nothing.”
- Ship a **working interactive demo**: forms that submit, lists that refresh, API actions that mutate visible state, seeded sample data on first load.
- Match Depth/UI fidelity: **low** = fewer screens but still working; **medium/hard** = multi-panel / richer interactions as locked.
- Forbidden as DONE: placeholder lorem, single unstyled form with no success path, README-only, preview HTML that isn’t wired to real behavior.
- `api_only` still needs a usable operator surface (static console or preview that calls the live API) unless the PRD explicitly forbids any UI.

## Shells / servers
- Do **not** leave `npm install`, servers, or long jobs hung in the background across stops.
- Prefer foreground commands; if you background a server, verify `/health` then keep implementing in the same turn.
- Before printing DONE, kill orphaned duplicate servers on the same port.

## When you would normally stop
Instead of ending the turn with prose: make the next tool call immediately.
Only end a turn after printing an explicit `DONE task_…` (or equivalent) line.
After DONE, immediately open the **next** task’s single `platform_prompt.md` (never the whole forged paste file).
