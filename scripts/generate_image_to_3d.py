#!/usr/bin/env python3
"""Text prompt -> image (diffusion model) -> 3D mesh (image-to-3D model).

Two independent calls against your company's TensorStudio deployment:

  1. Image generation: OpenAI-compatible POST {OPENAI_BASE_URL}/images/generations
     using IMAGE_MODEL (e.g. a Flux/SDXL deployment). Same auth as the rest of
     this repo (OPENAI_API_KEY).

  2. Image-to-3D: POST to THREED_API_URL with the generated image, using
     THREED_API_KEY. This endpoint's exact request/response shape depends on
     how TripoSR/InstantMesh/Hunyuan3D-2 is deployed on your side — the
     request body below is a reasonable starting guess (image bytes fine,
     multipart/form-data), not a confirmed contract. Adjust
     `call_image_to_3d()` once you have the real API docs.

Neither call goes through Chakra or ox-alpha — this is a direct, deterministic
pipeline, no coding agent involved.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> dict[str, str]:
    env: dict[str, str] = dict(os.environ)
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def generate_image(prompt: str, *, base_url: str, api_key: str, model: str) -> bytes:
    """Call an OpenAI-compatible /images/generations endpoint. Returns PNG bytes."""
    url = f"{base_url.rstrip('/')}/images/generations"
    body = {"model": model, "prompt": prompt, "n": 1, "response_format": "b64_json"}
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Image generation HTTP {exc.code}: {detail}") from exc

    b64 = payload["data"][0]["b64_json"]
    return base64.b64decode(b64)


def call_image_to_3d(image_bytes: bytes, *, api_url: str, api_key: str) -> bytes:
    """Call the image-to-3D deployment. Returns raw .glb bytes.

    PLACEHOLDER CONTRACT — confirm and adjust against your actual deployment:
      request:  multipart/form-data, field "image" = PNG bytes
      response: raw application/octet-stream .glb body
    """
    boundary = "----3dgen-boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="input.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    request = urllib.request.Request(
        api_url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Image-to-3D HTTP {exc.code}: {detail}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Text prompt -> image -> 3D mesh")
    parser.add_argument("prompt", help="Text prompt describing the object to generate")
    parser.add_argument("--out-dir", default="experiments/generated_3d", help="Output directory")
    parser.add_argument("--image-only", action="store_true", help="Stop after image generation")
    args = parser.parse_args()

    env = load_env()
    base_url = env.get("OPENAI_BASE_URL", "")
    api_key = env.get("OPENAI_API_KEY", "")
    image_model = env.get("IMAGE_MODEL", "")
    threed_url = env.get("THREED_API_URL", "")
    threed_key = env.get("THREED_API_KEY", api_key)

    if not base_url or not api_key:
        print("error: OPENAI_BASE_URL / OPENAI_API_KEY not set in .env", file=sys.stderr)
        return 1
    if not image_model:
        print(
            "error: set IMAGE_MODEL in .env to your deployed image model's name "
            "(e.g. IMAGE_MODEL=flux-dev)",
            file=sys.stderr,
        )
        return 1

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating image for: {args.prompt!r} (model={image_model})")
    image_bytes = generate_image(args.prompt, base_url=base_url, api_key=api_key, model=image_model)
    image_path = out_dir / "generated.png"
    image_path.write_bytes(image_bytes)
    print(f"Image saved: {image_path} ({len(image_bytes)} bytes)")

    if args.image_only:
        return 0

    if not threed_url:
        print(
            "\nSkipping 3D step: THREED_API_URL not set in .env. "
            "Set THREED_API_URL (and THREED_API_KEY if different from OPENAI_API_KEY) "
            "once your TripoSR/InstantMesh/Hunyuan3D-2 deployment is live, then re-run "
            "with --image-only omitted.",
            file=sys.stderr,
        )
        return 0

    print(f"Generating mesh from image (endpoint={threed_url})")
    glb_bytes = call_image_to_3d(image_bytes, api_url=threed_url, api_key=threed_key)
    glb_path = out_dir / "output.glb"
    glb_path.write_bytes(glb_bytes)
    print(f"Mesh saved: {glb_path} ({len(glb_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
