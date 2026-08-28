#!/usr/bin/env bash
# Start the Chakra gRPC backend (read-only use of harness/chakra — no modifications).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
    set -a
    source "$ROOT/.env"
    set +a
fi

CHAKRA_ROOT="$ROOT/harness/chakra"

export PATH="$CHAKRA_ROOT/node_modules/.bin:$PATH"
export GRPC_HOST="${GRPC_HOST:-localhost}"
export GRPC_PORT="${GRPC_PORT:-50051}"

# Fire autocompact earlier than the default near-window threshold so long
# harness pipelines summarize older context before the session fills up.
# Override in .env (e.g. 40–60) or unset DISABLE_AUTO_COMPACT for long runs.
export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE="${CLAUDE_AUTOCOMPACT_PCT_OVERRIDE:-55}"

if ! command -v bun >/dev/null 2>&1; then
  echo "error: bun is required to start Chakra. Install from https://bun.sh" >&2
  echo "For offline client testing, run: python -m client.mock_server" >&2
  exit 1
fi

cd "$CHAKRA_ROOT"
echo "Starting Chakra gRPC at ${GRPC_HOST}:${GRPC_PORT} ..."
echo "Autocompact PCT override: ${CLAUDE_AUTOCOMPACT_PCT_OVERRIDE}"
exec bun run dev:grpc
