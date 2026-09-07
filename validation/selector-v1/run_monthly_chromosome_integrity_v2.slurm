#!/usr/bin/env bash
#SBATCH --partition=prod
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --array=1-142%24
#SBATCH --job-name=bacselect-s6v2
#SBATCH --output=/home/rwhite/slurm-logs/bacselect/chromosome-integrity-v2/%A_%a.out
#SBATCH --error=/home/rwhite/slurm-logs/bacselect/chromosome-integrity-v2/%A_%a.err

set -euo pipefail

fail() {
    printf 'ERROR | %s\n' "$*" >&2
    exit 1
}

REPO="$HOME/github/bacselect-monthly-gbff-recovery"
SOURCE_REPO="$HOME/github/bacselect"
PY="$HOME/.conda/envs/bacselect-dev/bin/python"

PARALLEL="$REPO/validation/selector-v1/run_monthly_chromosome_integrity_v2_parallel.py"

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

[[ -n "${BACSELECT_STAGE6_COMMIT:-}" ]] ||
    fail "BACSELECT_STAGE6_COMMIT is unset"

[[ -n "${BACSELECT_STAGE6_WORK_ROOT:-}" ]] ||
    fail "BACSELECT_STAGE6_WORK_ROOT is unset"

[[ -n "${SLURM_ARRAY_TASK_ID:-}" ]] ||
    fail "SLURM_ARRAY_TASK_ID is unset"

mkdir -p "$BACSELECT_STAGE6_WORK_ROOT/shards"

"$PY" "$PARALLEL" worker \
    --repo "$REPO" \
    --source-repo "$SOURCE_REPO" \
    --production-root "$MONTHLY" \
    --stage1-root "$STAGE1" \
    --source-production-commit "$SOURCE_COMMIT" \
    --completion-execution-commit "$COMPLETION_COMMIT" \
    --cache-execution-commit "$CACHE_COMMIT" \
    --source-truth-execution-commit "$STAGE4_COMMIT" \
    --biosample-execution-commit "$STAGE5_COMMIT" \
    --chromosome-execution-commit "$BACSELECT_STAGE6_COMMIT" \
    --expected-completion-sha256 "$COMPLETION_SHA" \
    --expected-catalogue-sha256 "$CATALOGUE_SHA" \
    --expected-source-truth-completion-sha256 "$STAGE4_COMPLETION_SHA" \
    --expected-biosample-completion-sha256 "$STAGE5_COMPLETION_SHA" \
    --work-manifest "$BACSELECT_STAGE6_WORK_ROOT/submission/work-manifest.tsv" \
    --shard-root "$BACSELECT_STAGE6_WORK_ROOT/shards" \
    --task-id "$SLURM_ARRAY_TASK_ID"
