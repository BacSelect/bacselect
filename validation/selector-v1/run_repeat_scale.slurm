#!/usr/bin/env bash
#SBATCH --job-name=bac-rscale
#SBATCH --partition=prod
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --array=1-111%8
#SBATCH --chdir=/home/rwhite/github/bacselect
#SBATCH --output=/home/rwhite/slurm-logs/bacselect/%x-%A_%a.out
#SBATCH --error=/home/rwhite/slurm-logs/bacselect/%x-%A_%a.err

set -euo pipefail

export PATH="/opt/bioinf/anaconda3/anaconda3-5.0.0.1/bin:$PATH"
export PYTHONUNBUFFERED=1

REPO="/home/rwhite/github/bacselect"

CONDA="/opt/bioinf/anaconda3/anaconda3-5.0.0.1/bin/conda"
ENV_NAME="bacselect-repeat"

WORKER="$REPO/validation/selector-v1/run_repeat_scale_batch.py"
INPUT_HASHES="$REPO/validation/selector-v1/repeat-scale-production-inputs.sha256"
SOURCE_AUDITS="$REPO/validation/selector-v1/repeat-scale-source-snapshot.tsv"

FINCH_DRIVER="$REPO/vendor/project-finch/experiment-0/compute_structural_features.py"
FINCH_BASIC="$REPO/vendor/project-finch/experiment-0/basic_structural_features.py"
ENGINE_SOURCE="$REPO/vendor/project-finch/experiment-0/structural_features_fast.cpp"

ENV_LOCK="$REPO/envs/bacselect-repeat-linux-64.lock"

TARGETS="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/repeat-scale/concordance-inputs/repeat-concordance-targets.tsv"

REFERENCE_MATRIX="/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/corrected-eligible-percentile-feature-space/corrected-eligible-structural-feature-matrix.tsv"

SNAPSHOT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/ncbi-sequence-validation-snapshot"

OUTPUT_BASE="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/repeat-scale/alternative-k-grid"

EXPECTED_TARGET_SHA256="bc4acba1384524f956887d02d2f54aa7e501a2c23e2930b779a4e6520d8fcee1"
EXPECTED_REFERENCE_SHA256="fd264bedda627d737a647de601c8b835f53baeca246724e9aafb73fd50c9d656"
EXPECTED_ENV_LOCK_SHA256="aa6984b17e86f7d0627379e295fabed837cf7d43cc6a9fd80f32b7092ac5f64f"

K_VALUES="50,75,100,150,200,300,400,600,800,1200,1600,2400,3200"


timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}


sha256_file() {
    sha256sum "$1" | awk '{print $1}'
}


require_sha256() {
    local path="$1"
    local expected="$2"
    local label="$3"

    if [[ ! -f "$path" ]]; then
        echo "ERROR | $label missing: $path"
        exit 1
    fi

    local observed
    observed="$(sha256_file "$path")"

    if [[ "$observed" != "$expected" ]]; then
        echo "ERROR | $label SHA256 mismatch"
        echo "expected=$expected"
        echo "observed=$observed"
        exit 1
    fi
}


if [[ -z "${SLURM_ARRAY_TASK_ID:-}" ]]; then
    echo "ERROR | SLURM_ARRAY_TASK_ID is not set"
    exit 1
fi

if (( SLURM_ARRAY_TASK_ID < 1 || SLURM_ARRAY_TASK_ID > 111 )); then
    echo "ERROR | invalid array task: $SLURM_ARRAY_TASK_ID"
    exit 1
fi

BATCH_ID="$(printf 'batch-%03d' "$SLURM_ARRAY_TASK_ID")"


cd "$REPO"

if [[ -n "$(git status --porcelain)" ]]; then
    echo "ERROR | BacSelect repository is not clean"
    git status --short
    exit 1
fi

HEAD_COMMIT="$(git rev-parse HEAD)"
ORIGIN_MAIN="$(git rev-parse origin/main)"

if [[ "$HEAD_COMMIT" != "$ORIGIN_MAIN" ]]; then
    echo "ERROR | HEAD differs from origin/main"
    echo "HEAD=$HEAD_COMMIT"
    echo "origin/main=$ORIGIN_MAIN"
    exit 1
fi

EXPECTED_COMMIT="${BACSELECT_EXPECTED_COMMIT:-}"

if [[ ! "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
    echo "ERROR | BACSELECT_EXPECTED_COMMIT must be a full 40-character commit hash"
    exit 1
fi

if [[ "$HEAD_COMMIT" != "$EXPECTED_COMMIT" ]]; then
    echo "ERROR | production commit pin mismatch"
    echo "expected=$EXPECTED_COMMIT"
    echo "HEAD=$HEAD_COMMIT"
    exit 1
fi


for required in \
    "$WORKER" \
    "$INPUT_HASHES" \
    "$SOURCE_AUDITS" \
    "$FINCH_DRIVER" \
    "$FINCH_BASIC" \
    "$ENGINE_SOURCE" \
    "$ENV_LOCK" \
    "$TARGETS" \
    "$REFERENCE_MATRIX"
do
    if [[ ! -f "$required" ]]; then
        echo "ERROR | required input missing: $required"
        exit 1
    fi
done

if [[ ! -d "$SNAPSHOT_ROOT/$BATCH_ID" ]]; then
    echo "ERROR | snapshot batch missing: $SNAPSHOT_ROOT/$BATCH_ID"
    exit 1
fi


echo "===== production source hash gates ====="

(
    cd "$REPO"
    sha256sum -c \
        "validation/selector-v1/repeat-scale-production-inputs.sha256"
)

require_sha256 \
    "$TARGETS" \
    "$EXPECTED_TARGET_SHA256" \
    "repeat-scale target manifest"

require_sha256 \
    "$REFERENCE_MATRIX" \
    "$EXPECTED_REFERENCE_SHA256" \
    "frozen reference matrix"

require_sha256 \
    "$ENV_LOCK" \
    "$EXPECTED_ENV_LOCK_SHA256" \
    "repeat environment lock"


EXPECTED_SOURCE_HEADER=$'batch\tbatch_summary_sha256\tcandidate_sequence_audit_sha256\tcomponent_sequence_audit_sha256\tpackage_files_sha256'
OBSERVED_SOURCE_HEADER="$(sed -n '1p' "$SOURCE_AUDITS")"

if [[ "$OBSERVED_SOURCE_HEADER" != "$EXPECTED_SOURCE_HEADER" ]]; then
    echo "ERROR | source snapshot audit manifest header mismatch"
    exit 1
fi

SOURCE_ROW_COUNT="$(
    awk -F'\t' \
        -v batch="$BATCH_ID" \
        'NR > 1 && $1 == batch { count += 1 } END { print count + 0 }' \
        "$SOURCE_AUDITS"
)"

if [[ "$SOURCE_ROW_COUNT" != "1" ]]; then
    echo "ERROR | expected exactly one source audit row for $BATCH_ID"
    echo "observed_rows=$SOURCE_ROW_COUNT"
    exit 1
fi

SOURCE_ROW="$(
    awk -F'\t' \
        -v batch="$BATCH_ID" \
        'NR > 1 && $1 == batch { print $2 "\t" $3 "\t" $4 "\t" $5 }' \
        "$SOURCE_AUDITS"
)"

IFS=$'\t' read -r \
    EXPECTED_BATCH_SUMMARY_SHA256 \
    EXPECTED_CANDIDATE_AUDIT_SHA256 \
    EXPECTED_COMPONENT_AUDIT_SHA256 \
    EXPECTED_PACKAGE_FILES_SHA256 \
    <<< "$SOURCE_ROW"

require_sha256 \
    "$SNAPSHOT_ROOT/$BATCH_ID/batch-summary.json" \
    "$EXPECTED_BATCH_SUMMARY_SHA256" \
    "$BATCH_ID batch summary"

require_sha256 \
    "$SNAPSHOT_ROOT/$BATCH_ID/candidate-sequence-audit.tsv" \
    "$EXPECTED_CANDIDATE_AUDIT_SHA256" \
    "$BATCH_ID candidate sequence audit"

require_sha256 \
    "$SNAPSHOT_ROOT/$BATCH_ID/component-sequence-audit.tsv" \
    "$EXPECTED_COMPONENT_AUDIT_SHA256" \
    "$BATCH_ID component sequence audit"

require_sha256 \
    "$SNAPSHOT_ROOT/$BATCH_ID/package-files.tsv" \
    "$EXPECTED_PACKAGE_FILES_SHA256" \
    "$BATCH_ID package file manifest"


if ! "$CONDA" env list | awk -v name="$ENV_NAME" '
    $1 == name { found = 1 }
    END { exit(found ? 0 : 1) }
'; then
    echo "ERROR | conda environment not found: $ENV_NAME"
    exit 1
fi

LIVE_ENV_LOCK_SHA256="$(
    "$CONDA" list \
        --explicit \
        -n "$ENV_NAME" \
    | sha256sum \
    | awk '{print $1}'
)"

