==================================================
PROCEDURAL 3D ASSET GENERATION BRIEF
The sandbox / lifecycle rules elsewhere in this objective still govern
execution boundaries, environment isolation, and verification markers.
==================================================

ASSET TO BUILD:
Minecraft-style blocky humanoid character

Build a blocky humanoid character from exactly 6 axis-aligned boxes, using this EXACT numeric blueprint in block units (a `--scale` CLI flag multiplies every dimension uniformly; these are the scale=1.0 values; +x/-x is left/right, +y/-y is depth, z is up):
  - leg_left:  size 0.5 x 0.5 x 1.5, spanning x=[-0.5,0.0], y=[-0.25,0.25], z=[0.0,1.5]
  - leg_right: size 0.5 x 0.5 x 1.5, spanning x=[0.0,0.5],  y=[-0.25,0.25], z=[0.0,1.5]
  - torso:     size 1.0 x 0.5 x 1.5, spanning x=[-0.5,0.5], y=[-0.25,0.25], z=[1.5,3.0]
  - arm_left:  size 0.5 x 0.5 x 1.5, spanning x=[-1.0,-0.5], y=[-0.25,0.25], z=[1.5,3.0]
  - arm_right: size 0.5 x 0.5 x 1.5, spanning x=[0.5,1.0],  y=[-0.25,0.25], z=[1.5,3.0]
  - head:      size 1.0 x 1.0 x 1.0, spanning x=[-0.5,0.5], y=[-0.5,0.5],  z=[3.0,4.0]
Every adjacent pair above must share a face exactly (no gaps, no overlaps): leg_left/leg_right touch at x=0; torso sits directly on both legs (torso z=1.5 == legs' top z=1.5); arm_left/arm_right touch torso's left/right faces exactly (x=-0.5 and x=0.5); head sits directly on torso (head z=3.0 == torso top z=3.0). Each of the 6 parts MUST be a separately named sub-object/group/node in the exported file (e.g. a trimesh.Scene with named geometries, or named meshes/groups/objects in whichever framework you're using) -- do not weld everything into one anonymous mesh, since the part names and per-part bounding boxes are what the validation step below checks. Each part MUST have a distinct flat RGB color baked into its faces/vertices (not left as default white): head=(255,219,172) skin tone, torso=(60,120,190) shirt blue, arm_left/arm_right=(255,219,172) skin tone, leg_left/leg_right=(60,60,140) pants navy.
REQUIRED SELF-VALIDATION (in addition to the standard checklist below) -- the script must assert every one of these and exit non-zero with a clear message if any fail:
  1. Exactly 6 named parts exist, named exactly: head, torso, arm_left, arm_right, leg_left, leg_right (case-sensitive).
  2. Each part's bounding-box dimensions match its specified size (scaled by --scale) within 1% tolerance.
  3. Each part's baked color matches its specified RGB within a small tolerance, and is not (255,255,255) default white.
  4. Each required adjacency above holds within 1% of one block unit (scaled): compute the shared-face coordinate for each pair from their bounding boxes and assert the gap is ~0.
  5. Print one VALIDATION line per part with its name, bounding box, and color, plus one final line confirming all adjacency checks passed.

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
