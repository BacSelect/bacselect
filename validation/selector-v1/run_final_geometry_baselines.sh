#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/github/bacselect"

fail() {
    echo "FAIL | $*" >&2
    exit 1
}

[[ -d "$REPO/.git" ]] || \
    fail "BacSelect repository not found at $REPO"

cd "$REPO"

EXPECTED_COMMIT="$(
    git rev-parse HEAD
)"

[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || \
    fail "could not resolve full HEAD commit"

[[ "$(git rev-parse origin/main)" == "$EXPECTED_COMMIT" ]] || \
    fail "HEAD and origin/main differ"

[[ -z "$(git status --porcelain)" ]] || \
    fail "BacSelect working tree is not clean"

OUT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/final-geometry-baselines/$EXPECTED_COMMIT"

[[ ! -e "$OUT" ]] || \
    fail "output directory already exists: $OUT"

CONDA="${CONDA_EXE:-}"

if [[ -z "$CONDA" ]]; then
    CONDA="$(command -v conda || true)"
fi

[[ -n "$CONDA" && -x "$CONDA" ]] || \
    fail "could not resolve conda executable"

export BACSELECT_EXPECTED_COMMIT="$EXPECTED_COMMIT"

PYTHONPATH="$REPO/src:$REPO/validation/selector-v1" \
    "$CONDA" run \
        --no-capture-output \
        -n bacselect-dev \
        python3 \
        validation/selector-v1/derive_final_geometry_baselines.py \
        --output-dir "$OUT"
