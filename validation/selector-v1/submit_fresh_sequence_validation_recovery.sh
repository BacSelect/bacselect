#!/usr/bin/env bash
set -euo pipefail

REPO="/home/rwhite/github/bacselect"
RECOVERY="$REPO/validation/selector-v1/run_acquisition_unavailable_recovery.slurm"
AGGREGATE="$REPO/validation/selector-v1/aggregate_fresh_sequence_validation_recovery.slurm"

SOURCE_COMMIT="7aba4b0a2aa22c05ce808bf9b5811606bd3d2293"
SOURCE_ROOT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation/$SOURCE_COMMIT"

fail() {
    printf 'ERROR | %s\n' "$*" >&2
    exit 1
}

cd "$REPO"

commit="$(git rev-parse HEAD)"
origin="$(git rev-parse origin/main)"

[[ "$commit" == "$origin" ]] ||
    fail "HEAD does not match origin/main; push before recovery execution"

[[ -z "$(git status --porcelain)" ]] ||
    fail "repository is not clean"

for batch in 024 028
do
    [[ ! -d "$SOURCE_ROOT/batch-$batch" ]] ||
        fail "source batch-$batch unexpectedly finalized"

    [[ -d "$SOURCE_ROOT/batch-$batch.partial" ]] ||
        fail "source batch-$batch partial missing"
done

final_count="$(
    find "$SOURCE_ROOT" \
        -maxdepth 1 \
        -type d \
        -name 'batch-[0-9][0-9][0-9]' \
        | wc -l \
        | tr -d '[:space:]'
)"

[[ "$final_count" == "29" ]] ||
    fail "expected exactly 29 source finalized batches"

RECOVERY_ROOT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation-recovery/$commit/source-$SOURCE_COMMIT"

[[ ! -e "$RECOVERY_ROOT" ]] ||
    fail "recovery output root already exists"

mkdir -p "$HOME/slurm-logs/bacselect/fresh-sequence-recovery"
mkdir -p "$RECOVERY_ROOT/submission"

printf '%s\n' '===== submit acquisition-unavailable recovery ====='
recover_out="$(sbatch "$RECOVERY")"
printf '%s\n' "$recover_out"
recover_job="$(printf '%s\n' "$recover_out" | awk '{print $NF}')"

[[ "$recover_job" =~ ^[0-9]+$ ]] ||
    fail "unable to parse recovery job id"

printf '%s\n' '===== submit complete aggregate audit ====='
aggregate_out="$(
    sbatch \
        --dependency="afterok:${recover_job}" \
        "$AGGREGATE"
)"
printf '%s\n' "$aggregate_out"
aggregate_job="$(printf '%s\n' "$aggregate_out" | awk '{print $NF}')"

[[ "$aggregate_job" =~ ^[0-9]+$ ]] ||
    fail "unable to parse aggregate job id"

cat > "$RECOVERY_ROOT/submission/submission-definition.tsv" <<EOF
field	value
schema_version	2
recovery_commit	$commit
source_production_commit	$SOURCE_COMMIT
source_final_batches	29
source_failed_partial_batches	2
recovery_batches	24,28
recovery_job_id	$recover_job
aggregate_job_id	$aggregate_job
dependency	afterok:$recover_job
recovery_rule	datasets_catalog_without_sequence_payload
source_evidence_mutated	no
recovery_uses_package_copy	yes
frozen_targets	15326
EOF

sha256sum \
    "$RECOVERY_ROOT/submission/submission-definition.tsv" \
    > "$RECOVERY_ROOT/submission/submission-artifacts-sha256.txt"

cat "$RECOVERY_ROOT/submission/submission-definition.tsv"
cat "$RECOVERY_ROOT/submission/submission-artifacts-sha256.txt"

printf 'PASS | recovery submitted | recovery=%s | aggregate=%s\n' \
    "$recover_job" "$aggregate_job"
