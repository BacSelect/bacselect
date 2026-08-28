#!/usr/bin/env bash
#SBATCH --job-name=bacsel-stage3-r3
#SBATCH --partition=prod
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home/rwhite/slurm-logs/bacselect/chromosome-integrity-recovery/%j.out
#SBATCH --error=/home/rwhite/slurm-logs/bacselect/chromosome-integrity-recovery/%j.err

set -euo pipefail

PRODUCTION_REPO="/home/rwhite/github/bacselect"

EXPECTED_COMMIT="dfe72a4c0c6ddef3af999c10b2db66d05b0eca88"

WRAPPER_RELATIVE="validation/selector-v1/run_chromosome_integrity_execution.py"
EXPECTED_WRAPPER_SHA256="b08610d72e1ff0ba5c06561c537c4f5150bae7698f1d9c7fdfef57720f4eed80"

PY="/home/rwhite/.conda/envs/bacselect-dev/bin/python"

HISTORICAL_ROOT="/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/ncbi-sequence-validation-snapshot"

CACHE_REUSE_ACCESSIONS="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/final-acquisition-manifests/a8f045506ac4a3f17034cd9170867995a87eb894/cache-reuse-accessions.txt"

CACHE_REUSE_MANIFEST="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/final-acquisition-manifests/a8f045506ac4a3f17034cd9170867995a87eb894/cache-reuse-manifest.tsv"

CACHE_VERIFICATION="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/historical-cache-verification/e6ab34e64cdb949813e533550e19dababd1d80ab/aggregate/historical-cache-content-verification.tsv"

FRESH_ROOT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation/7aba4b0a2aa22c05ce808bf9b5811606bd3d2293"

RECOVERY_ROOT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation-recovery/f9bfb99ff163a73899ebb53ad7e1eff69a1f492e/source-7aba4b0a2aa22c05ce808bf9b5811606bd3d2293"

STAGE2_DECISIONS="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/repeated-biosample-execution-recovery/attempt-001/38b49a677fa9e6e6832816392a788ea16905c6b0/stage2-repeated-biosample-decisions.tsv"

EXPECTED_STAGE2_DECISIONS_SHA256="3613195996b8d8d1a5d6cbb23976a5418d97666054aa8ef33601b5ac31a7979a"

HISTORICAL_ADJUDICATIONS="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/chromosome-integrity-inputs/dfe72a4c0c6ddef3af999c10b2db66d05b0eca88/source-replicon-integrity-adjudications.tsv"

EXPECTED_HISTORICAL_ADJUDICATIONS_SHA256="def13131598e351d06c943f8a8e614e49b2c0b4bc55210ac7c9efd20f1f58828"

ATTEMPT1_PARTIAL="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/chromosome-integrity-execution/dfe72a4c0c6ddef3af999c10b2db66d05b0eca88.partial"

EXPECTED_ATTEMPT1_INPUT_MANIFEST_SHA256="1de0fb5430383ea7c287fbdbb7da90a61ce3866115991c566bf6f53bb816cbf3"

EXPECTED_ATTEMPT1_PREDECISION_SHA256="0402007175b88d7e95aea07e2296fb15f0c546398c51624d55ab329adbe001ad"

ATTEMPT2_JOB_ID="2508496"

ATTEMPT2_PARTIAL="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/chromosome-integrity-execution-recovery/attempt-002/dfe72a4c0c6ddef3af999c10b2db66d05b0eca88.partial"

ATTEMPT2_FINAL="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/chromosome-integrity-execution-recovery/attempt-002/dfe72a4c0c6ddef3af999c10b2db66d05b0eca88"

ATTEMPT2_STDOUT="/home/rwhite/slurm-logs/bacselect/chromosome-integrity-recovery/2508496.out"

ATTEMPT2_STDERR="/home/rwhite/slurm-logs/bacselect/chromosome-integrity-recovery/2508496.err"

EXPECTED_ATTEMPT2_INPUT_MANIFEST_SHA256="1de0fb5430383ea7c287fbdbb7da90a61ce3866115991c566bf6f53bb816cbf3"

EXPECTED_ATTEMPT2_PREDECISION_SHA256="0402007175b88d7e95aea07e2296fb15f0c546398c51624d55ab329adbe001ad"

EXPECTED_ATTEMPT2_STDOUT_SHA256="f264015db2469c101fbf62640a255d16c55ebd9121e1fc895b4371eefc301ee3"

EXPECTED_ATTEMPT2_STDERR_SHA256="18c1ec27c3eccdadf3f0717fe52d551b3a14d72a381a7e91f0a28609097023fe"

OUTPUT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/chromosome-integrity-execution-recovery/attempt-003"

FINAL_DIR="$OUTPUT_ROOT/$EXPECTED_COMMIT"
PARTIAL_DIR="$OUTPUT_ROOT/$EXPECTED_COMMIT.partial"

sha256_file() {
    sha256sum "$1" |
        awk '{print $1}'
}

