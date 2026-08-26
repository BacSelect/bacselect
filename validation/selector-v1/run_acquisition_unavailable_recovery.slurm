#!/usr/bin/env bash
#SBATCH --job-name=bacsel-acq-recover
#SBATCH --partition=prod
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --array=24,28%2
#SBATCH --nodelist=kscprod-bio8
#SBATCH --chdir=/home/rwhite/github/bacselect
#SBATCH --output=/home/rwhite/slurm-logs/bacselect/fresh-sequence-recovery/%A_%a.out
#SBATCH --error=/home/rwhite/slurm-logs/bacselect/fresh-sequence-recovery/%A_%a.err

set -euo pipefail

REPO="/home/rwhite/github/bacselect"
SCRIPT="$REPO/validation/selector-v1/recover_acquisition_unavailable.py"
MIN_FREE_KIB=$((20 * 1024 * 1024))

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

host="$(hostname -s)"
[[ "$host" == "kscprod-bio8" ]] ||
    fail "unexpected execution node: $host"

case "${SLURM_ARRAY_TASK_ID:-}" in
    24|28) ;;
    *) fail "unexpected recovery batch" ;;
esac

available="$(
    df -Pk /NGS/scratch/EXT/Rhys_wkdir \
        | awk 'NR==2 {print $4}'
)"

[[ "$available" =~ ^[0-9]+$ ]] ||
    fail "unable to determine scratch free space"

(( available >= MIN_FREE_KIB )) ||
    fail "less than 20 GiB free on shared scratch"

printf 'recovery_commit=%s\n' "$commit"
printf 'source_commit=%s\n' "7aba4b0a2aa22c05ce808bf9b5811606bd3d2293"
printf 'batch=batch-%03d\n' "$SLURM_ARRAY_TASK_ID"
printf 'host=%s\n' "$(hostname)"

python3 "$SCRIPT" \
    --batch "$SLURM_ARRAY_TASK_ID"

python3 "$SCRIPT" \
    --batch "$SLURM_ARRAY_TASK_ID" \
    --audit-only
