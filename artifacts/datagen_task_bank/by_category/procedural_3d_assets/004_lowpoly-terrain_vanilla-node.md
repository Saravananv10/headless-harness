==================================================
PROCEDURAL 3D ASSET GENERATION BRIEF
The sandbox / lifecycle rules elsewhere in this objective still govern
execution boundaries, environment isolation, and verification markers.
==================================================

ASSET TO BUILD:
Low-poly procedural terrain

Generate a heightmapped terrain mesh from a grid of vertices, where each vertex's elevation comes from combining at least 3 octaves of value/Perlin-style noise (decreasing amplitude, increasing frequency per octave) rather than a single sine/cosine wave. Grid resolution and world-space scale must be CLI-configurable, and the noise must be seeded so terrain is exactly reproducible.

FRAMEWORK: Vanilla Node.js (zero 3D dependencies, hand-written OBJ)
Export format(s): obj

SETUP:
No npm dependencies for generation or validation -- plain Node.js `fs` module only. This task specifically demonstrates producing a correct 3D file format from first principles without any 3D library.

GENERATION / EXPORT APPROACH:
Compute vertex and face arrays yourself, then hand-write the Wavefront OBJ text format directly: one `v x y z` line per vertex, one `f a b c` line per triangular face using 1-indexed vertex references (OBJ is 1-indexed, not 0-indexed -- this is a common bug, be careful). Write to `output.obj` with Node's `fs.writeFileSync`.

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
Write a small standalone parser (also zero dependencies) that re-reads `output.obj`, counts `v ` and `f ` lines, and for every face line checks that all referenced indices fall within `[1, vertexCount]`. Assert vertex count > 0, face count > 0, and zero out-of-range face indices.
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
   - `output.obj`
   - The generator script itself, kept as a permanent, reusable file (not
     deleted after running).

Before declaring IMPLEMENTATION_STATUS: COMPLETE, actually run the script
and show its real stdout, including the VALIDATION summary line(s) for
every requested format. Record the exact "Command run:" lines with exit
codes as the harness's verification step requires -- do not claim success
without that command output.
