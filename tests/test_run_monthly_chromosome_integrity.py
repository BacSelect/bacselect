from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from bacselect import source_chromosome_integrity


WRAPPER = (
    Path(
        __file__
    )
    .resolve()
    .parents[
        1
    ]
    / "validation"
    / "selector-v1"
    / "run_monthly_chromosome_integrity.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "_monthly_chromosome_executor_test",
        WRAPPER,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        spec.name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


class FakeStage5:
    @staticmethod
    def validate_sha256(
        value,
        *,
        label,
    ):
        assert label

        if (
            not isinstance(
                value,
                str,
            )
            or len(
                value
            )
            != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in value
            )
        ):
            raise ValueError(
                "bad sha"
            )

        return value

    @staticmethod
    def validate_commit(
        value,
    ):
        if (
            not isinstance(
                value,
                str,
            )
            or len(
                value
            )
            != 40
        ):
            raise ValueError(
                "bad commit"
            )

        return value

    @staticmethod
    def validate_count(
        value,
        *,
        label,
    ):
        assert label

        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
            or value < 0
        ):
            raise ValueError(
                "bad count"
            )

        return value

    @staticmethod
    def write_no_clobber(
        path,
        payload,
    ):
        descriptor = os.open(
            path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL,
            0o644,
        )

        try:
            os.write(
                descriptor,
                payload,
            )
            os.fsync(
                descriptor
            )
        finally:
            os.close(
                descriptor
            )

    @staticmethod
    def _require_real_directory(
        path,
        *,
        label,
    ):
        assert label

        value = Path(
            path
        )

        if (
            value.is_symlink()
            or not value.is_dir()
        ):
            raise RuntimeError(
                "not directory"
            )

        return value

    @staticmethod
    def _require_regular_file(
        path,
        *,
        label,
    ):
        assert label

        value = Path(
            path
        )

        if (
            value.is_symlink()
            or not value.is_file()
        ):
            raise RuntimeError(
                "not file"
            )

        return value

    @staticmethod
    def _require_exact_inventory(
        directory,
        *,
        expected_files,
        label,
    ):
        assert label

        observed = {
            item.name
            for item in Path(
                directory
            ).iterdir()
        }

        if observed != expected_files:
            raise RuntimeError(
                "inventory"
            )

    @staticmethod
    def fsync_directory(
        path,
    ):
        descriptor = os.open(
            path,
            os.O_RDONLY,
        )

        try:
            os.fsync(
                descriptor
            )
        finally:
            os.close(
                descriptor
            )


def package_row(
    accession,
    name,
    payload,
):
    path = (
        f"ncbi_dataset/data/"
        f"{accession}/{name}"
    )

    return {
        "path":
            path,
        "size_bytes":
            str(
                len(
                    payload
                )
            ),
        "sha256":
            hashlib.sha256(
                payload
            ).hexdigest(),
    }


def test_monthly_provider_explicitly_rejects_project_finch_reuse():
    module = load_module()

    observed = module.monthly_historical_provider(
        "GCA_000000001.1"
    )

    assert (
        observed.uses_historical_project_finch_package
        is False
    )

    assert observed.cache_content_verification is None
    assert observed.adjudication_accession is None
    assert observed.adjudication_outcome is None


def test_monthly_provider_gives_informative_triggered_reason():
    module = load_module()

    components = (
        source_chromosome_integrity
        .PrimaryComponentEvidence(
            molecule_class="Chromosome",
            topology="circular",
            definition="complete chromosome",
        ),
        source_chromosome_integrity
        .PrimaryComponentEvidence(
            molecule_class="Chromosome",
            topology="linear",
            definition="chromosome sequence",
        ),
    )

    observed = (
        source_chromosome_integrity
        .evaluate(
            accession="GCA_000000001.1",
            components=components,
            historical=(
                module.monthly_historical_provider(
                    "GCA_000000001.1"
                )
            ),
        )
    )

    assert (
        observed.status
        == source_chromosome_integrity.UNRESOLVED
    )

    assert (
        observed.reason
        == "NOT_HISTORICAL_PROJECT_FINCH_PACKAGE"
    )


