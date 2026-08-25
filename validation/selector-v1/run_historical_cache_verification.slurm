#!/usr/bin/env bash
#SBATCH --job-name=bacsel-cachehash
#SBATCH --partition=prod
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=04:00:00
#SBATCH --array=1-111%4

set -euo pipefail

fail() {
    printf 'FAIL | %s\n' "$*" >&2
    exit 1
}

EXPECTED_VERIFIER_SHA256="c0f2114907111ae9f7f89695fefcafa79fe4da3e3ed71acc597c5101db13963d"
EXPECTED_IMPLEMENTATION_NOTE_SHA256="f324c9021ddea58b9098f72a91b20b0040343007e9ce259e6c1ae9e2803fad6c"
EXPECTED_SNAPSHOT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/ncbi-sequence-validation-snapshot"
EXPECTED_OUTPUT_PARENT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/historical-cache-verification"

[[ -n "${BACSELECT_REPO_ROOT:-}" ]] ||
    fail "BACSELECT_REPO_ROOT is not set"

[[ -n "${BACSELECT_EXPECTED_COMMIT:-}" ]] ||
    fail "BACSELECT_EXPECTED_COMMIT is not set"

[[ -n "${BACSELECT_CACHE_VERIFY_OUTPUT_ROOT:-}" ]] ||
    fail "BACSELECT_CACHE_VERIFY_OUTPUT_ROOT is not set"

task="${SLURM_ARRAY_TASK_ID:-}"

[[ "$task" =~ ^[0-9]+$ ]] ||
    fail "SLURM_ARRAY_TASK_ID is missing or invalid"

(( task >= 1 && task <= 111 )) ||
    fail "SLURM_ARRAY_TASK_ID is outside 1..111"

REPO_ROOT="$(realpath "$BACSELECT_REPO_ROOT")"
SNAPSHOT_ROOT="$(realpath "$EXPECTED_SNAPSHOT_ROOT")"
OUTPUT_ROOT="$(realpath -m "$BACSELECT_CACHE_VERIFY_OUTPUT_ROOT")"
EXPECTED_OUTPUT_ROOT="$(
    realpath -m "$EXPECTED_OUTPUT_PARENT/$BACSELECT_EXPECTED_COMMIT"
)"

[[ -d "$REPO_ROOT/.git" ]] ||
    fail "BACSELECT_REPO_ROOT is not a Git repository"

[[ "$OUTPUT_ROOT" == "$EXPECTED_OUTPUT_ROOT" ]] ||
    fail "output root does not match expected commit-scoped path"

[[ -d "$SNAPSHOT_ROOT" ]] ||
    fail "historical snapshot root is missing"

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
WRAPPER="validation/selector-v1/run_historical_cache_verification.slurm"
IMPLEMENTATION_NOTE="validation/selector-v1/prospective-historical-cache-verification-implementation.md"

VERIFIER_SHA256="$(sha256sum "$VERIFIER" | awk '{print $1}')"
WRAPPER_SHA256="$(sha256sum "$WRAPPER" | awk '{print $1}')"
IMPLEMENTATION_NOTE_SHA256="$(
    sha256sum "$IMPLEMENTATION_NOTE" | awk '{print $1}'
)"

[[ "$VERIFIER_SHA256" == "$EXPECTED_VERIFIER_SHA256" ]] ||
    fail "historical cache verifier SHA256 changed"

[[ "$IMPLEMENTATION_NOTE_SHA256" == \
    "$EXPECTED_IMPLEMENTATION_NOTE_SHA256" ]] ||
    fail "historical cache implementation note SHA256 changed"

BATCH="$(printf 'batch-%03d' "$task")"
BATCH_DIR="$SNAPSHOT_ROOT/$BATCH"
BATCHES_OUTPUT_ROOT="$OUTPUT_ROOT/batches"
OUT="$BATCHES_OUTPUT_ROOT/$BATCH"

[[ -d "$BATCH_DIR" ]] ||
    fail "historical batch directory is missing: $BATCH_DIR"

[[ -d "$BATCHES_OUTPUT_ROOT" ]] ||
    fail "batch output root does not exist"

