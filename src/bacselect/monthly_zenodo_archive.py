"""Pure Zenodo scholarly-archive contract for BacSelect monthly production."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import re
from typing import Any


ZENODO_ARCHIVE_MANIFEST_SCHEMA = (
    "bacselect-zenodo-archive-manifest-v1"
)

ZENODO_PUBLICATION_RECEIPT_SCHEMA = (
    "bacselect-zenodo-publication-receipt-v1"
)

ZENODO_SEALED_RECEIPT_SCHEMA = (
    "bacselect-zenodo-sealed-receipt-v1"
)

ZENODO_PROVIDER_ID = "zenodo"

ZENODO_DEFAULT_RECORD_MAX_BYTES = (
    50_000_000_000
)

ZENODO_MAX_FILES_PER_RECORD = 100

ZENODO_SEAL_MIN_DAYS = 45

ZENODO_PRODUCTION_DOI_PREFIX = (
    "10.5281/zenodo."
)

ZENODO_SANDBOX_DOI_PREFIX = (
    "10.5072/zenodo."
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

DOI_RE = re.compile(
    r"^10\.(?:5281|5072)/zenodo\.[0-9]+$"
)


class ZenodoArchiveContractError(
    ValueError
):
    """Raised when the frozen Zenodo archive contract is violated."""


@dataclass(
    frozen=True,
    order=True,
)
class ZenodoArchiveFile:
    filename: str
    sha256: str
    size_bytes: int


@dataclass(
    frozen=True,
    order=True,
)
class ZenodoReadbackObservation:
    filename: str
    sha256: str
    size_bytes: int


@dataclass(
    frozen=True,
)
class ZenodoPublishedRecord:
    record_id: int
    concept_record_id: int
    doi: str
    publication_utc: str


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


def _sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise ZenodoArchiveContractError(
            f"{label} must be a lowercase SHA256"
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
        raise ZenodoArchiveContractError(
            "Git commit must be a lowercase 40-character SHA"
        )

    return value


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
        raise ZenodoArchiveContractError(
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
        raise ZenodoArchiveContractError(
            "source snapshot ID does not match release identity"
        )

    timestamp_prefix = (
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
            timestamp_prefix
        )
        + r"(?:[01][0-9]|2[0-3])"
        + r"[0-5][0-9]"
        + r"[0-5][0-9]"
        + r"Z$"
    )

    if pattern.fullmatch(
        value
    ) is None:
        raise ZenodoArchiveContractError(
            "source snapshot ID does not match release identity"
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
        raise ZenodoArchiveContractError(
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
        raise ZenodoArchiveContractError(
            "Zenodo archive filename is invalid"
        )

    return value


def _size_bytes(
    value: object,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 0
    ):
        raise ZenodoArchiveContractError(
            "file size must be a non-negative integer"
        )

    return value


def _positive_record_id(
    value: object,
    *,
    label: str,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value <= 0
    ):
        raise ZenodoArchiveContractError(
            f"{label} must be a positive integer"
        )

    return value


def _environment(
    value: object,
) -> str:
    if value not in {
        "production",
        "sandbox",
    }:
        raise ZenodoArchiveContractError(
            "Zenodo environment is invalid"
        )

    return str(
        value
    )


def _doi(
    value: object,
    *,
    environment: str,
) -> str:
    env = _environment(
        environment
    )

    if (
        not isinstance(
            value,
            str,
        )
        or DOI_RE.fullmatch(
            value
        )
        is None
    ):
        raise ZenodoArchiveContractError(
            "Zenodo DOI is invalid"
        )

    prefix = (
        ZENODO_PRODUCTION_DOI_PREFIX
        if env == "production"
        else ZENODO_SANDBOX_DOI_PREFIX
    )

    if not value.startswith(
        prefix
    ):
        raise ZenodoArchiveContractError(
            "Zenodo DOI does not match archive environment"
        )

    return value


def _utc_datetime(
    value: object,
    *,
    label: str,
) -> datetime:
    if not isinstance(
        value,
        str,
    ):
        raise ZenodoArchiveContractError(
            f"{label} must be UTC text"
        )

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError as exc:
        raise ZenodoArchiveContractError(
            f"{label} is invalid"
        ) from exc

    if (
        parsed.tzinfo
        is None
        or parsed.utcoffset()
        != timedelta(
            0
        )
    ):
        raise ZenodoArchiveContractError(
            f"{label} must be UTC"
        )

    return parsed


def _audit_archive_file(
    value: ZenodoArchiveFile,
) -> ZenodoArchiveFile:
    if not isinstance(
        value,
        ZenodoArchiveFile,
    ):
        raise TypeError(
            "Zenodo archive file has wrong type"
        )

    return ZenodoArchiveFile(
        filename=_filename(
            value.filename
        ),
        sha256=_sha256(
            value.sha256,
            label="archive file SHA256",
        ),
        size_bytes=_size_bytes(
            value.size_bytes
        ),
    )


def build_zenodo_archive_manifest(
    *,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    stage_id: str,
    record_part_index: int,
    record_part_count: int,
    files: Sequence[
        ZenodoArchiveFile
    ],
) -> dict[
    str,
    object,
]:
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

    if (
        isinstance(
            record_part_index,
            bool,
        )
        or not isinstance(
            record_part_index,
            int,
        )
        or record_part_index < 1
    ):
        raise ZenodoArchiveContractError(
            "record part index must be positive"
        )

    if (
        isinstance(
            record_part_count,
            bool,
        )
        or not isinstance(
            record_part_count,
            int,
        )
        or record_part_count < 1
    ):
        raise ZenodoArchiveContractError(
            "record part count must be positive"
        )

    if (
        record_part_index
        > record_part_count
    ):
        raise ZenodoArchiveContractError(
            "record part index exceeds part count"
        )

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
        _audit_archive_file(
            value
        )
        for value in files
    )

    if not checked:
        raise ZenodoArchiveContractError(
            "Zenodo archive manifest cannot be empty"
        )

    if len(
        checked
    ) > ZENODO_MAX_FILES_PER_RECORD:
        raise ZenodoArchiveContractError(
            "Zenodo record exceeds frozen file-count limit"
        )

    names = [
        value.filename
        for value in checked
    ]

    if len(
        names
    ) != len(
        set(
            names
        )
    ):
        raise ZenodoArchiveContractError(
            "Zenodo archive filenames must be unique"
        )

    total_bytes = sum(
        value.size_bytes
        for value in checked
    )

    if (
        total_bytes
        > ZENODO_DEFAULT_RECORD_MAX_BYTES
    ):
        raise ZenodoArchiveContractError(
            "Zenodo record exceeds frozen default byte quota"
        )

    ordered = tuple(
        sorted(
            checked,
            key=lambda value:
                value.filename,
        )
    )

    return {
        "schema_version":
            ZENODO_ARCHIVE_MANIFEST_SCHEMA,
        "provider_id":
            ZENODO_PROVIDER_ID,
        "release_id":
            release,
        "source_snapshot_id":
            snapshot,
        "origin_git_commit":
            commit,
        "stage_id":
            stage,
        "record_part_index":
            record_part_index,
        "record_part_count":
            record_part_count,
        "file_count":
            len(
                ordered
            ),
        "total_bytes":
            total_bytes,
        "files":
            [
                {
                    "filename":
                        value.filename,
                    "sha256":
                        value.sha256,
                    "size_bytes":
                        value.size_bytes,
                }
                for value in ordered
            ],
    }


def serialize_zenodo_archive_manifest(
    **kwargs: Any,
) -> bytes:
    return _canonical_json_bytes(
        build_zenodo_archive_manifest(
            **kwargs
        )
    )


def audit_zenodo_archive_manifest(
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
            "Zenodo archive manifest must be bytes"
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
        raise ZenodoArchiveContractError(
            "invalid Zenodo archive manifest JSON"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise ZenodoArchiveContractError(
            "Zenodo archive manifest must be a JSON object"
        )

    if _canonical_json_bytes(
        record
    ) != payload:
        raise ZenodoArchiveContractError(
            "Zenodo archive manifest is not canonical JSON"
        )

    expected_keys = {
        "schema_version",
        "provider_id",
        "release_id",
        "source_snapshot_id",
        "origin_git_commit",
        "stage_id",
        "record_part_index",
        "record_part_count",
        "file_count",
        "total_bytes",
        "files",
    }

    if set(
        record
    ) != expected_keys:
        raise ZenodoArchiveContractError(
            "Zenodo archive manifest key set changed"
        )

    if record[
        "schema_version"
    ] != ZENODO_ARCHIVE_MANIFEST_SCHEMA:
        raise ZenodoArchiveContractError(
            "Zenodo archive manifest schema changed"
        )

    if record[
        "provider_id"
    ] != ZENODO_PROVIDER_ID:
        raise ZenodoArchiveContractError(
            "Zenodo archive provider identity changed"
        )

    raw_files = record[
        "files"
    ]

    if not isinstance(
        raw_files,
        list,
    ):
        raise ZenodoArchiveContractError(
            "Zenodo archive files must be a list"
        )

    files = []

    for value in raw_files:
        if (
            not isinstance(
                value,
                dict,
            )
            or set(
                value
            )
            != {
                "filename",
                "sha256",
                "size_bytes",
            }
        ):
            raise ZenodoArchiveContractError(
                "Zenodo archive file schema changed"
            )

        files.append(
            ZenodoArchiveFile(
                filename=value[
                    "filename"
                ],
                sha256=value[
                    "sha256"
                ],
                size_bytes=value[
                    "size_bytes"
                ],
            )
        )

    rebuilt = build_zenodo_archive_manifest(
        release_id=record[
            "release_id"
        ],
        source_snapshot_id=record[
            "source_snapshot_id"
        ],
        origin_git_commit=record[
            "origin_git_commit"
        ],
        stage_id=record[
            "stage_id"
        ],
        record_part_index=record[
            "record_part_index"
        ],
        record_part_count=record[
            "record_part_count"
        ],
        files=files,
    )

    if rebuilt != record:
        raise ZenodoArchiveContractError(
            "Zenodo archive manifest derived identity changed"
        )

    return record


def _expected_readback(
    manifest_payload: bytes,
) -> tuple[
    ZenodoReadbackObservation,
    ...,
]:
    manifest = (
        audit_zenodo_archive_manifest(
            manifest_payload
        )
    )

    return tuple(
        ZenodoReadbackObservation(
            filename=value[
                "filename"
            ],
            sha256=value[
                "sha256"
            ],
            size_bytes=value[
                "size_bytes"
            ],
        )
        for value in manifest[
            "files"
        ]
    )


def audit_zenodo_readback(
    manifest_payload: bytes,
    *,
    observations: Sequence[
        ZenodoReadbackObservation
    ],
) -> tuple[
    ZenodoReadbackObservation,
    ...,
]:
    if (
        isinstance(
            observations,
            (
                str,
                bytes,
            ),
        )
        or not isinstance(
            observations,
            Sequence,
        )
    ):
        raise TypeError(
            "Zenodo readback observations must be a sequence"
        )

    checked = []

    for value in observations:
        if not isinstance(
            value,
            ZenodoReadbackObservation,
        ):
            raise TypeError(
                "Zenodo readback observation has wrong type"
            )

        checked.append(
            ZenodoReadbackObservation(
                filename=_filename(
                    value.filename
                ),
                sha256=_sha256(
                    value.sha256,
                    label="Zenodo readback SHA256",
                ),
                size_bytes=_size_bytes(
                    value.size_bytes
                ),
            )
        )

    ordered = tuple(
        sorted(
            checked,
            key=lambda value:
                value.filename,
        )
    )

    if ordered != _expected_readback(
        manifest_payload
    ):
        raise ZenodoArchiveContractError(
            "Zenodo SHA256 readback does not match archive manifest"
        )

    return ordered


def _audit_published_record(
    value: ZenodoPublishedRecord,
    *,
    environment: str,
) -> ZenodoPublishedRecord:
    if not isinstance(
        value,
        ZenodoPublishedRecord,
    ):
        raise TypeError(
            "published Zenodo record has wrong type"
        )

    env = _environment(
        environment
    )

    _utc_datetime(
        value.publication_utc,
        label="Zenodo publication timestamp",
    )

    return ZenodoPublishedRecord(
        record_id=_positive_record_id(
            value.record_id,
            label="Zenodo record ID",
        ),
        concept_record_id=_positive_record_id(
            value.concept_record_id,
            label="Zenodo concept record ID",
        ),
        doi=_doi(
            value.doi,
            environment=env,
        ),
        publication_utc=(
            value.publication_utc
        ),
    )


def _readback_rows(
    observations: Sequence[
        ZenodoReadbackObservation
    ],
) -> list[
    dict[
        str,
        object,
    ]
]:
    return [
        {
            "filename":
                value.filename,
            "sha256":
                value.sha256,
            "size_bytes":
                value.size_bytes,
        }
        for value in observations
    ]


def build_zenodo_publication_receipt(
    manifest_payload: bytes,
    *,
    environment: str,
    published_record: ZenodoPublishedRecord,
    readback_observations: Sequence[
        ZenodoReadbackObservation
    ],
    verified_at_utc: str,
) -> dict[
    str,
    object,
]:
    manifest = (
        audit_zenodo_archive_manifest(
            manifest_payload
        )
    )

    env = _environment(
        environment
    )

    published = _audit_published_record(
        published_record,
        environment=env,
    )

    readback = audit_zenodo_readback(
        manifest_payload,
        observations=(
            readback_observations
        ),
    )

    publication_time = _utc_datetime(
        published.publication_utc,
        label="Zenodo publication timestamp",
    )

    verified_time = _utc_datetime(
        verified_at_utc,
        label="Zenodo verification timestamp",
    )

    if (
        verified_time
        < publication_time
    ):
        raise ZenodoArchiveContractError(
            "Zenodo verification predates publication"
        )

    return {
        "schema_version":
            ZENODO_PUBLICATION_RECEIPT_SCHEMA,
        "archive_state":
            "PUBLISHED_VERIFIED",
        "provider_id":
            ZENODO_PROVIDER_ID,
        "environment":
            env,
        "release_id":
            manifest[
                "release_id"
            ],
        "source_snapshot_id":
            manifest[
                "source_snapshot_id"
            ],
        "origin_git_commit":
            manifest[
                "origin_git_commit"
            ],
        "stage_id":
            manifest[
                "stage_id"
            ],
        "record_part_index":
            manifest[
                "record_part_index"
            ],
        "record_part_count":
            manifest[
                "record_part_count"
            ],
        "archive_manifest_sha256":
            hashlib.sha256(
                manifest_payload
            ).hexdigest(),
        "zenodo_record_id":
            published.record_id,
        "zenodo_concept_record_id":
            published.concept_record_id,
        "zenodo_doi":
            published.doi,
        "publication_utc":
            published.publication_utc,
        "verified_at_utc":
            verified_at_utc,
        "verified_files":
            _readback_rows(
                readback
            ),
    }


def serialize_zenodo_publication_receipt(
    manifest_payload: bytes,
    **kwargs: Any,
) -> bytes:
    return _canonical_json_bytes(
        build_zenodo_publication_receipt(
            manifest_payload,
            **kwargs,
        )
    )


def audit_zenodo_publication_receipt(
    receipt_payload: bytes,
    *,
    manifest_payload: bytes,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        receipt_payload,
        bytes,
    ):
        raise TypeError(
            "Zenodo publication receipt must be bytes"
        )

    try:
        record = json.loads(
            receipt_payload.decode(
                "ascii"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ZenodoArchiveContractError(
            "invalid Zenodo publication receipt JSON"
        ) from exc

    if (
        not isinstance(
            record,
            dict,
        )
        or _canonical_json_bytes(
            record
        )
        != receipt_payload
    ):
        raise ZenodoArchiveContractError(
            "Zenodo publication receipt is not canonical JSON"
        )

    expected_keys = {
        "schema_version",
        "archive_state",
        "provider_id",
        "environment",
        "release_id",
        "source_snapshot_id",
        "origin_git_commit",
        "stage_id",
        "record_part_index",
        "record_part_count",
        "archive_manifest_sha256",
        "zenodo_record_id",
        "zenodo_concept_record_id",
        "zenodo_doi",
        "publication_utc",
        "verified_at_utc",
        "verified_files",
    }

    if set(
        record
    ) != expected_keys:
        raise ZenodoArchiveContractError(
            "Zenodo publication receipt key set changed"
        )

    if record[
        "schema_version"
    ] != ZENODO_PUBLICATION_RECEIPT_SCHEMA:
        raise ZenodoArchiveContractError(
            "Zenodo publication receipt schema changed"
        )

    if record[
        "archive_state"
    ] != "PUBLISHED_VERIFIED":
        raise ZenodoArchiveContractError(
            "Zenodo publication archive state changed"
        )

    if record[
        "provider_id"
    ] != ZENODO_PROVIDER_ID:
        raise ZenodoArchiveContractError(
            "Zenodo publication provider identity changed"
        )

    observations = []

    raw_files = record[
        "verified_files"
    ]

    if not isinstance(
        raw_files,
        list,
    ):
        raise ZenodoArchiveContractError(
            "verified files must be a list"
        )

    for value in raw_files:
        if (
            not isinstance(
                value,
                dict,
            )
            or set(
                value
            )
            != {
                "filename",
                "sha256",
                "size_bytes",
            }
        ):
            raise ZenodoArchiveContractError(
                "verified file schema changed"
            )

        observations.append(
            ZenodoReadbackObservation(
                filename=value[
                    "filename"
                ],
                sha256=value[
                    "sha256"
                ],
                size_bytes=value[
                    "size_bytes"
                ],
            )
        )

    rebuilt = build_zenodo_publication_receipt(
        manifest_payload,
        environment=record[
            "environment"
        ],
        published_record=(
            ZenodoPublishedRecord(
                record_id=record[
                    "zenodo_record_id"
                ],
                concept_record_id=record[
                    "zenodo_concept_record_id"
                ],
                doi=record[
                    "zenodo_doi"
                ],
                publication_utc=record[
                    "publication_utc"
                ],
            )
        ),
        readback_observations=(
            observations
        ),
        verified_at_utc=record[
            "verified_at_utc"
        ],
    )

    if rebuilt != record:
        raise ZenodoArchiveContractError(
            "Zenodo publication receipt derived identity changed"
        )

    return record


def build_zenodo_sealed_receipt(
    manifest_payload: bytes,
    *,
    publication_receipt_payload: bytes,
    readback_observations: Sequence[
        ZenodoReadbackObservation
    ],
    sealed_verified_at_utc: str,
) -> dict[
    str,
    object,
]:
    publication = (
        audit_zenodo_publication_receipt(
            publication_receipt_payload,
            manifest_payload=(
                manifest_payload
            ),
        )
    )

    readback = audit_zenodo_readback(
        manifest_payload,
        observations=(
            readback_observations
        ),
    )

    publication_time = _utc_datetime(
        publication[
            "publication_utc"
        ],
        label="Zenodo publication timestamp",
    )

    sealed_time = _utc_datetime(
        sealed_verified_at_utc,
        label="Zenodo sealed verification timestamp",
    )

    if (
        sealed_time
        < publication_time
        + timedelta(
            days=ZENODO_SEAL_MIN_DAYS
        )
    ):
        raise ZenodoArchiveContractError(
            "Zenodo sealed verification is inside the frozen 45-day window"
        )

    return {
        "schema_version":
            ZENODO_SEALED_RECEIPT_SCHEMA,
        "archive_state":
            "SEALED_VERIFIED",
        "provider_id":
            ZENODO_PROVIDER_ID,
        "environment":
            publication[
                "environment"
            ],
        "release_id":
            publication[
                "release_id"
            ],
        "source_snapshot_id":
            publication[
                "source_snapshot_id"
            ],
        "origin_git_commit":
            publication[
                "origin_git_commit"
            ],
        "stage_id":
            publication[
                "stage_id"
            ],
        "record_part_index":
            publication[
                "record_part_index"
            ],
        "record_part_count":
            publication[
                "record_part_count"
            ],
        "archive_manifest_sha256":
            publication[
                "archive_manifest_sha256"
            ],
        "publication_receipt_sha256":
            hashlib.sha256(
                publication_receipt_payload
            ).hexdigest(),
        "zenodo_record_id":
            publication[
                "zenodo_record_id"
            ],
        "zenodo_concept_record_id":
            publication[
                "zenodo_concept_record_id"
            ],
        "zenodo_doi":
            publication[
                "zenodo_doi"
            ],
        "publication_utc":
            publication[
                "publication_utc"
            ],
        "sealed_verified_at_utc":
            sealed_verified_at_utc,
        "verified_files":
            _readback_rows(
                readback
            ),
    }


def serialize_zenodo_sealed_receipt(
    manifest_payload: bytes,
    **kwargs: Any,
) -> bytes:
    return _canonical_json_bytes(
        build_zenodo_sealed_receipt(
            manifest_payload,
            **kwargs,
        )
    )


def audit_zenodo_sealed_receipt(
    receipt_payload: bytes,
    *,
    manifest_payload: bytes,
    publication_receipt_payload: bytes,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        receipt_payload,
        bytes,
    ):
        raise TypeError(
            "Zenodo sealed receipt must be bytes"
        )

    try:
        record = json.loads(
            receipt_payload.decode(
                "ascii"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ZenodoArchiveContractError(
            "invalid Zenodo sealed receipt JSON"
        ) from exc

    if (
        not isinstance(
            record,
            dict,
        )
        or _canonical_json_bytes(
            record
        )
        != receipt_payload
    ):
        raise ZenodoArchiveContractError(
            "Zenodo sealed receipt is not canonical JSON"
        )

    expected_keys = {
        "schema_version",
        "archive_state",
        "provider_id",
        "environment",
        "release_id",
        "source_snapshot_id",
        "origin_git_commit",
        "stage_id",
        "record_part_index",
        "record_part_count",
        "archive_manifest_sha256",
        "publication_receipt_sha256",
        "zenodo_record_id",
        "zenodo_concept_record_id",
        "zenodo_doi",
        "publication_utc",
        "sealed_verified_at_utc",
        "verified_files",
    }

    if set(
        record
    ) != expected_keys:
        raise ZenodoArchiveContractError(
            "Zenodo sealed receipt key set changed"
        )

    if record[
        "schema_version"
    ] != ZENODO_SEALED_RECEIPT_SCHEMA:
        raise ZenodoArchiveContractError(
            "Zenodo sealed receipt schema changed"
        )

    if record[
        "archive_state"
    ] != "SEALED_VERIFIED":
        raise ZenodoArchiveContractError(
            "Zenodo sealed archive state changed"
        )

    if record[
        "provider_id"
    ] != ZENODO_PROVIDER_ID:
        raise ZenodoArchiveContractError(
            "Zenodo sealed provider identity changed"
        )

    raw_files = record[
        "verified_files"
    ]

    if not isinstance(
        raw_files,
        list,
    ):
        raise ZenodoArchiveContractError(
            "sealed verified files must be a list"
        )

    observations = []

    for value in raw_files:
        if (
            not isinstance(
                value,
                dict,
            )
            or set(
                value
            )
            != {
                "filename",
                "sha256",
                "size_bytes",
            }
        ):
            raise ZenodoArchiveContractError(
                "sealed verified file schema changed"
            )

        observations.append(
            ZenodoReadbackObservation(
                filename=value[
                    "filename"
                ],
                sha256=value[
                    "sha256"
                ],
                size_bytes=value[
                    "size_bytes"
                ],
            )
        )

    rebuilt = build_zenodo_sealed_receipt(
        manifest_payload,
        publication_receipt_payload=(
            publication_receipt_payload
        ),
        readback_observations=(
            observations
        ),
        sealed_verified_at_utc=record[
            "sealed_verified_at_utc"
        ],
    )

    if rebuilt != record:
        raise ZenodoArchiveContractError(
            "Zenodo sealed receipt derived identity changed"
        )

    return record
