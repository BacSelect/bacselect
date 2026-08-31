from __future__ import annotations

import json
import os
from pathlib import Path
import tarfile

import pytest

from bacselect.monthly_zenodo_archive import (
    ZENODO_DEFAULT_RECORD_MAX_BYTES,
    ZENODO_MAX_FILES_PER_RECORD,
    ZenodoArchiveFile,
)
from bacselect.monthly_zenodo_packaging import (
    ZENODO_PACKAGE_MANIFEST_MEMBER,
    ZENODO_RECORD_CONTROL_BYTE_RESERVE,
    ZENODO_RECORD_CONTROL_FILE_RESERVE,
    ZENODO_RECORD_PAYLOAD_MAX_BYTES,
    ZENODO_RECORD_PAYLOAD_MAX_FILES,
    ZenodoPackagingError,
    audit_deterministic_zenodo_package,
    audit_zenodo_package_manifest,
    build_zenodo_record_part_manifests,
    plan_zenodo_record_parts,
    serialize_zenodo_package_manifest,
    write_deterministic_zenodo_package,
)


RELEASE = "2026.09"

SNAPSHOT = (
    "bacselect-source-2026.09-"
    "20260901T000000Z"
)

COMMIT = "a" * 40

STAGE = "stage3b-batch-00001"


def make_sources(
    root: Path,
):
    (
        root
        / "b"
    ).mkdir(
        parents=True
    )

    (
        root
        / "a.txt"
    ).write_bytes(
        b"alpha\n"
    )

    (
        root
        / "b"
        / "c.bin"
    ).write_bytes(
        b"xyz"
    )

    return (
        "b/c.bin",
        "a.txt",
    )


def package_kwargs(
    root: Path,
):
    return {
        "root":
            root,
        "release_id":
            RELEASE,
        "source_snapshot_id":
            SNAPSHOT,
        "origin_git_commit":
            COMMIT,
        "stage_id":
            STAGE,
    }


def archive_file(
    name: str,
    size: int,
    *,
    digest: str = "1" * 64,
):
    return ZenodoArchiveFile(
        filename=name,
        sha256=digest,
        size_bytes=size,
    )


def test_package_manifest_is_deterministic_and_sorted(
    tmp_path,
):
    paths = make_sources(
        tmp_path
    )

    first = serialize_zenodo_package_manifest(
        **package_kwargs(
            tmp_path
        ),
        logical_paths=paths,
    )

    second = serialize_zenodo_package_manifest(
        **package_kwargs(
            tmp_path
        ),
        logical_paths=tuple(
            reversed(
                paths
            )
        ),
    )

    assert first == second

    record = json.loads(
        first.decode(
            "ascii"
        )
    )

    assert [
        value[
            "logical_path"
        ]
        for value in record[
            "files"
        ]
    ] == [
        "a.txt",
        "b/c.bin",
    ]


def test_unsafe_paths_are_rejected(
    tmp_path,
):
    make_sources(
        tmp_path
    )

    for value in (
        "../x",
        "/abs",
        r"a\b",
        ".",
        ZENODO_PACKAGE_MANIFEST_MEMBER,
    ):
        with pytest.raises(
            ZenodoPackagingError
        ):
            serialize_zenodo_package_manifest(
                **package_kwargs(
                    tmp_path
                ),
                logical_paths=(
                    value,
                ),
            )


def test_duplicate_paths_are_rejected(
    tmp_path,
):
    make_sources(
        tmp_path
    )

    with pytest.raises(
        ZenodoPackagingError,
        match="unique",
    ):
        serialize_zenodo_package_manifest(
            **package_kwargs(
                tmp_path
            ),
            logical_paths=(
                "a.txt",
                "a.txt",
            ),
        )


def test_symlinks_are_rejected(
    tmp_path,
):
    make_sources(
        tmp_path
    )

    (
        tmp_path
        / "link"
    ).symlink_to(
        tmp_path
        / "a.txt"
    )

    with pytest.raises(
        ZenodoPackagingError,
        match="symlink",
    ):
        serialize_zenodo_package_manifest(
            **package_kwargs(
                tmp_path
            ),
            logical_paths=(
                "link",
            ),
        )


