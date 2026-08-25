#!/usr/bin/env bash
#SBATCH --job-name=bacsel-fdet
#SBATCH --partition=prod
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00

set -euo pipefail

fail() {
    printf 'FAIL | %s\n' "$*" >&2
    exit 1
}

[[ -n "${BACSELECT_REPO_ROOT:-}" ]] ||
    fail "BACSELECT_REPO_ROOT is not set"
[[ -n "${BACSELECT_FINAL_DETERMINISM_OUTPUT_DIR:-}" ]] ||
    fail "BACSELECT_FINAL_DETERMINISM_OUTPUT_DIR is not set"
[[ -n "${BACSELECT_EXPECTED_COMMIT:-}" ]] ||
    fail "BACSELECT_EXPECTED_COMMIT is not set"

REPO_ROOT="$(realpath "$BACSELECT_REPO_ROOT")"
cd "$REPO_ROOT"

HEAD_COMMIT="$(git rev-parse HEAD)"
ORIGIN_MAIN="$(git rev-parse origin/main)"

[[ "$HEAD_COMMIT" == "$ORIGIN_MAIN" ]] || fail "HEAD does not match origin/main"
[[ "$HEAD_COMMIT" == "$BACSELECT_EXPECTED_COMMIT" ]] ||
    fail "HEAD does not match expected commit"
[[ -z "$(git status --porcelain)" ]] || fail "working tree is not clean"

OUTPUT_DIR="$(realpath -m "$BACSELECT_FINAL_DETERMINISM_OUTPUT_DIR")"
REPO_REAL="$(realpath -m "$REPO_ROOT")"
case "$OUTPUT_DIR/" in
    "$REPO_REAL/"*) fail "output directory must be outside repository" ;;
esac
[[ ! -e "$OUTPUT_DIR" ]] || fail "output directory already exists"

RUNNER="validation/selector-v1/run_final_determinism.py"
WRAPPER="validation/selector-v1/run_final_determinism.slurm"
METHOD="validation/selector-v1/final-determinism-update-stability-method.md"
ENV_LOCK="envs/bacselect-dev-linux-64.lock"

RUNNER_SHA256="$(sha256sum "$RUNNER" | awk '{print $1}')"
WRAPPER_SHA256="$(sha256sum "$WRAPPER" | awk '{print $1}')"
METHOD_SHA256="$(sha256sum "$METHOD" | awk '{print $1}')"
ENV_LOCK_SHA256="$(sha256sum "$ENV_LOCK" | awk '{print $1}')"

printf '%s\n' '===== BacSelect final deterministic rebuild ====='
printf 'job_id\t%s\n' "${SLURM_JOB_ID:-not_slurm}"
printf 'git_commit\t%s\n' "$HEAD_COMMIT"
printf 'runner_sha256\t%s\n' "$RUNNER_SHA256"
printf 'wrapper_sha256\t%s\n' "$WRAPPER_SHA256"
printf 'method_sha256\t%s\n' "$METHOD_SHA256"
printf 'env_lock_sha256\t%s\n' "$ENV_LOCK_SHA256"
printf 'start_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

export PYTHONPATH="$REPO_ROOT/src"

conda run --no-capture-output \
    -n bacselect-dev \
    python "$RUNNER" \
        --output-dir "$OUTPUT_DIR"

for name in \
    final-determinism-percentile-matrix.tsv \
    final-determinism-ladders.tsv \
    final-determinism-coverage.tsv \
    final-determinism-report.json
do
    [[ -s "$OUTPUT_DIR/$name" ]] || fail "missing scientific output: $name"
done

PROVENANCE="$OUTPUT_DIR/final-determinism-provenance.tsv"
{
    printf 'field\tvalue\n'
    printf 'job_id\t%s\n' "${SLURM_JOB_ID:-not_slurm}"
    printf 'git_commit\t%s\n' "$HEAD_COMMIT"
    printf 'origin_main\t%s\n' "$ORIGIN_MAIN"
    printf 'expected_commit\t%s\n' "$BACSELECT_EXPECTED_COMMIT"
    printf 'runner_sha256\t%s\n' "$RUNNER_SHA256"
    printf 'wrapper_sha256\t%s\n' "$WRAPPER_SHA256"
    printf 'method_sha256\t%s\n' "$METHOD_SHA256"
    printf 'env_lock_sha256\t%s\n' "$ENV_LOCK_SHA256"
    for name in \
        final-determinism-percentile-matrix.tsv \
        final-determinism-ladders.tsv \
        final-determinism-coverage.tsv \
        final-determinism-report.json
    do
        printf '%s_sha256\t%s\n' \
            "${name//[^A-Za-z0-9]/_}" \
            "$(sha256sum "$OUTPUT_DIR/$name" | awk '{print $1}')"
    done
    printf 'identity_blinding\tREQUIRED\n'
    printf 'selector_decision_rule_introduced\tNO\n'
} > "$PROVENANCE"

printf '%s\n' '===== provenance SHA256 ====='
sha256sum "$PROVENANCE"
printf 'finish_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' 'PASS | final deterministic-rebuild job completed'
