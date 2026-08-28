==================================================
PROCEDURAL 3D ASSET GENERATION BRIEF
The sandbox / lifecycle rules elsewhere in this objective still govern
execution boundaries, environment isolation, and verification markers.
==================================================

ASSET TO BUILD:
Parametric spiral staircase

Generate a helical staircase: rectangular step-tread boxes distributed along a helix around a central vertical axis, each step rotated incrementally around the axis and raised incrementally in height. Number of steps, helix radius, rise-per-step, and total rotation must be CLI-configurable.

FRAMEWORK: Babylon.js (Node.js, headless NullEngine)
Export format(s): glb

SETUP:
`npm init -y && npm install @babylonjs/core @babylonjs/serializers @gltf-transform/core`. Use plain Node.js with ES modules.

GENERATION / EXPORT APPROACH:
Create a headless scene with `new NullEngine()` and `new Scene(engine)` (no browser/canvas needed). Build the mesh via `VertexData` (positions/indices/normals set from your generated arrays) applied with `.applyToMesh()` on a `Mesh` instance in that scene. Export using `GLTF2Export.GLBAsync(scene, "output")` from `@babylonjs/serializers/glTF/2.0`, then write the resulting glTFData's file buffer to `output.glb`.

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
Reload `output.glb` independently using `@gltf-transform/core`'s `NodeIO` and assert at least one mesh with non-empty POSITION and indices accessors, same as the three.js task -- a different library than the exporter.
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
   - The generator script itself, kept as a permanent, reusable file (not
     deleted after running).

Before declaring IMPLEMENTATION_STATUS: COMPLETE, actually run the script
and show its real stdout, including the VALIDATION summary line(s) for
every requested format. Record the exact "Command run:" lines with exit
codes as the harness's verification step requires -- do not claim success
without that command output.
