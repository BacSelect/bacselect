from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bacselect.monthly_zenodo_archive import (
    ZENODO_DEFAULT_RECORD_MAX_BYTES,
    ZENODO_MAX_FILES_PER_RECORD,
    ZenodoArchiveContractError,
    ZenodoArchiveFile,
    ZenodoPublishedRecord,
    ZenodoReadbackObservation,
    audit_zenodo_archive_manifest,
    audit_zenodo_publication_receipt,
    audit_zenodo_readback,
    audit_zenodo_sealed_receipt,
    build_zenodo_archive_manifest,
    build_zenodo_publication_receipt,
    build_zenodo_sealed_receipt,
    serialize_zenodo_archive_manifest,
    serialize_zenodo_publication_receipt,
    serialize_zenodo_sealed_receipt,
)


RELEASE = "2026.09"

SNAPSHOT = (
    "bacselect-source-2026.09-"
    "20260901T000000Z"
)

COMMIT = "a" * 40

STAGE = "stage3b-batch-00001"


def files():
    return (
        ZenodoArchiveFile(
            "b.tar",
            "2" * 64,
            1000,
        ),
        ZenodoArchiveFile(
            "a.json",
            "1" * 64,
            100,
        ),
    )


def manifest_bytes():
    return (
        serialize_zenodo_archive_manifest(
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            record_part_index=1,
            record_part_count=1,
            files=files(),
        )
    )


def readback():
    return (
        ZenodoReadbackObservation(
            "a.json",
            "1" * 64,
            100,
        ),
        ZenodoReadbackObservation(
            "b.tar",
            "2" * 64,
            1000,
        ),
    )


def published(
    *,
    sandbox=False,
):
    prefix = (
        "10.5072"
        if sandbox
        else "10.5281"
    )

    return ZenodoPublishedRecord(
        record_id=12345678,
        concept_record_id=12345677,
        doi=(
            f"{prefix}/zenodo.12345678"
        ),
        publication_utc=(
            "2026-09-01T04:00:00+00:00"
        ),
    )


def test_manifest_is_canonical_deterministic_and_sorted():
    first = manifest_bytes()

    second = (
        serialize_zenodo_archive_manifest(
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            record_part_index=1,
            record_part_count=1,
            files=tuple(
                reversed(
                    files()
                )
            ),
        )
    )

    assert first == second

    record = json.loads(
        first.decode(
            "ascii"
        )
    )

    assert [
        value[
            "filename"
        ]
        for value in record[
            "files"
        ]
    ] == [
        "a.json",
        "b.tar",
    ]

    assert record[
        "total_bytes"
    ] == 1100


def test_manifest_refuses_more_than_100_files():
    many = tuple(
        ZenodoArchiveFile(
            f"file-{index:03d}.bin",
            f"{index:064x}",
            1,
        )
        for index in range(
            ZENODO_MAX_FILES_PER_RECORD
            + 1
        )
    )

    with pytest.raises(
        ZenodoArchiveContractError,
        match="file-count",
    ):
        build_zenodo_archive_manifest(
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            record_part_index=1,
            record_part_count=2,
            files=many,
        )


def test_manifest_refuses_default_50gb_quota_overrun():
    with pytest.raises(
        ZenodoArchiveContractError,
        match="byte quota",
    ):
        build_zenodo_archive_manifest(
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            record_part_index=1,
            record_part_count=1,
            files=(
                ZenodoArchiveFile(
                    "large.bin",
                    "3" * 64,
                    (
                        ZENODO_DEFAULT_RECORD_MAX_BYTES
                        + 1
                    ),
                ),
            ),
        )


def test_source_snapshot_requires_exact_release_day_one():
    with pytest.raises(
        ZenodoArchiveContractError,
        match="source snapshot",
    ):
        build_zenodo_archive_manifest(
            release_id=RELEASE,
            source_snapshot_id=(
                "bacselect-source-2026.09-"
                "20260902T000000Z"
            ),
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            record_part_index=1,
            record_part_count=1,
            files=files(),
        )


def test_manifest_refuses_unsafe_or_duplicate_filenames():
    for name in (
        "../x",
        "a/b",
        r"a\b",
        ".hidden",
    ):
        with pytest.raises(
            ZenodoArchiveContractError,
            match="filename",
        ):
            build_zenodo_archive_manifest(
                release_id=RELEASE,
                source_snapshot_id=SNAPSHOT,
                origin_git_commit=COMMIT,
                stage_id=STAGE,
                record_part_index=1,
                record_part_count=1,
                files=(
                    ZenodoArchiveFile(
                        name,
                        "4" * 64,
                        1,
                    ),
                ),
            )

    with pytest.raises(
        ZenodoArchiveContractError,
        match="unique",
    ):
        build_zenodo_archive_manifest(
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            record_part_index=1,
            record_part_count=1,
            files=(
                ZenodoArchiveFile(
                    "same.bin",
                    "4" * 64,
                    1,
                ),
                ZenodoArchiveFile(
                    "same.bin",
                    "5" * 64,
                    1,
                ),
            ),
        )