[[ ! -e "$OUT" ]] ||
    fail "batch verification output already exists: $OUT"

CONDA="${CONDA_EXE:-}"

if [[ -z "$CONDA" ]]; then
    CONDA="$(command -v conda || true)"
fi

[[ -n "$CONDA" && -x "$CONDA" ]] ||
    fail "could not resolve conda executable"

printf '%s\n' '===== BacSelect historical cache content verification ====='
printf 'job_id\t%s\n' "${SLURM_JOB_ID:-unknown}"
printf 'array_job_id\t%s\n' "${SLURM_ARRAY_JOB_ID:-unknown}"
printf 'array_task_id\t%s\n' "$task"
printf 'batch\t%s\n' "$BATCH"
printf 'host\t%s\n' "$(hostname)"
printf 'git_commit\t%s\n' "$HEAD_COMMIT"
printf 'origin_main\t%s\n' "$ORIGIN_MAIN"
printf 'verifier_sha256\t%s\n' "$VERIFIER_SHA256"
printf 'wrapper_sha256\t%s\n' "$WRAPPER_SHA256"
printf 'implementation_note_sha256\t%s\n' "$IMPLEMENTATION_NOTE_SHA256"
printf 'snapshot_root\t%s\n' "$SNAPSHOT_ROOT"
printf 'output_dir\t%s\n' "$OUT"
printf 'cpus_per_task\t%s\n' "${SLURM_CPUS_PER_TASK:-unknown}"
printf 'memory_mb\t%s\n' "${SLURM_MEM_PER_NODE:-unknown}"
printf 'start_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' '=========================================================='

export PYTHONPATH="$REPO_ROOT/src"

"$CONDA" run \
    --no-capture-output \
    -n bacselect-dev \
    python -m bacselect.source_cache_verify \
        verify-batch \
        --batch-dir "$BATCH_DIR" \
        --output-dir "$OUT"

for name in \
    package-file-verification.tsv \
    accession-cache-verification.tsv \
    batch-cache-verification-summary.json
do
    [[ -s "$OUT/$name" ]] ||
        fail "expected verifier output is missing or empty: $name"
done

PROVENANCE="$OUT/run-provenance.tsv"

{
    printf 'field\tvalue\n'
    printf 'slurm_job_id\t%s\n' "${SLURM_JOB_ID:-unknown}"
    printf 'slurm_array_job_id\t%s\n' "${SLURM_ARRAY_JOB_ID:-unknown}"
    printf 'slurm_array_task_id\t%s\n' "$task"
    printf 'batch\t%s\n' "$BATCH"
    printf 'host\t%s\n' "$(hostname)"
    printf 'git_commit\t%s\n' "$HEAD_COMMIT"
    printf 'origin_main\t%s\n' "$ORIGIN_MAIN"
    printf 'expected_commit\t%s\n' "$BACSELECT_EXPECTED_COMMIT"
    printf 'verifier_sha256\t%s\n' "$VERIFIER_SHA256"
    printf 'wrapper_sha256\t%s\n' "$WRAPPER_SHA256"
    printf 'implementation_note_sha256\t%s\n' "$IMPLEMENTATION_NOTE_SHA256"
    printf 'snapshot_root\t%s\n' "$SNAPSHOT_ROOT"
    printf 'output_dir\t%s\n' "$OUT"
    printf 'cpus_per_task\t%s\n' "${SLURM_CPUS_PER_TASK:-unknown}"
    printf 'memory_mb\t%s\n' "${SLURM_MEM_PER_NODE:-unknown}"
    printf 'finished_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$PROVENANCE"

(
    cd "$OUT"
    sha256sum \
        package-file-verification.tsv \
        accession-cache-verification.tsv \
        batch-cache-verification-summary.json \
        run-provenance.tsv
) > "$OUT/batch-artifacts-sha256.txt"

[[ -s "$OUT/batch-artifacts-sha256.txt" ]] ||
    fail "batch artifact SHA256 manifest is missing"

printf '%s\n' '===== batch artifact SHA256 ====='
cat "$OUT/batch-artifacts-sha256.txt"

printf 'finish_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'PASS | %s historical cache verification completed\n' "$BATCH"
