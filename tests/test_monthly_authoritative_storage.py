from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bacselect.monthly_authoritative_storage import (
    AuthoritativeArtifact,
    AuthoritativeStorageError,
    StoredObjectObservation,
    artifact_from_bytes,
    artifact_from_file,
    audit_authoritative_manifest,
    audit_authoritative_receipt,
    authoritative_manifest_key,
    authoritative_receipt_key,
    build_authoritative_manifest,
    expected_stored_objects,
    object_key_for_sha256,
    serialize_authoritative_manifest,
    serialize_authoritative_receipt,
)


RELEASE = "2026.09"

SNAPSHOT = (
    "bacselect-source-2026.09-"
    "20260901T000000Z"
)

COMMIT = "a" * 40

STAGE = "stage3b-batch-00001"


def artifacts():
    return (
        artifact_from_bytes(
            "attempt-origin.json",
            b"attempt\n",
        ),
        artifact_from_bytes(
            "package/data/genome.fna",
            b"ACGT\n",
        ),
    )


def manifest_bytes(
    values=None,
):
    if values is None:
        values = artifacts()

    return serialize_authoritative_manifest(
        release_id=RELEASE,
        source_snapshot_id=SNAPSHOT,
        origin_git_commit=COMMIT,
        stage_id=STAGE,
        artifacts=values,
    )


def test_object_key_is_content_addressed():
    digest = "1" * 64

    assert object_key_for_sha256(
        digest
    ) == (
        "objects/sha256/"
        "11/11/"
        + digest
    )


def test_manifest_is_canonical_deterministic_and_sorted():
    values = artifacts()

    first = manifest_bytes(
        values
    )

    second = manifest_bytes(
        tuple(
            reversed(
                values
            )
        )
    )

    assert first == second

    observed = json.loads(
        first.decode(
            "ascii"
        )
    )

    assert [
        item[
            "logical_path"
        ]
        for item in observed[
            "artifacts"
        ]
    ] == [
        "attempt-origin.json",
        "package/data/genome.fna",
    ]

    assert first.endswith(
        b"\n"
    )


def test_same_content_is_deduplicated_but_logical_paths_are_preserved():
    payload = b"same\n"

    values = (
        artifact_from_bytes(
            "one.txt",
            payload,
        ),
        artifact_from_bytes(
            "two.txt",
            payload,
        ),
    )

    record = build_authoritative_manifest(
        release_id=RELEASE,
        source_snapshot_id=SNAPSHOT,
        origin_git_commit=COMMIT,
        stage_id=STAGE,
        artifacts=values,
    )

    assert record[
        "artifact_count"
    ] == 2

    assert record[
        "unique_object_count"
    ] == 1

    assert record[
        "total_logical_bytes"
    ] == 10

    assert record[
        "total_unique_bytes"
    ] == 5


def test_unsafe_logical_paths_are_rejected():
    unsafe = (
        "/absolute",
        "../escape",
        "a/../escape",
        "a//b",
        "./a",
        "a\\b",
    )

    for value in unsafe:
        with pytest.raises(
            AuthoritativeStorageError
        ):
            artifact_from_bytes(
                value,
                b"x",
            )


def test_duplicate_logical_paths_are_rejected():
    values = (
        artifact_from_bytes(
            "same.txt",
            b"one",
        ),
        artifact_from_bytes(
            "same.txt",
            b"two",
        ),
    )

    with pytest.raises(
        AuthoritativeStorageError,
        match="unique",
    ):
        manifest_bytes(
            values
        )


def test_source_snapshot_must_match_release():
    with pytest.raises(
        AuthoritativeStorageError,
        match="source snapshot",
    ):
        serialize_authoritative_manifest(
            release_id=RELEASE,
            source_snapshot_id=(
                "bacselect-source-2026.10-"
                "20261001T000000Z"
            ),
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            artifacts=artifacts(),
        )


def test_manifest_audit_refuses_mutated_object_key():
    payload = manifest_bytes()

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    record[
        "artifacts"
    ][0][
        "object_key"
    ] = (
        "objects/sha256/"
        + "f" * 64
    )

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
        AuthoritativeStorageError,
        match="object key",
    ):
        audit_authoritative_manifest(
            mutated
        )


