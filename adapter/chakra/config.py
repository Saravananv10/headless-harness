"""Resolve Chakra client configuration from harness ConnectionConfig."""

from __future__ import annotations

import os
from typing import Any

from client.config import ChakraConfig, load_config

from interface.models.requests import ConnectionConfig


def resolve_chakra_config(
    connection: ConnectionConfig | None = None,
) -> tuple[ChakraConfig, float]:
    """Map generic connection config onto Chakra-specific settings."""
    base = load_config()
    if connection is None:
        return base, 5.0

    host = base.grpc_host
    port = base.grpc_port
    timeout = connection.options.get("timeout_seconds", 5.0)

    if connection.endpoint:
        endpoint = connection.endpoint.strip()
        if "://" in endpoint:
            endpoint = endpoint.split("://", 1)[1]
        if ":" in endpoint:
            host_part, port_part = endpoint.rsplit(":", 1)
            host = host_part or host
            if port_part.isdigit():
                port = int(port_part)

    options: dict[str, Any] = dict(connection.options)
    host = str(options.get("host", host))
    if "port" in options:
        port = int(options["port"])

    # ChakraConfig is immutable; return a new instance with resolved endpoint.
    return ChakraConfig(
        repo_root=base.repo_root,
        chakra_root=base.chakra_root,
        grpc_host=host,
        grpc_port=port,
        proto_path=base.proto_path,
        service_name=base.service_name,
        method_name=base.method_name,
    ), float(timeout)


def apply_connection_env(config: ChakraConfig) -> None:
    """Publish endpoint to environment variables read by load_config()."""
    os.environ["CHAKRA_GRPC_HOST"] = config.grpc_host
    os.environ["CHAKRA_GRPC_PORT"] = str(config.grpc_port)
