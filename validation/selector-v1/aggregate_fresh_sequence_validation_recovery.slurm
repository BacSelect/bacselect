#!/usr/bin/env bash
#SBATCH --job-name=bacsel-acq-audit2
#SBATCH --partition=prod
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --chdir=/home/rwhite/github/bacselect
#SBATCH --output=/home/rwhite/slurm-logs/bacselect/fresh-sequence-recovery/%j.out
#SBATCH --error=/home/rwhite/slurm-logs/bacselect/fresh-sequence-recovery/%j.err

set -euo pipefail

REPO="/home/rwhite/github/bacselect"
SCRIPT="$REPO/validation/selector-v1/audit_fresh_sequence_validation_recovery.py"

fail() {
    printf 'ERROR | %s\n' "$*" >&2
    exit 1
}

cd "$REPO"

commit="$(git rev-parse HEAD)"
origin="$(git rev-parse origin/main)"

[[ "$commit" == "$origin" ]] ||
    fail "HEAD does not match origin/main"

[[ -z "$(git status --porcelain)" ]] ||
    fail "repository is not clean"

ROOT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation-recovery/$commit/source-7aba4b0a2aa22c05ce808bf9b5811606bd3d2293"
SUMMARY="$ROOT/fresh-sequence-validation-recovery-summary.json"

python3 "$SCRIPT" \
    --recovery-commit "$commit" \
    --output "$SUMMARY"

printf 'summary\t%s\n' "$SUMMARY"
sha256sum "$SUMMARY"
