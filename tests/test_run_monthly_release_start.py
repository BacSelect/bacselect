"""Synthetic tests for the BacSelect monthly source-snapshot execution wrapper."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import stat
import sys

import pytest

from bacselect.monthly_release_start import (
    audit_release_start_checkpoint,
    audit_source_snapshot_record,
    sha256_bytes,
)


WRAPPER_PATH = (
    Path(__file__).parents[1]
    / "validation/selector-v1/run_monthly_release_start.py"
)


def load_wrapper():
    name = "_bacselect_monthly_release_start_wrapper_test"

    spec = importlib.util.spec_from_file_location(
        name,
        WRAPPER_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
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

START = "2032-04-01T00:00:00Z"
QUERY_START = "2032-04-01T00:00:01Z"
QUERY_END = "2032-04-01T00:00:02Z"

LAUNCHER = (
    "/synthetic/environment/bin/datasets",
)

RAW = (
    b'{"accession":"GCA_800000001.1"}\n'
)

STDERR = b"synthetic diagnostic\n"


def timestamp_provider():
    values = iter(
        (
            QUERY_START,
            QUERY_END,
        )
    )

    return lambda: next(
        values
    )


def test_scientific_command_is_exact_frozen_vector() -> None:
    assert wrapper.scientific_query_command() == (
        "datasets",
        "summary",
        "genome",
        "taxon",
        "2",
        "--assembly-source",
        "GenBank",
        "--assembly-level",
        "complete",
        "--assembly-version",
        "current",
        "--mag",
        "exclude",
        "--exclude-multi-isolate",
        "--limit",
        "all",
        "--as-json-lines",
    )


def test_scientific_command_does_not_exclude_all_atypical() -> None:
    assert "--exclude-atypical" not in (
        wrapper.scientific_query_command()
    )


def test_output_root_uses_release_and_commit() -> None:
    observed = wrapper.output_root_for_release(
        Path(
            "/synthetic/monthly"
        ),
        "2032.04",
        COMMIT,
    )

    assert observed.parts[
        -3:
    ] == (
        "2032.04",
        "production",
        COMMIT,
    )


def test_launcher_must_end_in_datasets() -> None:
    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="must end with datasets",
    ):
        wrapper.validate_launcher_prefix(
            (
                "conda",
                "run",
            )
        )


def test_string_launcher_is_refused() -> None:
    with pytest.raises(
        TypeError,
        match="argument sequence",
    ):
        wrapper.validate_launcher_prefix(
            "datasets"
        )


def test_day_two_start_is_refused_before_output_creation(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    called = False

    def runner(
        command,
        *,
        cwd,
    ):
        nonlocal called
        called = True

        return wrapper.QueryResult(
            stdout=RAW,
            stderr=b"",
            returncode=0,
        )

    with pytest.raises(
        Exception,
        match="UTC day 01",
    ):
        wrapper.execute_monthly_source_snapshot(
            repo=tmp_path,
            output_root=output,
            execution_commit=COMMIT,
            snapshot_start_utc=(
                "2032-04-02T00:00:00Z"
            ),
            launcher_prefix=LAUNCHER,
            query_runner=runner,
            timestamp_provider=timestamp_provider(),
        )

    assert called is False
    assert not output.exists()


def test_checkpoint_is_durable_and_audited_before_query(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    observations = []

    def runner(
        command,
        *,
        cwd,
    ):
        checkpoint_path = (
            output
            / wrapper.CHECKPOINT_NAME
        )

        observations.append(
            checkpoint_path.is_file()
        )

        payload = checkpoint_path.read_bytes()

        observations.append(
            audit_release_start_checkpoint(
                payload,
                expected_git_commit=COMMIT,
            )[
                "release_id"
            ]
        )

        observations.append(
            stat.S_IMODE(
                checkpoint_path.stat().st_mode
            )
        )

        return wrapper.QueryResult(
            stdout=RAW,
            stderr=STDERR,
            returncode=0,
        )

    wrapper.execute_monthly_source_snapshot(
        repo=tmp_path,
        output_root=output,
        execution_commit=COMMIT,
        snapshot_start_utc=START,
        launcher_prefix=LAUNCHER,
        query_runner=runner,
        timestamp_provider=timestamp_provider(),
    )

    assert observations == [
        True,
        "2032.04",
        0o644,
    ]


def test_query_runner_receives_exact_launcher_plus_discovery_args(
    tmp_path: Path,
) -> None:
    observed = []

    def runner(
        command,
        *,
        cwd,
    ):
        observed.append(
            tuple(
                command
            )
        )

        return wrapper.QueryResult(
            stdout=RAW,
            stderr=b"",
            returncode=0,
        )

    wrapper.execute_monthly_source_snapshot(
        repo=tmp_path,
        output_root=tmp_path / "run",
        execution_commit=COMMIT,
        snapshot_start_utc=START,
        launcher_prefix=LAUNCHER,
        query_runner=runner,
        timestamp_provider=timestamp_provider(),
    )

    assert observed == [
        (
            *LAUNCHER,
            *wrapper.source_eligibility.DISCOVERY_ARGS,
        )
    ]


def test_success_preserves_stdout_and_stderr_exactly(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=RAW,
            stderr=STDERR,
            returncode=0,
        )

    wrapper.execute_monthly_source_snapshot(
        repo=tmp_path,
        output_root=output,
        execution_commit=COMMIT,
        snapshot_start_utc=START,
        launcher_prefix=LAUNCHER,
        query_runner=runner,
        timestamp_provider=timestamp_provider(),
    )

    assert (
        output
        / wrapper.RAW_RESPONSE_NAME
    ).read_bytes() == RAW

    assert (
        output
        / wrapper.QUERY_STDERR_NAME
    ).read_bytes() == STDERR


def test_success_writes_exact_five_artifacts(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=RAW,
            stderr=STDERR,
            returncode=0,
        )

    wrapper.execute_monthly_source_snapshot(
        repo=tmp_path,
        output_root=output,
        execution_commit=COMMIT,
        snapshot_start_utc=START,
        launcher_prefix=LAUNCHER,
        query_runner=runner,
        timestamp_provider=timestamp_provider(),
    )

    assert {
        path.name
        for path in output.iterdir()
        if path.is_file()
    } == {
        wrapper.CHECKPOINT_NAME,
        wrapper.RAW_RESPONSE_NAME,
        wrapper.QUERY_STDERR_NAME,
        wrapper.QUERY_EXECUTION_NAME,
        wrapper.SOURCE_SNAPSHOT_RECORD_NAME,
    }


def test_success_artifact_modes_are_0644(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=RAW,
            stderr=b"",
            returncode=0,
        )

    wrapper.execute_monthly_source_snapshot(
        repo=tmp_path,
        output_root=output,
        execution_commit=COMMIT,
        snapshot_start_utc=START,
        launcher_prefix=LAUNCHER,
        query_runner=runner,
        timestamp_provider=timestamp_provider(),
    )

    for path in output.iterdir():
        if path.is_file():
            assert stat.S_IMODE(
                path.stat().st_mode
            ) == 0o644


def test_source_snapshot_record_audits_against_raw_stdout(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=RAW,
            stderr=b"",
            returncode=0,
        )

    wrapper.execute_monthly_source_snapshot(
        repo=tmp_path,
        output_root=output,
        execution_commit=COMMIT,
        snapshot_start_utc=START,
        launcher_prefix=LAUNCHER,
        query_runner=runner,
        timestamp_provider=timestamp_provider(),
    )

    checkpoint = (
        output
        / wrapper.CHECKPOINT_NAME
    ).read_bytes()

    snapshot = (
        output
        / wrapper.SOURCE_SNAPSHOT_RECORD_NAME
    ).read_bytes()

    record = audit_source_snapshot_record(
        snapshot,
        release_start_checkpoint=checkpoint,
        raw_response=RAW,
    )

    assert record[
        "release_id"
    ] == "2032.04"


def test_query_execution_record_binds_both_streams_and_exit_status(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=RAW,
            stderr=STDERR,
            returncode=0,
        )

    wrapper.execute_monthly_source_snapshot(
        repo=tmp_path,
        output_root=output,
        execution_commit=COMMIT,
        snapshot_start_utc=START,
        launcher_prefix=LAUNCHER,
        query_runner=runner,
        timestamp_provider=timestamp_provider(),
    )

    record = json.loads(
        (
            output
            / wrapper.QUERY_EXECUTION_NAME
        ).read_text(
            encoding="utf-8"
        )
    )

    assert record[
        "exit_status"
    ] == 0

    assert record[
        "raw_stdout_sha256"
    ] == sha256_bytes(
        RAW
    )

    assert record[
        "raw_stderr_sha256"
    ] == sha256_bytes(
        STDERR
    )

    assert record[
        "status"
    ] == wrapper.QUERY_STATUS_SUCCESS


def test_nonzero_query_retains_evidence_and_blocks_snapshot_record(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=b"partial\n",
            stderr=b"network failure\n",
            returncode=7,
        )

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="source query failed",
    ):
        wrapper.execute_monthly_source_snapshot(
            repo=tmp_path,
            output_root=output,
            execution_commit=COMMIT,
            snapshot_start_utc=START,
            launcher_prefix=LAUNCHER,
            query_runner=runner,
            timestamp_provider=timestamp_provider(),
        )

    assert (
        output
        / wrapper.CHECKPOINT_NAME
    ).is_file()

    assert (
        output
        / wrapper.RAW_RESPONSE_NAME
    ).read_bytes() == b"partial\n"

    assert (
        output
        / wrapper.QUERY_STDERR_NAME
    ).read_bytes() == b"network failure\n"

    assert (
        output
        / wrapper.QUERY_EXECUTION_NAME
    ).is_file()

    assert not (
        output
        / wrapper.SOURCE_SNAPSHOT_RECORD_NAME
    ).exists()


def test_nonzero_query_execution_record_is_failed(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=b"partial\n",
            stderr=b"failure\n",
            returncode=9,
        )

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
    ):
        wrapper.execute_monthly_source_snapshot(
            repo=tmp_path,
            output_root=output,
            execution_commit=COMMIT,
            snapshot_start_utc=START,
            launcher_prefix=LAUNCHER,
            query_runner=runner,
            timestamp_provider=timestamp_provider(),
        )

    record = json.loads(
        (
            output
            / wrapper.QUERY_EXECUTION_NAME
        ).read_text(
            encoding="utf-8"
        )
    )

    assert record[
        "exit_status"
    ] == 9

    assert record[
        "status"
    ] == wrapper.QUERY_STATUS_FAILED


def test_zero_exit_empty_stdout_is_fail_closed(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=b"",
            stderr=b"",
            returncode=0,
        )

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="empty stdout",
    ):
        wrapper.execute_monthly_source_snapshot(
            repo=tmp_path,
            output_root=output,
            execution_commit=COMMIT,
            snapshot_start_utc=START,
            launcher_prefix=LAUNCHER,
            query_runner=runner,
            timestamp_provider=timestamp_provider(),
        )

    record = json.loads(
        (
            output
            / wrapper.QUERY_EXECUTION_NAME
        ).read_text(
            encoding="utf-8"
        )
    )

    assert record[
        "status"
    ] == wrapper.QUERY_STATUS_EMPTY

    assert not (
        output
        / wrapper.SOURCE_SNAPSHOT_RECORD_NAME
    ).exists()


def test_existing_output_root_blocks_query(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "run"
    )

    output.mkdir()

    called = False

    def runner(
        command,
        *,
        cwd,
    ):
        nonlocal called
        called = True

        return wrapper.QueryResult(
            stdout=RAW,
            stderr=b"",
            returncode=0,
        )

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="already exists",
    ):
        wrapper.execute_monthly_source_snapshot(
            repo=tmp_path,
            output_root=output,
            execution_commit=COMMIT,
            snapshot_start_utc=START,
            launcher_prefix=LAUNCHER,
            query_runner=runner,
            timestamp_provider=timestamp_provider(),
        )

    assert called is False


def test_query_start_before_snapshot_is_refused_before_runner(
    tmp_path: Path,
) -> None:
    called = False

    def runner(
        command,
        *,
        cwd,
    ):
        nonlocal called
        called = True

        return wrapper.QueryResult(
            stdout=RAW,
            stderr=b"",
            returncode=0,
        )

    times = iter(
        (
            "2032-03-31T23:59:59Z",
            QUERY_END,
        )
    )

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="before snapshot start",
    ):
        wrapper.execute_monthly_source_snapshot(
            repo=tmp_path,
            output_root=tmp_path / "run",
            execution_commit=COMMIT,
            snapshot_start_utc=START,
            launcher_prefix=LAUNCHER,
            query_runner=runner,
            timestamp_provider=lambda: next(
                times
            ),
        )

    assert called is False


def test_query_completion_before_query_start_fails_closed(
    tmp_path: Path,
) -> None:
    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=RAW,
            stderr=b"",
            returncode=0,
        )

    times = iter(
        (
            QUERY_END,
            QUERY_START,
        )
    )

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="completion precedes",
    ):
        wrapper.execute_monthly_source_snapshot(
            repo=tmp_path,
            output_root=tmp_path / "run",
            execution_commit=COMMIT,
            snapshot_start_utc=START,
            launcher_prefix=LAUNCHER,
            query_runner=runner,
            timestamp_provider=lambda: next(
                times
            ),
        )


def test_repository_preflight_accepts_exact_synthetic_bindings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        wrapper,
        "__file__",
        str(
            tmp_path
            / "validation/selector-v1/run_monthly_release_start.py"
        ),
    )

    expected_wrapper = "c" * 64
    expected_test = "d" * 64

    def git_reader(
        repo,
        *args,
    ):
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

    def sha_reader(
        path,
    ):
        text = str(
            path
        )

        if text.endswith(
            str(
                wrapper.METHOD_RELATIVE
            )
        ):
            return wrapper.EXPECTED_METHOD_SHA256

        if text.endswith(
            str(
                wrapper.CORE_RELATIVE
            )
        ):
            return wrapper.EXPECTED_CORE_SHA256

        if text.endswith(
            str(
                wrapper.CORE_TEST_RELATIVE
            )
        ):
            return wrapper.EXPECTED_CORE_TEST_SHA256

        if text.endswith(
            str(
                wrapper.WRAPPER_TEST_RELATIVE
            )
        ):
            return expected_test

        if text.endswith(
            str(
                Path(
                    "validation/selector-v1/"
                    "run_monthly_release_start.py"
                )
            )
        ):
            return expected_wrapper

        if text.endswith(
            str(
                wrapper.ENVIRONMENT_RELATIVE
            )
        ):
            return wrapper.EXPECTED_DATASETS_ENVIRONMENT_SHA256

        raise AssertionError(
            path
        )

    wrapper.repository_preflight(
        tmp_path,
        expected_commit=COMMIT,
        expected_wrapper_sha256=expected_wrapper,
        expected_wrapper_test_sha256=expected_test,
        git_reader=git_reader,
        file_sha256_reader=sha_reader,
    )


def test_repository_preflight_refuses_wrong_head(
    tmp_path: Path,
) -> None:
    def git_reader(
        repo,
        *args,
    ):
        if args == (
            "rev-parse",
            "HEAD",
        ):
            return "b" * 40

        return COMMIT

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="HEAD mismatch",
    ):
        wrapper.repository_preflight(
            tmp_path,
            expected_commit=COMMIT,
            expected_wrapper_sha256="c" * 64,
            expected_wrapper_test_sha256="d" * 64,
            git_reader=git_reader,
            file_sha256_reader=lambda path: "0" * 64,
        )


def test_repository_preflight_refuses_wrong_origin_main(
    tmp_path: Path,
) -> None:
    def git_reader(
        repo,
        *args,
    ):
        if args == (
            "rev-parse",
            "HEAD",
        ):
            return COMMIT

        if args == (
            "rev-parse",
            "origin/main",
        ):
            return "b" * 40

        return ""

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="origin/main mismatch",
    ):
        wrapper.repository_preflight(
            tmp_path,
            expected_commit=COMMIT,
            expected_wrapper_sha256="c" * 64,
            expected_wrapper_test_sha256="d" * 64,
            git_reader=git_reader,
            file_sha256_reader=lambda path: "0" * 64,
        )


def test_repository_preflight_refuses_dirty_tree(
    tmp_path: Path,
) -> None:
    def git_reader(
        repo,
        *args,
    ):
        if args in {
            (
                "rev-parse",
                "HEAD",
            ),
            (
                "rev-parse",
                "origin/main",
            ),
        }:
            return COMMIT

        if args == (
            "status",
            "--porcelain",
        ):
            return " M file"

        raise AssertionError(
            args
        )

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="not clean",
    ):
        wrapper.repository_preflight(
            tmp_path,
            expected_commit=COMMIT,
            expected_wrapper_sha256="c" * 64,
            expected_wrapper_test_sha256="d" * 64,
            git_reader=git_reader,
            file_sha256_reader=lambda path: "0" * 64,
        )


def test_environment_preflight_validates_pinned_version(
    tmp_path: Path,
    monkeypatch,
) -> None:
    environment = (
        tmp_path
        / wrapper.ENVIRONMENT_RELATIVE
    )

    environment.parent.mkdir(
        parents=True
    )

    environment.write_bytes(
        b"synthetic-lock\n"
    )

    synthetic_sha = wrapper.sha256_file(
        environment
    )

    monkeypatch.setattr(
        wrapper,
        "EXPECTED_DATASETS_ENVIRONMENT_SHA256",
        synthetic_sha,
    )

    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=b"datasets version: 18.35.0\n",
            stderr=b"",
            returncode=0,
        )

    prefix = wrapper.environment_preflight(
        tmp_path,
        command_runner=runner,
        datasets_executable="/synthetic/environment/bin/datasets",
    )

    assert prefix == (
        "/synthetic/environment/bin/datasets",
    )


def test_environment_preflight_refuses_version_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    environment = (
        tmp_path
        / wrapper.ENVIRONMENT_RELATIVE
    )

    environment.parent.mkdir(
        parents=True
    )

    environment.write_bytes(
        b"synthetic-lock\n"
    )

    monkeypatch.setattr(
        wrapper,
        "EXPECTED_DATASETS_ENVIRONMENT_SHA256",
        wrapper.sha256_file(
            environment
        ),
    )

    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.QueryResult(
            stdout=b"datasets version: 99.99.0\n",
            stderr=b"",
            returncode=0,
        )

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="version mismatch",
    ):
        wrapper.environment_preflight(
            tmp_path,
            command_runner=runner,
            datasets_executable="/synthetic/environment/bin/datasets",
        )


def test_main_requires_explicit_real_execution_authorization() -> None:
    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="explicit authorization",
    ):
        wrapper.main(
            (
                "--expected-commit",
                COMMIT,
                "--expected-wrapper-sha256",
                "c" * 64,
                "--expected-wrapper-test-sha256",
                "d" * 64,
                "--production-root",
                "/synthetic/monthly",
                "--datasets-executable",
                "/synthetic/environment/bin/datasets",
            )
        )


def test_cli_exposes_no_release_id_argument() -> None:
    source = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    assert 'parser.add_argument(\n        "--release-id"' not in source
    assert 'parser.add_argument(\n        "--snapshot-start' not in source


def test_wrapper_test_uses_only_synthetic_accessions() -> None:
    source = Path(
        __file__
    ).read_text(
        encoding="utf-8"
    )

    assert "GCA_800000001.1" in source


def test_output_root_requires_absolute_production_root() -> None:
    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="production root must be an absolute path",
    ):
        wrapper.output_root_for_release(
            Path(
                "relative/monthly"
            ),
            "2032.04",
            COMMIT,
        )


def test_environment_preflight_requires_absolute_datasets_executable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    environment = (
        tmp_path
        / wrapper.ENVIRONMENT_RELATIVE
    )

    environment.parent.mkdir(
        parents=True
    )

    environment.write_bytes(
        b"synthetic-lock\n"
    )

    monkeypatch.setattr(
        wrapper,
        "EXPECTED_DATASETS_ENVIRONMENT_SHA256",
        wrapper.sha256_file(
            environment
        ),
    )

    with pytest.raises(
        wrapper.MonthlyReleaseExecutionError,
        match="datasets executable path must be absolute",
    ):
        wrapper.environment_preflight(
            tmp_path,
            datasets_executable="relative/bin/datasets",
        )


def test_monthly_wrapper_has_no_institutional_execution_bindings() -> None:
    source = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "/NGS/",
        "Rhys_wkdir",
        "finch-ncbi-datasets",
        "SLURM_",
        "sbatch",
        "srun",
        "self-hosted",
        "site.env",
    )

    for token in forbidden:
        assert token not in source