def test_completion_roundtrip():
    module = load_module()

    kwargs = {
        "release_id":
            "2034.05",
        "source_snapshot_id":
            "snapshot",
        "execution_commit":
            "a" * 40,
        "biosample_decisions_sha256":
            "1" * 64,
        "biosample_record_sha256":
            "2" * 64,
        "biosample_completion_sha256":
            "3" * 64,
        "continue_count":
            3,
        "continue_accessions_sha256":
            "4" * 64,
        "decision_count":
            3,
        "triggered_candidate_count":
            1,
        "nontriggered_candidate_count":
            2,
        "historical_adjudication_reuse_count":
            0,
        "pass_count":
            2,
        "excluded_count":
            0,
        "unresolved_count":
            1,
        "decisions_sha256":
            "5" * 64,
        "record_sha256":
            "6" * 64,
        "stage5_execution":
            FakeStage5,
    }

    payload = (
        module.build_completion_receipt(
            **kwargs
        )
    )

    observed = (
        module.audit_completion_receipt(
            payload,
            **kwargs
        )
    )

    assert (
        observed[
            "schema_version"
        ]
        == module.COMPLETION_SCHEMA
    )

    assert (
        observed[
            "status"
        ]
        == module.COMPLETION_STATUS
    )

    assert payload == (
        json.dumps(
            observed,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def test_completion_rejects_population_accounting():
    module = load_module()

    with pytest.raises(
        module.MonthlyChromosomeExecutionError,
        match="population accounting",
    ):
        module.build_completion_receipt(
            release_id="2034.05",
            source_snapshot_id="snapshot",
            execution_commit="a" * 40,
            biosample_decisions_sha256="1" * 64,
            biosample_record_sha256="2" * 64,
            biosample_completion_sha256="3" * 64,
            continue_count=2,
            continue_accessions_sha256="4" * 64,
            decision_count=1,
            triggered_candidate_count=0,
            nontriggered_candidate_count=1,
            historical_adjudication_reuse_count=0,
            pass_count=1,
            excluded_count=0,
            unresolved_count=0,
            decisions_sha256="5" * 64,
            record_sha256="6" * 64,
            stage5_execution=FakeStage5,
        )


def test_completion_forbids_historical_reuse():
    module = load_module()

    with pytest.raises(
        module.MonthlyChromosomeExecutionError,
        match="must not reuse",
    ):
        module.build_completion_receipt(
            release_id="2034.05",
            source_snapshot_id="snapshot",
            execution_commit="a" * 40,
            biosample_decisions_sha256="1" * 64,
            biosample_record_sha256="2" * 64,
            biosample_completion_sha256="3" * 64,
            continue_count=1,
            continue_accessions_sha256="4" * 64,
            decision_count=1,
            triggered_candidate_count=1,
            nontriggered_candidate_count=0,
            historical_adjudication_reuse_count=1,
            pass_count=1,
            excluded_count=0,
            unresolved_count=0,
            decisions_sha256="5" * 64,
            record_sha256="6" * 64,
            stage5_execution=FakeStage5,
        )


def test_prior_materialization_writes_entire_accession_package(
    tmp_path,
):
    module = load_module()

    accession = "GCA_000000001.1"

    payloads = {
        "genomic.fna":
            b">CP000001.1\nACGT\n",
        "sequence_report.jsonl":
            b'{"assemblyAccession":"GCA_000000001.1"}\n',
        "genomic.gbff":
            b"LOCUS test 4 bp DNA circular\n",
    }

    rows = tuple(
        package_row(
            accession,
            name,
            payload,
        )
        for name, payload
        in payloads.items()
    )

    by_sha = {
        row[
            "sha256"
        ]:
            payloads[
                Path(
                    row[
                        "path"
                    ]
                ).name
            ]
        for row in rows
    }

    class Cache:
        @staticmethod
        def read_required_object(
            authoritative_root,
            *,
            sha256,
            expected_size_bytes,
            label,
        ):
            assert authoritative_root == (
                tmp_path
                / "objects"
            )

            assert label

            payload = by_sha[
                sha256
            ]

            assert (
                len(
                    payload
                )
                == expected_size_bytes
            )

            return SimpleNamespace(
                payload=payload,
                size_bytes=len(
                    payload
                ),
                sha256=sha256,
            )

    bridge = SimpleNamespace(
        accession=accession,
        package_rows=rows,
    )

    authoritative = (
        tmp_path
        / "objects"
    )

    authoritative.mkdir()

    materialization = (
        tmp_path
        / "materialization"
    )

    materialization.mkdir()

    candidate_root, observations = (
        module.materialize_prior_package(
            cache_execution=Cache,
            authoritative_root=authoritative,
            materialization_root=materialization,
            bridge=bridge,
            stage5_execution=FakeStage5,
        )
    )

    assert len(
        observations
    ) == 3

    for name, expected in (
        payloads.items()
    ):
        path = (
            candidate_root
            / "package"
            / "ncbi_dataset"
            / "data"
            / accession
            / name
        )

        assert path.read_bytes() == expected


def test_prior_materialization_rejects_non_accession_scoped_row(
    tmp_path,
):
    module = load_module()

    accession = "GCA_000000001.1"

    payload = b"x"

    row = {
        "path":
            "README.md",
        "size_bytes":
            "1",
        "sha256":
            hashlib.sha256(
                payload
            ).hexdigest(),
    }

    bridge = SimpleNamespace(
        accession=accession,
        package_rows=(
            row,
        ),
    )

    class Cache:
        @staticmethod
        def read_required_object(
            *args,
            **kwargs,
        ):
            return SimpleNamespace(
                payload=payload,
            )

    authoritative = (
        tmp_path
        / "objects"
    )

    authoritative.mkdir()

    materialization = (
        tmp_path
        / "materialization"
    )

    materialization.mkdir()

    with pytest.raises(
        module.MonthlyChromosomeExecutionError,
        match="not accession scoped",
    ):
        module.materialize_prior_package(
            cache_execution=Cache,
            authoritative_root=authoritative,
            materialization_root=materialization,
            bridge=bridge,
            stage5_execution=FakeStage5,
        )


def test_package_path_rejects_traversal():
    module = load_module()

    row = {
        "path":
            "../escape",
        "size_bytes":
            "1",
        "sha256":
            "1" * 64,
    }

    with pytest.raises(
        module.MonthlyChromosomeExecutionError,
        match="unsafe",
    ):
        module._package_row_identity(
            row,
            stage5_execution=FakeStage5,
        )


def test_current_package_observation_checks_all_rows(
    tmp_path,
):
    module = load_module()

    accession = "GCA_000000001.1"

    batch = (
        tmp_path
        / "batch-00001"
    )

    package = (
        batch
        / "package"
        / "ncbi_dataset"
        / "data"
        / accession
    )

    package.mkdir(
        parents=True
    )

    payloads = {
        "genomic.fna":
            b">CP000001.1\nACGT\n",
        "sequence_report.jsonl":
            b"{}\n",
        "genomic.gbff":
            b"GBFF\n",
    }

    rows = []

    for name, payload in (
        payloads.items()
    ):
        path = (
            package
            / name
        )

        path.write_bytes(
            payload
        )

        rows.append(
            package_row(
                accession,
                name,
                payload,
            )
        )

    class Stage5(
        FakeStage5
    ):
        @staticmethod
        def resolve_manifest_path(
            batch_dir,
            relative_path,
        ):
            return (
                batch_dir
                / "package"
                / relative_path
            )

    bridge = SimpleNamespace(
        accession=accession,
        package_rows=tuple(
            rows
        ),
    )

    observations = (
        module.observe_current_package(
            batch_dir=batch,
            bridge=bridge,
            stage5_execution=Stage5,
        )
    )

    assert len(
        observations
    ) == 3


def test_current_package_observation_rejects_mutated_file(
    tmp_path,
):
    module = load_module()

    path = (
        tmp_path
        / "file"
    )

    path.write_bytes(
        b"before"
    )

    observation = (
        module.PackageFileObservation(
            path=path,
            size_bytes=len(
                b"before"
            ),
            sha256=hashlib.sha256(
                b"before"
            ).hexdigest(),
        )
    )

    path.write_bytes(
        b"after"
    )

    with pytest.raises(
        module.MonthlyChromosomeExecutionError,
        match="current package file changed",
    ):
        module.verify_package_observations(
            stage5_execution=FakeStage5,
            stage4_execution=SimpleNamespace(),
            cache_execution=SimpleNamespace(),
            current_completion_context=SimpleNamespace(),
            execution_commit="a" * 40,
            authoritative_root=tmp_path,
            local_observations=(
                observation,
            ),
            authoritative_observations=(),
            current_batch_observations=(),
            prior_batch_observations=(),
        )


def test_authoritative_observation_is_reauthenticated(
    tmp_path,
):
    module = load_module()

    calls = []

    class Cache:
        @staticmethod
        def read_required_object(
            authoritative_root,
            *,
            sha256,
            expected_size_bytes,
            label,
        ):
            calls.append(
                (
                    authoritative_root,
                    sha256,
                    expected_size_bytes,
                    label,
                )
            )

    observation = (
        module.AuthoritativePackageObservation(
            sha256="1" * 64,
            size_bytes=10,
        )
    )

    module.verify_package_observations(
        stage5_execution=FakeStage5,
        stage4_execution=SimpleNamespace(),
        cache_execution=Cache,
        current_completion_context=SimpleNamespace(),
        execution_commit="a" * 40,
        authoritative_root=tmp_path,
        local_observations=(),
        authoritative_observations=(
            observation,
        ),
        current_batch_observations=(),
        prior_batch_observations=(),
    )

    assert len(
        calls
    ) == 1

    assert calls[
        0
    ][
        1
    ] == "1" * 64


def test_current_batch_is_reauthenticated():
    module = load_module()

    expected = SimpleNamespace(
        provenance={
            "batch":
                "x",
        },
        candidate_rows=(
            {
                "a":
                    "b",
            },
        ),
        component_rows=(
            {
                "c":
                    "d",
            },
        ),
        package_rows=(
            {
                "e":
                    "f",
            },
        ),
    )

    observation = SimpleNamespace(
        provenance=(
            expected.provenance
        ),
        batch=expected,
    )

    class Stage4:
        @staticmethod
        def _current_batch_evidence(
            **kwargs,
        ):
            return expected

    module.verify_package_observations(
        stage5_execution=FakeStage5,
        stage4_execution=Stage4,
        cache_execution=SimpleNamespace(),
        current_completion_context=SimpleNamespace(),
        execution_commit="a" * 40,
        authoritative_root=Path("."),
        local_observations=(),
        authoritative_observations=(),
        current_batch_observations=(
            observation,
        ),
        prior_batch_observations=(),
    )


def test_prior_batch_is_reauthenticated():
    module = load_module()

    expected = SimpleNamespace(
        provenance={
            "batch":
                "x",
        },
        candidate_rows=(
            {
                "a":
                    "b",
            },
        ),
        component_rows=(
            {
                "c":
                    "d",
            },
        ),
        package_rows=(
            {
                "e":
                    "f",
            },
        ),
    )

    observation = SimpleNamespace(
        provenance=(
            expected.provenance
        ),
        batch=expected,
    )

    class Cache:
        @staticmethod
        def load_batch_evidence(
            authoritative_root,
            *,
            provenance,
        ):
            assert provenance == (
                expected.provenance
            )

            return expected

    module.verify_package_observations(
        stage5_execution=FakeStage5,
        stage4_execution=SimpleNamespace(),
        cache_execution=Cache,
        current_completion_context=SimpleNamespace(),
        execution_commit="a" * 40,
        authoritative_root=Path("."),
        local_observations=(),
        authoritative_observations=(),
        current_batch_observations=(),
        prior_batch_observations=(
            observation,
        ),
    )


def test_publish_stage_uses_hard_links_and_removes_partial(
    tmp_path,
):
    module = load_module()

    partial = (
        tmp_path
        / module.PARTIAL_NAME
    )

    final = (
        tmp_path
        / module.STAGE_NAME
    )

    partial.mkdir()

    decisions = b"a\n"
    record = b"{}\n"

    FakeStage5.write_no_clobber(
        partial
        / module.DECISIONS_NAME,
        decisions,
    )

    FakeStage5.write_no_clobber(
        partial
        / module.RECORD_NAME,
        record,
    )

    source_inode = (
        partial
        / module.DECISIONS_NAME
    ).stat().st_ino

    stability_calls = []

    module.publish_stage(
        stage1_root=tmp_path,
        partial=partial,
        final=final,
        expected_decisions=decisions,
        expected_record=record,
        auditor=lambda d, r:
            (
                d == decisions
                and r == record
            ),
        stability_check=lambda:
            stability_calls.append(
                True
            ),
        stage5_execution=FakeStage5,
    )

    assert not partial.exists()
    assert final.is_dir()

    assert (
        final
        / module.DECISIONS_NAME
    ).stat().st_ino == source_inode

    assert len(
        stability_calls
    ) == 2


def test_publish_completion_uses_hard_link(
    tmp_path,
):
    module = load_module()

    payload = b"{}\n"

    calls = []

    observed = module.publish_completion(
        stage1_root=tmp_path,
        payload=payload,
        auditor=lambda value:
            value == payload,
        stability_check=lambda:
            calls.append(
                True
            ),
        stage5_execution=FakeStage5,
    )

    assert observed.read_bytes() == payload

    assert not (
        tmp_path
        / module.COMPLETION_TEMP_NAME
    ).exists()

    assert len(
        calls
    ) == 2


def test_frozen_dependency_inventory_contains_pure_stage6():
    module = load_module()

    assert (
        Path(
            "src/bacselect/"
            "monthly_chromosome_integrity.py"
        )
        in module.FROZEN_DEPENDENCIES
    )


def test_no_project_finch_runtime_path_constant():
    module = load_module()

    values = tuple(
        str(
            value
        )
        for name, value
        in vars(
            module
        ).items()
        if name.isupper()
    )

    assert not any(
        "/NGS/" in value
        for value in values
    )


def test_publish_stage_cleans_partial_final_on_second_link_failure(
    tmp_path,
):
    module = load_module()

    partial = (
        tmp_path
        / module.PARTIAL_NAME
    )

    final = (
        tmp_path
        / module.STAGE_NAME
    )

    partial.mkdir()

    decisions = b"decisions\n"
    record = b"{}\n"

    FakeStage5.write_no_clobber(
        partial
        / module.DECISIONS_NAME,
        decisions,
    )

    FakeStage5.write_no_clobber(
        partial
        / module.RECORD_NAME,
        record,
    )

    original = (
        module._link_no_clobber
    )

    calls = 0

    def fail_second(
        source,
        destination,
    ):
        nonlocal calls

        calls += 1

        if calls == 2:
            raise (
                module
                .MonthlyChromosomeExecutionError(
                    "synthetic second-link failure"
                )
            )

        return original(
            source,
            destination,
        )

    module._link_no_clobber = (
        fail_second
    )

    try:
        with pytest.raises(
            module.MonthlyChromosomeExecutionError,
            match="synthetic second-link failure",
        ):
            module.publish_stage(
                stage1_root=tmp_path,
                partial=partial,
                final=final,
                expected_decisions=decisions,
                expected_record=record,
                auditor=lambda d, r:
                    (
                        d == decisions
                        and r == record
                    ),
                stability_check=lambda:
                    None,
                stage5_execution=FakeStage5,
            )
    finally:
        module._link_no_clobber = (
            original
        )

    assert partial.is_dir()

    assert (
        partial
        / module.DECISIONS_NAME
    ).read_bytes() == decisions

    assert (
        partial
        / module.RECORD_NAME
    ).read_bytes() == record

    assert not final.exists()


def test_publish_stage_cleans_final_on_postlink_stability_failure(
    tmp_path,
):
    module = load_module()

    partial = (
        tmp_path
        / module.PARTIAL_NAME
    )

    final = (
        tmp_path
        / module.STAGE_NAME
    )

    partial.mkdir()

    decisions = b"decisions\n"
    record = b"{}\n"

    FakeStage5.write_no_clobber(
        partial
        / module.DECISIONS_NAME,
        decisions,
    )

    FakeStage5.write_no_clobber(
        partial
        / module.RECORD_NAME,
        record,
    )

    calls = 0

    def stability():
        nonlocal calls

        calls += 1

        if calls == 2:
            raise (
                module
                .MonthlyChromosomeExecutionError(
                    "synthetic stability failure"
                )
            )

    with pytest.raises(
        module.MonthlyChromosomeExecutionError,
        match="synthetic stability failure",
    ):
        module.publish_stage(
            stage1_root=tmp_path,
            partial=partial,
            final=final,
            expected_decisions=decisions,
            expected_record=record,
            auditor=lambda d, r:
                (
                    d == decisions
                    and r == record
                ),
            stability_check=stability,
            stage5_execution=FakeStage5,
        )

    assert calls == 2
    assert partial.is_dir()
    assert not final.exists()


def test_publish_completion_cleans_failed_publication(
    tmp_path,
):
    module = load_module()

    calls = 0

    def stability():
        nonlocal calls

        calls += 1

        if calls == 2:
            raise (
                module
                .MonthlyChromosomeExecutionError(
                    "synthetic completion stability failure"
                )
            )

    with pytest.raises(
        module.MonthlyChromosomeExecutionError,
        match="synthetic completion stability failure",
    ):
        module.publish_completion(
            stage1_root=tmp_path,
            payload=b"{}\n",
            auditor=lambda value:
                value == b"{}\n",
            stability_check=stability,
            stage5_execution=FakeStage5,
        )

    assert calls == 2

    assert not (
        tmp_path
        / module.COMPLETION_NAME
    ).exists()

    assert not (
        tmp_path
        / module.COMPLETION_TEMP_NAME
    ).exists()


def test_owned_hard_link_cleanup_refuses_unrelated_file(
    tmp_path,
):
    module = load_module()

    source = (
        tmp_path
        / "source"
    )

    destination = (
        tmp_path
        / "destination"
    )

    source.write_bytes(
        b"source"
    )

    destination.write_bytes(
        b"other"
    )

    with pytest.raises(
        module.MonthlyChromosomeExecutionError,
        match="not the created hard link",
    ):
        module._remove_owned_hard_link(
            source=source,
            destination=destination,
            label="synthetic",
        )

    assert destination.read_bytes() == b"other"
