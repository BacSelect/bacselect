#!/usr/bin/env bash
set -euo pipefail

fail() {
    printf 'FAIL | %s\n' "$*" >&2
    exit 1
}

REPO_ROOT="${1:-$HOME/github/bacselect}"
EXPECTED_SNAPSHOT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/ncbi-sequence-validation-snapshot"
OUTPUT_PARENT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/historical-cache-verification"

REPO_ROOT="$(realpath "$REPO_ROOT")"

[[ -d "$REPO_ROOT/.git" ]] ||
    fail "repository not found: $REPO_ROOT"

cd "$REPO_ROOT"

HEAD_COMMIT="$(git rev-parse HEAD)"
ORIGIN_MAIN="$(git rev-parse origin/main)"

[[ "$HEAD_COMMIT" == "$ORIGIN_MAIN" ]] ||
    fail "HEAD does not match origin/main"

[[ -z "$(git status --porcelain)" ]] ||
    fail "repository working tree is not clean"

ARRAY_WRAPPER="validation/selector-v1/run_historical_cache_verification.slurm"
AGGREGATE_WRAPPER="validation/selector-v1/aggregate_historical_cache_verification.slurm"
SUBMIT_HELPER="validation/selector-v1/submit_historical_cache_verification.sh"
VERIFIER="src/bacselect/source_cache_verify.py"
IMPLEMENTATION_NOTE="validation/selector-v1/prospective-historical-cache-verification-implementation.md"
EXECUTION_NOTE="validation/selector-v1/prospective-historical-cache-verification-execution.md"

for path in \
    "$ARRAY_WRAPPER" \
    "$AGGREGATE_WRAPPER" \
    "$SUBMIT_HELPER" \
    "$VERIFIER" \
    "$IMPLEMENTATION_NOTE" \
    "$EXECUTION_NOTE"
do
    [[ -f "$path" ]] ||
        fail "required file is missing: $path"
done

[[ -d "$EXPECTED_SNAPSHOT_ROOT" ]] ||
    fail "historical snapshot root is missing"

BATCH_COUNT="$(
    find "$EXPECTED_SNAPSHOT_ROOT" \
        -mindepth 1 \
        -maxdepth 1 \
        -type d \
        -name 'batch-[0-9][0-9][0-9]' \
        | wc -l \
        | tr -d '[:space:]'
)"

[[ "$BATCH_COUNT" == "111" ]] ||
    fail "expected 111 historical batch directories; observed $BATCH_COUNT"

OUTPUT_ROOT="$OUTPUT_PARENT/$HEAD_COMMIT"
LOG_ROOT="$HOME/slurm-logs/bacselect/historical-cache-verification/$HEAD_COMMIT"

[[ ! -e "$OUTPUT_ROOT" ]] ||
    fail "commit-scoped output root already exists: $OUTPUT_ROOT"

mkdir -p \
    "$OUTPUT_ROOT/batches" \
    "$LOG_ROOT"

ARRAY_WRAPPER_SHA256="$(sha256sum "$ARRAY_WRAPPER" | awk '{print $1}')"
AGGREGATE_WRAPPER_SHA256="$(sha256sum "$AGGREGATE_WRAPPER" | awk '{print $1}')"
SUBMIT_HELPER_SHA256="$(sha256sum "$SUBMIT_HELPER" | awk '{print $1}')"
VERIFIER_SHA256="$(sha256sum "$VERIFIER" | awk '{print $1}')"
IMPLEMENTATION_NOTE_SHA256="$(sha256sum "$IMPLEMENTATION_NOTE" | awk '{print $1}')"
EXECUTION_NOTE_SHA256="$(sha256sum "$EXECUTION_NOTE" | awk '{print $1}')"

SUBMISSION_DEFINITION="$OUTPUT_ROOT/submission-definition.tsv"

