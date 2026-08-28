"""prompt_compose.py — assemble a task's own narrative into a PRD-style
objective, then wrap it with the existing harness lifecycle contract.

Deterministic by default: every bank task already carries its own spec-level
detail (Title, Description, Step-by-Step Process, Decision Tree/Scenarios,
Industry Standard), so no per-category template or LLM call is required to
produce a usable objective. An optional LLM expansion pass can add extra
platform depth.
"""

from __future__ import annotations

from pathlib import Path

from verification.prompts import build_unified_pipeline_objective

from datagen.task_spec import TaskSpec

BRIEF_HEADER = """==================================================
DOMAIN TASK BRIEF (FROM TASK BANK)
This block was extracted from a task-bank entry for THIS task only. It
specifies the product/workflow to build. The sandbox / lifecycle rules
elsewhere in this objective still govern execution boundaries, environment
isolation, and verification markers.
==================================================
"""


def compose_brief(
    spec: TaskSpec, *, data_dir: Path | None = None, data_files: list[str] | None = None
) -> str:
    """Assemble the task's own content into one objective brief.

    A bank task usually already carries a fully LLM-expanded PRD in
    `spec.platform_prompt` (produced ahead of time by prompt_forge) — that is
    strictly higher quality than reassembling it from raw fields, so it's
    used verbatim when present. Falls back to deterministic field assembly
    for the rare task bank entry with no forged platform_prompt.
    """
    if spec.platform_prompt.strip():
        parts = [BRIEF_HEADER, spec.platform_prompt.strip()]
        if data_dir and data_files:
            rel_files = "\n".join(f"  - {Path(f).name}" for f in data_files)
            parts += [
                "",
                f"Pre-generated input data is available at {data_dir} — read and use these "
                f"files as the task's source data (do not fabricate different input data):\n{rel_files}",
            ]
        return "\n".join(parts)

    parts = [BRIEF_HEADER, f"Title: {spec.title}", "", f"Description: {spec.description}"]
    if spec.process_steps:
        parts += ["", f"Step-by-Step Process:\n{spec.process_steps}"]
    if spec.decision_tree:
        parts += [
            "",
            f"Decision Tree / Scenarios (handle these branches explicitly):\n{spec.decision_tree}",
        ]
    if spec.standards:
        parts += ["", f"Industry Standard / Framework to align with: {spec.standards}"]
    if spec.variant:
        parts += ["", f"Variant requirements: {spec.variant}"]
    if data_dir and data_files:
        rel_files = "\n".join(f"  - {Path(f).name}" for f in data_files)
        parts += [
            "",
            f"Pre-generated input data is available at {data_dir} — read and use these "
            f"files as the task's source data (do not fabricate different input data):\n{rel_files}",
        ]
    category_line = spec.category + (f" / {spec.subcategory}" if spec.subcategory else "")
    parts += ["", f"Category: {category_line}"]
    return "\n".join(parts)


def compose_objective(
    spec: TaskSpec,
    *,
    repo_path: str,
    max_repair_iterations: int = 3,
    include_verification: bool = True,
    data_dir: Path | None = None,
    data_files: list[str] | None = None,
    llm_expand: bool = False,
    llm=None,
) -> str:
    """Build the final ConversationRunner-ready objective for one task."""
    brief = compose_brief(spec, data_dir=data_dir, data_files=data_files)

    if llm_expand and llm is not None:
        from prompt_forge.meta_prompt import META_SYSTEM_PROMPT

        expanded = llm.complete(
            [
                {"role": "system", "content": META_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Expand the following task brief into a more detailed, unique "
                        "platform PRD while preserving every requirement stated. Output "
                        "the PRD only, no commentary.\n\n" + brief
                    ),
                },
            ],
            temperature=0.7,
        )
        if len(expanded.strip()) > 600:
            brief = (
                f"{brief}\n\n--------------------------------------------------\n"
                f"EXPANDED PRD\n{expanded.strip()}"
            )

    return build_unified_pipeline_objective(
        repo_path=repo_path,
        objective=brief,
        max_repair_iterations=max_repair_iterations,
        include_verification=include_verification,
    )
