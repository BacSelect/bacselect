#!/usr/bin/env bash
#SBATCH --job-name=bacsel-final-random
#SBATCH --partition=prod
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=02:00:00

set -euo pipefail

fail() {
    printf 'FAIL | %s\n' "$*" >&2
    exit 1
}

[[ -n "${BACSELECT_REPO_ROOT:-}" ]] || \
    fail "BACSELECT_REPO_ROOT is not set"

[[ -n "${BACSELECT_EXPECTED_COMMIT:-}" ]] || \
    fail "BACSELECT_EXPECTED_COMMIT is not set"

[[ -n "${BACSELECT_RANDOM_OUTPUT_DIR:-}" ]] || \
    fail "BACSELECT_RANDOM_OUTPUT_DIR is not set"

REPO_ROOT="$(
    realpath "$BACSELECT_REPO_ROOT"
)"

[[ -d "$REPO_ROOT/.git" ]] || \
    fail "BACSELECT_REPO_ROOT is not a Git repository"

cd "$REPO_ROOT"

HEAD_COMMIT="$(
    git rev-parse HEAD
)"
ORIGIN_MAIN="$(
    git rev-parse origin/main
)"

[[ "$HEAD_COMMIT" == "$BACSELECT_EXPECTED_COMMIT" ]] || \
    fail "HEAD does not match BACSELECT_EXPECTED_COMMIT"

[[ "$ORIGIN_MAIN" == "$BACSELECT_EXPECTED_COMMIT" ]] || \
    fail "origin/main does not match BACSELECT_EXPECTED_COMMIT"

[[ -z "$(git status --porcelain)" ]] || \
    fail "repository working tree is not clean"

OUTPUT_DIR="$(
    realpath -m \
        "$BACSELECT_RANDOM_OUTPUT_DIR"
)"

REPO_REAL="$(
    realpath -m "$REPO_ROOT"
)"

case "$OUTPUT_DIR/" in
    "$REPO_REAL/"*)
        fail "output directory must be outside repository"
        ;;
esac

[[ ! -e "$OUTPUT_DIR" ]] || \
    fail "output directory already exists: $OUTPUT_DIR"

CONDA="${CONDA_EXE:-}"

if [[ -z "$CONDA" ]]; then
    CONDA="$(command -v conda || true)"
fi

[[ -n "$CONDA" && -x "$CONDA" ]] || \
    fail "could not resolve conda executable"

printf '%s\n' '===== BacSelect final random coverage ====='
printf 'job_id\t%s\n' "${SLURM_JOB_ID:-not_slurm}"
printf 'host\t%s\n' "$(hostname)"
printf 'git_commit\t%s\n' "$HEAD_COMMIT"
printf 'origin_main\t%s\n' "$ORIGIN_MAIN"
printf 'output_dir\t%s\n' "$OUTPUT_DIR"
printf 'cpus_per_task\t%s\n' "${SLURM_CPUS_PER_TASK:-unknown}"
printf 'start_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' '==========================================='

export PYTHONPATH="$REPO_ROOT/src:$REPO_ROOT/validation/selector-v1"

"$CONDA" run \
    --no-capture-output \
    -n bacselect-dev \
    python3 \
    validation/selector-v1/run_final_random_coverage.py \
    --replicates 1000 \
    --output-dir "$OUTPUT_DIR"

for output_name in \
    final300-2400-random-coverage-replicates.tsv \
    final300-2400-random-coverage-summary.tsv \
    final300-2400-random-coverage-provenance.json \
    final300-2400-random-coverage-sha256.txt
do
    [[ -s "$OUTPUT_DIR/$output_name" ]] || \
        fail "expected output missing: $output_name"
done

printf '%s\n' '===== output SHA256 ====='
sha256sum \
    "$OUTPUT_DIR/final300-2400-random-coverage-replicates.tsv" \
    "$OUTPUT_DIR/final300-2400-random-coverage-summary.tsv" \
    "$OUTPUT_DIR/final300-2400-random-coverage-provenance.json" \
    "$OUTPUT_DIR/final300-2400-random-coverage-sha256.txt"

printf 'finish_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' 'PASS | final random coverage job completed'