{
    printf 'field\tvalue\n'
    printf 'git_commit\t%s\n' "$HEAD_COMMIT"
    printf 'origin_main\t%s\n' "$ORIGIN_MAIN"
    printf 'snapshot_root\t%s\n' "$EXPECTED_SNAPSHOT_ROOT"
    printf 'output_root\t%s\n' "$OUTPUT_ROOT"
    printf 'log_root\t%s\n' "$LOG_ROOT"
    printf 'array_spec\t1-111%%4\n'
    printf 'array_partition\tprod\n'
    printf 'array_cpus_per_task\t1\n'
    printf 'array_memory\t2G\n'
    printf 'array_time\t04:00:00\n'
    printf 'aggregate_partition\tprod\n'
    printf 'aggregate_cpus_per_task\t1\n'
    printf 'aggregate_memory\t2G\n'
    printf 'aggregate_time\t01:00:00\n'
    printf 'array_wrapper_sha256\t%s\n' "$ARRAY_WRAPPER_SHA256"
    printf 'aggregate_wrapper_sha256\t%s\n' "$AGGREGATE_WRAPPER_SHA256"
    printf 'submit_helper_sha256\t%s\n' "$SUBMIT_HELPER_SHA256"
    printf 'verifier_sha256\t%s\n' "$VERIFIER_SHA256"
    printf 'implementation_note_sha256\t%s\n' "$IMPLEMENTATION_NOTE_SHA256"
    printf 'execution_note_sha256\t%s\n' "$EXECUTION_NOTE_SHA256"
    printf 'submitted_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$SUBMISSION_DEFINITION"

SUBMISSION_DEFINITION_SHA256="$(
    sha256sum "$SUBMISSION_DEFINITION" | awk '{print $1}'
)"

EXPORTS="ALL,BACSELECT_REPO_ROOT=$REPO_ROOT,BACSELECT_EXPECTED_COMMIT=$HEAD_COMMIT,BACSELECT_CACHE_VERIFY_OUTPUT_ROOT=$OUTPUT_ROOT"

printf '%s\n' '===== submit historical cache verification array ====='

ARRAY_JOB_RAW="$(
    sbatch \
        --parsable \
        --export="$EXPORTS" \
        --output="$LOG_ROOT/%x-%A_%a.out" \
        --error="$LOG_ROOT/%x-%A_%a.err" \
        "$ARRAY_WRAPPER"
)"

ARRAY_JOB_ID="${ARRAY_JOB_RAW%%;*}"

[[ "$ARRAY_JOB_ID" =~ ^[0-9]+$ ]] ||
    fail "unexpected array job id: $ARRAY_JOB_RAW"

printf 'array_job_id\t%s\n' "$ARRAY_JOB_ID"

printf '%s\n' '===== submit dependent aggregation ====='

AGG_JOB_RAW="$(
    sbatch \
        --parsable \
        --dependency="afterok:$ARRAY_JOB_ID" \
        --export="$EXPORTS" \
        --output="$LOG_ROOT/%x-%j.out" \
        --error="$LOG_ROOT/%x-%j.err" \
        "$AGGREGATE_WRAPPER"
)"

AGG_JOB_ID="${AGG_JOB_RAW%%;*}"

[[ "$AGG_JOB_ID" =~ ^[0-9]+$ ]] ||
    fail "unexpected aggregate job id: $AGG_JOB_RAW"

printf 'aggregate_job_id\t%s\n' "$AGG_JOB_ID"

{
    printf 'job_role\tjob_id\tdependency\n'
    printf 'array\t%s\tNONE\n' "$ARRAY_JOB_ID"
    printf 'aggregate\t%s\tafterok:%s\n' \
        "$AGG_JOB_ID" \
        "$ARRAY_JOB_ID"
} > "$OUTPUT_ROOT/submission-job-ids.tsv"

{
    printf '%s  submission-definition.tsv\n' \
        "$SUBMISSION_DEFINITION_SHA256"
    printf '%s  submission-job-ids.tsv\n' \
        "$(
            sha256sum "$OUTPUT_ROOT/submission-job-ids.tsv" |
                awk '{print $1}'
        )"
} > "$OUTPUT_ROOT/submission-artifacts-sha256.txt"

printf '%s\n' '===== submission definition ====='
cat "$SUBMISSION_DEFINITION"

printf '%s\n' '===== submission jobs ====='
cat "$OUTPUT_ROOT/submission-job-ids.tsv"

printf '%s\n' '===== submission artifact SHA256 ====='
cat "$OUTPUT_ROOT/submission-artifacts-sha256.txt"

printf '%s\n' 'PASS | historical cache verification submitted'
