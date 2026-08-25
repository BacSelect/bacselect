#!/usr/bin/env bash
set -euo pipefail

REPO="/home/rwhite/github/bacselect"
WORKER="$REPO/validation/selector-v1/fresh_sequence_validation_batch.py"
ARRAY="$REPO/validation/selector-v1/run_fresh_sequence_validation.slurm"
AGGREGATE="$REPO/validation/selector-v1/aggregate_fresh_sequence_validation.slurm"
LOG_ROOT="/home/rwhite/slurm-logs/bacselect/fresh-sequence-validation"
fail() { printf 'ERROR | %s\n' "$*" >&2; exit 1; }

cd "$REPO"
commit="$(git rev-parse HEAD)"
origin="$(git rev-parse origin/main)"
[[ "$commit" == "$origin" ]] || fail "HEAD does not match origin/main; push before network retrieval"
[[ -z "$(git status --porcelain)" ]] || fail "repository is not clean"

OUTPUT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation/$commit"
[[ ! -e "$OUTPUT_ROOT" ]] || fail "output root already exists: $OUTPUT_ROOT"
mkdir -p "$LOG_ROOT"
mkdir -p "$OUTPUT_ROOT/submission"

printf '%s\n' '===== frozen batch plans ====='
python3 "$WORKER" --batch 1 --plan
python3 "$WORKER" --batch 31 --plan

printf '%s\n' '===== submit array ====='
array_output="$(sbatch "$ARRAY")"
printf '%s\n' "$array_output"
array_job="$(printf '%s\n' "$array_output" | awk '{print $NF}')"
[[ "$array_job" =~ ^[0-9]+$ ]] || fail "unable to parse array job id"

printf '%s\n' '===== submit aggregate ====='
aggregate_output="$(sbatch --dependency="afterok:${array_job}" "$AGGREGATE")"
printf '%s\n' "$aggregate_output"
aggregate_job="$(printf '%s\n' "$aggregate_output" | awk '{print $NF}')"
[[ "$aggregate_job" =~ ^[0-9]+$ ]] || fail "unable to parse aggregate job id"

cat > "$OUTPUT_ROOT/submission/submission-definition.tsv" <<EOF
field	value
schema_version	1
production_commit	$commit
array_job_id	$array_job
aggregate_job_id	$aggregate_job
dependency	afterok:$array_job
array_spec	1-31%2
fresh_targets	15326
fresh_batches	31
batch_size	500
final_batch_size	326
EOF

cat > "$OUTPUT_ROOT/submission/submission-job-ids.tsv" <<EOF
role	job_id
array	$array_job
aggregate	$aggregate_job
EOF

sha256sum \
    "$OUTPUT_ROOT/submission/submission-definition.tsv" \
    "$OUTPUT_ROOT/submission/submission-job-ids.tsv" \
    > "$OUTPUT_ROOT/submission/submission-artifacts-sha256.txt"

printf '%s\n' '===== submission artifacts ====='
cat "$OUTPUT_ROOT/submission/submission-definition.tsv"
cat "$OUTPUT_ROOT/submission/submission-artifacts-sha256.txt"
printf 'PASS | submitted fresh sequence validation | array=%s | aggregate=%s\n' "$array_job" "$aggregate_job"
