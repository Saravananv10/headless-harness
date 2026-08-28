"""Load Chakra backend location and connection settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "chakra.yaml"


@dataclass(frozen=True)
class ChakraConfig:
    """Resolved configuration for talking to the Chakra gRPC backend."""

    repo_root: Path
    chakra_root: Path
    grpc_host: str
    grpc_port: int
    proto_path: Path
    service_name: str
    method_name: str

    @property
    def address(self) -> str:
        return f"{self.grpc_host}:{self.grpc_port}"


def load_config(config_path: Path | None = None) -> ChakraConfig:
    """Load config from YAML, overridden by environment variables."""
    path = config_path or _DEFAULT_CONFIG
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    chakra = raw["chakra"]
    repo_root = _REPO_ROOT

    chakra_root = Path(chakra["root"])
    if not chakra_root.is_absolute():
        chakra_root = repo_root / chakra_root

    grpc = chakra["grpc"]
    proto_rel = chakra["proto"]["local_copy"]
    proto_path = Path(proto_rel)
    if not proto_path.is_absolute():
        proto_path = repo_root / proto_path

    host = os.environ.get("CHAKRA_GRPC_HOST", grpc["host"])
    port = int(os.environ.get("CHAKRA_GRPC_PORT", grpc["port"]))

    return ChakraConfig(
        repo_root=repo_root,
        chakra_root=chakra_root,
        grpc_host=host,
        grpc_port=port,
        proto_path=proto_path,
        service_name=grpc["service"],
        method_name=grpc["method"],
    )