def test_package_bytes_are_deterministic_and_ignore_source_metadata(
    tmp_path,
):
    root = (
        tmp_path
        / "root"
    )

    root.mkdir()

    paths = make_sources(
        root
    )

    first_path = (
        tmp_path
        / "one.tar"
    )

    second_path = (
        tmp_path
        / "two.tar"
    )

    first = (
        write_deterministic_zenodo_package(
            **package_kwargs(
                root
            ),
            logical_paths=paths,
            output_path=first_path,
        )
    )

    os.chmod(
        root
        / "a.txt",
        0o600,
    )

    os.utime(
        root
        / "a.txt",
        (
            123456789,
            123456789,
        ),
    )

    second = (
        write_deterministic_zenodo_package(
            **package_kwargs(
                root
            ),
            logical_paths=tuple(
                reversed(
                    paths
                )
            ),
            output_path=second_path,
        )
    )

    assert (
        first_path.read_bytes()
        == second_path.read_bytes()
    )

    assert first.sha256 == (
        second.sha256
    )

    assert first.size_bytes == (
        second.size_bytes
    )


def test_package_member_order_and_metadata_are_normalized(
    tmp_path,
):
    root = (
        tmp_path
        / "root"
    )

    root.mkdir()

    paths = make_sources(
        root
    )

    output = (
        tmp_path
        / "package.tar"
    )

    write_deterministic_zenodo_package(
        **package_kwargs(
            root
        ),
        logical_paths=paths,
        output_path=output,
    )

    with tarfile.open(
        output,
        "r:",
    ) as archive:
        members = archive.getmembers()

        assert [
            member.name
            for member in members
        ] == [
            ZENODO_PACKAGE_MANIFEST_MEMBER,
            "a.txt",
            "b/c.bin",
        ]

        for member in members:
            assert (
                member.mode,
                member.uid,
                member.gid,
                member.uname,
                member.gname,
                member.mtime,
            ) == (
                0o644,
                0,
                0,
                "",
                "",
                0,
            )


def test_embedded_manifest_matches_source_content(
    tmp_path,
):
    root = (
        tmp_path
        / "root"
    )

    root.mkdir()

    paths = make_sources(
        root
    )

    output = (
        tmp_path
        / "package.tar"
    )

    write_deterministic_zenodo_package(
        **package_kwargs(
            root
        ),
        logical_paths=paths,
        output_path=output,
    )

    with tarfile.open(
        output,
        "r:",
    ) as archive:
        handle = archive.extractfile(
            ZENODO_PACKAGE_MANIFEST_MEMBER
        )

        assert handle is not None

        manifest_payload = (
            handle.read()
        )

    record = json.loads(
        manifest_payload.decode(
            "ascii"
        )
    )

    assert record[
        "source_file_count"
    ] == 2

    assert record[
        "source_total_bytes"
    ] == 9

    audit_deterministic_zenodo_package(
        output,
        manifest_payload=(
            manifest_payload
        ),
    )


def test_existing_output_is_refused(
    tmp_path,
):
    root = (
        tmp_path
        / "root"
    )

    root.mkdir()

    make_sources(
        root
    )

    output = (
        tmp_path
        / "package.tar"
    )

    output.write_bytes(
        b"existing"
    )

    with pytest.raises(
        ZenodoPackagingError,
        match="already exists",
    ):
        write_deterministic_zenodo_package(
            **package_kwargs(
                root
            ),
            logical_paths=(
                "a.txt",
            ),
            output_path=output,
        )


def test_record_part_plan_is_deterministic_and_sorted():
    parts = plan_zenodo_record_parts(
        (
            archive_file(
                "b.tar",
                2,
            ),
            archive_file(
                "a.tar",
                1,
            ),
        )
    )

    assert [
        [
            value.filename
            for value in part
        ]
        for part in parts
    ] == [
        [
            "a.tar",
            "b.tar",
        ]
    ]


def test_record_part_plan_splits_at_byte_limit():
    parts = plan_zenodo_record_parts(
        (
            archive_file(
                "a.tar",
                ZENODO_RECORD_PAYLOAD_MAX_BYTES
                - 1,
            ),
            archive_file(
                "b.tar",
                2,
            ),
        )
    )

    assert len(
        parts
    ) == 2


def test_record_part_plan_reserves_control_file_slot():
    files = tuple(
        ZenodoArchiveFile(
            filename=f"{index:03d}.tar",
            sha256=f"{index:064x}",
            size_bytes=1,
        )
        for index in range(
            ZENODO_RECORD_PAYLOAD_MAX_FILES
            + 1
        )
    )

    parts = plan_zenodo_record_parts(
        files
    )

    assert [
        len(
            part
        )
        for part in parts
    ] == [
        99,
        1,
    ]


def test_record_part_plan_rejects_oversized_single_file():
    with pytest.raises(
        ZenodoPackagingError,
        match="single",
    ):
        plan_zenodo_record_parts(
            (
                archive_file(
                    "x.tar",
                    ZENODO_RECORD_PAYLOAD_MAX_BYTES
                    + 1,
                ),
            )
        )