require_sha256() {
    local file="$1"
    local expected="$2"
    local label="$3"
    local observed

    test -f "$file" || {
        echo "ERROR | missing $label: $file" >&2
        exit 1
    }

    test ! -L "$file" || {
        echo "ERROR | symlink not permitted for $label: $file" >&2
        exit 1
    }

    observed="$(sha256_file "$file")"

    test "$observed" = "$expected" || {
        echo "ERROR | $label SHA256 mismatch" >&2
        echo "expected=$expected" >&2
        echo "observed=$observed" >&2
        exit 1
    }
}

echo "===== Stage 3 recovery attempt 003 ====="
date

cd "$PRODUCTION_REPO" || exit 1

test "$(git rev-parse HEAD)" = "$EXPECTED_COMMIT" || {
    echo "ERROR | production HEAD differs from frozen commit" >&2
    exit 1
}

test "$(git rev-parse origin/main)" = "$EXPECTED_COMMIT" || {
    echo "ERROR | production origin/main differs from frozen commit" >&2
    exit 1
}

test -z "$(git status --porcelain)" || {
    echo "ERROR | production BacSelect checkout is not clean" >&2
    git status --short >&2
    exit 1
}

require_sha256 \
    "$PRODUCTION_REPO/$WRAPPER_RELATIVE" \
    "$EXPECTED_WRAPPER_SHA256" \
    "Stage 3 production wrapper"

echo "PASS | exact frozen production checkout"

echo
echo "===== preserve failed attempt 001 ====="

test -d "$ATTEMPT1_PARTIAL" || {
    echo "ERROR | attempt-001 partial directory missing" >&2
    exit 1
}

require_sha256 \
    "$ATTEMPT1_PARTIAL/stage3-input-evidence-manifest.tsv" \
    "$EXPECTED_ATTEMPT1_INPUT_MANIFEST_SHA256" \
    "attempt-001 input-evidence manifest"

require_sha256 \
    "$ATTEMPT1_PARTIAL/stage3-predecision-provenance.json" \
    "$EXPECTED_ATTEMPT1_PREDECISION_SHA256" \
    "attempt-001 predecision provenance"

for forbidden in \
    stage3-chromosome-integrity-decisions.tsv \
    stage3-execution-provenance.json \
    stage3-aggregate-summary.json
do
    test ! -e "$ATTEMPT1_PARTIAL/$forbidden" || {
        echo "ERROR | attempt 001 unexpectedly contains $forbidden" >&2
        exit 1
    }
done

echo "PASS | failed attempt 001 remains immutable and outcome-free"

echo
echo "===== require failed attempt 002 ====="

ATTEMPT2_ACTIVE_STATE="$(
    squeue \
        -h \
        -j "$ATTEMPT2_JOB_ID" \
        -o "%T" \
        2>/dev/null \
    || true
)"

printf 'attempt2_active_state=%s\n' \
    "${ATTEMPT2_ACTIVE_STATE:-NONE}"

test -z "$ATTEMPT2_ACTIVE_STATE" || {
    echo "ERROR | attempt 002 is still active" >&2
    exit 1
}

test ! -e "$ATTEMPT2_FINAL" || {
    echo "ERROR | attempt 002 completed; attempt 003 is forbidden" >&2
    exit 1
}

test -d "$ATTEMPT2_PARTIAL" || {
    echo "ERROR | failed attempt-002 partial directory missing" >&2
    exit 1
}

EXPECTED_ATTEMPT2_FILES="$(
    printf '%s\n%s\n' \
        "stage3-input-evidence-manifest.tsv" \
        "stage3-predecision-provenance.json" \
    | sort
)"

OBSERVED_ATTEMPT2_FILES="$(
    find "$ATTEMPT2_PARTIAL" \
        -maxdepth 1 \
        -type f \
        -printf '%f\n' \
    | sort
)"

test "$OBSERVED_ATTEMPT2_FILES" = \
    "$EXPECTED_ATTEMPT2_FILES" || {
    echo "ERROR | attempt 002 has unexpected partial artifacts" >&2
    printf '%s\n' "$OBSERVED_ATTEMPT2_FILES" >&2
    exit 1
}

require_sha256 \
    "$ATTEMPT2_PARTIAL/stage3-input-evidence-manifest.tsv" \
    "$EXPECTED_ATTEMPT2_INPUT_MANIFEST_SHA256" \
    "attempt-002 input-evidence manifest"

require_sha256 \
    "$ATTEMPT2_PARTIAL/stage3-predecision-provenance.json" \
    "$EXPECTED_ATTEMPT2_PREDECISION_SHA256" \
    "attempt-002 predecision provenance"

require_sha256 \
    "$ATTEMPT2_STDOUT" \
    "$EXPECTED_ATTEMPT2_STDOUT_SHA256" \
    "attempt-002 Slurm stdout"

