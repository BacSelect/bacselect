#!/usr/bin/env bash
#SBATCH --job-name=bacsel-cacheagg
#SBATCH --partition=prod
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=01:00:00

set -euo pipefail

fail() {
    printf 'FAIL | %s\n' "$*" >&2
    exit 1
}

EXPECTED_VERIFIER_SHA256="c0f2114907111ae9f7f89695fefcafa79fe4da3e3ed71acc597c5101db13963d"
EXPECTED_SNAPSHOT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/ncbi-sequence-validation-snapshot"
EXPECTED_OUTPUT_PARENT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/historical-cache-verification"

[[ -n "${BACSELECT_REPO_ROOT:-}" ]] ||
    fail "BACSELECT_REPO_ROOT is not set"

[[ -n "${BACSELECT_EXPECTED_COMMIT:-}" ]] ||
    fail "BACSELECT_EXPECTED_COMMIT is not set"

[[ -n "${BACSELECT_CACHE_VERIFY_OUTPUT_ROOT:-}" ]] ||
    fail "BACSELECT_CACHE_VERIFY_OUTPUT_ROOT is not set"

REPO_ROOT="$(realpath "$BACSELECT_REPO_ROOT")"
OUTPUT_ROOT="$(realpath -m "$BACSELECT_CACHE_VERIFY_OUTPUT_ROOT")"
EXPECTED_OUTPUT_ROOT="$(
    realpath -m "$EXPECTED_OUTPUT_PARENT/$BACSELECT_EXPECTED_COMMIT"
)"
BATCHES_ROOT="$OUTPUT_ROOT/batches"
AGGREGATE_OUT="$OUTPUT_ROOT/aggregate"

[[ "$OUTPUT_ROOT" == "$EXPECTED_OUTPUT_ROOT" ]] ||
    fail "output root does not match expected commit-scoped path"

[[ -d "$EXPECTED_SNAPSHOT_ROOT" ]] ||
    fail "historical snapshot root is missing"

[[ -d "$BATCHES_ROOT" ]] ||
    fail "batch verification results root is missing"

[[ ! -e "$AGGREGATE_OUT" ]] ||
    fail "aggregate output already exists"

cd "$REPO_ROOT"

HEAD_COMMIT="$(git rev-parse HEAD)"
ORIGIN_MAIN="$(git rev-parse origin/main)"

[[ "$HEAD_COMMIT" == "$BACSELECT_EXPECTED_COMMIT" ]] ||
    fail "HEAD does not match BACSELECT_EXPECTED_COMMIT"

[[ "$ORIGIN_MAIN" == "$BACSELECT_EXPECTED_COMMIT" ]] ||
    fail "origin/main does not match BACSELECT_EXPECTED_COMMIT"

[[ -z "$(git status --porcelain)" ]] ||
    fail "repository working tree is not clean"

VERIFIER="src/bacselect/source_cache_verify.py"
WRAPPER="validation/selector-v1/aggregate_historical_cache_verification.slurm"

VERIFIER_SHA256="$(sha256sum "$VERIFIER" | awk '{print $1}')"
WRAPPER_SHA256="$(sha256sum "$WRAPPER" | awk '{print $1}')"

[[ "$VERIFIER_SHA256" == "$EXPECTED_VERIFIER_SHA256" ]] ||
    fail "historical cache verifier SHA256 changed"

BATCH_COUNT="$(
    find "$BATCHES_ROOT" \
        -mindepth 1 \
        -maxdepth 1 \
        -type d \
        -name 'batch-[0-9][0-9][0-9]' \
        | wc -l \
        | tr -d '[:space:]'
)"

[[ "$BATCH_COUNT" == "111" ]] ||
    fail "expected 111 batch result directories; observed $BATCH_COUNT"

printf '%s\n' '===== verify completed batch artifacts ====='

for task in $(seq 1 111)
do
    batch="$(printf 'batch-%03d' "$task")"
    dir="$BATCHES_ROOT/$batch"

    [[ -d "$dir" ]] ||
        fail "missing batch result directory: $batch"

    [[ -s "$dir/batch-artifacts-sha256.txt" ]] ||
        fail "missing batch artifact manifest: $batch"

    (
        cd "$dir"
        sha256sum -c batch-artifacts-sha256.txt
    ) >/dev/null

    printf 'PASS | %s artifact manifest\n' "$batch"
done

CONDA="${CONDA_EXE:-}"

if [[ -z "$CONDA" ]]; then
    CONDA="$(command -v conda || true)"
fi

[[ -n "$CONDA" && -x "$CONDA" ]] ||
    fail "could not resolve conda executable"

printf '%s\n' '===== BacSelect historical cache verification aggregation ====='
printf 'job_id\t%s\n' "${SLURM_JOB_ID:-unknown}"
printf 'host\t%s\n' "$(hostname)"
printf 'git_commit\t%s\n' "$HEAD_COMMIT"
printf 'origin_main\t%s\n' "$ORIGIN_MAIN"
printf 'verifier_sha256\t%s\n' "$VERIFIER_SHA256"
printf 'wrapper_sha256\t%s\n' "$WRAPPER_SHA256"
printf 'results_root\t%s\n' "$BATCHES_ROOT"
printf 'output_dir\t%s\n' "$AGGREGATE_OUT"
printf 'start_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' '=============================================================='

export PYTHONPATH="$REPO_ROOT/src"

"$CONDA" run \
    --no-capture-output \
    -n bacselect-dev \
    python -m bacselect.source_cache_verify \
        aggregate \
        --results-root "$BATCHES_ROOT" \
        --output-dir "$AGGREGATE_OUT"

for name in \
    historical-cache-content-verification.tsv \
    historical-cache-content-verification-summary.json
do
    [[ -s "$AGGREGATE_OUT/$name" ]] ||
        fail "expected aggregate output is missing or empty: $name"
done

PROVENANCE="$AGGREGATE_OUT/run-provenance.tsv"

{
    printf 'field\tvalue\n'
    printf 'slurm_job_id\t%s\n' "${SLURM_JOB_ID:-unknown}"
    printf 'host\t%s\n' "$(hostname)"
    printf 'git_commit\t%s\n' "$HEAD_COMMIT"
    printf 'origin_main\t%s\n' "$ORIGIN_MAIN"
    printf 'expected_commit\t%s\n' "$BACSELECT_EXPECTED_COMMIT"
    printf 'verifier_sha256\t%s\n' "$VERIFIER_SHA256"
    printf 'wrapper_sha256\t%s\n' "$WRAPPER_SHA256"
    printf 'snapshot_root\t%s\n' "$EXPECTED_SNAPSHOT_ROOT"
    printf 'batch_results_root\t%s\n' "$BATCHES_ROOT"
    printf 'aggregate_output_dir\t%s\n' "$AGGREGATE_OUT"
    printf 'batch_count\t111\n'
    printf 'finished_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$PROVENANCE"

(
    cd "$AGGREGATE_OUT"
    sha256sum \
        historical-cache-content-verification.tsv \
        historical-cache-content-verification-summary.json \
        run-provenance.tsv
) > "$AGGREGATE_OUT/aggregate-artifacts-sha256.txt"

printf '%s\n' '===== aggregate summary ====='
cat "$AGGREGATE_OUT/historical-cache-content-verification-summary.json"

printf '%s\n' '===== aggregate artifact SHA256 ====='
cat "$AGGREGATE_OUT/aggregate-artifacts-sha256.txt"

printf 'finish_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' 'PASS | historical cache verification aggregation completed'
