#!/usr/bin/env bash
#SBATCH --job-name=bacsel-final-lofo
#SBATCH --partition=prod
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=12:00:00

set -euo pipefail

fail() {
    printf 'FAIL | %s\n' "$*" >&2
    exit 1
}

command -v git >/dev/null 2>&1 ||
    fail "git not found"

command -v conda >/dev/null 2>&1 ||
    fail "conda not found"

[[ -n "${BACSELECT_REPO_ROOT:-}" ]] ||
    fail "BACSELECT_REPO_ROOT is not set"

[[ -n "${BACSELECT_FINAL_LOFO_OUTPUT_DIR:-}" ]] ||
    fail "BACSELECT_FINAL_LOFO_OUTPUT_DIR is not set"

[[ -n "${BACSELECT_EXPECTED_COMMIT:-}" ]] ||
    fail "BACSELECT_EXPECTED_COMMIT is not set"

REPO_ROOT="$(
    realpath "$BACSELECT_REPO_ROOT"
)"

[[ -d "$REPO_ROOT/.git" ]] ||
    fail "BACSELECT_REPO_ROOT is not a Git repository: $REPO_ROOT"

cd "$REPO_ROOT"

HEAD_COMMIT="$(git rev-parse HEAD)"
ORIGIN_MAIN="$(git rev-parse origin/main)"

[[ "$HEAD_COMMIT" == "$BACSELECT_EXPECTED_COMMIT" ]] ||
    fail "HEAD does not match BACSELECT_EXPECTED_COMMIT"

[[ "$ORIGIN_MAIN" == "$BACSELECT_EXPECTED_COMMIT" ]] ||
    fail "origin/main does not match BACSELECT_EXPECTED_COMMIT"

[[ -z "$(git status --porcelain)" ]] ||
    fail "repository working tree is not clean"

OUTPUT_DIR="$(
    realpath -m "$BACSELECT_FINAL_LOFO_OUTPUT_DIR"
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

REPORT="$OUTPUT_DIR/final300-2400-lofo.tsv"
PROVENANCE="$OUTPUT_DIR/final300-2400-lofo-provenance.tsv"

for output in \
    "$REPORT" \
    "$PROVENANCE"
do
    [[ ! -e "$output" ]] ||
        fail "output already exists: $output"
done

RUNNER="validation/selector-v1/run_final_lofo.py"
WRAPPER="validation/selector-v1/run_final_lofo.slurm"
ENV_LOCK="envs/bacselect-dev-linux-64.lock"
INPUT_MANIFEST="validation/selector-v1/final-feature-space-inputs.tsv"
REFERENCE_METRICS="validation/selector-v1/results/final300-2400-ops-vs-sr-metrics.tsv"
REFERENCE_SUMMARY="validation/selector-v1/results/final300-2400-ops-vs-sr-summary.json"

RUNNER_SHA256="$(
    sha256sum "$RUNNER" |
        awk '{print $1}'
)"

WRAPPER_SHA256="$(
    sha256sum "$WRAPPER" |
        awk '{print $1}'
)"

ENV_LOCK_SHA256="$(
    sha256sum "$ENV_LOCK" |
        awk '{print $1}'
)"

INPUT_MANIFEST_SHA256="$(
    sha256sum "$INPUT_MANIFEST" |
        awk '{print $1}'
)"

REFERENCE_METRICS_SHA256="$(
    sha256sum "$REFERENCE_METRICS" |
        awk '{print $1}'
)"

REFERENCE_SUMMARY_SHA256="$(
    sha256sum "$REFERENCE_SUMMARY" |
        awk '{print $1}'
)"

printf '%s\n' '===== BacSelect final 300/2400 LOFO validation ====='
printf 'job_id\t%s\n' "${SLURM_JOB_ID:-not_slurm}"
printf 'host\t%s\n' "$(hostname)"
printf 'git_commit\t%s\n' "$HEAD_COMMIT"
printf 'origin_main\t%s\n' "$ORIGIN_MAIN"
printf 'output_dir\t%s\n' "$OUTPUT_DIR"
printf 'cpus_per_task\t%s\n' "${SLURM_CPUS_PER_TASK:-unknown}"
printf 'memory\t%s\n' "${SLURM_MEM_PER_NODE:-unknown}"
printf 'runner_sha256\t%s\n' "$RUNNER_SHA256"
printf 'wrapper_sha256\t%s\n' "$WRAPPER_SHA256"
printf 'env_lock_sha256\t%s\n' "$ENV_LOCK_SHA256"
printf 'input_manifest_sha256\t%s\n' "$INPUT_MANIFEST_SHA256"
printf 'reference_metrics_sha256\t%s\n' "$REFERENCE_METRICS_SHA256"
printf 'reference_summary_sha256\t%s\n' "$REFERENCE_SUMMARY_SHA256"
printf 'start_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' '===================================================='

export PYTHONPATH="$REPO_ROOT/src"

conda run --no-capture-output \
    -n bacselect-dev \
    python "$RUNNER" \
        --output "$REPORT"

[[ -s "$REPORT" ]] ||
    fail "expected non-empty final LOFO report is missing"

REPORT_SHA256="$(
    sha256sum "$REPORT" |
        awk '{print $1}'
)"

REPORT_LINES="$(
    wc -l < "$REPORT" |
        tr -d '[:space:]'
)"

[[ "$REPORT_LINES" == "145" ]] ||
    fail "unexpected final LOFO report line count: $REPORT_LINES"

{
    printf 'field\tvalue\n'
    printf 'job_id\t%s\n' "${SLURM_JOB_ID:-not_slurm}"
    printf 'git_commit\t%s\n' "$HEAD_COMMIT"
    printf 'origin_main\t%s\n' "$ORIGIN_MAIN"
    printf 'runner_sha256\t%s\n' "$RUNNER_SHA256"
    printf 'wrapper_sha256\t%s\n' "$WRAPPER_SHA256"
    printf 'env_lock_sha256\t%s\n' "$ENV_LOCK_SHA256"
    printf 'input_manifest_sha256\t%s\n' "$INPUT_MANIFEST_SHA256"
    printf 'reference_metrics_sha256\t%s\n' "$REFERENCE_METRICS_SHA256"
    printf 'reference_summary_sha256\t%s\n' "$REFERENCE_SUMMARY_SHA256"
    printf 'report_sha256\t%s\n' "$REPORT_SHA256"
    printf 'report_lines\t%s\n' "$REPORT_LINES"
    printf 'panel_sizes\t10,20,50,100,200,500\n'
    printf 'removed_features\t12\n'
    printf 'selectors\tOPS,SR\n'
    printf 'selection_geometry\tfinal300-2400_leave_one_of_12\n'
    printf 'evaluation_geometry\tfrozen_final300-2400_full12\n'
    printf 'reference_geometry\tfrozen_final300-2400_full12\n'
    printf 'identity_blinding\tREQUIRED\n'
    printf 'selector_decision_rule_introduced\tNO\n'
} > "$PROVENANCE"

[[ -s "$PROVENANCE" ]] ||
    fail "expected non-empty provenance output is missing"

printf '%s\n' '===== output SHA256 ====='
sha256sum \
    "$REPORT" \
    "$PROVENANCE"

printf 'finish_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' 'PASS | final LOFO validation job completed'
