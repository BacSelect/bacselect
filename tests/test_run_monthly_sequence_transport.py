from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import zipfile

import pytest

from bacselect import source_eligibility
from bacselect.monthly_release_start import (
    canonical_json_bytes,
    serialize_release_start_checkpoint,
    serialize_source_snapshot_record,
    source_snapshot_id_from_start,
)
from bacselect.monthly_sequence_plan import (
    FRESH_BATCH_SIZE,
    FRESH_TARGET_FIELDS,
    NO_VERIFIED_CACHE,
    accession_manifest_bytes,
)
from bacselect.monthly_sequence_validation import (
    CANDIDATE_AUDIT_FIELDS,
    COMPONENT_AUDIT_FIELDS,
    PACKAGE_FILE_FIELDS,
    MonthlyValidatedPackage,
)


WRAPPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "run_monthly_sequence_transport.py"
)


def load_wrapper():
    spec = (
        importlib.util.spec_from_file_location(
            "run_monthly_sequence_transport",
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
        spec.name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


wrapper = load_wrapper()


COMMIT = "a" * 40

ENV_SHA = (
    "6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd"
)

START = "2026-09-01T00:00:00Z"
QUERY_START = "2026-09-01T00:00:01Z"
QUERY_END = "2026-09-01T00:01:00Z"

DATASETS = Path(
    "/opt/bacselect/bin/datasets"
)


def accession(
    number: int,
) -> str:
    return (
        f"GCA_{number:09d}.1"
    )


def biosample(
    number: int,
) -> str:
    return (
        f"SAMN{number:08d}"
    )


def manifest_bytes(
    count: int,
) -> bytes:
    rows = [
        "\t".join(
            FRESH_TARGET_FIELDS
        )
        + "\n"
    ]

    for number in range(
        1,
        count + 1,
    ):
        rows.append(
            f"{accession(number)}\t"
            f"{biosample(number)}\t"
            f"{NO_VERIFIED_CACHE}\n"
        )

    return "".join(
        rows
    ).encode(
        "ascii"
    )


def make_upstream(
    tmp_path: Path,
    *,
    count: int = 1,
):
    production_root = (
        tmp_path
        / "production-root"
    )

    stage1_root = (
        production_root
        / "2026.09"
        / "production"
        / COMMIT
    )

    stage1_root.mkdir(
        parents=True
    )

    checkpoint = (
        serialize_release_start_checkpoint(
            snapshot_start_utc=START,
            expected_git_commit=COMMIT,
            ncbi_datasets_version="18.35.0",
            ncbi_datasets_environment_sha256=(
                ENV_SHA
            ),
        )
    )

    raw = (
        b'{"accession":"GCA_000000001.1"}\n'
    )

    command = (
        "datasets",
        *source_eligibility.DISCOVERY_ARGS,
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
            source_query_command=command,
            raw_response=raw,
        )
    )

    (
        stage1_root
        / "release-start-checkpoint.json"
    ).write_bytes(
        checkpoint
    )

    (
        stage1_root
        / "assembly_data_report.raw.jsonl"
    ).write_bytes(
        raw
    )

    snapshot_path = (
        stage1_root
        / "source-snapshot-record.json"
    )

    snapshot_path.write_bytes(
        snapshot
    )

    plan_root = (
        stage1_root
        / "sequence-plan"
    )

    plan_root.mkdir()

    fresh = manifest_bytes(
        count
    )

    manifest_path = (
        plan_root
        / "fresh-targets.tsv"
    )

    manifest_path.write_bytes(
        fresh
    )

    accessions = tuple(
        accession(
            number
        )
        for number in range(
            1,
            count + 1,
        )
    )

    fresh_accessions_sha = (
        hashlib.sha256(
            accession_manifest_bytes(
                accessions
            )
        ).hexdigest()
    )

    snapshot_sha = (
        hashlib.sha256(
            snapshot
        ).hexdigest()
    )

    batch_count = (
        count
        + FRESH_BATCH_SIZE
        - 1
    ) // FRESH_BATCH_SIZE

    record = {
        "schema_version":
            "bacselect-monthly-sequence-plan-v1",
        "source_snapshot_id":
            source_snapshot_id_from_start(
                START
            ),
        "source_snapshot_record_sha256":
            snapshot_sha,
        "retained_count":
            count,
        "cache_reuse_count":
            0,
        "fresh_acquisition_count":
            count,
        "retained_accessions_sha256":
            "1" * 64,
        "cache_reuse_accessions_sha256":
            "2" * 64,
        "fresh_acquisition_accessions_sha256":
            fresh_accessions_sha,
        "fresh_target_manifest_sha256":
            hashlib.sha256(
                fresh
            ).hexdigest(),
        "fresh_batch_size":
            FRESH_BATCH_SIZE,
        "fresh_batch_count":
            batch_count,
        "fresh_acquisition_reason_counts":
            {
                NO_VERIFIED_CACHE:
                    count,
            },
    }

    plan_path = (
        plan_root
        / "monthly-sequence-plan-record.json"
    )

    plan_payload = (
        json.dumps(
            record,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )

    plan_path.write_bytes(
        plan_payload
    )

    return {
        "production_root":
            production_root.resolve(),
        "stage1_root":
            stage1_root.resolve(),
        "plan_path":
            plan_path.resolve(),
        "manifest_path":
            manifest_path.resolve(),
    }


def test_repository_preflight_accepts_exact_synthetic_state():
    values = {
        (
            "rev-parse",
            "HEAD",
        ):
            COMMIT,
        (
            "rev-parse",
            "origin/main",
        ):
            COMMIT,
        (
            "status",
            "--porcelain",
        ):
            "",
    }

    def git_reader(
        repo,
        *arguments,
    ):
        return values[
            arguments
        ]

    wrapper_sha = "3" * 64
    test_sha = "4" * 64

    def hash_reader(
        path,
    ):
        if path.name == (
            "run_monthly_sequence_transport.py"
        ):
            return wrapper_sha

        if path.name == (
            "test_run_monthly_sequence_transport.py"
        ):
            return test_sha

        return ENV_SHA

    wrapper.repository_preflight(
        Path(
            "/repo"
        ),
        expected_commit=COMMIT,
        expected_wrapper_sha256=(
            wrapper_sha
        ),
        expected_wrapper_test_sha256=(
            test_sha
        ),
        git_reader=git_reader,
        file_sha256_reader=hash_reader,
    )


def test_repository_preflight_refuses_dirty_tree():
    def git_reader(
        repo,
        *arguments,
    ):
        if arguments == (
            "status",
            "--porcelain",
        ):
            return " M changed"

        return COMMIT

    with pytest.raises(
        wrapper.MonthlySequenceTransportExecutionError,
        match="not clean",
    ):
        wrapper.repository_preflight(
            Path(
                "/repo"
            ),
            expected_commit=COMMIT,
            expected_wrapper_sha256=(
                "3" * 64
            ),
            expected_wrapper_test_sha256=(
                "4" * 64
            ),
            git_reader=git_reader,
            file_sha256_reader=(
                lambda path:
                    ENV_SHA
            ),
        )


def test_environment_preflight_validates_exact_version():
    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.CommandResult(
            returncode=0,
            stdout=b"datasets version: 18.35.0\n",
            stderr=b"",
        )

    observed = (
        wrapper.environment_preflight(
            Path(
                "/repo"
            ),
            datasets_executable=(
                DATASETS
            ),
            command_runner=runner,
            file_sha256_reader=(
                lambda path:
                    ENV_SHA
            ),
        )
    )

    assert observed == DATASETS


def test_environment_preflight_refuses_version_mismatch():
    def runner(
        command,
        *,
        cwd,
    ):
        return wrapper.CommandResult(
            returncode=0,
            stdout=b"datasets version: 99.0.0\n",
            stderr=b"",
        )

    with pytest.raises(
        wrapper.MonthlySequenceTransportExecutionError,
        match="version mismatch",
    ):
        wrapper.environment_preflight(
            Path(
                "/repo"
            ),
            datasets_executable=(
                DATASETS
            ),
            command_runner=runner,
            file_sha256_reader=(
                lambda path:
                    ENV_SHA
            ),
        )


def test_upstream_contract_audits_stage1_and_stage2(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=2,
    )

    upstream = (
        wrapper.load_upstream_contract(
            production_root=(
                paths[
                    "production_root"
                ]
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            sequence_plan_record=(
                paths[
                    "plan_path"
                ]
            ),
            fresh_target_manifest=(
                paths[
                    "manifest_path"
                ]
            ),
            expected_commit=COMMIT,
        )
    )

    assert (
        upstream.source_snapshot_id
        == source_snapshot_id_from_start(
            START
        )
    )

    assert upstream.fresh_target_count == 2
    assert upstream.fresh_batch_count == 1
    assert len(
        upstream.targets
    ) == 2


def test_upstream_contract_refuses_stage2_artifact_outside_stage1_root(
    tmp_path,
):
    paths = make_upstream(
        tmp_path
    )

    outside = (
        tmp_path
        / "outside.tsv"
    )

    outside.write_bytes(
        paths[
            "manifest_path"
        ].read_bytes()
    )

    with pytest.raises(
        wrapper.MonthlySequenceTransportExecutionError,
        match="must be below",
    ):
        wrapper.load_upstream_contract(
            production_root=(
                paths[
                    "production_root"
                ]
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            sequence_plan_record=(
                paths[
                    "plan_path"
                ]
            ),
            fresh_target_manifest=(
                outside.resolve()
            ),
            expected_commit=COMMIT,
        )


def test_dynamic_second_batch_is_derived_internally(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=501,
    )

    upstream = (
        wrapper.load_upstream_contract(
            production_root=(
                paths[
                    "production_root"
                ]
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            sequence_plan_record=(
                paths[
                    "plan_path"
                ]
            ),
            fresh_target_manifest=(
                paths[
                    "manifest_path"
                ]
            ),
            expected_commit=COMMIT,
        )
    )

    second = (
        wrapper.derive_transport_batch(
            upstream,
            batch_index=2,
        )
    )

    assert second.batch_count == 2
    assert len(
        second.targets
    ) == 1

    assert (
        second.targets[
            0
        ].canonical_genbank_assembly_accession
        == accession(
            501
        )
    )


def fake_metadata_validator(
    package,
    targets,
):
    report = (
        package
        / "ncbi_dataset"
        / "data"
        / "assembly_data_report.jsonl"
    )

    return (
        report.parent,
        {
            target.canonical_genbank_assembly_accession:
                target.source_biosample
            for target in targets
        },
        report,
    )


def fake_validated_package(
    package,
    targets,
):
    candidate = {
        field: ""
        for field in CANDIDATE_AUDIT_FIELDS
    }

    candidate[
        "canonical_genbank_assembly_accession"
    ] = (
        targets[
            0
        ].canonical_genbank_assembly_accession
    )

    component = {
        field: ""
        for field in COMPONENT_AUDIT_FIELDS
    }

    component[
        "canonical_genbank_assembly_accession"
    ] = (
        targets[
            0
        ].canonical_genbank_assembly_accession
    )

    package_file = {
        field: ""
        for field in PACKAGE_FILE_FIELDS
    }

    package_file[
        "path"
    ] = "synthetic"

    package_file[
        "size_bytes"
    ] = "4"

    package_file[
        "sha256"
    ] = "f" * 64

    report = (
        package
        / "ncbi_dataset"
        / "data"
        / "assembly_data_report.jsonl"
    )

    return MonthlyValidatedPackage(
        candidate_rows=(
            candidate,
        ),
        component_rows=(
            component,
        ),
        package_file_rows=(
            package_file,
        ),
        assembly_data_report=report,
    )


def make_executor(
    tmp_path,
):
    paths = make_upstream(
        tmp_path
    )

    upstream = (
        wrapper.load_upstream_contract(
            production_root=(
                paths[
                    "production_root"
                ]
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            sequence_plan_record=(
                paths[
                    "plan_path"
                ]
            ),
            fresh_target_manifest=(
                paths[
                    "manifest_path"
                ]
            ),
            expected_commit=COMMIT,
        )
    )

    batch = (
        wrapper.derive_transport_batch(
            upstream,
            batch_index=1,
        )
    )

    return (
        paths,
        batch,
    )


def create_dehydrated_zip(
    filename: Path,
):
    fetch = (
        "https://example.invalid/payload"
        "\t4"
        "\tdata/GCA_000000001.1/payload.bin\n"
    )

    with zipfile.ZipFile(
        filename,
        "w",
    ) as archive:
        archive.writestr(
            "ncbi_dataset/fetch.txt",
            fetch,
        )

        archive.writestr(
            (
                "ncbi_dataset/data/"
                "assembly_data_report.jsonl"
            ),
            "{}\n",
        )


def hydrate_payload(
    package: Path,
):
    path = (
        package
        / "ncbi_dataset"
        / "data"
        / "GCA_000000001.1"
        / "payload.bin"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        b"ACGT"
    )


def test_full_execution_broad_rehydrate_success(
    tmp_path,
):
    (
        paths,
        batch,
    ) = make_executor(
        tmp_path
    )

    saw_pre_network = {
        "value":
            False,
    }

    def runner(
        command,
        *,
        cwd,
    ):
        command = tuple(
            command
        )

        if "download" in command:
            attempt = (
                paths[
                    "stage1_root"
                ]
                / "sequence-acquisition"
                / "batch-00001.partial"
                / "attempt-origin.json"
            )

            record = json.loads(
                attempt.read_text(
                    encoding="utf-8"
                )
            )

            assert record[
                "created_before_network_retrieval"
            ] is True

            assert record[
                "dehydrated_zip_sha256"
            ] is None

            saw_pre_network[
                "value"
            ] = True

            filename = Path(
                command[
                    command.index(
                        "--filename"
                    )
                    + 1
                ]
            )

            create_dehydrated_zip(
                filename
            )

            return wrapper.CommandResult(
                returncode=0,
                stdout=b"download ok\n",
                stderr=b"",
            )

        if (
            "rehydrate"
            in command
            and "--match"
            not in command
        ):
            package = Path(
                command[
                    command.index(
                        "--directory"
                    )
                    + 1
                ]
            )

            hydrate_payload(
                package
            )

            return wrapper.CommandResult(
                returncode=0,
                stdout=b"rehydrate ok\n",
                stderr=b"",
            )

        raise AssertionError(
            command
        )

    result = (
        wrapper.execute_transport_batch(
            repo=Path(
                "/repo"
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            batch=batch,
            datasets_executable=(
                DATASETS
            ),
            execution_commit=COMMIT,
            transport_implementation_sha256=(
                "e" * 64
            ),
            command_runner=runner,
            metadata_validator=(
                fake_metadata_validator
            ),
            package_validator=(
                fake_validated_package
            ),
        )
    )

    assert saw_pre_network[
        "value"
    ] is True

    assert result.batch_id == "batch-00001"
    assert result.output_dir.is_dir()

    summary = json.loads(
        (
            result.output_dir
            / "batch-summary.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert summary[
        "result"
    ] == "PASS"

    assert summary[
        "initial_unresolved_accessions"
    ] == 1

    assert summary[
        "targeted_retry_events"
    ] == []


def test_targeted_retry_recovers_unresolved_accession(
    tmp_path,
):
    (
        paths,
        batch,
    ) = make_executor(
        tmp_path
    )

    def runner(
        command,
        *,
        cwd,
    ):
        command = tuple(
            command
        )

        if "download" in command:
            filename = Path(
                command[
                    command.index(
                        "--filename"
                    )
                    + 1
                ]
            )

            create_dehydrated_zip(
                filename
            )

            return wrapper.CommandResult(
                returncode=0,
                stdout=b"",
                stderr=b"",
            )

        if (
            "rehydrate"
            in command
            and "--match"
            not in command
        ):
            return wrapper.CommandResult(
                returncode=1,
                stdout=b"",
                stderr=b"broad failed\n",
            )

        if "--match" in command:
            package = Path(
                command[
                    command.index(
                        "--directory"
                    )
                    + 1
                ]
            )

            hydrate_payload(
                package
            )

            return wrapper.CommandResult(
                returncode=0,
                stdout=b"target recovered\n",
                stderr=b"",
            )

        raise AssertionError(
            command
        )

    result = (
        wrapper.execute_transport_batch(
            repo=Path(
                "/repo"
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            batch=batch,
            datasets_executable=(
                DATASETS
            ),
            execution_commit=COMMIT,
            transport_implementation_sha256=(
                "e" * 64
            ),
            command_runner=runner,
            metadata_validator=(
                fake_metadata_validator
            ),
            package_validator=(
                fake_validated_package
            ),
        )
    )

    summary = json.loads(
        (
            result.output_dir
            / "batch-summary.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert summary[
        "broad_rehydrate_exit_code"
    ] == 1

    assert len(
        summary[
            "targeted_retry_events"
        ]
    ) == 1

    assert summary[
        "targeted_retry_events"
    ][0][
        "remaining"
    ] == []


def test_retry_exhaustion_retains_partial(
    tmp_path,
):
    (
        paths,
        batch,
    ) = make_executor(
        tmp_path
    )

    def runner(
        command,
        *,
        cwd,
    ):
        command = tuple(
            command
        )

        if "download" in command:
            filename = Path(
                command[
                    command.index(
                        "--filename"
                    )
                    + 1
                ]
            )

            create_dehydrated_zip(
                filename
            )

            return wrapper.CommandResult(
                returncode=0,
                stdout=b"",
                stderr=b"",
            )

        return wrapper.CommandResult(
            returncode=1,
            stdout=b"",
            stderr=b"still unavailable\n",
        )

    with pytest.raises(
        wrapper.MonthlySequenceTransportExecutionError,
        match="bounded targeted recovery",
    ):
        wrapper.execute_transport_batch(
            repo=Path(
                "/repo"
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            batch=batch,
            datasets_executable=(
                DATASETS
            ),
            execution_commit=COMMIT,
            transport_implementation_sha256=(
                "e" * 64
            ),
            command_runner=runner,
            metadata_validator=(
                fake_metadata_validator
            ),
            package_validator=(
                fake_validated_package
            ),
        )

    partial = (
        paths[
            "stage1_root"
        ]
        / "sequence-acquisition"
        / "batch-00001.partial"
    )

    assert partial.is_dir()

    events = json.loads(
        (
            partial
            / "targeted-retry-events.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert len(
        events
    ) == 2


def test_resume_after_stage3a_failure_reuses_completed_transport(
    tmp_path,
):
    (
        paths,
        batch,
    ) = make_executor(
        tmp_path
    )

    command_calls = []

    def first_runner(
        command,
        *,
        cwd,
    ):
        command = tuple(
            command
        )

        command_calls.append(
            command
        )

        if "download" in command:
            filename = Path(
                command[
                    command.index(
                        "--filename"
                    )
                    + 1
                ]
            )

            create_dehydrated_zip(
                filename
            )

            return wrapper.CommandResult(
                returncode=0,
                stdout=b"",
                stderr=b"",
            )

        if (
            "rehydrate"
            in command
            and "--match"
            not in command
        ):
            package = Path(
                command[
                    command.index(
                        "--directory"
                    )
                    + 1
                ]
            )

            hydrate_payload(
                package
            )

            return wrapper.CommandResult(
                returncode=0,
                stdout=b"",
                stderr=b"",
            )

        raise AssertionError(
            command
        )

    def failing_validator(
        package,
        targets,
    ):
        raise ValueError(
            "synthetic Stage 3A failure"
        )

    with pytest.raises(
        wrapper.MonthlySequenceTransportExecutionError,
        match="Stage 3A",
    ):
        wrapper.execute_transport_batch(
            repo=Path(
                "/repo"
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            batch=batch,
            datasets_executable=(
                DATASETS
            ),
            execution_commit=COMMIT,
            transport_implementation_sha256=(
                "e" * 64
            ),
            command_runner=first_runner,
            metadata_validator=(
                fake_metadata_validator
            ),
            package_validator=(
                failing_validator
            ),
        )

    first_call_count = len(
        command_calls
    )

    def forbidden_runner(
        command,
        *,
        cwd,
    ):
        raise AssertionError(
            "resume unexpectedly executed transport command"
        )

    result = (
        wrapper.execute_transport_batch(
            repo=Path(
                "/repo"
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            batch=batch,
            datasets_executable=(
                DATASETS
            ),
            execution_commit=COMMIT,
            transport_implementation_sha256=(
                "e" * 64
            ),
            resume=True,
            command_runner=(
                forbidden_runner
            ),
            metadata_validator=(
                fake_metadata_validator
            ),
            package_validator=(
                fake_validated_package
            ),
        )
    )

    assert len(
        command_calls
    ) == first_call_count

    assert result.output_dir.is_dir()


def test_main_requires_explicit_authorization():
    with pytest.raises(
        wrapper.MonthlySequenceTransportExecutionError,
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
                "/tmp/production",
                "--stage1-root",
                "/tmp/stage1",
                "--sequence-plan-record",
                "/tmp/plan.json",
                "--fresh-target-manifest",
                "/tmp/fresh.tsv",
                "--batch-index",
                "1",
                "--datasets-executable",
                "/tmp/datasets",
            )
        )


def test_transport_json_supports_sequence_evidence_and_normalizes_tuples():
    payload = {
        "command": (
            "datasets",
            "rehydrate",
        ),
        "events": [
            {
                "attempt":
                    1,
            },
        ],
    }

    encoded = (
        wrapper.transport_json_bytes(
            payload
        )
    )

    observed = json.loads(
        encoded.decode(
            "utf-8"
        )
    )

    assert observed == {
        "command": [
            "datasets",
            "rehydrate",
        ],
        "events": [
            {
                "attempt":
                    1,
            },
        ],
    }

    assert (
        wrapper.json_normalized(
            payload
        )
        == observed
    )

    assert encoded.endswith(
        b"\n"
    )


def test_download_failure_retains_partial_and_execution_evidence(
    tmp_path,
):
    (
        paths,
        batch,
    ) = make_executor(
        tmp_path
    )

    calls = []

    def runner(
        command,
        *,
        cwd,
    ):
        command = tuple(
            command
        )

        calls.append(
            command
        )

        assert "download" in command

        return wrapper.CommandResult(
            returncode=7,
            stdout=b"synthetic download stdout\n",
            stderr=b"synthetic download failure\n",
        )

    with pytest.raises(
        wrapper.MonthlySequenceTransportExecutionError,
        match="dehydrated download failed",
    ):
        wrapper.execute_transport_batch(
            repo=Path(
                "/repo"
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            batch=batch,
            datasets_executable=(
                DATASETS
            ),
            execution_commit=COMMIT,
            transport_implementation_sha256=(
                "e" * 64
            ),
            command_runner=runner,
            metadata_validator=(
                fake_metadata_validator
            ),
            package_validator=(
                fake_validated_package
            ),
        )

    assert len(
        calls
    ) == 1

    partial = (
        paths[
            "stage1_root"
        ]
        / "sequence-acquisition"
        / "batch-00001.partial"
    )

    final = (
        paths[
            "stage1_root"
        ]
        / "sequence-acquisition"
        / "batch-00001"
    )

    assert partial.is_dir()
    assert not final.exists()

    attempt_path = (
        partial
        / "attempt-origin.json"
    )

    assert attempt_path.is_file()

    attempt = json.loads(
        attempt_path.read_text(
            encoding="utf-8"
        )
    )

    assert attempt[
        "created_before_network_retrieval"
    ] is True

    assert attempt[
        "dehydrated_zip_sha256"
    ] is None

    assert json.loads(
        (
            partial
            / "download-command.json"
        ).read_text(
            encoding="utf-8"
        )
    ) == list(
        calls[
            0
        ]
    )

    assert (
        partial
        / "download.stdout.txt"
    ).read_bytes() == (
        b"synthetic download stdout\n"
    )

    assert (
        partial
        / "download.stderr.txt"
    ).read_bytes() == (
        b"synthetic download failure\n"
    )

    assert (
        partial
        / "download-exit-code.txt"
    ).read_text(
        encoding="ascii"
    ) == "7\n"

    assert not (
        partial
        / "package"
    ).exists()

    assert not (
        partial
        / "dehydrated.zip"
    ).exists()