def test_manifest_audit_refuses_derived_tamper():
    record = json.loads(
        manifest_bytes().decode(
            "ascii"
        )
    )

    record[
        "total_bytes"
    ] += 1

    mutated = (
        json.dumps(
            record,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )

    with pytest.raises(
        ZenodoArchiveContractError,
        match="derived identity",
    ):
        audit_zenodo_archive_manifest(
            mutated
        )


def test_sha256_readback_requires_exact_file_identity():
    assert (
        audit_zenodo_readback(
            manifest_bytes(),
            observations=readback(),
        )
        == readback()
    )

    wrong = list(
        readback()
    )

    wrong[
        0
    ] = ZenodoReadbackObservation(
        "a.json",
        "f" * 64,
        100,
    )

    with pytest.raises(
        ZenodoArchiveContractError,
        match="SHA256",
    ):
        audit_zenodo_readback(
            manifest_bytes(),
            observations=wrong,
        )


def test_publication_receipt_binds_production_doi_and_sha256_readback():
    receipt = (
        build_zenodo_publication_receipt(
            manifest_bytes(),
            environment="production",
            published_record=published(),
            readback_observations=(
                readback()
            ),
            verified_at_utc=(
                "2026-09-01T04:30:00+00:00"
            ),
        )
    )

    assert receipt[
        "archive_state"
    ] == "PUBLISHED_VERIFIED"

    assert receipt[
        "zenodo_doi"
    ] == (
        "10.5281/zenodo.12345678"
    )

    assert receipt[
        "archive_manifest_sha256"
    ] == hashlib.sha256(
        manifest_bytes()
    ).hexdigest()


def test_production_and_sandbox_dois_cannot_be_confused():
    with pytest.raises(
        ZenodoArchiveContractError,
        match="environment",
    ):
        build_zenodo_publication_receipt(
            manifest_bytes(),
            environment="production",
            published_record=(
                published(
                    sandbox=True
                )
            ),
            readback_observations=(
                readback()
            ),
            verified_at_utc=(
                "2026-09-01T04:30:00+00:00"
            ),
        )

    receipt = (
        build_zenodo_publication_receipt(
            manifest_bytes(),
            environment="sandbox",
            published_record=(
                published(
                    sandbox=True
                )
            ),
            readback_observations=(
                readback()
            ),
            verified_at_utc=(
                "2026-09-01T04:30:00+00:00"
            ),
        )
    )

    assert receipt[
        "environment"
    ] == "sandbox"


def test_publication_verification_cannot_predate_publication():
    with pytest.raises(
        ZenodoArchiveContractError,
        match="predates",
    ):
        build_zenodo_publication_receipt(
            manifest_bytes(),
            environment="production",
            published_record=published(),
            readback_observations=(
                readback()
            ),
            verified_at_utc=(
                "2026-09-01T03:59:59+00:00"
            ),
        )


def test_publication_receipt_is_canonical_and_auditable():
    payload = (
        serialize_zenodo_publication_receipt(
            manifest_bytes(),
            environment="production",
            published_record=published(),
            readback_observations=(
                readback()
            ),
            verified_at_utc=(
                "2026-09-01T04:30:00+00:00"
            ),
        )
    )

    assert payload.endswith(
        b"\n"
    )

    audited = (
        audit_zenodo_publication_receipt(
            payload,
            manifest_payload=(
                manifest_bytes()
            ),
        )
    )

    assert audited[
        "archive_state"
    ] == "PUBLISHED_VERIFIED"


def test_publication_receipt_audit_refuses_tamper():
    payload = (
        serialize_zenodo_publication_receipt(
            manifest_bytes(),
            environment="production",
            published_record=published(),
            readback_observations=(
                readback()
            ),
            verified_at_utc=(
                "2026-09-01T04:30:00+00:00"
            ),
        )
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    record[
        "archive_manifest_sha256"
    ] = "f" * 64

    mutated = (
        json.dumps(
            record,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )

    with pytest.raises(
        ZenodoArchiveContractError,
        match="derived identity",
    ):
        audit_zenodo_publication_receipt(
            mutated,
            manifest_payload=(
                manifest_bytes()
            ),
        )


def test_sealed_receipt_refuses_any_time_before_45_days():
    publication = (
        serialize_zenodo_publication_receipt(
            manifest_bytes(),
            environment="production",
            published_record=published(),
            readback_observations=(
                readback()
            ),
            verified_at_utc=(
                "2026-09-01T04:30:00+00:00"
            ),
        )
    )

    with pytest.raises(
        ZenodoArchiveContractError,
        match="45-day",
    ):
        build_zenodo_sealed_receipt(
            manifest_bytes(),
            publication_receipt_payload=(
                publication
            ),
            readback_observations=(
                readback()
            ),
            sealed_verified_at_utc=(
                "2026-10-16T03:59:59+00:00"
            ),
        )


def test_sealed_receipt_requires_second_exact_readback_at_45_days():
    publication = (
        serialize_zenodo_publication_receipt(
            manifest_bytes(),
            environment="production",
            published_record=published(),
            readback_observations=(
                readback()
            ),
            verified_at_utc=(
                "2026-09-01T04:30:00+00:00"
            ),
        )
    )

    sealed = (
        build_zenodo_sealed_receipt(
            manifest_bytes(),
            publication_receipt_payload=(
                publication
            ),
            readback_observations=(
                readback()
            ),
            sealed_verified_at_utc=(
                "2026-10-16T04:00:00+00:00"
            ),
        )
    )

    assert sealed[
        "archive_state"
    ] == "SEALED_VERIFIED"

    assert sealed[
        "publication_receipt_sha256"
    ] == hashlib.sha256(
        publication
    ).hexdigest()

    wrong = list(
        readback()
    )

    wrong[
        1
    ] = ZenodoReadbackObservation(
        "b.tar",
        "f" * 64,
        1000,
    )

    with pytest.raises(
        ZenodoArchiveContractError,
        match="SHA256",
    ):
        build_zenodo_sealed_receipt(
            manifest_bytes(),
            publication_receipt_payload=(
                publication
            ),
            readback_observations=(
                wrong
            ),
            sealed_verified_at_utc=(
                "2026-10-16T04:00:00+00:00"
            ),
        )


def test_contract_is_pure_and_contains_no_network_or_token_execution():
    module = (
        Path(
            __file__
        ).resolve().parents[
            1
        ]
        / "src"
        / "bacselect"
        / "monthly_zenodo_archive.py"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "/NGS/",
        "Rhys_wkdir",
        "Project Finch",
        "SLURM_",
        "sbatch",
        "srun",
        "requests",
        "urllib",
        "urlopen",
        "subprocess",
        "ZENODO_ACCESS_TOKEN=",
        "access_token=",
        "Bearer ",
    )

    for token in forbidden:
        assert token not in module


def test_sealed_receipt_is_canonical_and_auditable():
    publication = (
        serialize_zenodo_publication_receipt(
            manifest_bytes(),
            environment="production",
            published_record=published(),
            readback_observations=(
                readback()
            ),
            verified_at_utc=(
                "2026-09-01T04:30:00+00:00"
            ),
        )
    )

    sealed = (
        serialize_zenodo_sealed_receipt(
            manifest_bytes(),
            publication_receipt_payload=(
                publication
            ),
            readback_observations=(
                readback()
            ),
            sealed_verified_at_utc=(
                "2026-10-16T04:00:00+00:00"
            ),
        )
    )

    assert sealed.endswith(
        b"\n"
    )

    audited = (
        audit_zenodo_sealed_receipt(
            sealed,
            manifest_payload=(
                manifest_bytes()
            ),
            publication_receipt_payload=(
                publication
            ),
        )
    )

    assert audited[
        "archive_state"
    ] == "SEALED_VERIFIED"


def test_sealed_receipt_audit_refuses_tamper():
    publication = (
        serialize_zenodo_publication_receipt(
            manifest_bytes(),
            environment="production",
            published_record=published(),
            readback_observations=(
                readback()
            ),
            verified_at_utc=(
                "2026-09-01T04:30:00+00:00"
            ),
        )
    )

    sealed = (
        serialize_zenodo_sealed_receipt(
            manifest_bytes(),
            publication_receipt_payload=(
                publication
            ),
            readback_observations=(
                readback()
            ),
            sealed_verified_at_utc=(
                "2026-10-16T04:00:00+00:00"
            ),
        )
    )

    record = json.loads(
        sealed.decode(
            "ascii"
        )
    )

    record[
        "publication_receipt_sha256"
    ] = "f" * 64

    mutated = (
        json.dumps(
            record,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )

    with pytest.raises(
        ZenodoArchiveContractError,
        match="derived identity",
    ):
        audit_zenodo_sealed_receipt(
            mutated,
            manifest_payload=(
                manifest_bytes()
            ),
            publication_receipt_payload=(
                publication
            ),
        )
