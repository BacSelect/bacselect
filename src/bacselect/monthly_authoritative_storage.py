"""Pure authoritative-storage contract for BacSelect monthly production."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


AUTHORITATIVE_MANIFEST_SCHEMA = (
    "bacselect-authoritative-storage-manifest-v1"
)

AUTHORITATIVE_RECEIPT_SCHEMA = (
    "bacselect-authoritative-storage-receipt-v1"
)

OBJECT_PREFIX = "objects/sha256"
MANIFEST_PREFIX = "manifests/monthly"
RECEIPT_PREFIX = "receipts/monthly"

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

GIT_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

RELEASE_ID_RE = re.compile(
    r"^[0-9]{4}\.(0[1-9]|1[0-2])$"
)

STAGE_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9._-]{0,127}$"
)


class AuthoritativeStorageError(
    ValueError
):
    """Raised when authoritative-storage identity is invalid."""


@dataclass(
    frozen=True,
    order=True,
)
class AuthoritativeArtifact:
    """One logical production artifact."""

    logical_path: str
    sha256: str
    size_bytes: int


@dataclass(
    frozen=True,
    order=True,
)
class StoredObjectObservation:
    """Read-back identity for one object in durable storage."""

    object_key: str
    sha256: str
    size_bytes: int


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
        raise AuthoritativeStorageError(
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
        raise AuthoritativeStorageError(
            "origin Git commit must be a lowercase 40-character SHA"
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
        raise AuthoritativeStorageError(
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
        raise AuthoritativeStorageError(
            "source snapshot ID does not match release identity"
        )

    release_timestamp_prefix = (
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
            release_timestamp_prefix
        )
        + "(?:[01][0-9]|2[0-3])"
        + "[0-5][0-9]"
        + "[0-5][0-9]"
        + "Z$"
    )

    if pattern.fullmatch(
        value
    ) is None:
        raise AuthoritativeStorageError(
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
        raise AuthoritativeStorageError(
            "stage ID is invalid"
        )

    return value


def _size_bytes(
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
        or value < 0
    ):
        raise AuthoritativeStorageError(
            f"{label} must be a non-negative integer"
        )

    return value


def _logical_path(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
    ):
        raise AuthoritativeStorageError(
            "logical artifact path must be non-empty text"
        )

    if "\\" in value:
        raise AuthoritativeStorageError(
            "logical artifact path must use POSIX separators"
        )

    if value.startswith(
        "/"
    ):
        raise AuthoritativeStorageError(
            "logical artifact path must be relative"
        )

    parts = value.split(
        "/"
    )

    if any(
        part
        in {
            "",
            ".",
            "..",
        }
        for part in parts
    ):
        raise AuthoritativeStorageError(
            "logical artifact path is unsafe"
        )

    return value


def object_key_for_sha256(
    sha256: str,
) -> str:
    digest = _sha256(
        sha256,
        label="object SHA256",
    )

    return (
        f"{OBJECT_PREFIX}/"
        f"{digest[:2]}/"
        f"{digest[2:4]}/"
        f"{digest}"
    )


def artifact_from_bytes(
    logical_path: str,
    payload: bytes,
) -> AuthoritativeArtifact:
    path = _logical_path(
        logical_path
    )

    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "artifact payload must be bytes"
        )

    return AuthoritativeArtifact(
        logical_path=path,
        sha256=hashlib.sha256(
            payload
        ).hexdigest(),
        size_bytes=len(
            payload
        ),
    )


def artifact_from_file(
    logical_path: str,
    path: Path,
) -> AuthoritativeArtifact:
    logical = _logical_path(
        logical_path
    )

    if not isinstance(
        path,
        Path,
    ):
        raise TypeError(
            "artifact source must be a pathlib.Path"
        )

    if not path.is_file():
        raise AuthoritativeStorageError(
            f"artifact source does not exist: {path}"
        )

    digest = hashlib.sha256()
    size = 0

    with path.open(
        "rb"
    ) as handle:
        for block in iter(
            lambda:
                handle.read(
                    1024 * 1024
                ),
            b"",
        ):
            digest.update(
                block
            )

            size += len(
                block
            )

    return AuthoritativeArtifact(
        logical_path=logical,
        sha256=digest.hexdigest(),
        size_bytes=size,
    )


def _audit_artifact(
    artifact: AuthoritativeArtifact,
) -> AuthoritativeArtifact:
    if not isinstance(
        artifact,
        AuthoritativeArtifact,
    ):
        raise TypeError(
            "artifact must be an AuthoritativeArtifact"
        )

    return AuthoritativeArtifact(
        logical_path=_logical_path(
            artifact.logical_path
        ),
        sha256=_sha256(
            artifact.sha256,
            label="artifact SHA256",
        ),
        size_bytes=_size_bytes(
            artifact.size_bytes,
            label="artifact size",
        ),
    )


def build_authoritative_manifest(
    *,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    stage_id: str,
    artifacts: Sequence[
        AuthoritativeArtifact
    ],
) -> dict[
    str,
    object,
]:
    """Build the deterministic mapping from logical artifacts to objects."""

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

    if not isinstance(
        artifacts,
        Sequence,
    ):
        raise TypeError(
            "artifacts must be a sequence"
        )

    checked = tuple(
        _audit_artifact(
            artifact
        )
        for artifact in artifacts
    )

    if not checked:
        raise AuthoritativeStorageError(
            "authoritative manifest cannot be empty"
        )

    logical_paths = [
        artifact.logical_path
        for artifact in checked
    ]

    if len(
        logical_paths
    ) != len(
        set(
            logical_paths
        )
    ):
        raise AuthoritativeStorageError(
            "logical artifact paths must be unique"
        )

    ordered = tuple(
        sorted(
            checked,
            key=lambda artifact:
                artifact.logical_path,
        )
    )

    unique_objects = {
        artifact.sha256:
            artifact.size_bytes
        for artifact in ordered
    }

    if len(
        unique_objects
    ) != len(
        {
            (
                artifact.sha256,
                artifact.size_bytes,
            )
            for artifact in ordered
        }
    ):
        raise AuthoritativeStorageError(
            "one content SHA256 maps to inconsistent sizes"
        )

    return {
        "schema_version":
            AUTHORITATIVE_MANIFEST_SCHEMA,
        "release_id":
            release,
        "source_snapshot_id":
            snapshot,
        "origin_git_commit":
            commit,
        "stage_id":
            stage,
        "artifact_count":
            len(
                ordered
            ),
        "total_logical_bytes":
            sum(
                artifact.size_bytes
                for artifact in ordered
            ),
        "unique_object_count":
            len(
                unique_objects
            ),
        "total_unique_bytes":
            sum(
                unique_objects.values()
            ),
        "artifacts":
            [
                {
                    "logical_path":
                        artifact.logical_path,
                    "sha256":
                        artifact.sha256,
                    "size_bytes":
                        artifact.size_bytes,
                    "object_key":
                        object_key_for_sha256(
                            artifact.sha256
                        ),
                }
                for artifact in ordered
            ],
    }


def serialize_authoritative_manifest(
    *,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    stage_id: str,
    artifacts: Sequence[
        AuthoritativeArtifact
    ],
) -> bytes:
    return _canonical_json_bytes(
        build_authoritative_manifest(
            release_id=release_id,
            source_snapshot_id=(
                source_snapshot_id
            ),
            origin_git_commit=(
                origin_git_commit
            ),
            stage_id=stage_id,
            artifacts=artifacts,
        )
    )


def audit_authoritative_manifest(
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
            "authoritative manifest must be bytes"
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
        raise AuthoritativeStorageError(
            "invalid authoritative manifest JSON"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise AuthoritativeStorageError(
            "authoritative manifest must be a JSON object"
        )

    if _canonical_json_bytes(
        record
    ) != payload:
        raise AuthoritativeStorageError(
            "authoritative manifest is not canonical JSON"
        )

    expected_keys = {
        "schema_version",
        "release_id",
        "source_snapshot_id",
        "origin_git_commit",
        "stage_id",
        "artifact_count",
        "total_logical_bytes",
        "unique_object_count",
        "total_unique_bytes",
        "artifacts",
    }

    if set(
        record
    ) != expected_keys:
        raise AuthoritativeStorageError(
            "authoritative manifest key set changed"
        )

    if record[
        "schema_version"
    ] != AUTHORITATIVE_MANIFEST_SCHEMA:
        raise AuthoritativeStorageError(
            "authoritative manifest schema changed"
        )

    artifacts_value = record[
        "artifacts"
    ]

    if not isinstance(
        artifacts_value,
        list,
    ):
        raise AuthoritativeStorageError(
            "authoritative manifest artifacts must be a list"
        )

    artifacts = []

    for value in artifacts_value:
        if (
            not isinstance(
                value,
                dict,
            )
            or set(
                value
            )
            != {
                "logical_path",
                "sha256",
                "size_bytes",
                "object_key",
            }
        ):
            raise AuthoritativeStorageError(
                "authoritative artifact entry schema changed"
            )

        artifact = AuthoritativeArtifact(
            logical_path=_logical_path(
                value[
                    "logical_path"
                ]
            ),
            sha256=_sha256(
                value[
                    "sha256"
                ],
                label="artifact SHA256",
            ),
            size_bytes=_size_bytes(
                value[
                    "size_bytes"
                ],
                label="artifact size",
            ),
        )

        if value[
            "object_key"
        ] != object_key_for_sha256(
            artifact.sha256
        ):
            raise AuthoritativeStorageError(
                "authoritative artifact object key changed"
            )

        artifacts.append(
            artifact
        )

    rebuilt = build_authoritative_manifest(
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
        artifacts=artifacts,
    )

    if rebuilt != record:
        raise AuthoritativeStorageError(
            "authoritative manifest derived identity changed"
        )

    return record


def authoritative_manifest_key(
    payload: bytes,
) -> str:
    record = audit_authoritative_manifest(
        payload
    )

    digest = hashlib.sha256(
        payload
    ).hexdigest()

    return (
        f"{MANIFEST_PREFIX}/"
        f"{record['release_id']}/"
        f"production/"
        f"{record['origin_git_commit']}/"
        f"{record['stage_id']}/"
        f"sha256/"
        f"{digest}.json"
    )


def expected_stored_objects(
    manifest_payload: bytes,
) -> tuple[
    StoredObjectObservation,
    ...,
]:
    """Return every object that must be read-back verified."""

    manifest = audit_authoritative_manifest(
        manifest_payload
    )

    observations = {}

    for artifact in manifest[
        "artifacts"
    ]:
        key = artifact[
            "object_key"
        ]

        observations[
            key
        ] = StoredObjectObservation(
            object_key=key,
            sha256=artifact[
                "sha256"
            ],
            size_bytes=artifact[
                "size_bytes"
            ],
        )

    manifest_sha = hashlib.sha256(
        manifest_payload
    ).hexdigest()

    manifest_key = authoritative_manifest_key(
        manifest_payload
    )

    observations[
        manifest_key
    ] = StoredObjectObservation(
        object_key=manifest_key,
        sha256=manifest_sha,
        size_bytes=len(
            manifest_payload
        ),
    )

    return tuple(
        sorted(
            observations.values(),
            key=lambda observation:
                observation.object_key,
        )
    )


def _audit_observation(
    observation: StoredObjectObservation,
) -> StoredObjectObservation:
    if not isinstance(
        observation,
        StoredObjectObservation,
    ):
        raise TypeError(
            "stored object observation has wrong type"
        )

    if (
        not isinstance(
            observation.object_key,
            str,
        )
        or not observation.object_key
    ):
        raise AuthoritativeStorageError(
            "stored object key is invalid"
        )

    return StoredObjectObservation(
        object_key=observation.object_key,
        sha256=_sha256(
            observation.sha256,
            label="stored object SHA256",
        ),
        size_bytes=_size_bytes(
            observation.size_bytes,
            label="stored object size",
        ),
    )


def build_authoritative_receipt(
    manifest_payload: bytes,
    *,
    observed_objects: Sequence[
        StoredObjectObservation
    ],
) -> dict[
    str,
    object,
]:
    """
    Build a receipt only after exact durable-object read-back verification.
    """

    manifest = audit_authoritative_manifest(
        manifest_payload
    )

    expected = expected_stored_objects(
        manifest_payload
    )

    checked = tuple(
        sorted(
            (
                _audit_observation(
                    observation
                )
                for observation in observed_objects
            ),
            key=lambda observation:
                observation.object_key,
        )
    )

    if len(
        checked
    ) != len(
        {
            observation.object_key
            for observation in checked
        }
    ):
        raise AuthoritativeStorageError(
            "stored object observations contain duplicate keys"
        )

    if checked != expected:
        raise AuthoritativeStorageError(
            "durable stored-object readback does not match manifest"
        )

    manifest_sha = hashlib.sha256(
        manifest_payload
    ).hexdigest()

    return {
        "schema_version":
            AUTHORITATIVE_RECEIPT_SCHEMA,
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
        "manifest_sha256":
            manifest_sha,
        "manifest_object_key":
            authoritative_manifest_key(
                manifest_payload
            ),
        "verified_object_count":
            len(
                checked
            ),
        "verified_objects":
            [
                {
                    "object_key":
                        observation.object_key,
                    "sha256":
                        observation.sha256,
                    "size_bytes":
                        observation.size_bytes,
                }
                for observation in checked
            ],
    }


def serialize_authoritative_receipt(
    manifest_payload: bytes,
    *,
    observed_objects: Sequence[
        StoredObjectObservation
    ],
) -> bytes:
    return _canonical_json_bytes(
        build_authoritative_receipt(
            manifest_payload,
            observed_objects=(
                observed_objects
            ),
        )
    )


def audit_authoritative_receipt(
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
            "authoritative receipt must be bytes"
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
        raise AuthoritativeStorageError(
            "invalid authoritative receipt JSON"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise AuthoritativeStorageError(
            "authoritative receipt must be a JSON object"
        )

    if _canonical_json_bytes(
        record
    ) != receipt_payload:
        raise AuthoritativeStorageError(
            "authoritative receipt is not canonical JSON"
        )

    expected_keys = {
        "schema_version",
        "release_id",
        "source_snapshot_id",
        "origin_git_commit",
        "stage_id",
        "manifest_sha256",
        "manifest_object_key",
        "verified_object_count",
        "verified_objects",
    }

    if set(
        record
    ) != expected_keys:
        raise AuthoritativeStorageError(
            "authoritative receipt key set changed"
        )

    if record[
        "schema_version"
    ] != AUTHORITATIVE_RECEIPT_SCHEMA:
        raise AuthoritativeStorageError(
            "authoritative receipt schema changed"
        )

    values = record[
        "verified_objects"
    ]

    if not isinstance(
        values,
        list,
    ):
        raise AuthoritativeStorageError(
            "verified objects must be a list"
        )

    observations = []

    for value in values:
        if (
            not isinstance(
                value,
                dict,
            )
            or set(
                value
            )
            != {
                "object_key",
                "sha256",
                "size_bytes",
            }
        ):
            raise AuthoritativeStorageError(
                "verified object entry schema changed"
            )

        observations.append(
            StoredObjectObservation(
                object_key=value[
                    "object_key"
                ],
                sha256=value[
                    "sha256"
                ],
                size_bytes=value[
                    "size_bytes"
                ],
            )
        )

    rebuilt = build_authoritative_receipt(
        manifest_payload,
        observed_objects=(
            observations
        ),
    )

    if rebuilt != record:
        raise AuthoritativeStorageError(
            "authoritative receipt does not match manifest"
        )

    return record


def authoritative_receipt_key(
    receipt_payload: bytes,
    *,
    manifest_payload: bytes,
) -> str:
    record = audit_authoritative_receipt(
        receipt_payload,
        manifest_payload=(
            manifest_payload
        ),
    )

    digest = hashlib.sha256(
        receipt_payload
    ).hexdigest()

    return (
        f"{RECEIPT_PREFIX}/"
        f"{record['release_id']}/"
        f"production/"
        f"{record['origin_git_commit']}/"
        f"{record['stage_id']}/"
        f"sha256/"
        f"{digest}.json"
    )
