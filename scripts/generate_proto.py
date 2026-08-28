"""Regenerate Python gRPC stubs from client/proto/chakra.proto."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = REPO_ROOT / "client" / "proto"
OUT_DIR = REPO_ROOT / "client" / "generated"
GRPC_FILE = OUT_DIR / "chakra_pb2_grpc.py"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "__init__.py").touch()

    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{PROTO_DIR}",
        f"--python_out={OUT_DIR}",
        f"--grpc_python_out={OUT_DIR}",
        str(PROTO_DIR / "chakra.proto"),
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=REPO_ROOT)

    text = GRPC_FILE.read_text(encoding="utf-8")
    text = text.replace(
        "import chakra_pb2 as chakra__pb2",
        "from client.generated import chakra_pb2 as chakra__pb2",
    )
    GRPC_FILE.write_text(text, encoding="utf-8")
    print(f"Generated stubs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