require_sha256 \
    "$ATTEMPT2_STDERR" \
    "$EXPECTED_ATTEMPT2_STDERR_SHA256" \
    "attempt-002 Slurm stderr"

grep -Fq \
    "PASS | Stage 3 input reconstructed and rebound" \
    "$ATTEMPT2_STDOUT" || {
    echo "ERROR | attempt-002 Stage 3 boundary evidence absent" >&2
    exit 1
}

grep -Fq \
    "stage3_input_candidate_count=68278" \
    "$ATTEMPT2_STDOUT" || {
    echo "ERROR | attempt-002 candidate-count evidence absent" >&2
    exit 1
}

grep -Fq \
    "stage3_input_membership_sha256=e86944d3e8b0407a7901c1a996f7adb42eeda3efffd3384fec7a8d87859209f4" \
    "$ATTEMPT2_STDOUT" || {
    echo "ERROR | attempt-002 membership evidence absent" >&2
    exit 1
}

grep -Fq \
    "historical_adjudication_rows_parsed=false" \
    "$ATTEMPT2_STDOUT" || {
    echo "ERROR | attempt-002 predecision boundary absent" >&2
    exit 1
}

grep -Fq \
    "JOB 2508496 ON kscprod-bio8 CANCELLED AT 2026-08-29T02:00:50 DUE TO TIME LIMIT" \
    "$ATTEMPT2_STDERR" || {
    echo "ERROR | exact attempt-002 timeout evidence absent" >&2
    exit 1
}

for forbidden in \
    stage3-chromosome-integrity-decisions.tsv \
    stage3-execution-provenance.json \
    stage3-aggregate-summary.json \
    stage3-content-manifest.tsv
do
    test ! -e "$ATTEMPT2_PARTIAL/$forbidden" || {
        echo "ERROR | attempt 002 unexpectedly contains $forbidden" >&2
        exit 1
    }
done

echo "PASS | attempt 002 is exact, timed out, preserved, and outcome-free"

echo
echo "===== no competing Stage 3 recovery process ====="

if pgrep -af \
    'run_chromosome_integrity_execution.py.*chromosome-integrity-execution-recovery/attempt-002' \
    >/dev/null
then
    echo "ERROR | attempt-002 Stage 3 process still exists" >&2
    exit 1
fi

echo "PASS | no attempt-002 Stage 3 process remains"

echo
echo "===== recovery inputs ====="

require_sha256 \
    "$STAGE2_DECISIONS" \
    "$EXPECTED_STAGE2_DECISIONS_SHA256" \
    "Stage 2 decision artifact"

require_sha256 \
    "$HISTORICAL_ADJUDICATIONS" \
    "$EXPECTED_HISTORICAL_ADJUDICATIONS_SHA256" \
    "historical chromosome-integrity adjudications"

for root in \
    "$HISTORICAL_ROOT" \
    "$FRESH_ROOT" \
    "$RECOVERY_ROOT"
do
    test -d "$root" || {
        echo "ERROR | required sequence root missing: $root" >&2
        exit 1
    }

    test ! -L "$root" || {
        echo "ERROR | required sequence root is a symlink: $root" >&2
        exit 1
    }
done

echo "PASS | recovery inputs present"

echo
echo "===== attempt-002 output boundary ====="

test ! -e "$FINAL_DIR" || {
    echo "ERROR | attempt-002 final directory already exists" >&2
    exit 1
}

test ! -e "$PARTIAL_DIR" || {
    echo "ERROR | attempt-002 partial directory already exists" >&2
    exit 1
}

echo "PASS | attempt-002 output state is new"

echo
echo "===== execute unchanged frozen Stage 3 wrapper ====="
echo "slurm_job_id=${SLURM_JOB_ID:-UNKNOWN}"
echo "expected_commit=$EXPECTED_COMMIT"
echo "output_root=$OUTPUT_ROOT"
date

export PYTHONUNBUFFERED=1
export PYTHONPATH="$PRODUCTION_REPO/src"

"$PY" \
    "$PRODUCTION_REPO/$WRAPPER_RELATIVE" \
    --repo "$PRODUCTION_REPO" \
    --expected-commit "$EXPECTED_COMMIT" \
    --expected-wrapper-sha256 "$EXPECTED_WRAPPER_SHA256" \
    --historical-root "$HISTORICAL_ROOT" \
    --cache-reuse-accessions "$CACHE_REUSE_ACCESSIONS" \
    --cache-reuse-manifest "$CACHE_REUSE_MANIFEST" \
    --cache-verification "$CACHE_VERIFICATION" \
    --fresh-root "$FRESH_ROOT" \
    --recovery-root "$RECOVERY_ROOT" \
    --stage2-decisions "$STAGE2_DECISIONS" \
    --historical-adjudications "$HISTORICAL_ADJUDICATIONS" \
    --output-root "$OUTPUT_ROOT"

echo
echo "PASS | Stage 3 recovery attempt 003 process exited successfully"
date
