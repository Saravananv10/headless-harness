"""Generate artifacts/datagen_task_bank/by_category/procedural_3d_assets/ —
21 procedurally-describable 3D objects x 4 frameworks = 84 tasks.

Each task asks an LLM coding agent to write a script (in the given
framework) that procedurally generates the object's geometry and exports it
to a real mesh file (.glb/.obj) — no external assets/textures/datasets
needed, so every task is a from-scratch build (datagen.data_need heuristic
routes these as greenfield, no input-data synthesis triggered).

Robustness + verification requirements are baked into every platform_prompt:
determinism (seeded), CLI parameterization, pre-export geometry validation,
per-format export error handling, and an independent post-export reload
check that prints a structured VALIDATION line as real evidence — mirroring
scripts/prompt_templates.py's build_3d_asset_objective(), adapted per
framework. The harness's own verification/independent_verify.py layer
re-executes the agent's claimed "Command run:" lines on top of this.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORY = "procedural_3d_assets"
OUT_DIR = ROOT / "artifacts" / "datagen_task_bank" / "by_category" / CATEGORY

# ---------------------------------------------------------------------------
# 20 objects — purely procedural/parametric, no external assets required.
# ---------------------------------------------------------------------------

OBJECTS: list[dict] = [
    {
        "slug": "lowpoly-terrain",
        "title": "Low-poly procedural terrain",
        "desc": (
            "Generate a heightmapped terrain mesh from a grid of vertices, where each "
            "vertex's elevation comes from combining at least 3 octaves of value/Perlin-style "
            "noise (decreasing amplitude, increasing frequency per octave) rather than a single "
            "sine/cosine wave. Grid resolution and world-space scale must be CLI-configurable, "
            "and the noise must be seeded so terrain is exactly reproducible."
        ),
    },
    {
        "slug": "pine-tree",
        "title": "Procedural low-poly pine tree",
        "desc": (
            "Build a stylized pine tree from a tapered cylindrical trunk plus 3-5 stacked "
            "conical foliage tiers of decreasing radius toward the top. Trunk height/radius and "
            "the number/size of foliage tiers must be CLI-configurable."
        ),
    },
    {
        "slug": "spiral-staircase",
        "title": "Parametric spiral staircase",
        "desc": (
            "Generate a helical staircase: rectangular step-tread boxes distributed along a "
            "helix around a central vertical axis, each step rotated incrementally around the "
            "axis and raised incrementally in height. Number of steps, helix radius, "
            "rise-per-step, and total rotation must be CLI-configurable."
        ),
    },
    {
        "slug": "icosphere",
        "title": "Geodesic icosphere",
        "desc": (
            "Build a geodesic sphere by starting from a regular icosahedron and recursively "
            "subdividing each triangular face N times, then projecting every vertex onto a "
            "sphere of a given radius. Subdivision level (0-4) and radius must be "
            "CLI-configurable; higher levels must produce a proportionally denser, still-valid "
            "manifold mesh."
        ),
    },
    {
        "slug": "torus-knot",
        "title": "Parametric (p,q) torus knot",
        "desc": (
            "Generate a tube mesh following a (p,q) torus knot curve (p and q winding numbers "
            "around the torus's two axes), swept with a circular cross-section of a given tube "
            "radius along the knot's path. p, q, tube radius, and path segment count must be "
            "CLI-configurable."
        ),
    },
    {
        "slug": "voxel-castle-tower",
        "title": "Voxel-style castle tower",
        "desc": (
            "Build a cylindrical tower approximated from stacked cube 'voxel' blocks arranged "
            "in a ring per level, topped with alternating raised/lowered crenellation blocks "
            "around the rim. Tower height (levels), ring radius (in voxel units), and "
            "crenellation pattern must be CLI-configurable."
        ),
    },
    {
        "slug": "gear-wheel",
        "title": "Parametric involute gear wheel",
        "desc": (
            "Generate a gear wheel: a cylindrical disc with N teeth extruded around its rim "
            "(trapezoidal or involute-style tooth profile), plus a central bore hole. Number of "
            "teeth, module (tooth size), disc thickness, and bore radius must be "
            "CLI-configurable."
        ),
    },
    {
        "slug": "rock-cluster",
        "title": "Low-poly rock cluster",
        "desc": (
            "Generate a cluster of 4-8 low-poly rocks, each built by perturbing an "
            "icosahedron's vertices along their normals with seeded random noise (breaking the "
            "perfect-sphere look), then placed at randomized (seeded) positions, rotations, and "
            "scales so they form a natural-looking cluster without overlapping at the cluster "
            "center."
        ),
    },
    {
        "slug": "picket-fence",
        "title": "Procedural picket-fence section",
        "desc": (
            "Build a repeating fence section: two horizontal rail beams connecting a row of "
            "evenly spaced vertical picket boards with pointed (pyramid-capped) tops. Picket "
            "count, spacing, picket height/width, and rail height must be CLI-configurable."
        ),
    },
    {
        "slug": "mobius-strip",
        "title": "Mobius strip surface",
        "desc": (
            "Generate a Mobius strip as a parametric surface mesh: sweep a short line segment "
            "along a circular path while simultaneously rotating the segment by half a turn "
            "(180 degrees) over one full loop, producing the characteristic single-sided, "
            "single-edge non-orientable band. Loop radius, strip width, and mesh resolution "
            "(segments along the loop and across the width) must be CLI-configurable."
        ),
    },
    {
        "slug": "lowpoly-mushroom",
        "title": "Stylized low-poly mushroom",
        "desc": (
            "Build a mushroom from a hemispherical (or flattened-dome) cap mesh seated atop a "
            "tapered cylindrical stem. Cap radius/flatness, stem height/radius, and mesh "
            "resolution must be CLI-configurable."
        ),
    },
    {
        "slug": "brick-wall-panel",
        "title": "Procedural brick-wall panel (running bond)",
        "desc": (
            "Generate a wall panel as a grid of rectangular brick prisms arranged in a "
            "running-bond pattern (each row offset by half a brick width from the row above), "
            "separated by a configurable mortar gap. Panel width/height (in bricks), brick "
            "dimensions, and mortar gap must be CLI-configurable."
        ),
    },
    {
        "slug": "coil-spring",
        "title": "Parametric helical coil spring",
        "desc": (
            "Generate a coil spring as a tube mesh swept along a helical path (circling a "
            "central axis while rising steadily along it). Coil radius, tube (wire) radius, "
            "number of coils, total spring height, and path segment count must be "
            "CLI-configurable."
        ),
    },
    {
        "slug": "robot-arm",
        "title": "Simple 3-joint robot arm (default pose)",
        "desc": (
            "Assemble a robot arm from a chain of primitive segments -- a base cylinder, "
            "followed by two box 'link' segments connected by cylindrical 'joint' sleeves at "
            "each connection point -- positioned in a plausible bent default pose (not a flat "
            "line). Segment lengths/radii must be CLI-configurable; all segments must be merged "
            "into a single exported mesh."
        ),
    },
    {
        "slug": "crystal-cluster",
        "title": "Procedural crystal cluster",
        "desc": (
            "Generate a cluster of 5-10 elongated bipyramid ('double cone') crystal shapes, "
            "each with a hexagonal or square cross-section, at seeded-random orientations, "
            "positions, and lengths, clustered around a common base point without full overlap "
            "at the origin."
        ),
    },
    {
        "slug": "lowpoly-boat-hull",
        "title": "Low-poly boat hull (lofted cross-sections)",
        "desc": (
            "Build a simple boat hull by defining 2D cross-section profile curves (narrow/"
            "pointed at bow and stern, wider amidships) at evenly spaced stations along the "
            "hull's length, then connecting corresponding points across adjacent stations to "
            "form a lofted hull surface, closed at bow and stern. Hull length, number of "
            "stations, and beam (max width) must be CLI-configurable."
        ),
    },
    {
        "slug": "star-extrusion",
        "title": "3D extruded star shape",
        "desc": (
            "Generate a 3D star ornament by extruding a 2D N-pointed star polygon (alternating "
            "outer and inner radius vertices) to a given depth, producing a solid star prism "
            "with front, back, and side faces. Number of points, outer/inner radius, and "
            "extrusion depth must be CLI-configurable."
        ),
    },
    {
        "slug": "procedural-maze",
        "title": "Procedural 2.5D maze block",
        "desc": (
            "Generate a maze as wall box-segments arranged on a grid via a seeded randomized "
            "maze-generation algorithm (e.g. randomized depth-first backtracker), sitting on a "
            "flat rectangular base plate. Grid width/height (in cells) and wall height/thickness "
            "must be CLI-configurable; the generated maze must be a single connected solvable "
            "path from one corner to the opposite corner -- verify connectivity "
            "programmatically before export."
        ),
    },
    {
        "slug": "wireframe-globe",
        "title": "Wireframe latitude/longitude globe",
        "desc": (
            "Build a sphere represented only as a wireframe of latitude and longitude rings -- "
            "each ring modeled as a thin torus (a tube swept around a circle) rather than as "
            "flat line-primitives, so the result is a real solid mesh. Sphere radius, number of "
            "latitude rings, number of longitude rings, and tube thickness must be "
            "CLI-configurable."
        ),
    },
    {
        "slug": "parametric-vase",
        "title": "Parametric lathed vase",
        "desc": (
            "Generate a vase by revolving a 2D profile curve (radius as a function of height -- "
            "narrower at the neck, wider at the belly) 360 degrees around the vertical axis. "
            "Profile control points (or function), height, and radial segment count must be "
            "CLI-configurable."
        ),
    },
    {
        "slug": "minecraft-person",
        "title": "Minecraft-style blocky humanoid character",
        "desc": (
            "Build a blocky humanoid character from exactly 6 axis-aligned boxes, using this "
            "EXACT numeric blueprint in block units (a `--scale` CLI flag multiplies every "
            "dimension uniformly; these are the scale=1.0 values; +x/-x is left/right, "
            "+y/-y is depth, z is up):\n"
            "  - leg_left:  size 0.5 x 0.5 x 1.5, spanning x=[-0.5,0.0], y=[-0.25,0.25], z=[0.0,1.5]\n"
            "  - leg_right: size 0.5 x 0.5 x 1.5, spanning x=[0.0,0.5],  y=[-0.25,0.25], z=[0.0,1.5]\n"
            "  - torso:     size 1.0 x 0.5 x 1.5, spanning x=[-0.5,0.5], y=[-0.25,0.25], z=[1.5,3.0]\n"
            "  - arm_left:  size 0.5 x 0.5 x 1.5, spanning x=[-1.0,-0.5], y=[-0.25,0.25], z=[1.5,3.0]\n"
            "  - arm_right: size 0.5 x 0.5 x 1.5, spanning x=[0.5,1.0],  y=[-0.25,0.25], z=[1.5,3.0]\n"
            "  - head:      size 1.0 x 1.0 x 1.0, spanning x=[-0.5,0.5], y=[-0.5,0.5],  z=[3.0,4.0]\n"
            "Every adjacent pair above must share a face exactly (no gaps, no overlaps): "
            "leg_left/leg_right touch at x=0; torso sits directly on both legs (torso z=1.5 == "
            "legs' top z=1.5); arm_left/arm_right touch torso's left/right faces exactly "
            "(x=-0.5 and x=0.5); head sits directly on torso (head z=3.0 == torso top z=3.0). "
            "Each of the 6 parts MUST be a separately named sub-object/group/node in the "
            "exported file (e.g. a trimesh.Scene with named geometries, or named "
            "meshes/groups/objects in whichever framework you're using) -- do not weld "
            "everything into one anonymous mesh, since the part names and per-part bounding "
            "boxes are what the validation step below checks. Each part MUST have a distinct "
            "flat RGB color baked into its faces/vertices (not left as default white): "
            "head=(255,219,172) skin tone, torso=(60,120,190) shirt blue, "
            "arm_left/arm_right=(255,219,172) skin tone, "
            "leg_left/leg_right=(60,60,140) pants navy.\n"
            "REQUIRED SELF-VALIDATION (in addition to the standard checklist below) -- the "
            "script must assert every one of these and exit non-zero with a clear message if "
            "any fail:\n"
            "  1. Exactly 6 named parts exist, named exactly: head, torso, arm_left, arm_right, "
            "leg_left, leg_right (case-sensitive).\n"
            "  2. Each part's bounding-box dimensions match its specified size (scaled by "
            "--scale) within 1% tolerance.\n"
            "  3. Each part's baked color matches its specified RGB within a small tolerance, "
            "and is not (255,255,255) default white.\n"
            "  4. Each required adjacency above holds within 1% of one block unit (scaled): "
            "compute the shared-face coordinate for each pair from their bounding boxes and "
            "assert the gap is ~0.\n"
            "  5. Print one VALIDATION line per part with its name, bounding box, and color, "
            "plus one final line confirming all adjacency checks passed."
        ),
    },
]

assert len(OBJECTS) == 21

# ---------------------------------------------------------------------------
# 4 frameworks — each a genuinely different install/export/validate path.
# ---------------------------------------------------------------------------

FRAMEWORKS: list[dict] = [
    {
        "key": "python-trimesh",
        "label": "Python (trimesh + numpy)",
        "language_runtime": "python",
        "formats": ["glb", "obj"],
        "install": (
            "Set up a project-local virtual environment and `pip install numpy trimesh`. "
            "No other dependencies should be required for mesh construction and export."
        ),
        "export": (
            "Build the mesh as `numpy` vertex/face arrays, wrap in `trimesh.Trimesh(vertices=..., "
            "faces=..., process=False)`, then call `mesh.export(path, file_type=\"glb\")` and "
            "`mesh.export(path, file_type=\"obj\")` for each requested format independently "
            "(wrap each in its own try/except)."
        ),
        "validate": (
            "Reload each exported file with `trimesh.load(path, force=\"mesh\")` and assert "
            "`loaded.vertices.shape[0] > 0` and `loaded.faces.shape[0] > 0`."
        ),
    },
    {
        "key": "threejs",
        "label": "Three.js (Node.js)",
        "language_runtime": "javascript",
        "formats": ["glb"],
        "install": (
            "`npm init -y && npm install three @gltf-transform/core @gltf-transform/extensions`. "
            "Use plain Node.js with ES modules (`\"type\": \"module\"` in package.json)."
        ),
        "export": (
            "Construct the geometry procedurally with `THREE.BufferGeometry` (set `position`, "
            "`normal`, and `index` attributes directly from your generated arrays -- do not use "
            "any of three.js's built-in primitive generators for the object itself, only for "
            "assembling primitives if the object is genuinely primitive-based). Export to glTF "
            "binary using three's `GLTFExporter` "
            "(`three/examples/jsm/exporters/GLTFExporter.js`) with `binary: true`, writing the "
            "returned ArrayBuffer to `output.glb`."
        ),
        "validate": (
            "Reload `output.glb` independently using `@gltf-transform/core`'s `NodeIO` "
            "(`new NodeIO().read(path)`), then assert the document has at least one mesh with a "
            "non-empty `POSITION` accessor (vertex count > 0) and at least one non-empty indices "
            "accessor (face count > 0). Using a different library than the exporter for this "
            "check is deliberate -- it is a genuinely independent verification, not a same-code "
            "round-trip."
        ),
    },
    {
        "key": "babylonjs",
        "label": "Babylon.js (Node.js, headless NullEngine)",
        "language_runtime": "javascript",
        "formats": ["glb"],
        "install": (
            "`npm init -y && npm install @babylonjs/core @babylonjs/serializers "
            "@gltf-transform/core`. Use plain Node.js with ES modules."
        ),
        "export": (
            "Create a headless scene with `new NullEngine()` and `new Scene(engine)` (no "
            "browser/canvas needed). Build the mesh via `VertexData` (positions/indices/normals "
            "set from your generated arrays) applied with `.applyToMesh()` on a `Mesh` instance "
            "in that scene. Export using `GLTF2Export.GLBAsync(scene, \"output\")` from "
            "`@babylonjs/serializers/glTF/2.0`, then write the resulting glTFData's file buffer "
            "to `output.glb`."
        ),
        "validate": (
            "Reload `output.glb` independently using `@gltf-transform/core`'s `NodeIO` and "
            "assert at least one mesh with non-empty POSITION and indices accessors, same as "
            "the three.js task -- a different library than the exporter."
        ),
    },
    {
        "key": "vanilla-node",
        "label": "Vanilla Node.js (zero 3D dependencies, hand-written OBJ)",
        "language_runtime": "javascript",
        "formats": ["obj"],
        "install": (
            "No npm dependencies for generation or validation -- plain Node.js `fs` module "
            "only. This task specifically demonstrates producing a correct 3D file format from "
            "first principles without any 3D library."
        ),
        "export": (
            "Compute vertex and face arrays yourself, then hand-write the Wavefront OBJ text "
            "format directly: one `v x y z` line per vertex, one `f a b c` line per triangular "
            "face using 1-indexed vertex references (OBJ is 1-indexed, not 0-indexed -- this is "
            "a common bug, be careful). Write to `output.obj` with Node's `fs.writeFileSync`."
        ),
        "validate": (
            "Write a small standalone parser (also zero dependencies) that re-reads "
            "`output.obj`, counts `v ` and `f ` lines, and for every face line checks that all "
            "referenced indices fall within `[1, vertexCount]`. Assert vertex count > 0, face "
            "count > 0, and zero out-of-range face indices."
        ),
    },
]

assert len(FRAMEWORKS) == 4


# ---------------------------------------------------------------------------
# Prompt composition
# ---------------------------------------------------------------------------

BRIEF_HEADER = """==================================================
PROCEDURAL 3D ASSET GENERATION BRIEF
The sandbox / lifecycle rules elsewhere in this objective still govern
execution boundaries, environment isolation, and verification markers.
==================================================
"""


def build_platform_prompt(obj: dict, fw: dict) -> str:
    formats = fw["formats"]
    format_list = ", ".join(formats)
    export_lines = "\n".join(f"   - `output.{fmt}`" for fmt in formats)

    return f"""{BRIEF_HEADER}
ASSET TO BUILD:
{obj['title']}

{obj['desc']}

FRAMEWORK: {fw['label']}
Export format(s): {format_list}

SETUP:
{fw['install']}

GENERATION / EXPORT APPROACH:
{fw['export']}

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
{fw['validate']}
   Print a structured summary as one of the last lines of output, e.g.:
   `VALIDATION: {{"format": "glb", "vertices": N, "faces": N, "bbox": [...], "bytes": N}}`
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
{export_lines}
   - The generator script itself, kept as a permanent, reusable file (not
     deleted after running).

Before declaring IMPLEMENTATION_STATUS: COMPLETE, actually run the script
and show its real stdout, including the VALIDATION summary line(s) for
every requested format. Record the exact "Command run:" lines with exit
codes as the harness's verification step requires -- do not claim success
without that command output.
"""


def build_seed(idx: int, obj: dict, fw: dict) -> dict:
    task_id = f"3d_{idx:03d}_{obj['slug']}_{fw['key']}"
    return {
        "index": f"{idx:03d}",
        "id": task_id,
        "title": f"{obj['title']} ({fw['label']})",
        "seed": (
            f"Build a script from scratch in {fw['label']} that procedurally generates: "
            f"{obj['desc']} Save to {', '.join(fw['formats'])} with deterministic seeding, "
            f"CLI parameterization, and an independent post-save validation step."
        ),
        "source": "original",
        "category": CATEGORY,
        "workdir": f"task_{CATEGORY}_{idx:03d}",
        "dimensions_hint": {
            "complexity": "medium",
            "value": "medium",
            "language_runtime": fw["language_runtime"],
            "artifact_type": "3d_asset_generator",
            "task_family": "coding_implement",
            "business_domain": "graphics_tooling",
            "modality": "3d_geometry",
            "verification_mode": "runtime_pass",
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    idx = 0
    for obj in OBJECTS:
        for fw in FRAMEWORKS:
            idx += 1
            seed = build_seed(idx, obj, fw)
            prompt = build_platform_prompt(obj, fw)

            json_path = OUT_DIR / f"{idx:03d}_{obj['slug']}_{fw['key']}.json"
            md_path = OUT_DIR / f"{idx:03d}_{obj['slug']}_{fw['key']}.md"
            json_path.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
            md_path.write_text(prompt, encoding="utf-8")

    print(f"Wrote {idx} tasks ({len(OBJECTS)} objects x {len(FRAMEWORKS)} frameworks) to {OUT_DIR}")


if __name__ == "__main__":
    main()