def test_manifest_key_is_release_commit_stage_and_content_addressed():
    payload = manifest_bytes()

    digest = hashlib.sha256(
        payload
    ).hexdigest()

    assert authoritative_manifest_key(
        payload
    ) == (
        "manifests/monthly/"
        f"{RELEASE}/"
        "production/"
        f"{COMMIT}/"
        f"{STAGE}/"
        "sha256/"
        f"{digest}.json"
    )


def test_expected_storage_objects_include_manifest_itself():
    payload = manifest_bytes()

    observed = expected_stored_objects(
        payload
    )

    keys = {
        value.object_key
        for value in observed
    }

    assert authoritative_manifest_key(
        payload
    ) in keys

    assert len(
        observed
    ) == 3


def test_receipt_refuses_missing_or_incorrect_readback():
    payload = manifest_bytes()

    expected = expected_stored_objects(
        payload
    )

    with pytest.raises(
        AuthoritativeStorageError,
        match="readback",
    ):
        serialize_authoritative_receipt(
            payload,
            observed_objects=(
                expected[:-1]
            ),
        )

    wrong = list(
        expected
    )

    first = wrong[
        0
    ]

    wrong[
        0
    ] = StoredObjectObservation(
        object_key=(
            first.object_key
        ),
        sha256="f" * 64,
        size_bytes=(
            first.size_bytes
        ),
    )

    with pytest.raises(
        AuthoritativeStorageError,
        match="readback",
    ):
        serialize_authoritative_receipt(
            payload,
            observed_objects=(
                wrong
            ),
        )


def test_verified_receipt_is_canonical_auditable_and_content_addressed():
    payload = manifest_bytes()

    observed = expected_stored_objects(
        payload
    )

    receipt = (
        serialize_authoritative_receipt(
            payload,
            observed_objects=(
                observed
            ),
        )
    )

    audited = audit_authoritative_receipt(
        receipt,
        manifest_payload=(
            payload
        ),
    )

    assert audited[
        "verified_object_count"
    ] == len(
        observed
    )

    receipt_digest = hashlib.sha256(
        receipt
    ).hexdigest()

    assert authoritative_receipt_key(
        receipt,
        manifest_payload=(
            payload
        ),
    ) == (
        "receipts/monthly/"
        f"{RELEASE}/"
        "production/"
        f"{COMMIT}/"
        f"{STAGE}/"
        "sha256/"
        f"{receipt_digest}.json"
    )


def test_file_hashing_and_contract_are_portable_and_history_free(
    tmp_path,
):
    source = (
        tmp_path
        / "artifact.bin"
    )

    source.write_bytes(
        b"portable\n"
    )

    artifact = artifact_from_file(
        "artifact.bin",
        source,
    )

    assert artifact == AuthoritativeArtifact(
        logical_path="artifact.bin",
        sha256=hashlib.sha256(
            b"portable\n"
        ).hexdigest(),
        size_bytes=9,
    )

    module = (
        Path(__file__).resolve().parents[
            1
        ]
        / "src"
        / "bacselect"
        / "monthly_authoritative_storage.py"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "/NGS/",
        "Rhys_wkdir",
        "finch-ncbi-datasets",
        "Project Finch",
        "SLURM_",
        "sbatch",
        "srun",
        "15_326",
        "70_477",
        "55_151",
    )

    for token in forbidden:
        assert token not in module


def test_source_snapshot_requires_exact_stage1_timestamp_form():
    malformed = (
        "bacselect-source-2026.09-"
        "not-a-timestamp"
    )

    with pytest.raises(
        AuthoritativeStorageError,
        match="source snapshot",
    ):
        serialize_authoritative_manifest(
            release_id=RELEASE,
            source_snapshot_id=malformed,
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            artifacts=artifacts(),
        )


def test_source_snapshot_timestamp_must_be_release_day_one():
    wrong_day = (
        "bacselect-source-2026.09-"
        "20260902T000000Z"
    )

    with pytest.raises(
        AuthoritativeStorageError,
        match="source snapshot",
    ):
        serialize_authoritative_manifest(
            release_id=RELEASE,
            source_snapshot_id=wrong_day,
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            artifacts=artifacts(),
        )