if [[ "$LIVE_ENV_LOCK_SHA256" != "$EXPECTED_ENV_LOCK_SHA256" ]]; then
    echo "ERROR | live bacselect-repeat environment differs from frozen lock"
    echo "expected=$EXPECTED_ENV_LOCK_SHA256"
    echo "observed=$LIVE_ENV_LOCK_SHA256"
    exit 1
fi


ENV_PREFIX="$("$CONDA" run -n "$ENV_NAME" python3 - <<'PY'
import os
import sys
print(os.path.dirname(os.path.dirname(sys.executable)))
PY
)"

if [[ -z "$ENV_PREFIX" || ! -d "$ENV_PREFIX" ]]; then
    echo "ERROR | could not resolve bacselect-repeat environment prefix"
    exit 1
fi

BUILD_DIR="$(
    mktemp \
        -d \
        "${TMPDIR:-/tmp}/bacselect-repeat-scale.${SLURM_JOB_ID:-manual}.${SLURM_ARRAY_TASK_ID}.XXXXXX"
)"

cleanup() {
    rm -rf "$BUILD_DIR"
}
trap cleanup EXIT

ENGINE="$BUILD_DIR/structural_features_fast"

for required in \
    "$ENV_PREFIX/bin/x86_64-conda-linux-gnu-c++" \
    "$ENV_PREFIX/include/divsufsort.h" \
    "$ENV_PREFIX/lib/libdivsufsort.so"
do
    if [[ ! -e "$required" ]]; then
        echo "ERROR | repeat build dependency missing: $required"
        exit 1
    fi
done

"$ENV_PREFIX/bin/x86_64-conda-linux-gnu-c++" \
    -std=c++17 \
    -O2 \
    -Wall \
    -Wextra \
    -Wpedantic \
    -Werror \
    -I"$ENV_PREFIX/include" \
    "$ENGINE_SOURCE" \
    -L"$ENV_PREFIX/lib" \
    -Wl,-rpath,"$ENV_PREFIX/lib" \
    -ldivsufsort \
    -o "$ENGINE"

if [[ ! -x "$ENGINE" ]]; then
    echo "ERROR | compiled repeat engine is not executable"
    exit 1
fi

ENGINE_SHA256="$(sha256_file "$ENGINE")"

OUTPUT_ROOT="$OUTPUT_BASE/$HEAD_COMMIT/production"

mkdir -p "$OUTPUT_ROOT"


echo "============================================================"
echo "BacSelect selector-v1 alternative-k repeat grid"
echo "started_utc=$(timestamp)"
echo "host=$(hostname)"
echo "slurm_job_id=${SLURM_JOB_ID:-unknown}"
echo "slurm_array_job_id=${SLURM_ARRAY_JOB_ID:-unknown}"
echo "slurm_array_task_id=$SLURM_ARRAY_TASK_ID"
echo "batch=$BATCH_ID"
echo "git_head=$HEAD_COMMIT"
echo "origin_main=$ORIGIN_MAIN"
echo "worker_sha256=$(sha256_file "$WORKER")"
echo "production_inputs_manifest_sha256=$(sha256_file "$INPUT_HASHES")"
echo "source_audit_manifest_sha256=$(sha256_file "$SOURCE_AUDITS")"
echo "finch_driver_sha256=$(sha256_file "$FINCH_DRIVER")"
echo "finch_basic_sha256=$(sha256_file "$FINCH_BASIC")"
echo "engine_source_sha256=$(sha256_file "$ENGINE_SOURCE")"
echo "engine_sha256=$ENGINE_SHA256"
echo "environment_lock_sha256=$LIVE_ENV_LOCK_SHA256"
echo "target_manifest_sha256=$(sha256_file "$TARGETS")"
echo "reference_matrix_sha256=$(sha256_file "$REFERENCE_MATRIX")"
echo "snapshot_root=$SNAPSHOT_ROOT"
echo "output_root=$OUTPUT_ROOT"
echo "k_values=$K_VALUES"
echo "============================================================"


"$CONDA" run \
    --no-capture-output \
    -n "$ENV_NAME" \
    env PYTHONPATH="$REPO/src" \
    python3 "$WORKER" \
        --snapshot-root "$SNAPSHOT_ROOT" \
        --targets "$TARGETS" \
        --reference-matrix "$REFERENCE_MATRIX" \
        --batch "$BATCH_ID" \
        --engine "$ENGINE" \
        --output-root "$OUTPUT_ROOT" \
        --production-inputs-manifest "$INPUT_HASHES" \
        --source-audit-manifest "$SOURCE_AUDITS"


echo "============================================================"
echo "PASS | BacSelect alternative-k repeat-grid task"
echo "finished_utc=$(timestamp)"
echo "batch=$BATCH_ID"
echo "k_values=$K_VALUES"
echo "============================================================"
