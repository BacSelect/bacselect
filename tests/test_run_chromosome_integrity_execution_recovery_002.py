from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCRIPT = (
    ROOT
    / "validation"
    / "selector-v1"
    / "run_chromosome_integrity_execution_recovery_002.slurm"
)


def text() -> str:
    return SCRIPT.read_text(
        encoding="utf-8"
    )


def test_recovery_uses_bacselect_slurm_prod_contract():
    observed = text()

    assert "#SBATCH --partition=prod" in observed
    assert "#SBATCH --time=08:00:00" in observed
    assert "#SBATCH --cpus-per-task=1" in observed
    assert "#SBATCH --mem=4G" in observed
    assert (
        "/home/rwhite/slurm-logs/bacselect/"
        "chromosome-integrity-recovery/%j.out"
        in observed
    )
    assert (
        "/home/rwhite/slurm-logs/bacselect/"
        "chromosome-integrity-recovery/%j.err"
        in observed
    )


def test_recovery_pins_original_scientific_execution():
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

    assert (
        "run_chromosome_integrity_execution.py"
        in observed
    )


def test_recovery_preserves_failed_attempt_001_evidence():
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
        "failed attempt 001 remains immutable and outcome-free"
        in observed
    )

    assert "rm -rf" not in observed

    assert (
        'mv "$ATTEMPT1_PARTIAL"'
        not in observed
    )


def test_recovery_uses_new_attempt_002_output_root():
    observed = text()

    assert (
        'OUTPUT_ROOT="/NGS/scratch/EXT/Rhys_wkdir/'
        "bacselect/selector-v1/"
        "chromosome-integrity-execution-recovery/"
        'attempt-002"'
        in observed
    )

    assert (
        'FINAL_DIR="$OUTPUT_ROOT/$EXPECTED_COMMIT"'
        in observed
    )

    assert (
        'PARTIAL_DIR="$OUTPUT_ROOT/$EXPECTED_COMMIT.partial"'
        in observed
    )


def test_recovery_requires_original_main_freeze():
    observed = text()

    assert (
        'git rev-parse HEAD'
        in observed
    )

    assert (
        'git rev-parse origin/main'
        in observed
    )

    assert (
        'git status --porcelain'
        in observed
    )


def test_recovery_pins_real_input_identities():
    observed = text()

    assert (
        "3613195996b8d8d1a5d6cbb23976a5418d97666054aa8ef33601b5ac31a7979a"
        in observed
    )

    assert (
        "def13131598e351d06c943f8a8e614e49b2c0b4bc55210ac7c9efd20f1f58828"
        in observed
    )


def test_recovery_uses_unbuffered_durable_execution():
    observed = text()

    assert "export PYTHONUNBUFFERED=1" in observed
    assert (
        'export PYTHONPATH="$PRODUCTION_REPO/src"'
        in observed
    )

    assert "nohup" not in observed
    assert "& disown" not in observed
