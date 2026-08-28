"""Milestone 1.1 — verify Chakra backend location and environment."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from client.config import load_config

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def _log_path() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return LOG_DIR / f"verify_chakra_{ts}.json"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("verify_chakra")
    config = load_config()

    results: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "milestone": "1.1",
        "checks": {},
    }

    def check(name: str, ok: bool, detail: str) -> None:
        results["checks"][name] = {"ok": ok, "detail": detail}
        status = "PASS" if ok else "FAIL"
        log.info("[%s] %s — %s", status, name, detail)

    check(
        "chakra_root_exists",
        config.chakra_root.is_dir(),
        str(config.chakra_root),
    )
    check(
        "proto_source_exists",
        (config.chakra_root / "src/proto/chakra.proto").is_file(),
        str(config.chakra_root / "src/proto/chakra.proto"),
    )
    check(
        "grpc_server_source_exists",
        (config.chakra_root / "src/grpc/server.ts").is_file(),
        str(config.chakra_root / "src/grpc/server.ts"),
    )
    check(
        "local_proto_copy_exists",
        config.proto_path.is_file(),
        str(config.proto_path),
    )
    check(
        "python_version",
        sys.version_info >= (3, 10),
        sys.version,
    )

    bun = shutil.which("bun")
    check("bun_available", bun is not None, bun or "not found — required to start Chakra gRPC")

    node = shutil.which("node")
    node_ok = False
    node_detail = node or "not found"
    if node:
        try:
            ver = subprocess.check_output([node, "--version"], text=True).strip()
            major = int(ver.lstrip("v").split(".")[0])
            node_ok = major >= 20
            node_detail = f"{ver} at {node} (Chakra requires >= 20)"
        except Exception as exc:
            node_detail = str(exc)
    if not node_ok:
        brew_node = Path("/opt/homebrew/bin/node")
        if brew_node.is_file():
            try:
                ver = subprocess.check_output([str(brew_node), "--version"], text=True).strip()
                major = int(ver.lstrip("v").split(".")[0])
                if major >= 20:
                    node_ok = True
                    node_detail = (
                        f"Active shell uses old node; {ver} available at {brew_node}. "
                        "Add /opt/homebrew/bin to PATH before starting Chakra."
                    )
            except Exception:
                pass
    check("node_version", node_ok, node_detail)

    npm = shutil.which("npm")
    check("npm_available", npm is not None, npm or "not found")

    chakra_pkg = config.chakra_root / "package.json"
    check("chakra_package_json", chakra_pkg.is_file(), str(chakra_pkg))

    node_modules = config.chakra_root / "node_modules"
    check("chakra_node_modules", node_modules.is_dir(), str(node_modules))

    out = _log_path()
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    log.info("Wrote verification log to %s", out)

    all_ok = all(
        c["ok"]
        for name, c in results["checks"].items()
        if name not in ("bun_available",)
    )
    critical = [k for k, v in results["checks"].items() if k not in ("bun_available",) and not v["ok"]]
    if critical:
        log.error("Failed checks: %s", ", ".join(critical))
        return 1
    if not results["checks"]["bun_available"]["ok"]:
        log.warning("Bun not found — install from https://bun.sh to start the real Chakra backend")
    if not results["checks"]["node_version"]["ok"]:
        log.warning("Node >= 20 required to run Chakra — use nvm or Homebrew node")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
