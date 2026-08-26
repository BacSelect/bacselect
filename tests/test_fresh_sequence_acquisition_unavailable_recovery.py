from pathlib import Path
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RECOVER = ROOT / "validation/selector-v1/recover_acquisition_unavailable.py"
AGGREGATE = ROOT / "validation/selector-v1/audit_fresh_sequence_validation_recovery.py"
RUNNER = ROOT / "validation/selector-v1/run_acquisition_unavailable_recovery.slurm"
AGGREGATE_RUNNER = ROOT / "validation/selector-v1/aggregate_fresh_sequence_validation_recovery.slurm"
SUBMIT = ROOT / "validation/selector-v1/submit_fresh_sequence_validation_recovery.sh"
METHOD = ROOT / "validation/selector-v1/fresh-sequence-acquisition-unavailable-recovery.md"
METHOD_JSON = ROOT / "validation/selector-v1/fresh-sequence-acquisition-unavailable-recovery.json"


def load_recovery():
    spec = importlib.util.spec_from_file_location("bacselect_recovery_test", RECOVER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_terminal_unavailable_rule_accepts_only_zero_size_sequence_report():
    module = load_recovery()

    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp)
        acc = "GCA_123456789.1"
        acc_dir = package / "ncbi_dataset" / "data" / acc
        acc_dir.mkdir(parents=True)
        (acc_dir / "sequence_report.jsonl").write_bytes(b"")

        entries = [{
            "relative_path": f"data/{acc}/sequence_report.jsonl",
            "expected_size": 0,
        }]
        problems = [(f"data/{acc}/sequence_report.jsonl", "empty")]

        assert (
            module.terminal_unavailable_reason(
                package,
                acc,
                entries,
                problems,
            )
            == "datasets_catalog_without_sequence_payload"
        )


def test_terminal_unavailable_rule_rejects_positive_expected_size():
    module = load_recovery()

    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp)
        acc = "GCA_123456789.1"
        acc_dir = package / "ncbi_dataset" / "data" / acc
        acc_dir.mkdir(parents=True)
        (acc_dir / "sequence_report.jsonl").write_bytes(b"")

        entries = [{
            "relative_path": f"data/{acc}/sequence_report.jsonl",
            "expected_size": 10,
        }]
        problems = [(f"data/{acc}/sequence_report.jsonl", "empty")]

        try:
            module.terminal_unavailable_reason(
                package,
                acc,
                entries,
                problems,
            )
        except SystemExit:
            pass
        else:
            raise AssertionError("positive expected size was accepted")


def test_terminal_unavailable_rule_rejects_present_fasta():
    module = load_recovery()

    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp)
        acc = "GCA_123456789.1"
        acc_dir = package / "ncbi_dataset" / "data" / acc
        acc_dir.mkdir(parents=True)
        (acc_dir / "sequence_report.jsonl").write_bytes(b"")
        (acc_dir / "x_genomic.fna").write_text(">x\nACGT\n", encoding="ascii")

        entries = [{
            "relative_path": f"data/{acc}/sequence_report.jsonl",
            "expected_size": 0,
        }]
        problems = [(f"data/{acc}/sequence_report.jsonl", "empty")]

        try:
            module.terminal_unavailable_reason(
                package,
                acc,
                entries,
                problems,
            )
        except SystemExit:
            pass
        else:
            raise AssertionError("present FASTA was accepted")


def test_recovery_contract_is_additive_and_frozen():
    module = load_recovery()

    assert module.SOURCE_PRODUCTION_COMMIT == "7aba4b0a2aa22c05ce808bf9b5811606bd3d2293"
    assert module.EXPECTED_TARGETS == 15326
    assert module.RECOVERY_BATCHES == (24, 28)
    assert module.UNAVAILABLE_REASON == "datasets_catalog_without_sequence_payload"



def test_target_rows_reuse_frozen_worker_normalization(monkeypatch):
    module = load_recovery()

    accession = "GCA_123456789.1"
    normalized = {
        "canonical_genbank_assembly_accession": accession,
        "fresh_biosample": "SAMN12345678",
        "source_biosample": "SAMN12345678",
        "acquisition_reason": "not_in_historical_cache",
    }

    class FakeWorker:
        @staticmethod
        def load_targets(repo):
            assert repo == module.REPO
            return [dict(normalized)]

    monkeypatch.setattr(module, "load_worker", lambda: FakeWorker())

    rows = module.target_rows_for((accession,))

    assert rows == [normalized]
    assert rows[0]["source_biosample"] == rows[0]["fresh_biosample"]

def test_recovery_uses_copy_and_pre_final_audit_before_atomic_rename():
    text = RECOVER.read_text(encoding="utf-8")

    assert "shutil.copytree(" in text
    assert "source_package" in text
    assert "copy_function=shutil.copy2" in text

    audit_call = text.index(
        "validate_recovery_artifacts(\n"
        "        partial_dir,"
    )
    rename_call = text.index(
        "partial_dir.replace(final_dir)"
    )

    assert audit_call < rename_call


def test_recovery_scheduler_is_bounded_and_pinned():
    text = RUNNER.read_text(encoding="utf-8")

    assert "#SBATCH --array=24,28%2" in text
    assert "#SBATCH --nodelist=kscprod-bio8" in text
    assert "git status --porcelain" in text
    assert "20 * 1024 * 1024" in text


def test_recovery_aggregate_requires_full_content_verification():
    text = AGGREGATE.read_text(encoding="utf-8")

    assert "verify_package_content=True" in text
    assert "requested target accounting mismatch" in text
    assert "candidate record count does not equal acquisition-available count" in text


def test_submit_preserves_source_failed_partials():
    text = SUBMIT.read_text(encoding="utf-8")

    assert "batch-$batch.partial" in text
    assert "expected exactly 29 source finalized batches" in text
    assert "afterok:${recover_job}" in text
    assert "source_evidence_mutated" in text
    assert "recovery_uses_package_copy" in text


def test_method_checkpoint_is_blinding_safe():
    text = METHOD.read_text(encoding="utf-8")
    payload = json.loads(METHOD_JSON.read_text(encoding="utf-8"))

    for token in ("GCA_", "GCF_", "SAMN", "SAMEA", "SAMD"):
        assert token not in text

    assert payload["frozen_requested_targets"] == 15326
    assert payload["classification_is_sequence_ineligibility"] is False
    assert payload["source_execution_is_modified"] is False
    assert payload["recovery_validates_package_copy"] is True
    assert payload["pre_final_content_audit"] is True
    assert payload["target_rows_use_frozen_worker_loader"] is True
    assert payload["selector_outcome_generated"] is False
    assert payload["target_set_changed"] is False


def test_no_selector_inputs_or_outcomes():
    for path in (RECOVER, AGGREGATE, RUNNER, AGGREGATE_RUNNER, SUBMIT):
        text = path.read_text(encoding="utf-8").lower()
        assert "selector_distance" not in text
        assert "panel_identity" not in text
        assert "ops_fingerprint" not in text
        assert "sr_fingerprint" not in text
