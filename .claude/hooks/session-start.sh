#!/bin/bash
# Project-scoped SessionStart hook: injects the ai-dev-bootstrap Development
# Context automatically, in every session that opens this repository,
# without relying on any per-machine global install (sidekick has no
# external dependencies, so running it straight from src/ is sufficient).
set -euo pipefail

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python3 -m sidekick.bootstrap --json
