#!/usr/bin/env bash
#SBATCH --job-name=bacsel-fresh-seq2
#SBATCH --partition=prod
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --array=1-31%2
#SBATCH --nodelist=kscprod-bio8
#SBATCH --chdir=/home/rwhite/github/bacselect
#SBATCH --output=/home/rwhite/slurm-logs/bacselect/fresh-sequence-validation/%A_%a.out
#SBATCH --error=/home/rwhite/slurm-logs/bacselect/fresh-sequence-validation/%A_%a.err

set -euo pipefail

REPO="/home/rwhite/github/bacselect"
WORKER="$REPO/validation/selector-v1/fresh_sequence_validation_batch.py"
AUDITOR="$REPO/validation/selector-v1/audit_fresh_sequence_validation.py"

MAX_ATTEMPTS=3
RETRY_DELAY_SECONDS=60
MIN_FREE_KIB=$((500 * 1024 * 1024))

timestamp() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
}

fail() {
    printf 'ERROR | %s\n' "$*" >&2
    exit 1
}

check_free_space() {
    local available

    available="$(
        df -Pk /NGS/scratch/EXT/Rhys_wkdir \
            | awk 'NR==2 {print $4}'
    )"

    [[ "$available" =~ ^[0-9]+$ ]] ||
        fail "unable to determine scratch free space"

    if (( available < MIN_FREE_KIB )); then
        fail "less than 500 GiB free on shared scratch"
    fi
}

prepare_attempt() {
    local attempt="$1"
    local download_rc=""
    local failed_root
    local failed_dir

    if [[ ! -d "$partial_dir" ]]; then
        mode="fresh"
        args=(
            --batch "$batch"
            --output-root "$OUTPUT_ROOT"
        )
        return
    fi

    if [[ \
        -f "$partial_dir/dehydrated.zip" \
        && -d "$partial_dir/package" \
        && -f "$partial_dir/attempt-origin.json" \
        && -f "$partial_dir/accessions.txt" \
    ]]; then
        mode="resume"
        args=(
            --batch "$batch"
            --output-root "$OUTPUT_ROOT"
            --resume
        )
        return
    fi

    if [[ -f "$partial_dir/download-exit-code.txt" ]]; then
        download_rc="$(
            tr -d '[:space:]' \
                < "$partial_dir/download-exit-code.txt"
        )"
    fi

    if [[ \
        "$download_rc" =~ ^[1-9][0-9]*$ \
        && ! -e "$partial_dir/dehydrated.zip" \
        && ! -e "$partial_dir/dehydrated.zip.partial" \
    ]]; then
        failed_root="$OUTPUT_ROOT/failed-attempts/$batch_id"
        failed_dir="$failed_root/before-attempt-$(printf '%02d' "$attempt")"

        mkdir -p "$failed_root"

        [[ ! -e "$failed_dir" ]] ||
            fail "failed-attempt archive already exists: $failed_dir"

        mv "$partial_dir" "$failed_dir"

        printf 'ARCHIVE | %s non-resumable failed download | %s\n' \
            "$batch_id" "$failed_dir"

        mode="fresh"
        args=(
            --batch "$batch"
            --output-root "$OUTPUT_ROOT"
        )
        return
    fi

    fail "$batch_id has unexpected non-resumable partial state; inspect manually"
}

cd "$REPO"

[[ -n "${SLURM_ARRAY_TASK_ID:-}" ]] ||
    fail "SLURM_ARRAY_TASK_ID is unset"

batch="$SLURM_ARRAY_TASK_ID"

if (( batch < 1 || batch > 31 )); then
    fail "array task outside frozen batch range"
fi

commit="$(git rev-parse HEAD)"
origin="$(git rev-parse origin/main)"

[[ "$commit" == "$origin" ]] ||
    fail "HEAD does not match origin/main"

[[ -z "$(git status --porcelain)" ]] ||
    fail "repository is not clean"

OUTPUT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation/$commit"

batch_id="$(printf 'batch-%03d' "$batch")"
final_dir="$OUTPUT_ROOT/$batch_id"
partial_dir="$OUTPUT_ROOT/${batch_id}.partial"

mkdir -p "$OUTPUT_ROOT"

fstype="$(findmnt -n -o FSTYPE -T "$OUTPUT_ROOT")"
source_fs="$(findmnt -n -o SOURCE -T "$OUTPUT_ROOT")"

case "$fstype" in
    nfs|nfs4) ;;
    *) fail "output root is not on NFS: $fstype" ;;
esac

case "$source_fs" in
    *esrprodbio_scratch*) ;;
    *) fail "output root is not on expected shared scratch" ;;
esac

host="$(hostname -s)"
[[ "$host" == "kscprod-bio8" ]] ||
    fail "unexpected execution node: $host"

check_free_space

printf '%s\n' "============================================================"
printf 'BacSelect corrected fresh sequence validation\n'
printf 'started_utc=%s\n' "$(timestamp)"
printf 'host=%s\n' "$(hostname)"
printf 'slurm_array_job_id=%s\n' "${SLURM_ARRAY_JOB_ID:-unknown}"
printf 'slurm_array_task_id=%s\n' "$batch"
printf 'git_head=%s\n' "$commit"
printf 'batch=%s\n' "$batch_id"
printf 'output_root=%s\n' "$OUTPUT_ROOT"
printf '%s\n' "============================================================"

if [[ -d "$final_dir" ]]; then
    [[ ! -e "$partial_dir" ]] ||
        fail "both final and partial outputs exist"

    PYTHONPATH="$REPO/src" \
        python3 "$AUDITOR" \
            --output-root "$OUTPUT_ROOT" \
            --production-commit "$commit" \
            --batch "$batch"

    printf 'SKIP | %s already finalized and validated\n' "$batch_id"
    exit 0
fi

success=0

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    check_free_space
    prepare_attempt "$attempt"

    printf '%s | %s attempt=%s mode=%s\n' \
        "$(timestamp)" "$batch_id" "$attempt" "$mode"

    set +e
    python3 "$WORKER" "${args[@]}"
    rc=$?
    set -e

    printf '%s | %s attempt=%s exit_code=%s\n' \
        "$(timestamp)" "$batch_id" "$attempt" "$rc"

    if [[ "$rc" -eq 0 ]]; then
        PYTHONPATH="$REPO/src" \
            python3 "$AUDITOR" \
                --output-root "$OUTPUT_ROOT" \
                --production-commit "$commit" \
                --batch "$batch"

        success=1
        break
    fi

    if [[ "$attempt" -lt "$MAX_ATTEMPTS" ]]; then
        printf '%s\n' 'RETRY | preserving or archiving failed state'
        printf 'RETRY | waiting %ss\n' "$RETRY_DELAY_SECONDS"
        sleep "$RETRY_DELAY_SECONDS"
    fi
done

if [[ "$success" -ne 1 ]]; then
    printf 'ERROR | %s failed after %s attempts\n' \
        "$batch_id" "$MAX_ATTEMPTS"

    if [[ -d "$partial_dir" ]]; then
        printf 'partial_preserved=yes\n'
        printf 'partial_path=%s\n' "$partial_dir"
    else
        printf 'partial_preserved=no\n'
    fi

    exit 1
fi

printf 'PASS | %s completed and validated\n' "$batch_id"
printf 'finished_utc=%s\n' "$(timestamp)"
