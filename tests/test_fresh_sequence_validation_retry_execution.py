from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
ARRAY = ROOT / "validation/selector-v1/run_fresh_sequence_validation_retry.slurm"
SUBMIT = ROOT / "validation/selector-v1/submit_fresh_sequence_validation_retry.sh"
INCIDENT_MD = ROOT / "validation/selector-v1/fresh-sequence-execution-incident.md"
INCIDENT_JSON = ROOT / "validation/selector-v1/fresh-sequence-execution-incident.json"


def test_corrected_array_preserves_scientific_batch_contract():
    text = ARRAY.read_text(encoding="utf-8")

    assert "#SBATCH --array=1-31%2" in text
    assert "MAX_ATTEMPTS=3" in text
    assert "RETRY_DELAY_SECONDS=60" in text


def test_corrected_array_uses_validated_node():
    text = ARRAY.read_text(encoding="utf-8")

    assert "#SBATCH --nodelist=kscprod-bio8" in text
    assert '[[ "$host" == "kscprod-bio8" ]]' in text


def test_pre_zip_failure_is_archived_before_fresh_retry():
    text = ARRAY.read_text(encoding="utf-8")

    assert "download-exit-code.txt" in text
    assert "failed-attempts" in text
    assert 'mv "$partial_dir" "$failed_dir"' in text
    assert 'mode="fresh"' in text
    assert 'mode="resume"' in text


def test_resume_requires_complete_resume_state():
    text = ARRAY.read_text(encoding="utf-8")

    assert '-f "$partial_dir/dehydrated.zip"' in text
    assert '-d "$partial_dir/package"' in text
    assert '-f "$partial_dir/attempt-origin.json"' in text
    assert '-f "$partial_dir/accessions.txt"' in text


def test_submit_records_superseded_failed_execution():
    text = SUBMIT.read_text(encoding="utf-8")

    assert "kscprod-bio8" in text
    assert "archive_failed_pre_zip_then_fresh_retry" in text
    assert "b172cd104cc81113b1da862abadc6245c6dd9f76" in text


def test_incident_checkpoint_is_blinding_safe():
    text = INCIDENT_MD.read_text(encoding="utf-8")
    payload = json.loads(INCIDENT_JSON.read_text(encoding="utf-8"))

    for token in ("GCA_", "GCF_", "SAMN", "SAMEA", "SAMD"):
        assert token not in text

    assert payload["sequence_validation_reached"] is False
    assert payload["selector_outcome_generated"] is False
    assert payload["target_set_changed"] is False
    assert payload["batch_size_changed"] is False
    assert payload["array_concurrency_changed"] is False
    assert payload["datasets_version_changed"] is False
    assert payload["acquisition_arguments_changed"] is False
