#!/usr/bin/env bash
#SBATCH --job-name=bacsel-random
#SBATCH --partition=prod
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=01:00:00

set -euo pipefail

SCRIPT_DIR="$(
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &&
    pwd
)"

REPO_ROOT="$(
    cd -- "$SCRIPT_DIR/../.." &&
    pwd
)"

cd "$REPO_ROOT"

fail() {
    printf 'FAIL | %s\n' "$*" >&2
    exit 1
}

command -v git >/dev/null 2>&1 ||
    fail "git not found"

command -v conda >/dev/null 2>&1 ||
    fail "conda not found"

[[ -n "${BACSELECT_RANDOM_OUTPUT_DIR:-}" ]] ||
    fail "BACSELECT_RANDOM_OUTPUT_DIR is not set"

HEAD_COMMIT="$(git rev-parse HEAD)"
ORIGIN_MAIN="$(git rev-parse origin/main)"

[[ "$HEAD_COMMIT" == "$ORIGIN_MAIN" ]] ||
    fail "HEAD does not match origin/main"

[[ -z "$(git status --porcelain)" ]] ||
    fail "repository working tree is not clean"

OUTPUT_DIR="$(
    realpath -m "$BACSELECT_RANDOM_OUTPUT_DIR"
)"

REPO_REAL="$(
    realpath -m "$REPO_ROOT"
)"

case "$OUTPUT_DIR/" in
    "$REPO_REAL/"*)
        fail "output directory must be outside the repository"
        ;;
esac

mkdir -p "$OUTPUT_DIR"

for output_name in \
    random-coverage-replicates.tsv \
    random-coverage-summary.tsv \
    random-coverage-provenance.tsv
do
    [[ ! -e "$OUTPUT_DIR/$output_name" ]] ||
        fail "output already exists: $OUTPUT_DIR/$output_name"
done

printf '%s\n' '===== BacSelect random coverage ====='
printf 'job_id\t%s\n' "${SLURM_JOB_ID:-not_slurm}"
printf 'host\t%s\n' "$(hostname)"
printf 'git_commit\t%s\n' "$HEAD_COMMIT"
printf 'origin_main\t%s\n' "$ORIGIN_MAIN"
printf 'output_dir\t%s\n' "$OUTPUT_DIR"
printf 'cpus_per_task\t%s\n' "${SLURM_CPUS_PER_TASK:-unknown}"
printf 'start_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' '====================================='

export PYTHONPATH="$REPO_ROOT/src"

conda run --no-capture-output \
    -n bacselect-dev \
    python validation/selector-v1/run_random_coverage.py \
        --replicates 1000 \
        --output-dir "$OUTPUT_DIR"

for output_name in \
    random-coverage-replicates.tsv \
    random-coverage-summary.tsv \
    random-coverage-provenance.tsv
do
    [[ -s "$OUTPUT_DIR/$output_name" ]] ||
        fail "expected non-empty output missing: $output_name"
done

printf '%s\n' '===== output SHA256 ====='
sha256sum \
    "$OUTPUT_DIR/random-coverage-replicates.tsv" \
    "$OUTPUT_DIR/random-coverage-summary.tsv" \
    "$OUTPUT_DIR/random-coverage-provenance.tsv"

printf 'finish_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' 'PASS | random coverage job completed'
