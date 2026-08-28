"""Step 4.1 — validate connection via ChakraHarness on real backend."""

from __future__ import annotations

from adapter.chakra import ChakraHarness
from interface import ConnectionConfig, Harness
from interface.capabilities import HarnessCapability
from phase4_common import journal_entry
from scripts.real_backend import connection_config, load_project_env


def main() -> int:
    load_project_env()
    harness: Harness = ChakraHarness()
    info = harness.connect(connection_config())
    caps = harness.capabilities()
    live = harness.connection_info()
    harness.disconnect()
    after = harness.connection_info()

    ok = (
        info.connected
        and info.adapter_name == "chakra"
        and live.connected
        and not after.connected
        and caps.supports(HarnessCapability.STREAMING)
        and caps.supports(HarnessCapability.SESSIONS)
    )

    journal_entry(
        milestone="Step 4.1 — Connection Adapter",
        design_decisions=[
            "ChakraHarness wraps ChakraClient behind Harness.connect/disconnect.",
            "Connection uses .env GRPC_HOST/GRPC_PORT via connection_config().",
        ],
        implementation=["adapter/chakra/harness.py", "adapter/chakra/config.py"],
        validation="PASS" if ok else "FAIL",
        issues=[],
        observations=[f"Connected to real backend at {info.endpoint}."],
        conclusions=["Connection adapter works against live Chakra."],
        next_steps=["Validate session adapter."],
    )
    print("Step 4.1 PASS" if ok else "Step 4.1 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
