"""Validation verdict extraction and verification PASS quality gates."""

from __future__ import annotations

import re
from enum import Enum

_VERDICT_RE = re.compile(
    r"VERDICT:\s*(PASS|FAIL|PARTIAL)\b",
    re.IGNORECASE,
)
_RUNTIME_CHECK_RE = re.compile(
    r"RUNTIME_CHECK:\s*PASS\b",
    re.IGNORECASE,
)
_USAGE_TOOL_USES_RE = re.compile(
    r"tool_uses:\s*(\d+)",
    re.IGNORECASE,
)
_COMMAND_EVIDENCE_RE = re.compile(
    r"(?:Command run:|\*\*Command run:\*\*|```(?:bash|sh|shell|zsh)?\b)",
    re.IGNORECASE,
)


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"


def parse_verdict(text: str) -> Verdict | None:
    """Extract the last VERDICT line from a validation report."""
    if not text or not text.strip():
        return None
    matches = list(_VERDICT_RE.finditer(text))
    if not matches:
        return None
    return Verdict(matches[-1].group(1).upper())


def is_verification_failure(verdict: Verdict | None) -> bool:
    """True when a verification outcome must drive repair (FAIL or PARTIAL)."""
    return verdict in (Verdict.FAIL, Verdict.PARTIAL)


def has_runtime_check_pass(text: str) -> bool:
    """True when the verifier recorded a successful build/run check."""
    if not text:
        return False
    return bool(_RUNTIME_CHECK_RE.search(text))


def has_verification_tool_evidence(text: str) -> bool:
    """
    True when the verification report shows real tool/shell work.

    Accepts either an explicit tool_uses count >= 1 in a usage footer, or
    command-run / shell-block evidence in the report body.
    """
    if not text:
        return False
    usage = _USAGE_TOOL_USES_RE.search(text)
    if usage is not None:
        try:
            if int(usage.group(1)) >= 1:
                return True
        except ValueError:
            pass
        # Explicit tool_uses: 0 means no evidence even if prose looks like commands.
        return False
    return bool(_COMMAND_EVIDENCE_RE.search(text))


def evaluation_rejects_pass(text: str) -> str | None:
    """
    Return a rejection reason if VERDICT: PASS is not acceptable, else None.

    Requires RUNTIME_CHECK: PASS and evidence of real verification work.
    """
    if not has_runtime_check_pass(text):
        return "missing RUNTIME_CHECK: PASS (build/run required)"
    if not has_verification_tool_evidence(text):
        return "missing verification tool/command evidence (zero-tool PASS rejected)"
    return None
