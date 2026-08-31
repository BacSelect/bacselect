"""Synthetic tests for monthly metadata-eligibility production execution."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import stat
import sys

import pytest

from bacselect import source_eligibility
from bacselect.monthly_metadata_eligibility import (
    audit_metadata_eligibility_record,
)
from bacselect.monthly_release_start import (
    serialize_release_start_checkpoint,
    serialize_source_snapshot_record,
)


WRAPPER_PATH = (
    Path(
        __file__
    ).parents[
        1
    ]
    / "validation/selector-v1/run_monthly_metadata_eligibility.py"
)


def load_wrapper():
    name = (
        "_bacselect_monthly_metadata_eligibility_execution_test"
    )

    spec = (
        importlib.util.spec_from_file_location(
            name,
            WRAPPER_PATH,
        )
    )

    assert spec is not None
    assert spec.loader is not None

    module = (
        importlib.util.module_from_spec(
            spec
        )
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


wrapper = load_wrapper()

COMMIT = "a" * 40

START = (
    "2032-04-01T00:00:00Z"
)

QUERY_START = (
    "2032-04-01T00:00:01Z"
)

QUERY_END = (
    "2032-04-01T00:00:02Z"
)

RELEASE = "2032.04"


def valid_record(
    accession: str,
    biosample: str,
):
    return {
        "accession":
            accession,
        "current_accession":
            accession,
        "source_database":
            "SOURCE_DATABASE_GENBANK",
        "assembly_info": {
            "assembly_status":
                "current",
            "assembly_level":
                "Complete Genome",
            "biosample": {
                "accession":
                    biosample,
            },
        },
    }


def raw_bytes(
    records,
):
    return b"".join(
        (
            json.dumps(
                value,
                separators=(
                    ",",
                    ":",
                ),
            )
            + "\n"
        ).encode(
            "utf-8"
        )
        for value in records
    )


def default_raw():
    contaminated = valid_record(
        "GCA_000000002.1",
        "SAMN2",
    )

    contaminated[
        "assembly_info"
    ][
        "atypical"
    ] = {
        "is_atypical":
            True,
        "warnings": [
            "contaminated",
        ],
    }

    return raw_bytes(
        (
            contaminated,
            valid_record(
                "GCA_000000001.1",
                "SAMN1",
            ),
        )
    )


def build_stage1(
    tmp_path: Path,
    *,
    raw: bytes | None = None,
    commit: str = COMMIT,
):
    if raw is None:
        raw = default_raw()

    production = (
        tmp_path
        / "production-root"
    )

    stage1 = (
        production
        / RELEASE
        / "production"
        / commit
    )

    stage1.mkdir(
        parents=True
    )

    checkpoint = (
        serialize_release_start_checkpoint(
            snapshot_start_utc=START,
            expected_git_commit=commit,
            ncbi_datasets_version=(
                wrapper.EXPECTED_DATASETS_VERSION
            ),
            ncbi_datasets_environment_sha256=(
                wrapper.EXPECTED_DATASETS_ENVIRONMENT_SHA256
            ),
        )
    )

    snapshot = (
        serialize_source_snapshot_record(
            release_start_checkpoint=(
                checkpoint
            ),
            source_query_started_utc=(
                QUERY_START
            ),
            source_query_completed_utc=(
                QUERY_END
            ),
            source_query_command=(
                "datasets",
                *source_eligibility.DISCOVERY_ARGS,
            ),
            raw_response=raw,
        )
    )

    (
        stage1
        / wrapper.CHECKPOINT_NAME
    ).write_bytes(
        checkpoint
    )

    (
        stage1
        / wrapper.RAW_RESPONSE_NAME
    ).write_bytes(
        raw
    )

    (
        stage1
        / wrapper.SOURCE_SNAPSHOT_RECORD_NAME
    ).write_bytes(
        snapshot
    )

    return (
        production,
        stage1,
    )


def test_stage_names_are_exact():
    assert wrapper.METADATA_STAGE_NAME == (
        "metadata-eligibility"
    )

    assert wrapper.METADATA_PARTIAL_STAGE_NAME == (
        "metadata-eligibility.partial"
    )

    assert wrapper.ASSESSMENTS_NAME == (
        "metadata-eligibility-assessments.jsonl"
    )

    assert wrapper.SUMMARY_NAME == (
        "metadata-eligibility-summary.json"
    )

    assert wrapper.RECORD_NAME == (
        "metadata-eligibility-record.json"
    )

    assert wrapper.COMPLETION_NAME == (
        "metadata-eligibility-completion.json"
    )

    assert wrapper.COMPLETION_STATUS == (
        "METADATA_ELIGIBILITY_EXECUTION_COMPLETE"
    )


def test_valid_stage1_contract_is_audited(
    tmp_path,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    observed = (
        wrapper.load_stage1_contract(
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            expected_commit=(
                COMMIT
            ),
        )
    )

    assert observed.release_id == (
        RELEASE
    )

    assert observed.stage1_root == (
        stage1.resolve()
    )

    assert observed.raw_response == (
        default_raw()
    )


def test_stage1_raw_tamper_fails_closed(
    tmp_path,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    (
        stage1
        / wrapper.RAW_RESPONSE_NAME
    ).write_bytes(
        b'{"changed":true}\n'
    )

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="Stage 1 source-snapshot audit failed",
    ):
        wrapper.load_stage1_contract(
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            expected_commit=(
                COMMIT
            ),
        )


def test_wrong_execution_commit_is_refused(
    tmp_path,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="different commit",
    ):
        wrapper.load_stage1_contract(
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            expected_commit=(
                "b" * 40
            ),
        )


def test_stage1_root_must_match_release_commit_identity(
    tmp_path,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    wrong = (
        tmp_path
        / "copied-stage1"
    )

    wrong.mkdir()

    for name in (
        wrapper.CHECKPOINT_NAME,
        wrapper.RAW_RESPONSE_NAME,
        wrapper.SOURCE_SNAPSHOT_RECORD_NAME,
    ):
        (
            wrong
            / name
        ).write_bytes(
            (
                stage1
                / name
            ).read_bytes()
        )

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="does not match",
    ):
        wrapper.load_stage1_contract(
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                wrong.resolve()
            ),
            expected_commit=(
                COMMIT
            ),
        )


def test_success_atomically_publishes_exact_three_artifacts(
    tmp_path,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    result = (
        wrapper.execute_monthly_metadata_eligibility(
            repo=tmp_path,
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            execution_commit=(
                COMMIT
            ),
        )
    )

    assert result.stage_root == (
        stage1
        / wrapper.METADATA_STAGE_NAME
    )

    assert not (
        stage1
        / wrapper.METADATA_PARTIAL_STAGE_NAME
    ).exists()

    assert (
        stage1
        / wrapper.COMPLETION_NAME
    ).is_file()

    assert {
        path.name
        for path in result.stage_root.iterdir()
        if path.is_file()
    } == {
        wrapper.ASSESSMENTS_NAME,
        wrapper.SUMMARY_NAME,
        wrapper.RECORD_NAME,
    }

    assert result.assessment_count == 2
    assert result.retained_count == 1
    assert result.excluded_count == 1
    assert result.withheld_count == 0


def test_completed_stage_modes_are_frozen(
    tmp_path,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    result = (
        wrapper.execute_monthly_metadata_eligibility(
            repo=tmp_path,
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            execution_commit=(
                COMMIT
            ),
        )
    )

    assert stat.S_IMODE(
        result.stage_root.stat().st_mode
    ) == 0o755

    for path in result.stage_root.iterdir():
        assert path.is_file()

        assert stat.S_IMODE(
            path.stat().st_mode
        ) == 0o644


def test_completed_record_independently_audits(
    tmp_path,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    result = (
        wrapper.execute_monthly_metadata_eligibility(
            repo=tmp_path,
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            execution_commit=(
                COMMIT
            ),
        )
    )

    upstream = (
        wrapper.load_stage1_contract(
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            expected_commit=(
                COMMIT
            ),
        )
    )

    assessments = (
        result.stage_root
        / wrapper.ASSESSMENTS_NAME
    ).read_bytes()

    summary = (
        result.stage_root
        / wrapper.SUMMARY_NAME
    ).read_bytes()

    record = (
        result.stage_root
        / wrapper.RECORD_NAME
    ).read_bytes()

    audited = (
        audit_metadata_eligibility_record(
            record,
            source_snapshot_id=(
                upstream.source_snapshot_id
            ),
            source_snapshot_record_sha256=(
                upstream.snapshot_sha256
            ),
            raw_response=(
                upstream.raw_response
            ),
            assessments_payload=(
                assessments
            ),
            summary_payload=(
                summary
            ),
            source_eligibility_sha256=(
                wrapper.EXPECTED_SOURCE_ELIGIBILITY_SHA256
            ),
        )
    )

    assert audited[
        "retained_count"
    ] == 1

    completion = (
        stage1
        / wrapper.COMPLETION_NAME
    ).read_bytes()

    wrapper.audit_completion_receipt(
        completion,
        release_id=(
            upstream.release_id
        ),
        source_snapshot_id=(
            upstream.source_snapshot_id
        ),
        source_snapshot_record_sha256=(
            upstream.snapshot_sha256
        ),
        execution_commit=(
            COMMIT
        ),
        assessments_sha256=(
            result.assessments_sha256
        ),
        summary_sha256=(
            result.summary_sha256
        ),
        record_sha256=(
            result.record_sha256
        ),
    )


def test_existing_completed_stage_is_never_overwritten(
    tmp_path,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    final = (
        stage1
        / wrapper.METADATA_STAGE_NAME
    )

    final.mkdir()

    marker = (
        final
        / "do-not-touch"
    )

    marker.write_text(
        "existing\n",
        encoding="utf-8",
    )

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="already exists",
    ):
        wrapper.execute_monthly_metadata_eligibility(
            repo=tmp_path,
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            execution_commit=(
                COMMIT
            ),
        )

    assert marker.read_text(
        encoding="utf-8"
    ) == "existing\n"


def test_existing_partial_stage_blocks_execution(
    tmp_path,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    (
        stage1
        / wrapper.METADATA_PARTIAL_STAGE_NAME
    ).mkdir()

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="partial stage already exists",
    ):
        wrapper.execute_monthly_metadata_eligibility(
            repo=tmp_path,
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            execution_commit=(
                COMMIT
            ),
        )


def test_existing_completion_receipt_blocks_execution(
    tmp_path,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    receipt = (
        stage1
        / wrapper.COMPLETION_NAME
    )

    receipt.write_text(
        "existing\n",
        encoding="utf-8",
    )

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="completion receipt already exists",
    ):
        wrapper.execute_monthly_metadata_eligibility(
            repo=tmp_path,
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            execution_commit=(
                COMMIT
            ),
        )

    assert receipt.read_text(
        encoding="utf-8"
    ) == "existing\n"


def test_failed_metadata_assessment_is_never_promoted(
    tmp_path,
):
    repeated = valid_record(
        "GCA_000000001.1",
        "SAMN1",
    )

    raw = raw_bytes(
        (
            repeated,
            repeated,
        )
    )

    production, stage1 = (
        build_stage1(
            tmp_path,
            raw=raw,
        )
    )

    with pytest.raises(
        Exception,
        match="assessment failed",
    ):
        wrapper.execute_monthly_metadata_eligibility(
            repo=tmp_path,
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            execution_commit=(
                COMMIT
            ),
        )

    assert not (
        stage1
        / wrapper.METADATA_STAGE_NAME
    ).exists()

    assert (
        stage1
        / wrapper.METADATA_PARTIAL_STAGE_NAME
    ).is_dir()


def test_post_promotion_audit_failure_has_no_completion_receipt(
    tmp_path,
    monkeypatch,
):
    production, stage1 = (
        build_stage1(
            tmp_path
        )
    )

    original = (
        wrapper.audit_metadata_assessments
    )

    calls = 0

    def audit(
        payload,
    ):
        nonlocal calls

        calls += 1

        if calls == 2:
            raise (
                wrapper.MonthlyMetadataEligibilityExecutionError(
                    "synthetic post-promotion audit failure"
                )
            )

        return original(
            payload
        )

    monkeypatch.setattr(
        wrapper,
        "audit_metadata_assessments",
        audit,
    )

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="synthetic post-promotion audit failure",
    ):
        wrapper.execute_monthly_metadata_eligibility(
            repo=tmp_path,
            production_root=(
                production.resolve()
            ),
            stage1_root=(
                stage1.resolve()
            ),
            execution_commit=(
                COMMIT
            ),
        )

    assert (
        stage1
        / wrapper.METADATA_STAGE_NAME
    ).is_dir()

    assert not (
        stage1
        / wrapper.COMPLETION_NAME
    ).exists()


def fake_git_reader(
    repo,
    *args,
):
    del repo

    if args == (
        "rev-parse",
        "HEAD",
    ):
        return COMMIT

    if args == (
        "rev-parse",
        "origin/main",
    ):
        return COMMIT

    if args == (
        "status",
        "--porcelain",
    ):
        return ""

    raise AssertionError(
        args
    )


def identity_file_reader(
    path,
    *,
    wrapper_sha="1" * 64,
    wrapper_test_sha="2" * 64,
):
    path = Path(
        path
    )

    if path.resolve() == Path(
        wrapper.__file__
    ).resolve():
        return wrapper_sha

    if path.name == (
        "source_eligibility.py"
    ):
        return (
            wrapper.EXPECTED_SOURCE_ELIGIBILITY_SHA256
        )

    if path.name == (
        "monthly_metadata_eligibility.py"
    ):
        return (
            wrapper.EXPECTED_METADATA_CORE_SHA256
        )

    if path.name == (
        "test_monthly_metadata_eligibility.py"
    ):
        return (
            wrapper.EXPECTED_METADATA_CORE_TEST_SHA256
        )

    if path.name == (
        "prospective-monthly-metadata-eligibility.md"
    ):
        return (
            wrapper.EXPECTED_METADATA_METHOD_SHA256
        )

    if path.name == (
        "prospective-monthly-metadata-eligibility-execution.md"
    ):
        return (
            wrapper.EXPECTED_EXECUTION_METHOD_SHA256
        )

    if path.name == (
        "test_run_monthly_metadata_eligibility.py"
    ):
        return wrapper_test_sha

    raise AssertionError(
        path
    )


def test_repository_preflight_accepts_exact_local_identity(
    tmp_path,
):
    wrapper.repository_preflight(
        tmp_path,
        expected_commit=(
            COMMIT
        ),
        expected_wrapper_sha256=(
            "1" * 64
        ),
        expected_wrapper_test_sha256=(
            "2" * 64
        ),
        git_reader=(
            fake_git_reader
        ),
        file_sha256_reader=(
            identity_file_reader
        ),
    )


def test_repository_preflight_refuses_wrong_origin_main(
    tmp_path,
):
    def reader(
        repo,
        *args,
    ):
        if args == (
            "rev-parse",
            "origin/main",
        ):
            return "b" * 40

        return fake_git_reader(
            repo,
            *args,
        )

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="origin/main",
    ):
        wrapper.repository_preflight(
            tmp_path,
            expected_commit=(
                COMMIT
            ),
            expected_wrapper_sha256=(
                "1" * 64
            ),
            expected_wrapper_test_sha256=(
                "2" * 64
            ),
            git_reader=reader,
            file_sha256_reader=(
                identity_file_reader
            ),
        )


def test_repository_preflight_refuses_dirty_tree(
    tmp_path,
):
    def reader(
        repo,
        *args,
    ):
        if args == (
            "status",
            "--porcelain",
        ):
            return "?? unexpected"

        return fake_git_reader(
            repo,
            *args,
        )

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="not clean",
    ):
        wrapper.repository_preflight(
            tmp_path,
            expected_commit=(
                COMMIT
            ),
            expected_wrapper_sha256=(
                "1" * 64
            ),
            expected_wrapper_test_sha256=(
                "2" * 64
            ),
            git_reader=reader,
            file_sha256_reader=(
                identity_file_reader
            ),
        )


def test_repository_preflight_refuses_frozen_core_mismatch(
    tmp_path,
):
    def reader(
        path,
    ):
        path = Path(
            path
        )

        if path.name == (
            "monthly_metadata_eligibility.py"
        ):
            return "0" * 64

        return identity_file_reader(
            path
        )

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="contract SHA256 mismatch",
    ):
        wrapper.repository_preflight(
            tmp_path,
            expected_commit=(
                COMMIT
            ),
            expected_wrapper_sha256=(
                "1" * 64
            ),
            expected_wrapper_test_sha256=(
                "2" * 64
            ),
            git_reader=(
                fake_git_reader
            ),
            file_sha256_reader=(
                reader
            ),
        )


def test_repository_preflight_refuses_execution_method_mismatch(
    tmp_path,
):
    def reader(
        path,
    ):
        path = Path(
            path
        )

        if path.name == (
            "prospective-monthly-metadata-eligibility-execution.md"
        ):
            return "0" * 64

        return identity_file_reader(
            path
        )

    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="execution method SHA256 mismatch",
    ):
        wrapper.repository_preflight(
            tmp_path,
            expected_commit=(
                COMMIT
            ),
            expected_wrapper_sha256=(
                "1" * 64
            ),
            expected_wrapper_test_sha256=(
                "2" * 64
            ),
            git_reader=(
                fake_git_reader
            ),
            file_sha256_reader=(
                reader
            ),
        )


def test_cli_requires_explicit_authorization():
    with pytest.raises(
        wrapper.MonthlyMetadataEligibilityExecutionError,
        match="explicit authorization",
    ):
        wrapper.main(
            (
                "--expected-commit",
                COMMIT,
                "--expected-wrapper-sha256",
                "1" * 64,
                "--expected-wrapper-test-sha256",
                "2" * 64,
                "--production-root",
                "/synthetic/production",
                "--stage1-root",
                "/synthetic/stage1",
            )
        )


def test_executor_has_no_network_or_external_scientific_execution():
    text = Path(
        wrapper.__file__
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "requests",
        "urllib.request",
        "urlopen",
        "http.client",
        "socket.",
        "curl ",
        "wget ",
        "datasets_executable",
        "command_runner",
        "query_runner",
    ):
        assert token not in text

    assert text.count(
        "subprocess.run("
    ) == 1

    assert '"git",' in text


def test_executor_has_no_historical_or_institutional_binding():
    text = Path(
        wrapper.__file__
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "/NGS/",
        "Rhys_wkdir",
        "Project Finch",
        "SLURM_",
        "sbatch",
        "srun",
        "70_477",
        "55_151",
        "15_326",
    ):
        assert token not in text
