from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "validation/selector-v1/fresh_sequence_validation_batch.py"
AUDITOR = ROOT / "validation/selector-v1/audit_fresh_sequence_validation.py"
ARRAY = ROOT / "validation/selector-v1/run_fresh_sequence_validation.slurm"
AGGREGATE = ROOT / "validation/selector-v1/aggregate_fresh_sequence_validation.slurm"
SUBMIT = ROOT / "validation/selector-v1/submit_fresh_sequence_validation.sh"


def load_auditor():
    spec = importlib.util.spec_from_file_location("bacselect_fresh_audit", AUDITOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_is_bacselect_bound():
    text = WORKER.read_text(encoding="utf-8")
    assert "EXPECTED_TARGETS = 15_326" in text
    assert "EXPECTED_BATCHES = 31" in text
    assert "1c9a73231d6b8ebfed76fb60621616588a4f51b1144e5d7880f14ddf26d1863b" in text
    assert "fresh_biosample" in text
    assert "not_in_historical_cache" in text
    assert "sequence-validation-targets.tsv" not in text


def test_worker_download_matches_frozen_design():
    text = WORKER.read_text(encoding="utf-8")
    assert '"genome,gbff,seq-report"' in text
    fragment = '            "--assembly-source",\n            "GenBank",\n'
    assert fragment not in text


def test_worker_records_vendor_origin():
    text = WORKER.read_text(encoding="utf-8")
    assert "780f8aabe2e6d9b4425498ee1f0170e3b0d55328100a4aea02efc875d4d29665" in text


def test_auditor_frozen_inputs():
    module = load_auditor()
    assert module.EXPECTED_TARGETS == 15326
    assert module.EXPECTED_BATCHES == 31
    assert module.BATCH_SIZE == 500
    assert module.EXPECTED_FINAL_BATCH_SIZE == 326
    assert module.FRESH_MANIFEST_SHA256 == "1c9a73231d6b8ebfed76fb60621616588a4f51b1144e5d7880f14ddf26d1863b"
    assert module.FRESH_BATCH_INDEX_SHA256 == "2a52f7ba3b23867bfe85078b47b840e5a1e240b09187d130fb0578087b483c4a"


def test_execution_is_conservatively_bounded():
    text = ARRAY.read_text(encoding="utf-8")
    assert "#SBATCH --array=1-31%2" in text
    assert "MAX_ATTEMPTS=3" in text
    assert "RETRY_DELAY_SECONDS=60" in text
    assert "500 * 1024 * 1024" in text


def test_array_requires_pushed_clean_commit():
    text = ARRAY.read_text(encoding="utf-8")
    assert '[[ "$commit" == "$origin" ]]' in text
    assert "git status --porcelain" in text


def test_aggregate_full_content_verification():
    text = AGGREGATE.read_text(encoding="utf-8")
    assert "--verify-package-content" in text
    assert "fresh-sequence-validation-summary.json" in text


def test_submit_requires_push_only_at_network_boundary():
    text = SUBMIT.read_text(encoding="utf-8")
    assert "push before network retrieval" in text
    assert "sbatch" in text
    assert 'afterok:${array_job}' in text


def test_no_selector_inputs():
    for path in (WORKER, AUDITOR, ARRAY, AGGREGATE, SUBMIT):
        text = path.read_text(encoding="utf-8").lower()
        assert "selector_distance" not in text
        assert "panel_identity" not in text
        assert "ops_fingerprint" not in text
        assert "sr_fingerprint" not in text
