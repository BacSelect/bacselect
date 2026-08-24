#!/usr/bin/env bash
#SBATCH --job-name=bac-rcon
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

WORKER="$REPO/validation/selector-v1/run_repeat_concordance_batch.py"
CONCORDANCE="$REPO/src/bacselect/repeat_concordance.py"

FINCH_DRIVER="$REPO/vendor/project-finch/experiment-0/compute_structural_features.py"
FINCH_BASIC="$REPO/vendor/project-finch/experiment-0/basic_structural_features.py"
ENGINE_SOURCE="$REPO/vendor/project-finch/experiment-0/structural_features_fast.cpp"

ENV_LOCK="$REPO/envs/bacselect-repeat-linux-64.lock"

TARGETS="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/repeat-scale/concordance-inputs/repeat-concordance-targets.tsv"

REFERENCE_MATRIX="/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/corrected-eligible-percentile-feature-space/corrected-eligible-structural-feature-matrix.tsv"

SNAPSHOT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/ncbi-sequence-validation-snapshot"

OUTPUT_BASE="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/repeat-scale/reference-concordance"

EXPECTED_WORKER_SHA256="4e012d24a04c547f2dd01564d4b01122de887b0858be2de20f457b64b120030b"

EXPECTED_CONCORDANCE_SHA256="6dc25a2d382ebdf0a5c6327b211bb4dae064363727b42864a725b626bb325a51"

EXPECTED_FINCH_DRIVER_SHA256="e4d76a44731000dc8330d6f3289aca76ce6562329dd371f6f63ec090ab42db50"

EXPECTED_FINCH_BASIC_SHA256="30bc3f52fdf68cf7b6433262935b3ed2bb189b256672687bea56f3a4f4cc043a"

EXPECTED_ENGINE_SOURCE_SHA256="bea979167a353c41e51bb96c83acebfb8e8136269d2902d99142c0780bf46925"

EXPECTED_ENV_LOCK_SHA256="aa6984b17e86f7d0627379e295fabed837cf7d43cc6a9fd80f32b7092ac5f64f"

EXPECTED_TARGET_SHA256="bc4acba1384524f956887d02d2f54aa7e501a2c23e2930b779a4e6520d8fcee1"

EXPECTED_REFERENCE_MATRIX_SHA256="fd264bedda627d737a647de601c8b835f53baeca246724e9aafb73fd50c9d656"


timestamp() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
}


sha256_file() {
    sha256sum "$1" | awk '{print $1}'
}


require_sha256() {
    local path="$1"
    local expected="$2"
    local label="$3"
    local observed

    if [[ ! -f "$path" ]]; then
        echo "ERROR | $label missing: $path"
        exit 1
    fi

    observed="$(sha256_file "$path")"

    if [[ "$observed" != "$expected" ]]; then
        echo "ERROR | $label SHA-256 mismatch"
        echo "expected=$expected"
        echo "observed=$observed"
        exit 1
    fi

    echo "PASS | $label SHA-256"
}


# ------------------------------------------------------------
# Resolve and validate array task.
# ------------------------------------------------------------

if [[ -z "${SLURM_ARRAY_TASK_ID:-}" ]]; then
    echo "ERROR | SLURM_ARRAY_TASK_ID is not set"
    exit 1
fi

if ! [[ "$SLURM_ARRAY_TASK_ID" =~ ^[0-9]+$ ]]; then
    echo "ERROR | invalid SLURM_ARRAY_TASK_ID"
    exit 1
fi

if ((
    SLURM_ARRAY_TASK_ID < 1
    || SLURM_ARRAY_TASK_ID > 111
)); then
    echo "ERROR | array task must be 1-111"
    exit 1
fi

BATCH_ID="$(
    printf 'batch-%03d' \
        "$SLURM_ARRAY_TASK_ID"
)"


# ------------------------------------------------------------
# Production must use a clean, locally pushed repository.
# ------------------------------------------------------------

cd "$REPO"

if [[ -n "$(git status --porcelain)" ]]; then
    echo "ERROR | Git working tree is not clean"
    git status --short
    exit 1
fi

HEAD_COMMIT="$(git rev-parse HEAD)"
ORIGIN_MAIN="$(git rev-parse origin/main)"

if [[ "$HEAD_COMMIT" != "$ORIGIN_MAIN" ]]; then
    echo "ERROR | HEAD differs from local origin/main"
    echo "HEAD=$HEAD_COMMIT"
    echo "origin/main=$ORIGIN_MAIN"
    exit 1
fi

OUTPUT_ROOT="$OUTPUT_BASE/$HEAD_COMMIT/production"


# ------------------------------------------------------------
# Freeze all scientific code and immutable inputs.
# ------------------------------------------------------------

require_sha256 \
    "$WORKER" \
    "$EXPECTED_WORKER_SHA256" \
    "repeat-concordance worker"

require_sha256 \
    "$CONCORDANCE" \
    "$EXPECTED_CONCORDANCE_SHA256" \
    "repeat-concordance module"

require_sha256 \
    "$FINCH_DRIVER" \
    "$EXPECTED_FINCH_DRIVER_SHA256" \
    "vendored Finch source loader"

