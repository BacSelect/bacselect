from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from urllib import parse as urllib_parse
import sys
import zipfile

import pytest

from bacselect import monthly_missing_datasets_gbff_execution as execution
from bacselect import monthly_sequence_recovery_authority as authority


ROOT = Path(__file__).resolve().parents[1]

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "test_monthly_missing_datasets_gbff_recovery.py"
)

FIXTURE_MODULE_NAME = (
    "_bacselect_missing_gbff_frozen_fixture"
)

spec = importlib.util.spec_from_file_location(
    FIXTURE_MODULE_NAME,
    FIXTURE_PATH,
)

if (
    spec is None
    or spec.loader is None
):
    raise RuntimeError(
        "could not load frozen missing-GBFF fixture"
    )

fixture = importlib.util.module_from_spec(
    spec
)

sys.modules[
    FIXTURE_MODULE_NAME
] = fixture

spec.loader.exec_module(
    fixture
)


RELEASE = "2026.09"
SOURCE_COMMIT = "a" * 40
RECOVERY_COMMIT = "b" * 40
BATCH = "batch-00072"

FIXED_TIME = "2026-09-02T00:00:00Z"


class FakeResponse:
    def __init__(
        self,
        payload,
    ):
        self.payload = payload

    def __enter__(
        self,
    ):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def read(
        self,
    ):
        return self.payload


class FakeEfetch:
    def __init__(
        self,
        mode="success",
    ):
        self.mode = mode
        self.calls = []

    def __call__(
        self,
        request,
        *,
        timeout,
    ):
        payload = urllib_parse.parse_qs(
            request.data.decode(
                "ascii"
            )
        )

        requested = tuple(
            payload[
                "id"
            ][
                0
            ].split(
                ","
            )
        )

        self.calls.append(
            {
                "requested":
                    requested,
                "timeout":
                    timeout,
                "db":
                    payload.get(
                        "db"
                    ),
                "rettype":
                    payload.get(
                        "rettype"
                    ),
                "retmode":
                    payload.get(
                        "retmode"
                    ),
            }
        )

        if self.mode == "fail":
            raise OSError(
                "synthetic EFetch failure"
            )

        if self.mode == "empty":
            return FakeResponse(
                b""
            )

        if self.mode == "wrong-component":
            payload_bytes = (
                fixture.gbff_bytes()
                .replace(
                    fixture.COMP.encode(
                        "ascii"
                    ),
                    b"CP999999.1",
                )
            )

            return FakeResponse(
                payload_bytes
            )

        if requested != (
            fixture.COMP,
        ):
            raise AssertionError(
                "unexpected synthetic component request: "
                f"{requested!r}"
            )

        return FakeResponse(
            fixture.gbff_bytes()
        )


def make_source_partial(
    tmp_path,
    *,
    zip_fetch_matches=True,
):
    sequence_root = (
        tmp_path
        / "sequence-acquisition"
    )

    partial = (
        sequence_root
        / f"{BATCH}.partial"
    )

    partial.mkdir(
        parents=True
    )

    package = fixture.make_package(
        partial
    )

    ncbi_root = (
        package
        / "ncbi_dataset"
    )

    acc_dir = (
        ncbi_root
        / "data"
        / fixture.ACC
    )

    fasta_files = [
        candidate
        for candidate
        in sorted(
            acc_dir.glob(
                "*.fna"
            )
        )
        if not candidate.name.endswith(
            (
                "_cds_from_genomic.fna",
                "_rna_from_genomic.fna",
            )
        )
    ]

    if len(
        fasta_files
    ) != 1:
        raise RuntimeError(
            "synthetic source fixture must contain "
            "exactly one genomic FASTA"
        )

    sequence_report = (
        acc_dir
        / "sequence_report.jsonl"
    )

    if (
        not sequence_report.is_file()
        or sequence_report.stat().st_size <= 0
    ):
        raise RuntimeError(
            "synthetic source fixture lacks "
            "sequence_report.jsonl"
        )

    fasta_destination = (
        fasta_files[
            0
        ]
        .relative_to(
            ncbi_root
        )
        .as_posix()
    )

    report_destination = (
        sequence_report
        .relative_to(
            ncbi_root
        )
        .as_posix()
    )

    fetch = (
        ncbi_root
        / "fetch.txt"
    )

    fetch.write_text(
        (
            "https://api.ncbi.nlm.nih.gov/"
            "datasets/fetch_h/synthetic-fasta"
            "\t0\t"
            f"{fasta_destination}\n"
            "https://api.ncbi.nlm.nih.gov/"
            "datasets/fetch_h/synthetic-sequence-report"
            "\t0\t"
            f"{report_destination}\n"
        ),
        encoding="utf-8",
    )

    fetch_payload = (
        fetch.read_bytes()
    )

    zip_payload = (
        fetch_payload
        if zip_fetch_matches
        else b"synthetic mismatched fetch\n"
    )

    with zipfile.ZipFile(
        partial
        / "dehydrated.zip",
        "w",
        compression=zipfile.ZIP_STORED,
    ) as archive:
        archive.writestr(
            execution.SOURCE_ZIP_FETCH_MEMBER,
            zip_payload,
        )

    (
        partial
        / "accessions.txt"
    ).write_text(
        fixture.ACC
        + "\n",
        encoding="ascii",
    )

    return (
        sequence_root,
        partial,
        package,
    )


