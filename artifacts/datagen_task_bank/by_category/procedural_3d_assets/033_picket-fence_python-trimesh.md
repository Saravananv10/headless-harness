==================================================
PROCEDURAL 3D ASSET GENERATION BRIEF
The sandbox / lifecycle rules elsewhere in this objective still govern
execution boundaries, environment isolation, and verification markers.
==================================================

ASSET TO BUILD:
Procedural picket-fence section

Build a repeating fence section: two horizontal rail beams connecting a row of evenly spaced vertical picket boards with pointed (pyramid-capped) tops. Picket count, spacing, picket height/width, and rail height must be CLI-configurable.

FRAMEWORK: Python (trimesh + numpy)
Export format(s): glb, obj

SETUP:
Set up a project-local virtual environment and `pip install numpy trimesh`. No other dependencies should be required for mesh construction and export.

GENERATION / EXPORT APPROACH:
Build the mesh as `numpy` vertex/face arrays, wrap in `trimesh.Trimesh(vertices=..., faces=..., process=False)`, then call `mesh.export(path, file_type="glb")` and `mesh.export(path, file_type="obj")` for each requested format independently (wrap each in its own try/except).

SCRIPT REQUIREMENTS (non-negotiable -- this script is a reusable artifact,
not a throwaway):

1. Determinism
   - Seed all randomness explicitly, and expose the seed as a CLI argument
     (default 42). Re-running with the same seed must produce
     byte-identical (or numerically identical) geometry.

2. Parameterization
   - Expose the asset's key dimensions/complexity/resolution described above
     as CLI flags with sensible defaults -- do not hardcode magic numbers
     with no way to override them.

3. Geometry validation BEFORE export
   - Assert vertex and face arrays are non-empty.
   - Assert no NaN or Infinity values in any vertex coordinate.
   - Assert every face index is within bounds of the vertex array.
   - Compute and log the bounding box; assert it is non-degenerate (no
     zero-volume axis unless the asset is intentionally flat/planar).

4. Export robustness
   - If exporting multiple formats, wrap each format's export in its own
     try/except so one format failing does not prevent the others from
     being written.
   - After writing each file, assert it exists and its size is above a sane
     minimum byte threshold (catches silently-empty/corrupt exports).
   - Create output directories as needed; do not assume they exist.

5. Independent post-export verification
Reload each exported file with `trimesh.load(path, force="mesh")` and assert `loaded.vertices.shape[0] > 0` and `loaded.faces.shape[0] > 0`.
   Print a structured summary as one of the last lines of output, e.g.:
   `VALIDATION: {"format": "glb", "vertices": N, "faces": N, "bbox": [...], "bytes": N}`
   for each format -- this is the evidence the verification step checks,
   not a bare "success" claim.

6. Error handling
   - On any failure (missing dependency, invalid geometry, export failure,
     failed reload), print a clear diagnostic message and exit with a
     non-zero exit code. Do not swallow exceptions silently.

7. Re-runnability
   - The script must run cleanly a second time against the same output
     path (overwrite, don't error on "file exists").

OUTPUT:
   Running the script must produce, in the working directory:
   - `output.glb`
   - `output.obj`
   - The generator script itself, kept as a permanent, reusable file (not
     deleted after running).

Before declaring IMPLEMENTATION_STATUS: COMPLETE, actually run the script
and show its real stdout, including the VALIDATION summary line(s) for
every requested format. Record the exact "Command run:" lines with exit
codes as the harness's verification step requires -- do not claim success
without that command output.
