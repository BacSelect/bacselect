"""Deterministic local archive packaging for BacSelect Zenodo records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import os
import re
import tarfile
from typing import Any

from bacselect.monthly_zenodo_archive import (
    ZENODO_DEFAULT_RECORD_MAX_BYTES,
    ZENODO_MAX_FILES_PER_RECORD,
    ZenodoArchiveFile,
    serialize_zenodo_archive_manifest,
)


ZENODO_PACKAGE_MANIFEST_SCHEMA = (
    "bacselect-zenodo-package-manifest-v1"
)

ZENODO_PACKAGE_MANIFEST_MEMBER = (
    "BACSELECT_PACKAGE_MANIFEST.json"
)

ZENODO_PACKAGE_FORMAT = "pax-tar"

ZENODO_PACKAGE_MEMBER_MODE = 0o644
ZENODO_PACKAGE_MEMBER_UID = 0
ZENODO_PACKAGE_MEMBER_GID = 0
ZENODO_PACKAGE_MEMBER_MTIME = 0

ZENODO_RECORD_CONTROL_FILE_RESERVE = 1
ZENODO_RECORD_CONTROL_BYTE_RESERVE = 1_000_000

ZENODO_RECORD_PAYLOAD_MAX_FILES = (
    ZENODO_MAX_FILES_PER_RECORD
    - ZENODO_RECORD_CONTROL_FILE_RESERVE
)

ZENODO_RECORD_PAYLOAD_MAX_BYTES = (
    ZENODO_DEFAULT_RECORD_MAX_BYTES
    - ZENODO_RECORD_CONTROL_BYTE_RESERVE
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

GIT_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

RELEASE_ID_RE = re.compile(
    r"^[0-9]{4}\.(?:0[1-9]|1[0-2])$"
)

STAGE_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9._-]{0,127}$"
)

FILENAME_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$"
)


class ZenodoPackagingError(
    ValueError
):
    """Raised when deterministic Zenodo packaging is invalid."""


def _release_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or RELEASE_ID_RE.fullmatch(
            value
        )
        is None
    ):
        raise ZenodoPackagingError(
            "release ID must have YYYY.MM form"
        )

    return value


def _source_snapshot_id(
    value: object,
    *,
    release_id: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ZenodoPackagingError(
            "source snapshot ID does not match release identity"
        )

    prefix = (
        release_id.replace(
            ".",
            "",
        )
        + "01T"
    )

    pattern = re.compile(
        "^"
        + re.escape(
            f"bacselect-source-{release_id}-"
        )
        + re.escape(
            prefix
        )
        + r"(?:[01][0-9]|2[0-3])"
        + r"[0-5][0-9]"
        + r"[0-5][0-9]"
        + r"Z$"
    )

    if pattern.fullmatch(
        value
    ) is None:
        raise ZenodoPackagingError(
            "source snapshot ID does not match release identity"
        )

    return value


def _git_commit(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or GIT_COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise ZenodoPackagingError(
            "Git commit must be a lowercase 40-character SHA"
        )

    return value


def _stage_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or STAGE_ID_RE.fullmatch(
            value
        )
        is None
    ):
        raise ZenodoPackagingError(
            "stage ID is invalid"
        )

    return value


def _filename(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or FILENAME_RE.fullmatch(
            value
        )
        is None
    ):
        raise ZenodoPackagingError(
            "Zenodo archive filename is invalid"
        )

    return value


def _archive_file(
    value: ZenodoArchiveFile,
) -> ZenodoArchiveFile:
    if not isinstance(
        value,
        ZenodoArchiveFile,
    ):
        raise TypeError(
            "archive file has wrong type"
        )

    if SHA256_RE.fullmatch(
        value.sha256
    ) is None:
        raise ZenodoPackagingError(
            "archive file SHA256 is invalid"
        )

    if (
        isinstance(
            value.size_bytes,
            bool,
        )
        or not isinstance(
            value.size_bytes,
            int,
        )
        or value.size_bytes < 0
    ):
        raise ZenodoPackagingError(
            "archive file size is invalid"
        )

    return ZenodoArchiveFile(
        filename=_filename(
            value.filename
        ),
        sha256=value.sha256,
        size_bytes=value.size_bytes,
    )


def _canonical_json_bytes(
    payload: Mapping[
        str,
        Any,
    ],
) -> bytes:
    if not isinstance(
        payload,
        Mapping,
    ):
        raise TypeError(
            "canonical JSON payload must be a mapping"
        )

    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )


def _logical_path(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or "\\" in value
    ):
        raise ZenodoPackagingError(
            "logical path is invalid"
        )

    path = PurePosixPath(
        value
    )

    canonical = path.as_posix()

    if (
        path.is_absolute()
        or value in {
            ".",
            "..",
        }
        or canonical != value
        or any(
            part in {
                "",
                ".",
                "..",
            }
            for part in path.parts
        )
    ):
        raise ZenodoPackagingError(
            "logical path is invalid"
        )

    if value == (
        ZENODO_PACKAGE_MANIFEST_MEMBER
    ):
        raise ZenodoPackagingError(
            "logical path collides with reserved package manifest"
        )

    return value


def _sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                1024
                * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def _source_path(
    root: Path,
    logical_path: str,
) -> Path:
    logical = _logical_path(
        logical_path
    )

    root_abs = root.resolve(
        strict=True
    )

    current = root_abs

    for part in PurePosixPath(
        logical
    ).parts:
        current = (
            current
            / part
        )

        if current.is_symlink():
            raise ZenodoPackagingError(
                f"source path contains symlink: {logical}"
            )

    if not current.is_file():
        raise ZenodoPackagingError(
            f"source path is not a regular file: {logical}"
        )

    resolved = current.resolve(
        strict=True
    )

    try:
        resolved.relative_to(
            root_abs
        )
    except ValueError as exc:
        raise ZenodoPackagingError(
            f"source path escapes package root: {logical}"
        ) from exc

    return resolved


def build_zenodo_package_manifest(
    *,
    root: Path,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    stage_id: str,
    logical_paths: Sequence[
        str
    ],
) -> dict[
    str,
    object,
]:
    if (
        isinstance(
            logical_paths,
            (
                str,
                bytes,
            ),
        )
        or not isinstance(
            logical_paths,
            Sequence,
        )
    ):
        raise TypeError(
            "logical paths must be a sequence"
        )

    release = _release_id(
        release_id
    )

    snapshot = _source_snapshot_id(
        source_snapshot_id,
        release_id=release,
    )

    commit = _git_commit(
        origin_git_commit
    )

    stage = _stage_id(
        stage_id
    )

    checked = tuple(
        _logical_path(
            value
        )
        for value in logical_paths
    )

    if not checked:
        raise ZenodoPackagingError(
            "package cannot be empty"
        )

    if len(
        checked
    ) != len(
        set(
            checked
        )
    ):
        raise ZenodoPackagingError(
            "logical paths must be unique"
        )

    rows = []

    for logical in sorted(
        checked
    ):
        path = _source_path(
            Path(
                root
            ),
            logical,
        )

        rows.append(
            {
                "logical_path":
                    logical,
                "sha256":
                    _sha256_file(
                        path
                    ),
                "size_bytes":
                    path.stat().st_size,
            }
        )

    return {
        "schema_version":
            ZENODO_PACKAGE_MANIFEST_SCHEMA,
        "package_format":
            ZENODO_PACKAGE_FORMAT,
        "release_id":
            release,
        "source_snapshot_id":
            snapshot,
        "origin_git_commit":
            commit,
        "stage_id":
            stage,
        "source_file_count":
            len(
                rows
            ),
        "source_total_bytes":
            sum(
                row[
                    "size_bytes"
                ]
                for row in rows
            ),
        "files":
            rows,
    }


def serialize_zenodo_package_manifest(
    **kwargs: Any,
) -> bytes:
    return _canonical_json_bytes(
        build_zenodo_package_manifest(
            **kwargs
        )
    )


def audit_zenodo_package_manifest(
    payload: bytes,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "package manifest must be bytes"
        )

    try:
        record = json.loads(
            payload.decode(
                "ascii"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ZenodoPackagingError(
            "invalid package manifest JSON"
        ) from exc

    if (
        not isinstance(
            record,
            dict,
        )
        or _canonical_json_bytes(
            record
        )
        != payload
    ):
        raise ZenodoPackagingError(
            "package manifest is not canonical JSON"
        )

    expected = {
        "schema_version",
        "package_format",
        "release_id",
        "source_snapshot_id",
        "origin_git_commit",
        "stage_id",
        "source_file_count",
        "source_total_bytes",
        "files",
    }

    if (
        set(
            record
        )
        != expected
        or record[
            "schema_version"
        ]
        != ZENODO_PACKAGE_MANIFEST_SCHEMA
        or record[
            "package_format"
        ]
        != ZENODO_PACKAGE_FORMAT
    ):
        raise ZenodoPackagingError(
            "package manifest schema changed"
        )

    release = _release_id(
        record[
            "release_id"
        ]
    )

    _source_snapshot_id(
        record[
            "source_snapshot_id"
        ],
        release_id=release,
    )

    _git_commit(
        record[
            "origin_git_commit"
        ]
    )

    _stage_id(
        record[
            "stage_id"
        ]
    )

    if not isinstance(
        record[
            "files"
        ],
        list,
    ):
        raise ZenodoPackagingError(
            "package manifest files must be a list"
        )

    rows = []

    for row in record[
        "files"
    ]:
        if (
            not isinstance(
                row,
                dict,
            )
            or set(
                row
            )
            != {
                "logical_path",
                "sha256",
                "size_bytes",
            }
        ):
            raise ZenodoPackagingError(
                "package manifest file schema changed"
            )

        logical = _logical_path(
            row[
                "logical_path"
            ]
        )

        digest = row[
            "sha256"
        ]

        size = row[
            "size_bytes"
        ]

        if (
            not isinstance(
                digest,
                str,
            )
            or SHA256_RE.fullmatch(
                digest
            )
            is None
        ):
            raise ZenodoPackagingError(
                "package member SHA256 is invalid"
            )

        if (
            isinstance(
                size,
                bool,
            )
            or not isinstance(
                size,
                int,
            )
            or size < 0
        ):
            raise ZenodoPackagingError(
                "package member size is invalid"
            )

        rows.append(
            {
                "logical_path":
                    logical,
                "sha256":
                    digest,
                "size_bytes":
                    size,
            }
        )

    if (
        rows
        != sorted(
            rows,
            key=lambda value:
                value[
                    "logical_path"
                ],
        )
        or len(
            {
                value[
                    "logical_path"
                ]
                for value in rows
            }
        )
        != len(
            rows
        )
    ):
        raise ZenodoPackagingError(
            "package manifest file order or uniqueness changed"
        )

    if (
        record[
            "source_file_count"
        ]
        != len(
            rows
        )
        or record[
            "source_total_bytes"
        ]
        != sum(
            value[
                "size_bytes"
            ]
            for value in rows
        )
    ):
        raise ZenodoPackagingError(
            "package manifest derived counts changed"
        )

    return record


def _tarinfo(
    name: str,
    size: int,
) -> tarfile.TarInfo:
    info = tarfile.TarInfo(
        name=name
    )

    info.size = size
    info.mode = (
        ZENODO_PACKAGE_MEMBER_MODE
    )
    info.uid = (
        ZENODO_PACKAGE_MEMBER_UID
    )
    info.gid = (
        ZENODO_PACKAGE_MEMBER_GID
    )
    info.uname = ""
    info.gname = ""
    info.mtime = (
        ZENODO_PACKAGE_MEMBER_MTIME
    )
    info.type = tarfile.REGTYPE
    info.pax_headers = {}

    return info


def audit_deterministic_zenodo_package(
    package_path: Path,
    *,
    manifest_payload: bytes,
) -> None:
    manifest = (
        audit_zenodo_package_manifest(
            manifest_payload
        )
    )

    expected_names = [
        ZENODO_PACKAGE_MANIFEST_MEMBER
    ] + [
        value[
            "logical_path"
        ]
        for value in manifest[
            "files"
        ]
    ]

    try:
        with tarfile.open(
            package_path,
            mode="r:",
        ) as archive:
            members = (
                archive.getmembers()
            )

            if [
                member.name
                for member in members
            ] != expected_names:
                raise ZenodoPackagingError(
                    "package member inventory changed"
                )

            for member in members:
                if (
                    not member.isfile()
                    or member.mode
                    != ZENODO_PACKAGE_MEMBER_MODE
                    or member.uid
                    != ZENODO_PACKAGE_MEMBER_UID
                    or member.gid
                    != ZENODO_PACKAGE_MEMBER_GID
                    or member.uname
                    != ""
                    or member.gname
                    != ""
                    or member.mtime
                    != ZENODO_PACKAGE_MEMBER_MTIME
                ):
                    raise ZenodoPackagingError(
                        "package member metadata changed"
                    )

            manifest_handle = (
                archive.extractfile(
                    members[
                        0
                    ]
                )
            )

            observed_manifest = (
                manifest_handle.read()
                if manifest_handle
                is not None
                else None
            )

            if observed_manifest != (
                manifest_payload
            ):
                raise ZenodoPackagingError(
                    "embedded package manifest changed"
                )

            by_name = {
                value[
                    "logical_path"
                ]:
                    value
                for value in manifest[
                    "files"
                ]
            }

            for member in members[
                1:
            ]:
                handle = (
                    archive.extractfile(
                        member
                    )
                )

                if handle is None:
                    raise ZenodoPackagingError(
                        "package member cannot be read"
                    )

                digest = hashlib.sha256()
                size = 0

                while True:
                    block = handle.read(
                        1024
                        * 1024
                    )

                    if not block:
                        break

                    digest.update(
                        block
                    )

                    size += len(
                        block
                    )

                expected = by_name[
                    member.name
                ]

                if (
                    digest.hexdigest()
                    != expected[
                        "sha256"
                    ]
                    or size
                    != expected[
                        "size_bytes"
                    ]
                ):
                    raise ZenodoPackagingError(
                        "package member content changed"
                    )

    except (
        tarfile.TarError,
        OSError,
    ) as exc:
        raise ZenodoPackagingError(
            "invalid deterministic package"
        ) from exc


def write_deterministic_zenodo_package(
    *,
    root: Path,
    logical_paths: Sequence[
        str
    ],
    output_path: Path,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    stage_id: str,
) -> ZenodoArchiveFile:
    output = Path(
        output_path
    )

    if output.exists():
        raise ZenodoPackagingError(
            "package output already exists"
        )

    _filename(
        output.name
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_payload = (
        serialize_zenodo_package_manifest(
            root=Path(
                root
            ),
            release_id=release_id,
            source_snapshot_id=(
                source_snapshot_id
            ),
            origin_git_commit=(
                origin_git_commit
            ),
            stage_id=stage_id,
            logical_paths=(
                logical_paths
            ),
        )
    )

    manifest = json.loads(
        manifest_payload.decode(
            "ascii"
        )
    )

    partial = output.with_name(
        output.name
        + ".partial"
    )

    if partial.exists():
        raise ZenodoPackagingError(
            "package partial output already exists"
        )

    try:
        with partial.open(
            "xb"
        ) as raw:
            with tarfile.open(
                fileobj=raw,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                archive.addfile(
                    _tarinfo(
                        ZENODO_PACKAGE_MANIFEST_MEMBER,
                        len(
                            manifest_payload
                        ),
                    ),
                    io.BytesIO(
                        manifest_payload
                    ),
                )

                for row in manifest[
                    "files"
                ]:
                    source = _source_path(
                        Path(
                            root
                        ),
                        row[
                            "logical_path"
                        ],
                    )

                    if (
                        source.stat().st_size
                        != row[
                            "size_bytes"
                        ]
                        or _sha256_file(
                            source
                        )
                        != row[
                            "sha256"
                        ]
                    ):
                        raise ZenodoPackagingError(
                            "source file changed during package creation"
                        )

                    with source.open(
                        "rb"
                    ) as handle:
                        archive.addfile(
                            _tarinfo(
                                row[
                                    "logical_path"
                                ],
                                row[
                                    "size_bytes"
                                ],
                            ),
                            handle,
                        )

            raw.flush()
            os.fsync(
                raw.fileno()
            )

        audit_deterministic_zenodo_package(
            partial,
            manifest_payload=(
                manifest_payload
            ),
        )

        os.replace(
            partial,
            output,
        )

    except Exception:
        try:
            partial.unlink()
        except FileNotFoundError:
            pass

        raise

    return ZenodoArchiveFile(
        filename=output.name,
        sha256=_sha256_file(
            output
        ),
        size_bytes=(
            output.stat().st_size
        ),
    )


def plan_zenodo_record_parts(
    files: Sequence[
        ZenodoArchiveFile
    ],
) -> tuple[
    tuple[
        ZenodoArchiveFile,
        ...,
    ],
    ...,
]:
    if (
        isinstance(
            files,
            (
                str,
                bytes,
            ),
        )
        or not isinstance(
            files,
            Sequence,
        )
    ):
        raise TypeError(
            "Zenodo archive files must be a sequence"
        )

    checked = tuple(
        _archive_file(
            value
        )
        for value in files
    )

    ordered = tuple(
        sorted(
            checked,
            key=lambda value:
                value.filename,
        )
    )

    if not ordered:
        raise ZenodoPackagingError(
            "record-part plan cannot be empty"
        )

    names = [
        value.filename
        for value in ordered
    ]

    if len(
        names
    ) != len(
        set(
            names
        )
    ):
        raise ZenodoPackagingError(
            "archive filenames must be unique"
        )

    parts = []
    current = []
    current_bytes = 0

    for value in ordered:
        if (
            value.size_bytes
            > ZENODO_RECORD_PAYLOAD_MAX_BYTES
        ):
            raise ZenodoPackagingError(
                "single archive file exceeds Zenodo record quota"
            )

        if (
            current
            and (
                len(
                    current
                )
                >= ZENODO_RECORD_PAYLOAD_MAX_FILES
                or current_bytes
                + value.size_bytes
                > ZENODO_RECORD_PAYLOAD_MAX_BYTES
            )
        ):
            parts.append(
                tuple(
                    current
                )
            )

            current = []
            current_bytes = 0

        current.append(
            value
        )

        current_bytes += (
            value.size_bytes
        )

    if current:
        parts.append(
            tuple(
                current
            )
        )

    return tuple(
        parts
    )


def build_zenodo_record_part_manifests(
    *,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    stage_id: str,
    files: Sequence[
        ZenodoArchiveFile
    ],
) -> tuple[
    bytes,
    ...,
]:
    parts = plan_zenodo_record_parts(
        files
    )

    count = len(
        parts
    )

    return tuple(
        serialize_zenodo_archive_manifest(
            release_id=release_id,
            source_snapshot_id=(
                source_snapshot_id
            ),
            origin_git_commit=(
                origin_git_commit
            ),
            stage_id=stage_id,
            record_part_index=index,
            record_part_count=count,
            files=part,
        )
        for index, part in enumerate(
            parts,
            start=1,
        )
    )