def test_record_part_plan_rejects_duplicate_filename():
    with pytest.raises(
        ZenodoPackagingError,
        match="unique",
    ):
        plan_zenodo_record_parts(
            (
                archive_file(
                    "x.tar",
                    1,
                ),
                archive_file(
                    "x.tar",
                    1,
                    digest="2" * 64,
                ),
            )
        )


def test_record_part_manifests_bind_part_geometry():
    files = (
        archive_file(
            "a.tar",
            ZENODO_RECORD_PAYLOAD_MAX_BYTES
            - 1,
        ),
        archive_file(
            "b.tar",
            2,
        ),
    )

    manifests = (
        build_zenodo_record_part_manifests(
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            files=files,
        )
    )

    assert len(
        manifests
    ) == 2

    records = [
        json.loads(
            value.decode(
                "ascii"
            )
        )
        for value in manifests
    ]

    assert [
        value[
            "record_part_index"
        ]
        for value in records
    ] == [
        1,
        2,
    ]

    assert all(
        value[
            "record_part_count"
        ]
        == 2
        for value in records
    )


def test_contract_has_no_network_or_history_bindings():
    module = (
        Path(
            __file__
        ).resolve().parents[
            1
        ]
        / "src"
        / "bacselect"
        / "monthly_zenodo_packaging.py"
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "requests",
        "urllib",
        "subprocess",
        "/NGS/",
        "Rhys_wkdir",
        "Project Finch",
        "SLURM_",
        "sbatch",
        "srun",
    ):
        assert token not in module


def test_package_manifest_audit_refuses_derived_tamper(
    tmp_path,
):
    make_sources(
        tmp_path
    )

    payload = (
        serialize_zenodo_package_manifest(
            **package_kwargs(
                tmp_path
            ),
            logical_paths=(
                "a.txt",
            ),
        )
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    record[
        "source_total_bytes"
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
        ZenodoPackagingError,
        match="derived counts",
    ):
        audit_zenodo_package_manifest(
            mutated
        )


def test_package_manifest_binds_exact_monthly_source_snapshot(
    tmp_path,
):
    make_sources(
        tmp_path
    )

    with pytest.raises(
        ZenodoPackagingError,
        match="source snapshot",
    ):
        serialize_zenodo_package_manifest(
            root=tmp_path,
            release_id=RELEASE,
            source_snapshot_id=(
                "bacselect-source-2026.09-"
                "20260902T000000Z"
            ),
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            logical_paths=(
                "a.txt",
            ),
        )


def test_noncanonical_posix_logical_paths_are_rejected(
    tmp_path,
):
    for value in (
        "a//b",
        "a/./b",
        "a/",
        "./a",
    ):
        with pytest.raises(
            ZenodoPackagingError,
            match="logical path",
        ):
            serialize_zenodo_package_manifest(
                **package_kwargs(
                    tmp_path
                ),
                logical_paths=(
                    value,
                ),
            )


def test_outer_archive_manifest_fits_frozen_record_headroom():
    files = []

    remaining_files = (
        ZENODO_RECORD_PAYLOAD_MAX_FILES
        - 1
    )

    for index in range(
        ZENODO_RECORD_PAYLOAD_MAX_FILES
    ):
        prefix = (
            f"{index:02d}-"
        )

        filename = (
            prefix
            + "x"
            * (
                255
                - len(
                    prefix
                )
            )
        )

        size = (
            ZENODO_RECORD_PAYLOAD_MAX_BYTES
            - remaining_files
            if index == 0
            else 1
        )

        files.append(
            ZenodoArchiveFile(
                filename=filename,
                sha256=f"{index:064x}",
                size_bytes=size,
            )
        )

    assert len(
        files
    ) == (
        ZENODO_RECORD_PAYLOAD_MAX_FILES
    )

    assert sum(
        value.size_bytes
        for value in files
    ) == (
        ZENODO_RECORD_PAYLOAD_MAX_BYTES
    )

    manifests = (
        build_zenodo_record_part_manifests(
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            origin_git_commit=COMMIT,
            stage_id=STAGE,
            files=tuple(
                files
            ),
        )
    )

    assert len(
        manifests
    ) == 1

    outer_manifest = manifests[
        0
    ]

    assert len(
        outer_manifest
    ) <= (
        ZENODO_RECORD_CONTROL_BYTE_RESERVE
    )

    assert (
        len(
            files
        )
        + ZENODO_RECORD_CONTROL_FILE_RESERVE
        <= ZENODO_MAX_FILES_PER_RECORD
    )

    assert (
        sum(
            value.size_bytes
            for value in files
        )
        + len(
            outer_manifest
        )
        <= ZENODO_DEFAULT_RECORD_MAX_BYTES
    )