require_sha256 \
    "$FINCH_BASIC" \
    "$EXPECTED_FINCH_BASIC_SHA256" \
    "vendored Finch basic module"

require_sha256 \
    "$ENGINE_SOURCE" \
    "$EXPECTED_ENGINE_SOURCE_SHA256" \
    "repeat-engine source"

require_sha256 \
    "$ENV_LOCK" \
    "$EXPECTED_ENV_LOCK_SHA256" \
    "repeat environment lock"

require_sha256 \
    "$TARGETS" \
    "$EXPECTED_TARGET_SHA256" \
    "55,306-genome concordance target manifest"

require_sha256 \
    "$REFERENCE_MATRIX" \
    "$EXPECTED_REFERENCE_MATRIX_SHA256" \
    "frozen corrected reference matrix"


if [[ ! -d "$SNAPSHOT_ROOT" ]]; then
    echo "ERROR | source snapshot root missing: $SNAPSHOT_ROOT"
    exit 1
fi

SOURCE_BATCH="$SNAPSHOT_ROOT/$BATCH_ID"

if [[ ! -d "$SOURCE_BATCH" ]]; then
    echo "ERROR | source batch missing: $SOURCE_BATCH"
    exit 1
fi


# ------------------------------------------------------------
# Require exact live repeat environment.
# ------------------------------------------------------------

LIVE_ENV_LOCK_SHA256="$(
    "$CONDA" list \
        --explicit \
        -n "$ENV_NAME" \
    | sha256sum \
    | awk '{print $1}'
)"

if [[ "$LIVE_ENV_LOCK_SHA256" != "$EXPECTED_ENV_LOCK_SHA256" ]]; then
    echo "ERROR | live repeat environment differs from frozen lock"
    echo "expected=$EXPECTED_ENV_LOCK_SHA256"
    echo "observed=$LIVE_ENV_LOCK_SHA256"
    exit 1
fi

echo "PASS | live repeat environment lock"


# ------------------------------------------------------------
# Prepare task-local compiled engine.
# ------------------------------------------------------------

TASK_TMP_BASE="${TMPDIR:-/tmp}"

TASK_TMP="$TASK_TMP_BASE/bacselect-repeat-concordance-${SLURM_JOB_ID:-unknown}-${SLURM_ARRAY_TASK_ID}"

rm -rf "$TASK_TMP"
mkdir -p "$TASK_TMP"

cleanup() {
    rm -rf "$TASK_TMP"
}

trap cleanup EXIT

ENGINE="$TASK_TMP/structural_features_fast"

ENV_PREFIX="$(
    "$CONDA" run \
        -n "$ENV_NAME" \
        python3 -c \
        'import os; print(os.environ["CONDA_PREFIX"])'
)"

if [[ -z "$ENV_PREFIX" ]]; then
    echo "ERROR | could not resolve repeat environment prefix"
    exit 1
fi

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

ENGINE_SHA256="$(sha256_file "$ENGINE")"

if [[ ! -x "$ENGINE" ]]; then
    echo "ERROR | compiled repeat engine is not executable"
    exit 1
fi


# ------------------------------------------------------------
# Record execution context.
# ------------------------------------------------------------

mkdir -p "$OUTPUT_ROOT"

echo "============================================================"
echo "BacSelect selector-v1 repeat reference concordance"
echo "started_utc=$(timestamp)"
echo "host=$(hostname)"
echo "slurm_job_id=${SLURM_JOB_ID:-unknown}"
echo "slurm_array_job_id=${SLURM_ARRAY_JOB_ID:-unknown}"
echo "slurm_array_task_id=$SLURM_ARRAY_TASK_ID"
echo "batch=$BATCH_ID"
echo "git_head=$HEAD_COMMIT"
echo "origin_main=$ORIGIN_MAIN"
echo "worker_sha256=$(sha256_file "$WORKER")"
echo "repeat_concordance_sha256=$(sha256_file "$CONCORDANCE")"
echo "finch_driver_sha256=$(sha256_file "$FINCH_DRIVER")"
echo "finch_basic_sha256=$(sha256_file "$FINCH_BASIC")"
echo "engine_source_sha256=$(sha256_file "$ENGINE_SOURCE")"
echo "engine_sha256=$ENGINE_SHA256"
echo "environment_lock_sha256=$LIVE_ENV_LOCK_SHA256"
echo "target_manifest_sha256=$(sha256_file "$TARGETS")"
echo "reference_matrix_sha256=$(sha256_file "$REFERENCE_MATRIX")"
echo "snapshot_root=$SNAPSHOT_ROOT"
echo "output_root=$OUTPUT_ROOT"
echo "k_values=150,400"
echo "============================================================"


# ------------------------------------------------------------
# Execute only the frozen 150/400 reference-concordance gate.
# ------------------------------------------------------------

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
        --output-root "$OUTPUT_ROOT"


echo "============================================================"
echo "PASS | BacSelect repeat reference concordance task"
echo "finished_utc=$(timestamp)"
echo "batch=$BATCH_ID"
echo "k_values=150,400"
echo "============================================================"
