#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$HOME/github/bacselect"
EXPECTED_COMMIT="3c77cd33902bde25571aa4c04ab8d2e528bbec97"

[[ -d "$REPO/.git" ]] || {
    echo "FAIL | BacSelect repo not found at $REPO" >&2
    exit 1
}

cd "$REPO"

[[ "$(git rev-parse HEAD)" == "$EXPECTED_COMMIT" ]] || {
    echo "FAIL | unexpected HEAD" >&2
    exit 1
}

[[ "$(git rev-parse origin/main)" == "$EXPECTED_COMMIT" ]] || {
    echo "FAIL | unexpected origin/main" >&2
    exit 1
}

[[ -z "$(git status --porcelain)" ]] || {
    echo "FAIL | BacSelect working tree is not clean" >&2
    exit 1
}

PYTHONPATH="$REPO/src" \
    conda run \
        --no-capture-output \
        -n bacselect-dev \
        python3 \
        "$PACKAGE_DIR/analyze_repeat_scale_selection.py"
