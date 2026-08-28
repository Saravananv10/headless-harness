==================================================
PROCEDURAL 3D ASSET GENERATION BRIEF
The sandbox / lifecycle rules elsewhere in this objective still govern
execution boundaries, environment isolation, and verification markers.
==================================================

ASSET TO BUILD:
Wireframe latitude/longitude globe

Build a sphere represented only as a wireframe of latitude and longitude rings -- each ring modeled as a thin torus (a tube swept around a circle) rather than as flat line-primitives, so the result is a real solid mesh. Sphere radius, number of latitude rings, number of longitude rings, and tube thickness must be CLI-configurable.

FRAMEWORK: Three.js (Node.js)
Export format(s): glb

SETUP:
`npm init -y && npm install three @gltf-transform/core @gltf-transform/extensions`. Use plain Node.js with ES modules (`"type": "module"` in package.json).

GENERATION / EXPORT APPROACH:
Construct the geometry procedurally with `THREE.BufferGeometry` (set `position`, `normal`, and `index` attributes directly from your generated arrays -- do not use any of three.js's built-in primitive generators for the object itself, only for assembling primitives if the object is genuinely primitive-based). Export to glTF binary using three's `GLTFExporter` (`three/examples/jsm/exporters/GLTFExporter.js`) with `binary: true`, writing the returned ArrayBuffer to `output.glb`.

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
Reload `output.glb` independently using `@gltf-transform/core`'s `NodeIO` (`new NodeIO().read(path)`), then assert the document has at least one mesh with a non-empty `POSITION` accessor (vertex count > 0) and at least one non-empty indices accessor (face count > 0). Using a different library than the exporter for this check is deliberate -- it is a genuinely independent verification, not a same-code round-trip.
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
