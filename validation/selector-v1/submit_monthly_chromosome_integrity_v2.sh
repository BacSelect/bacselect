#!/usr/bin/env bash
set -euo pipefail

fail() {
    printf 'ERROR | %s\n' "$*" >&2
    exit 1
}

REPO="$HOME/github/bacselect-monthly-gbff-recovery"
SOURCE_REPO="$HOME/github/bacselect"
PY="$HOME/.conda/envs/bacselect-dev/bin/python"

PARALLEL="$REPO/validation/selector-v1/run_monthly_chromosome_integrity_v2_parallel.py"
ARRAY="$REPO/validation/selector-v1/run_monthly_chromosome_integrity_v2.slurm"
AGGREGATE="$REPO/validation/selector-v1/aggregate_monthly_chromosome_integrity_v2.slurm"

SOURCE_COMMIT="abefc3b70d7fe7e079eeb52b762542dae565edf6"
COMPLETION_COMMIT="10f86bf8fe079b284d52128e1b29f977e2214f7f"
CACHE_COMMIT="80bd001371f430cfbc044f4a048f34689c2defdd"
STAGE4_COMMIT="6ff6bc3edb48489167571c9e0ef883992e0db4cf"
STAGE5_COMMIT="e8d01bb93eb496859aeb02ffd89695ad10032435"

COMPLETION_SHA="9199c7dd24d53ed6e88683d657f6b2ae8c7b0c48e279a3283b79b89b83cfe5e5"
CATALOGUE_SHA="1ee3cce9b47304d0832bc6f794d0af41e88442b859e66c99de7d67e38577dda7"
STAGE4_COMPLETION_SHA="8603f684915dd561396307cee090634adcfaeedf2db4211f51cab8e8387007fd"
STAGE5_COMPLETION_SHA="d5fd9b803faee209a77c36528ab8617eea6683b4263fa57662fbcb100c86b850"

MONTHLY="/NGS/scratch/EXT/Rhys_wkdir/bacselect/monthly"
STAGE1="$MONTHLY/2026.09/production/$SOURCE_COMMIT"

LOG_ROOT="$HOME/slurm-logs/bacselect/chromosome-integrity-v2"

cd "$REPO"

commit="$(git rev-parse HEAD)"

[[ -z "$(git status --porcelain)" ]] ||
    fail "repository is not clean"

OUTPUT_ROOT="$STAGE1/chromosome-integrity-parallel-v2/$commit"

[[ ! -e "$OUTPUT_ROOT" ]] ||
    fail "parallel Stage 6 output root already exists: $OUTPUT_ROOT"

mkdir -p "$LOG_ROOT"
mkdir -p "$OUTPUT_ROOT/submission"

printf '%s\n' '===== build frozen Stage6 work manifest ====='

"$PY" "$PARALLEL" plan \
    --repo "$REPO" \
    --source-repo "$SOURCE_REPO" \
    --production-root "$MONTHLY" \
    --stage1-root "$STAGE1" \
    --source-production-commit "$SOURCE_COMMIT" \
    --completion-execution-commit "$COMPLETION_COMMIT" \
    --cache-execution-commit "$CACHE_COMMIT" \
    --source-truth-execution-commit "$STAGE4_COMMIT" \
    --biosample-execution-commit "$STAGE5_COMMIT" \
    --chromosome-execution-commit "$commit" \
    --expected-completion-sha256 "$COMPLETION_SHA" \
    --expected-catalogue-sha256 "$CATALOGUE_SHA" \
    --expected-source-truth-completion-sha256 "$STAGE4_COMPLETION_SHA" \
    --expected-biosample-completion-sha256 "$STAGE5_COMPLETION_SHA" \
    --work-manifest "$OUTPUT_ROOT/submission/work-manifest.tsv"

work_sha="$(
    sha256sum "$OUTPUT_ROOT/submission/work-manifest.tsv" \
    | awk '{print $1}'
)"

printf '%s\n' '===== submit Stage6 array ====='

array_output="$(
    sbatch \
        --export="ALL,BACSELECT_STAGE6_COMMIT=$commit,BACSELECT_STAGE6_WORK_ROOT=$OUTPUT_ROOT" \
        "$ARRAY"
)"

printf '%s\n' "$array_output"

array_job="$(
    printf '%s\n' "$array_output" \
    | awk '{print $NF}'
)"

[[ "$array_job" =~ ^[0-9]+$ ]] ||
    fail "unable to parse array job id"

printf '%s\n' '===== submit dependent Stage6 aggregate ====='

aggregate_output="$(
    sbatch \
        --dependency="afterok:${array_job}" \
        --export="ALL,BACSELECT_STAGE6_COMMIT=$commit,BACSELECT_STAGE6_WORK_ROOT=$OUTPUT_ROOT" \
        "$AGGREGATE"
)"

printf '%s\n' "$aggregate_output"

aggregate_job="$(
    printf '%s\n' "$aggregate_output" \
    | awk '{print $NF}'
)"

[[ "$aggregate_job" =~ ^[0-9]+$ ]] ||
    fail "unable to parse aggregate job id"

{
    printf 'field\tvalue\n'
    printf 'schema_version\t%s\n' '1'
    printf 'release_id\t%s\n' '2026.09'
    printf 'source_production_commit\t%s\n' "$SOURCE_COMMIT"
    printf 'chromosome_execution_commit\t%s\n' "$commit"
    printf 'array_job_id\t%s\n' "$array_job"
    printf 'aggregate_job_id\t%s\n' "$aggregate_job"
    printf 'dependency\t%s\n' "afterok:$array_job"
    printf 'array_spec\t%s\n' '1-142%24'
    printf 'batch_count\t%s\n' '142'
    printf 'candidate_count\t%s\n' '68595'
    printf 'work_manifest_sha256\t%s\n' "$work_sha"
} > "$OUTPUT_ROOT/submission/submission-definition.tsv"

{
    printf 'role\tjob_id\n'
    printf 'array\t%s\n' "$array_job"
    printf 'aggregate\t%s\n' "$aggregate_job"
} > "$OUTPUT_ROOT/submission/submission-job-ids.tsv"

sha256sum \
    "$OUTPUT_ROOT/submission/work-manifest.tsv" \
    "$OUTPUT_ROOT/submission/submission-definition.tsv" \
    "$OUTPUT_ROOT/submission/submission-job-ids.tsv" \
    > "$OUTPUT_ROOT/submission/submission-artifacts-sha256.txt"

printf '%s\n' '===== submission ====='
cat "$OUTPUT_ROOT/submission/submission-definition.tsv"

printf
printf 'PASS | Stage6-v2 submitted | array=%s | aggregate=%s\n' \
    "$array_job" \
    "$aggregate_job"
