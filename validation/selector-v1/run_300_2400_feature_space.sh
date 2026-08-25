#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$HOME/github/bacselect"
EXPECTED_COMMIT="0f75c51edc37259f168ad10faf44d536dd9b75a5"

[[ -d "$REPO/.git" ]] || {
    echo "FAIL | BacSelect repository not found at $REPO" >&2
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

python3 -m py_compile \
    "$PACKAGE_DIR/build_300_2400_feature_space.py"

PYTHONPATH="$REPO/src" \
    conda run \
        --no-capture-output \
        -n bacselect-dev \
        python3 \
        "$PACKAGE_DIR/build_300_2400_feature_space.py"
