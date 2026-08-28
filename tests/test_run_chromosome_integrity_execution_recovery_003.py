from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCRIPT = (
    ROOT
    / "validation"
    / "selector-v1"
    / "run_chromosome_integrity_execution_recovery_003.slurm"
)


def text() -> str:
    return SCRIPT.read_text(
        encoding="utf-8"
    )


def test_attempt003_uses_24_hour_slurm_contract():
    observed = text()

    assert "#SBATCH --job-name=bacsel-stage3-r3" in observed
    assert "#SBATCH --partition=prod" in observed
    assert "#SBATCH --time=24:00:00" in observed
    assert "#SBATCH --cpus-per-task=1" in observed
    assert "#SBATCH --mem=4G" in observed


def test_attempt003_runs_original_frozen_scientific_wrapper():
    observed = text()

    assert (
        'EXPECTED_COMMIT="'
        "dfe72a4c0c6ddef3af999c10b2db66d05b0eca88"
        '"'
        in observed
    )

    assert (
        'EXPECTED_WRAPPER_SHA256="'
        "b08610d72e1ff0ba5c06561c537c4f5150bae7698f1d9c7fdfef57720f4eed80"
        '"'
        in observed
    )

    assert (
        'PRODUCTION_REPO="/home/rwhite/github/bacselect"'
        in observed
    )


def test_attempt003_has_separate_output_root():
    observed = text()

    assert (
        'OUTPUT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/'
        "bacselect/selector-v1/"
        "chromosome-integrity-execution-recovery/"
        'attempt-003"'
        in observed
    )


def test_attempt003_handles_absent_old_slurm_job():
    observed = text()

    assert 'ATTEMPT2_JOB_ID="2508496"' in observed
    assert '2>/dev/null' in observed
    assert '|| true' in observed
    assert (
        'test -z "$ATTEMPT2_ACTIVE_STATE"'
        in observed
    )


def test_attempt003_refuses_active_attempt002():
    observed = text()

    assert (
        "attempt 002 is still active"
        in observed
    )

    assert (
        "no attempt-002 Stage 3 process remains"
        in observed
    )


def test_attempt003_is_forbidden_after_attempt002_success():
    observed = text()

    assert 'test ! -e "$ATTEMPT2_FINAL"' in observed

    assert (
        "attempt 002 completed; attempt 003 is forbidden"
        in observed
    )


def test_attempt003_requires_exact_attempt002_partial():
    observed = text()

    assert (
        "1de0fb5430383ea7c287fbdbb7da90a61ce3866115991c566bf6f53bb816cbf3"
        in observed
    )

    assert (
        "0402007175b88d7e95aea07e2296fb15f0c546398c51624d55ab329adbe001ad"
        in observed
    )

    assert (
        "EXPECTED_ATTEMPT2_FILES"
        in observed
    )


def test_attempt003_binds_exact_attempt002_slurm_evidence():
    observed = text()

    assert (
        "f264015db2469c101fbf62640a255d16c55ebd9121e1fc895b4371eefc301ee3"
        in observed
    )

    assert (
        "18c1ec27c3eccdadf3f0717fe52d551b3a14d72a381a7e91f0a28609097023fe"
        in observed
    )

    assert (
        "CANCELLED AT 2026-08-29T02:00:50 "
        "DUE TO TIME LIMIT"
        in observed
    )


def test_attempt003_binds_attempt002_scientific_boundary():
    observed = text()

    assert (
        "PASS | Stage 3 input reconstructed and rebound"
        in observed
    )

    assert "stage3_input_candidate_count=68278" in observed

    assert (
        "stage3_input_membership_sha256="
        "e86944d3e8b0407a7901c1a996f7adb42eeda3efffd3384fec7a8d87859209f4"
        in observed
    )

    assert (
        "historical_adjudication_rows_parsed=false"
        in observed
    )


def test_attempt003_preserves_prior_attempts():
    observed = text()

    assert "rm -rf" not in observed
    assert 'mv "$ATTEMPT1_PARTIAL"' not in observed
    assert 'mv "$ATTEMPT2_PARTIAL"' not in observed

    assert (
        "failed attempt 001 remains immutable and outcome-free"
        in observed
    )

    assert (
        "attempt 002 is exact, timed out, preserved, and outcome-free"
        in observed
    )


def test_attempt003_does_not_depend_on_slurm_accounting():
    observed = text()

    assert "sacct" not in observed


def test_attempt003_remains_unbuffered():
    observed = text()

    assert "export PYTHONUNBUFFERED=1" in observed
    assert (
        'export PYTHONPATH="$PRODUCTION_REPO/src"'
        in observed
    )
