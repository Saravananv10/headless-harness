"""Reusable, detailed objective templates for LLM-generated-script tasks.

The harness's own lifecycle contract (verification/prompts.py) governs plan /
implement / verify markers. Templates here add a domain-specific requirements
brief on top of that — same pattern as datagen/prompt_compose.py's
DOMAIN TASK BRIEF header, but for ad-hoc (non-task-bank) runs.
"""

from __future__ import annotations

BRIEF_HEADER = """==================================================
PROCEDURAL 3D ASSET GENERATION BRIEF
The sandbox / lifecycle rules elsewhere in this objective still govern
execution boundaries, environment isolation, and verification markers.
==================================================
"""


def build_3d_asset_objective(
    description: str,
    *,
    formats: list[str] | None = None,
    seed: int = 42,
) -> str:
    """Compose a detailed, robustness-focused objective for a procedural 3D
    asset generation task (LLM writes a script; the script produces the
    mesh file(s) deterministically).
    """
    formats = formats or ["glb"]
    format_list = ", ".join(formats)
    export_lines = "\n".join(f"   - `output.{fmt}`" for fmt in formats)

    return f"""{BRIEF_HEADER}
ASSET TO BUILD:
{description.strip()}

Export format(s): {format_list}

SCRIPT REQUIREMENTS (non-negotiable — this script is a reusable artifact,
not a throwaway):

1. Determinism
   - Seed all randomness explicitly (e.g. `numpy.random.seed({seed})`), and
     expose the seed as a `--seed` CLI argument (default {seed}). Re-running
     with the same seed must produce byte-identical geometry.

2. Parameterization
   - Expose the asset's key dimensions/complexity (e.g. size, resolution,
     grid density) as argparse CLI flags with sensible defaults — do not
     hardcode magic numbers with no way to override them.

3. Geometry validation BEFORE export
   - Assert vertex and face arrays are non-empty.
   - Assert no NaN or Inf values in vertex coordinates.
   - Assert every face index is within bounds of the vertex array.
   - Compute and log the bounding box; assert it is non-degenerate
     (no zero-volume axis unless the asset is intentionally flat/planar).

4. Export robustness
   - Wrap each format's export in its own try/except so one format failing
     does not prevent the others from being written.
   - After writing each file, assert it exists and its size is above a
     sane minimum byte threshold (catches silently-empty/corrupt exports).
   - Create output directories as needed; do not assume they exist.

5. Independent post-export verification
   - Reload each exported file (via the same or a different loader) and
     assert: non-zero vertices/faces, correct file type, vertex/face counts
     consistent with what was generated (exact match, or a documented
     tolerance if the exporter triangulates/welds vertices).
   - Print a structured summary as the last line of output, e.g.:
     `VALIDATION: {{"format": "glb", "vertices": N, "faces": N, "bbox": [...], "bytes": N}}`
     for each format — this is the evidence the verification step checks,
     not a bare "success" claim.

6. Error handling
   - On any failure (missing dependency, invalid geometry, export failure,
     failed reload), print a clear diagnostic message and exit with a
     non-zero exit code. Do not swallow exceptions silently.
   - If a required library is missing, install it into the project's own
     virtual environment before retrying — do not fall back to silently
     skipping the step.

7. Re-runnability
   - The script must run cleanly a second time against the same output
     path (overwrite, don't error on "file exists").

OUTPUT:
   Running the script must produce, in the working directory:
{export_lines}
   - The generator script itself, kept as a permanent, reusable file
     (not deleted after running).

Before declaring IMPLEMENTATION_STATUS: COMPLETE, actually run the script
and show its real stdout, including the VALIDATION summary line(s) for
every requested format. Do not claim success without that command output.
"""
