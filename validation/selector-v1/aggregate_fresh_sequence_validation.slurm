#!/usr/bin/env bash
#SBATCH --job-name=bacsel-fresh-audit
#SBATCH --partition=prod
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --chdir=/home/rwhite/github/bacselect
#SBATCH --output=/home/rwhite/slurm-logs/bacselect/fresh-sequence-validation/%j-aggregate.out
#SBATCH --error=/home/rwhite/slurm-logs/bacselect/fresh-sequence-validation/%j-aggregate.err

set -euo pipefail

REPO="/home/rwhite/github/bacselect"
AUDITOR="$REPO/validation/selector-v1/audit_fresh_sequence_validation.py"
cd "$REPO"
commit="$(git rev-parse HEAD)"
origin="$(git rev-parse origin/main)"
[[ "$commit" == "$origin" ]] || { echo "ERROR | HEAD does not match origin/main" >&2; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "ERROR | repository is not clean" >&2; exit 1; }

OUTPUT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation/$commit"
SUMMARY="$OUTPUT_ROOT/fresh-sequence-validation-summary.json"
[[ -d "$OUTPUT_ROOT" ]] || { echo "ERROR | output root does not exist: $OUTPUT_ROOT" >&2; exit 1; }
[[ ! -e "$SUMMARY" ]] || { echo "ERROR | aggregate summary already exists: $SUMMARY" >&2; exit 1; }

printf 'BacSelect fresh sequence aggregate audit\n'
printf 'git_head=%s\n' "$commit"
printf 'output_root=%s\n' "$OUTPUT_ROOT"

python3 "$AUDITOR" \
    --output-root "$OUTPUT_ROOT" \
    --production-commit "$commit" \
    --verify-package-content \
    --write-summary "$SUMMARY"

printf '%s\n' '===== aggregate summary ====='
cat "$SUMMARY"
printf '%s\n' '===== aggregate summary identity ====='
sha256sum "$SUMMARY"
printf '%s\n' 'PASS | complete fresh sequence snapshot verified'
