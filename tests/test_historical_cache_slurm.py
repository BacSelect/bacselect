from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

ARRAY = ROOT / "validation/selector-v1/run_historical_cache_verification.slurm"
AGGREGATE = ROOT / "validation/selector-v1/aggregate_historical_cache_verification.slurm"
SUBMIT = ROOT / "validation/selector-v1/submit_historical_cache_verification.sh"


def text(path):
    return path.read_text(encoding="utf-8")


def test_array_resources_are_frozen():
    value = text(ARRAY)
    assert "#SBATCH --partition=prod" in value
    assert "#SBATCH --cpus-per-task=1" in value
    assert "#SBATCH --mem=2G" in value
    assert "#SBATCH --time=04:00:00" in value
    assert "#SBATCH --array=1-111%4" in value


def test_aggregate_resources_are_frozen():
    value = text(AGGREGATE)
    assert "#SBATCH --partition=prod" in value
    assert "#SBATCH --cpus-per-task=1" in value
    assert "#SBATCH --mem=2G" in value
    assert "#SBATCH --time=01:00:00" in value


def test_array_invokes_existing_cache_verifier():
    value = text(ARRAY)
    assert "python -m bacselect.source_cache_verify" in value
    assert "verify-batch" in value


def test_aggregate_uses_afterok_submission_dependency():
    assert '--dependency="afterok:$ARRAY_JOB_ID"' in text(SUBMIT)


def test_submission_derives_output_root_from_git_commit():
    value = text(SUBMIT)
    assert 'OUTPUT_ROOT="$OUTPUT_PARENT/$HEAD_COMMIT"' in value
    assert '[[ "$HEAD_COMMIT" == "$ORIGIN_MAIN" ]]' in value


def test_log_layout_is_commit_scoped():
    value = text(SUBMIT)
    assert (
        'LOG_ROOT="$HOME/slurm-logs/bacselect/'
        'historical-cache-verification/$HEAD_COMMIT"'
    ) in value
    assert "%x-%A_%a.out" in value
    assert "%x-%A_%a.err" in value


def test_runner_has_no_network_or_download_commands():
    combined = "\n".join([text(ARRAY), text(AGGREGATE)]).lower()
    forbidden = (
        "curl ",
        "wget ",
        "datasets ",
        "rehydrate",
        "download genome",
        "requests.",
        "urllib.",
        "http://",
        "https://",
    )
    for token in forbidden:
        assert token not in combined


def test_runner_never_copies_historical_sequence_data():
    combined = "\n".join([text(ARRAY), text(AGGREGATE)])
    assert re.search(r"(^|\n)\s*cp\s", combined) is None
    assert re.search(r"(^|\n)\s*rsync\s", combined) is None


def test_array_requires_absent_batch_output():
    value = text(ARRAY)
    assert '[[ ! -e "$OUT" ]]' in value
    assert "batch verification output already exists" in value


def test_aggregate_verifies_all_batch_artifact_manifests():
    value = text(AGGREGATE)
    assert "for task in $(seq 1 111)" in value
    assert "sha256sum -c batch-artifacts-sha256.txt" in value


def test_submit_requires_new_commit_scoped_output_root():
    value = text(SUBMIT)
    assert '[[ ! -e "$OUTPUT_ROOT" ]]' in value
    assert '"$OUTPUT_ROOT/batches"' in value


def test_submission_helper_does_not_run_real_verifier():
    value = text(SUBMIT)
    assert "python -m bacselect.source_cache_verify" not in value
    assert 'sha256sum "$EXPECTED_SNAPSHOT_ROOT' not in value