def run_execution(
    tmp_path,
    *,
    opener=None,
):
    (
        sequence_root,
        partial,
        package,
    ) = make_source_partial(
        tmp_path
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    fake = (
        FakeEfetch()
        if opener is None
        else opener
    )

    result = (
        execution
        .execute_missing_datasets_gbff_recovery(
            source_partial_dir=(
                partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            targets=(
                fixture.make_target(),
            ),
            urlopen_func=fake,
            sleep_func=lambda _:
                None,
            utc_now_func=lambda:
                FIXED_TIME,
        )
    )

    return (
        sequence_root,
        partial,
        package,
        recovery_root,
        fake,
        result,
    )


def test_full_lifecycle_finalizes_and_resolves_as_fresh_recovery(
    tmp_path,
):
    (
        sequence_root,
        partial,
        _,
        recovery_root,
        fake,
        result,
    ) = run_execution(
        tmp_path
    )

    assert len(
        fake.calls
    ) == 1

    assert fake.calls[
        0
    ][
        "requested"
    ] == (
        fixture.COMP,
    )

    assert result.batch_id == BATCH

    assert result.recovery_accessions == (
        fixture.ACC,
    )

    assert result.batch_dir == (
        recovery_root
        / BATCH
    )

    assert not (
        recovery_root
        / f"{BATCH}.partial"
    ).exists()

    assert (
        result.batch_dir
        / execution.RECOVERY_EVIDENCE_NAME
    ).is_file()

    accession_dir = (
        result.batch_dir
        / authority.PACKAGE_NAME
        / "ncbi_dataset"
        / "data"
        / fixture.ACC
    )

    gbff = (
        accession_dir
        / (
            f"{fixture.ACC}"
            "_efetch_components.gbff"
        )
    )

    provenance = (
        accession_dir
        / (
            f"{fixture.ACC}"
            "_efetch_components.json"
        )
    )

    assert gbff.is_file()
    assert provenance.is_file()

    payload = json.loads(
        provenance.read_text(
            encoding="utf-8"
        )
    )

    assert payload[
        "retrieval_method"
    ] == "ncbi_efetch_nuccore"

    assert payload[
        "endpoint"
    ] == (
        "https://eutils.ncbi.nlm.nih.gov/"
        "entrez/eutils/efetch.fcgi"
    )

    assert payload[
        "requested_component_accessions"
    ] == [
        fixture.COMP,
    ]

    assert payload[
        "retrieved_at_utc"
    ] == FIXED_TIME

    resolved = (
        authority
        .resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                BATCH,
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )
    )

    assert len(
        resolved
    ) == 1

    assert (
        resolved[
            0
        ].source_class
        == authority.SOURCE_CLASS_FRESH_RECOVERY
    )

    audited = (
        execution
        .audit_finalized_missing_datasets_gbff_recovery(
            batch_dir=(
                result.batch_dir
            ),
            source_partial_dir=(
                partial
            ),
            targets=(
                fixture.make_target(),
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )
    )

    assert audited == result


def test_source_zip_fetch_mismatch_rejected_before_workspace_or_network(
    tmp_path,
):
    (
        _,
        partial,
        _,
    ) = make_source_partial(
        tmp_path,
        zip_fetch_matches=False,
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    fake = FakeEfetch()

    with pytest.raises(
        execution.MonthlyMissingDatasetsGbffExecutionError,
        match="differs from extracted",
    ):
        execution.execute_missing_datasets_gbff_recovery(
            source_partial_dir=(
                partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            targets=(
                fixture.make_target(),
            ),
            urlopen_func=fake,
            sleep_func=lambda _:
                None,
            utc_now_func=lambda:
                FIXED_TIME,
        )

    assert fake.calls == []
    assert not recovery_root.exists()


def test_non_omission_source_rejected_before_workspace_or_network(
    tmp_path,
):
    (
        _,
        partial,
        package,
    ) = make_source_partial(
        tmp_path
    )

    acc_dir = (
        package
        / "ncbi_dataset"
        / "data"
        / fixture.ACC
    )

    (
        acc_dir
        / f"{fixture.ACC}_genomic.gbff"
    ).write_bytes(
        fixture.gbff_bytes()
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    fake = FakeEfetch()

    with pytest.raises(
        execution.MonthlyMissingDatasetsGbffExecutionError,
        match="contains no missing-Datasets-GBFF recovery target",
    ):
        execution.execute_missing_datasets_gbff_recovery(
            source_partial_dir=(
                partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            targets=(
                fixture.make_target(),
            ),
            urlopen_func=fake,
            sleep_func=lambda _:
                None,
            utc_now_func=lambda:
                FIXED_TIME,
        )

    assert fake.calls == []
    assert not recovery_root.exists()


def test_efetch_failure_preserves_recovery_partial_and_source(
    tmp_path,
):
    (
        _,
        partial,
        _,
    ) = make_source_partial(
        tmp_path
    )

    before = (
        authority
        .strict_tree_fingerprint(
            partial
        )
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    fake = FakeEfetch(
        mode="fail"
    )

    with pytest.raises(
        execution.MonthlyMissingDatasetsGbffExecutionError,
        match="failed after 3 attempts",
    ):
        execution.execute_missing_datasets_gbff_recovery(
            source_partial_dir=(
                partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            targets=(
                fixture.make_target(),
            ),
            urlopen_func=fake,
            sleep_func=lambda _:
                None,
            utc_now_func=lambda:
                FIXED_TIME,
        )

    after = (
        authority
        .strict_tree_fingerprint(
            partial
        )
    )

    assert before == after
    assert len(
        fake.calls
    ) == 3

    assert (
        recovery_root
        / f"{BATCH}.partial"
    ).is_dir()

    assert not (
        recovery_root
        / BATCH
    ).exists()


def test_empty_efetch_response_fails_closed(
    tmp_path,
):
    (
        _,
        partial,
        _,
    ) = make_source_partial(
        tmp_path
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    fake = FakeEfetch(
        mode="empty"
    )

    with pytest.raises(
        execution.MonthlyMissingDatasetsGbffExecutionError,
        match="failed after 3 attempts",
    ):
        execution.execute_missing_datasets_gbff_recovery(
            source_partial_dir=(
                partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            targets=(
                fixture.make_target(),
            ),
            urlopen_func=fake,
            sleep_func=lambda _:
                None,
            utc_now_func=lambda:
                FIXED_TIME,
        )

    assert len(
        fake.calls
    ) == 3

    assert (
        recovery_root
        / f"{BATCH}.partial"
    ).is_dir()

    assert not (
        recovery_root
        / BATCH
    ).exists()


def test_wrong_efetch_component_set_is_rejected_before_finalization(
    tmp_path,
):
    (
        _,
        partial,
        _,
    ) = make_source_partial(
        tmp_path
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    fake = FakeEfetch(
        mode="wrong-component"
    )

    with pytest.raises(
        execution.MonthlyMissingDatasetsGbffExecutionError,
        match="component set mismatch",
    ):
        execution.execute_missing_datasets_gbff_recovery(
            source_partial_dir=(
                partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=BATCH,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            targets=(
                fixture.make_target(),
            ),
            urlopen_func=fake,
            sleep_func=lambda _:
                None,
            utc_now_func=lambda:
                FIXED_TIME,
        )

    assert (
        recovery_root
        / f"{BATCH}.partial"
    ).is_dir()

    assert not (
        recovery_root
        / BATCH
    ).exists()


def test_tampered_cause_evidence_is_rejected_by_final_reaudit(
    tmp_path,
):
    (
        _,
        partial,
        _,
        _,
        _,
        result,
    ) = run_execution(
        tmp_path
    )

    evidence = (
        result.batch_dir
        / execution.RECOVERY_EVIDENCE_NAME
    )

    evidence.write_text(
        "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        execution.MonthlyMissingDatasetsGbffExecutionError,
        match=(
            "does not reproduce"
            "|not canonical"
        ),
    ):
        execution.audit_finalized_missing_datasets_gbff_recovery(
            batch_dir=(
                result.batch_dir
            ),
            source_partial_dir=(
                partial
            ),
            targets=(
                fixture.make_target(),
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )
