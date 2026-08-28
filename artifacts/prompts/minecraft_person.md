==================================================
PROCEDURAL 3D ASSET GENERATION BRIEF
The sandbox / lifecycle rules elsewhere in this objective still govern
execution boundaries, environment isolation, and verification markers.
==================================================

ASSET TO BUILD:
Build a Minecraft-style blocky humanoid character from axis-aligned box primitives: a cube head, a rectangular torso, two rectangular arms, and two rectangular legs, proportioned and positioned in the classic 'Steve/Alex' silhouette (arms at torso sides, legs below torso, head centered above torso) in a neutral standing pose, all boxes touching with no gaps or overlaps at the joints. Assign a distinct flat color to each body part (e.g. a skin tone for the head, a shirt color for the torso, a pants color for the legs) via per-face vertex colors -- no texture images required. Overall character height (in block units) and each part's proportions (relative to a base 'block' unit, Minecraft-style) must be CLI-configurable.

Export format(s): glb, obj

SCRIPT REQUIREMENTS (non-negotiable — this script is a reusable artifact,
not a throwaway):

1. Determinism
   - Seed all randomness explicitly (e.g. `numpy.random.seed(42)`), and
     expose the seed as a `--seed` CLI argument (default 42). Re-running
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
     `VALIDATION: {"format": "glb", "vertices": N, "faces": N, "bbox": [...], "bytes": N}`
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
   - `output.glb`
   - `output.obj`
   - The generator script itself, kept as a permanent, reusable file
     (not deleted after running).

Before declaring IMPLEMENTATION_STATUS: COMPLETE, actually run the script
and show its real stdout, including the VALIDATION summary line(s) for
every requested format. Do not claim success without that command output.
