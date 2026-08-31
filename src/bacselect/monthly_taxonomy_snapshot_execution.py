"""Operational support for BacSelect monthly taxonomy-snapshot Stage 7."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import ssl
from typing import Callable, Mapping
import urllib.request
import uuid

from bacselect import monthly_authoritative_storage
from bacselect import monthly_taxonomy_snapshot
from bacselect import source_taxonomy_acquisition


ACQUISITION_SCHEMA = (
    "bacselect-monthly-taxonomy-acquisition-v1"
)

ACQUISITION_STATUS = (
    "TAXONOMY_ACQUISITION_COMPLETE"
)

STAGE_ID = "taxonomy-snapshot"

ARCHIVE_NAME = (
    source_taxonomy_acquisition.ARCHIVE_NAME
)

ACQUISITION_PROVENANCE_NAME = (
    source_taxonomy_acquisition
    .ACQUISITION_PROVENANCE_NAME
)

CONTENT_MANIFEST_NAME = (
    source_taxonomy_acquisition
    .CONTENT_MANIFEST_NAME
)

RECORD_NAME = (
    "monthly-taxonomy-snapshot-record.json"
)

AUTHORITATIVE_MANIFEST_LOCAL_NAME = (
    "taxonomy-authoritative-storage-manifest.json"
)

AUTHORITATIVE_RECEIPT_LOCAL_NAME = (
    "taxonomy-authoritative-storage-receipt.json"
)

PARTIAL_ARCHIVE_NAME = (
    ARCHIVE_NAME
    + ".partial"
)

EXECUTION_METHOD_SHA256 = (
    "0dd4105b1360117cc79b185a55c69b5d"
    "519f058178b35635cd5e1d3a28aa342c"
)

EXPECTED_AUTHORITATIVE_VERIFIED_OBJECT_COUNT = 8

DEFAULT_TIMEOUT_SECONDS = 120.0

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

RELEASE_RE = re.compile(
    r"^[0-9]{4}\.[0-9]{2}$"
)

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

ACQUISITION_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "release_id",
        "source_snapshot_id",
        "source_snapshot_record_sha256",
        "source_raw_response_sha256",
        "chromosome_integrity_completion_sha256",
        "execution_git_commit",
        "execution_support_module_sha256",
        "validation_wrapper_sha256",
        "execution_method_sha256",
        "source_taxonomy_sha256",
        "requested_url",
        "final_url",
        "http_status",
        "etag",
        "last_modified",
        "acquisition_started_utc",
        "acquisition_completed_utc",
        "downloader_identity",
        "python_version",
        "openssl_version",
        "archive_member_count",
        "archive_sha256",
        "archive_size_bytes",
        "nodes_sha256",
        "nodes_size_bytes",
        "merged_sha256",
        "merged_size_bytes",
        "delnodes_sha256",
        "delnodes_size_bytes",
        "structural_validation_result",
        "taxonomy_resolution_performed",
        "structural_features_calculated",
        "selector_outcomes_calculated",
    }
)

AUTHORITATIVE_LOGICAL_PATHS = (
    f"{STAGE_ID}/{ARCHIVE_NAME}",
    f"{STAGE_ID}/nodes.dmp",
    f"{STAGE_ID}/merged.dmp",
    f"{STAGE_ID}/delnodes.dmp",
    f"{STAGE_ID}/{ACQUISITION_PROVENANCE_NAME}",
    f"{STAGE_ID}/{CONTENT_MANIFEST_NAME}",
    f"{STAGE_ID}/{RECORD_NAME}",
)

LOCAL_STAGE_FILES = frozenset(
    {
        ARCHIVE_NAME,
        "nodes.dmp",
        "merged.dmp",
        "delnodes.dmp",
        ACQUISITION_PROVENANCE_NAME,
        CONTENT_MANIFEST_NAME,
        RECORD_NAME,
        AUTHORITATIVE_MANIFEST_LOCAL_NAME,
        AUTHORITATIVE_RECEIPT_LOCAL_NAME,
    }
)


class MonthlyTaxonomyExecutionError(
    RuntimeError
):
    """Raised when monthly Stage 7 operational support fails closed."""


@dataclass(
    frozen=True,
)
class AuthenticatedMonthlyTaxonomyUpstream:
    """Wrapper-authenticated Stage 1 and Stage 6 evidence entering support."""

    release_id: str
    source_snapshot_id: str
    source_snapshot_record_payload: bytes
    source_snapshot_record_sha256: str
    raw_source_response_payload: bytes
    source_raw_response_sha256: str
    chromosome_integrity_decisions_sha256: str
    chromosome_integrity_record_sha256: str
    chromosome_integrity_completion_sha256: str
    execution_git_commit: str


@dataclass(
    frozen=True,
)
class MonthlyTaxonomySupportResult:
    """Accepted Stage 7 support outputs before canonical local publication."""

    workspace: Path
    release_id: str
    source_snapshot_id: str
    taxonomy_snapshot_id: str
    acquisition_provenance_sha256: str
    content_manifest_sha256: str
    record_sha256: str
    archive_sha256: str
    nodes_sha256: str
    merged_sha256: str
    delnodes_sha256: str
    authoritative_manifest_sha256: str
    authoritative_manifest_key: str
    authoritative_receipt_sha256: str
    authoritative_receipt_key: str
    authoritative_verified_object_count: int


def _canonical_json(
    value: Mapping[
        str,
        object,
    ],
) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
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
        raise MonthlyTaxonomyExecutionError(
            f"{label} is not a SHA256"
        )

    return value


def _commit(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyTaxonomyExecutionError(
            "execution Git commit is invalid"
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
        or RELEASE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyTaxonomyExecutionError(
            "release ID is invalid"
        )

    return value


def _nonempty_text(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value.strip() != value
    ):
        raise MonthlyTaxonomyExecutionError(
            f"{label} is invalid"
        )

    return value


def _positive_size(
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
        raise MonthlyTaxonomyExecutionError(
            f"{label} must be a positive integer"
        )

    return value


def _timestamp(
    value: object,
    *,
    label: str,
) -> str:
    text = _nonempty_text(
        value,
        label=label,
    )

    try:
        parsed = datetime.strptime(
            text,
            TIMESTAMP_FORMAT,
        )
    except ValueError as exc:
        raise MonthlyTaxonomyExecutionError(
            f"{label} is not canonical UTC"
        ) from exc

    if (
        parsed.strftime(
            TIMESTAMP_FORMAT
        )
        != text
    ):
        raise MonthlyTaxonomyExecutionError(
            f"{label} is not canonical UTC"
        )

    return text


def _utc_now() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .replace(
            microsecond=0
        )
        .strftime(
            TIMESTAMP_FORMAT
        )
    )


def _timeout(
    value: object,
) -> float:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            (
                int,
                float,
            ),
        )
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy network timeout is invalid"
        )

    result = float(
        value
    )

    if (
        not math.isfinite(
            result
        )
        or result <= 0.0
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy network timeout must be positive and finite"
        )

    return result


def _optional_header(
    value: object,
    *,
    label: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise MonthlyTaxonomyExecutionError(
            f"{label} must be text or null"
        )

    return value


def _require_bytes(
    value: object,
    *,
    label: str,
) -> bytes:
    if (
        not isinstance(
            value,
            bytes,
        )
        or not value
    ):
        raise MonthlyTaxonomyExecutionError(
            f"{label} must be non-empty bytes"
        )

    return value


def _sha256_bytes(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def execution_support_module_sha256() -> str:
    """Return the exact SHA256 of this production support module."""

    return source_taxonomy_acquisition.sha256_file(
        Path(
            __file__
        ).resolve()
    )


def _callable_identity(
    value: object,
) -> str:
    if callable(
        value
    ):
        module = getattr(
            value,
            "__module__",
            None,
        )

        qualname = getattr(
            value,
            "__qualname__",
            None,
        )

        if (
            isinstance(
                module,
                str,
            )
            and module
            and isinstance(
                qualname,
                str,
            )
            and qualname
        ):
            return (
                f"{module}.{qualname}"
            )

        cls = type(
            value
        )

        return (
            f"{cls.__module__}."
            f"{cls.__qualname__}"
        )

    raise MonthlyTaxonomyExecutionError(
        "taxonomy opener is not callable"
    )


def _require_real_directory(
    value: Path,
    *,
    label: str,
) -> Path:
    path = Path(
        value
    )

    if (
        path.is_symlink()
        or not path.is_dir()
    ):
        raise MonthlyTaxonomyExecutionError(
            f"{label} is not a real directory"
        )

    return path.resolve()


def _require_empty_workspace(
    value: Path,
) -> Path:
    path = _require_real_directory(
        value,
        label="taxonomy workspace",
    )

    if any(
        path.iterdir()
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy workspace is not empty"
        )

    return path


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    if (
        not os.path.lexists(
            path
        )
        or path.is_symlink()
        or not path.is_file()
    ):
        raise MonthlyTaxonomyExecutionError(
            f"{label} is not a regular file"
        )

    return path


def _fsync_directory(
    path: Path,
) -> None:
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


def _fsync_file(
    path: Path,
) -> None:
    with path.open(
        "rb"
    ) as handle:
        os.fsync(
            handle.fileno()
        )


def _write_no_clobber(
    path: Path,
    payload: bytes,
) -> None:
    if not isinstance(
        payload,
        bytes,
    ):
        raise MonthlyTaxonomyExecutionError(
            "published payload must be bytes"
        )

    descriptor = None

    try:
        descriptor = os.open(
            path,
            (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
            ),
            0o644,
        )

        os.fchmod(
            descriptor,
            0o644,
        )

        with os.fdopen(
            descriptor,
            "wb",
            closefd=True,
        ) as handle:
            descriptor = None

            handle.write(
                payload
            )

            handle.flush()

            os.fsync(
                handle.fileno()
            )

    except FileExistsError as exc:
        raise MonthlyTaxonomyExecutionError(
            f"refusing to overwrite file: {path}"
        ) from exc

    finally:
        if descriptor is not None:
            os.close(
                descriptor
            )


def _remove_owned_file(
    path: Path,
    *,
    device: int,
    inode: int,
) -> None:
    if not os.path.lexists(
        path
    ):
        return

    if (
        path.is_symlink()
        or not path.is_file()
    ):
        raise MonthlyTaxonomyExecutionError(
            "temporary cleanup target became unsafe"
        )

    observed = path.stat()

    if (
        observed.st_dev != device
        or observed.st_ino != inode
    ):
        raise MonthlyTaxonomyExecutionError(
            "temporary cleanup target identity changed"
        )

    path.unlink()


def _remove_owned_hard_link(
    *,
    source: Path,
    destination: Path,
) -> None:
    if not os.path.lexists(
        destination
    ):
        return

    if (
        destination.is_symlink()
        or not destination.is_file()
        or source.is_symlink()
        or not source.is_file()
    ):
        raise MonthlyTaxonomyExecutionError(
            "published cleanup target became unsafe"
        )

    source_stat = source.stat()
    destination_stat = (
        destination.stat()
    )

    if (
        source_stat.st_dev
        != destination_stat.st_dev
        or source_stat.st_ino
        != destination_stat.st_ino
    ):
        raise MonthlyTaxonomyExecutionError(
            "published cleanup target is not the created hard link"
        )

    destination.unlink()


def _storage_destination(
    authoritative_root: Path,
    key: str,
) -> Path:
    root = _require_real_directory(
        authoritative_root,
        label="authoritative root",
    )

    if (
        not isinstance(
            key,
            str,
        )
        or not key
    ):
        raise MonthlyTaxonomyExecutionError(
            "authoritative object key is invalid"
        )

    pure = PurePosixPath(
        key
    )

    if (
        pure.is_absolute()
        or str(
            pure
        )
        != key
        or any(
            part in {
                "",
                ".",
                "..",
            }
            for part in pure.parts
        )
    ):
        raise MonthlyTaxonomyExecutionError(
            "authoritative object key is unsafe"
        )

    current = root

    for part in pure.parts[
        :-1
    ]:
        child = (
            current
            / part
        )

        if os.path.lexists(
            child
        ):
            if (
                child.is_symlink()
                or not child.is_dir()
            ):
                raise MonthlyTaxonomyExecutionError(
                    "authoritative storage parent is unsafe"
                )

        else:
            child.mkdir(
                mode=0o755,
            )

            _fsync_directory(
                current
            )

        current = child

    return (
        current
        / pure.parts[-1]
    )


def _observe_file(
    path: Path,
    *,
    expected_sha256: str,
    expected_size_bytes: int,
    label: str,
) -> monthly_authoritative_storage.StoredObjectObservation:
    file_path = _require_regular_file(
        path,
        label=label,
    )

    identity = (
        source_taxonomy_acquisition
        .file_identity(
            file_path
        )
    )

    expected_sha = _sha256(
        expected_sha256,
        label=f"{label} SHA256",
    )

    expected_size = _positive_size(
        expected_size_bytes,
        label=f"{label} size",
    )

    if (
        identity.sha256
        != expected_sha
        or identity.size_bytes
        != expected_size
    ):
        raise MonthlyTaxonomyExecutionError(
            f"{label} identity changed"
        )

    return (
        monthly_authoritative_storage
        .StoredObjectObservation(
            object_key="",
            sha256=identity.sha256,
            size_bytes=identity.size_bytes,
        )
    )


def _observe_key(
    authoritative_root: Path,
    observation: (
        monthly_authoritative_storage
        .StoredObjectObservation
    ),
) -> monthly_authoritative_storage.StoredObjectObservation:
    destination = _storage_destination(
        authoritative_root,
        observation.object_key,
    )

    observed = _observe_file(
        destination,
        expected_sha256=(
            observation.sha256
        ),
        expected_size_bytes=(
            observation.size_bytes
        ),
        label="authoritative stored object",
    )

    return (
        monthly_authoritative_storage
        .StoredObjectObservation(
            object_key=(
                observation.object_key
            ),
            sha256=observed.sha256,
            size_bytes=(
                observed.size_bytes
            ),
        )
    )


def _temporary_storage_path(
    destination: Path,
) -> Path:
    return (
        destination.parent
        / (
            f".{destination.name}."
            f"stage7-{os.getpid()}-"
            f"{uuid.uuid4().hex}.partial"
        )
    )


def _publish_file_to_key(
    *,
    source: Path,
    authoritative_root: Path,
    key: str,
    expected_sha256: str,
    expected_size_bytes: int,
) -> monthly_authoritative_storage.StoredObjectObservation:
    source_file = _require_regular_file(
        Path(
            source
        ),
        label="authoritative source artifact",
    )

    source_identity = (
        source_taxonomy_acquisition
        .file_identity(
            source_file
        )
    )

    expected_sha = _sha256(
        expected_sha256,
        label="authoritative source SHA256",
    )

    expected_size = _positive_size(
        expected_size_bytes,
        label="authoritative source size",
    )

    if (
        source_identity.sha256
        != expected_sha
        or source_identity.size_bytes
        != expected_size
    ):
        raise MonthlyTaxonomyExecutionError(
            "authoritative source artifact identity changed"
        )

    destination = _storage_destination(
        authoritative_root,
        key,
    )

    expected_observation = (
        monthly_authoritative_storage
        .StoredObjectObservation(
            object_key=key,
            sha256=expected_sha,
            size_bytes=expected_size,
        )
    )

    if os.path.lexists(
        destination
    ):
        return _observe_key(
            authoritative_root,
            expected_observation,
        )

    temporary = _temporary_storage_path(
        destination
    )

    digest = hashlib.sha256()
    written = 0
    temporary_stat = None
    linked = False

    try:
        descriptor = os.open(
            temporary,
            (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
            ),
            0o644,
        )

        try:
            os.fchmod(
                descriptor,
                0o644,
            )

            with os.fdopen(
                descriptor,
                "wb",
                closefd=True,
            ) as target:
                descriptor = -1

                with source_file.open(
                    "rb"
                ) as origin:
                    while True:
                        block = origin.read(
                            8 * 1024 * 1024
                        )

                        if not block:
                            break

                        target.write(
                            block
                        )

                        digest.update(
                            block
                        )

                        written += len(
                            block
                        )

                target.flush()

                os.fsync(
                    target.fileno()
                )

        finally:
            if descriptor >= 0:
                os.close(
                    descriptor
                )

        if (
            digest.hexdigest()
            != expected_sha
            or written != expected_size
        ):
            raise MonthlyTaxonomyExecutionError(
                "temporary authoritative copy identity changed"
            )

        temporary_stat = (
            temporary.stat()
        )

        try:
            os.link(
                temporary,
                destination,
            )

            linked = True

        except FileExistsError:
            linked = False

        _fsync_directory(
            destination.parent
        )

        observed = _observe_key(
            authoritative_root,
            expected_observation,
        )

    except Exception:
        cleanup_errors = []

        if (
            linked
            and os.path.lexists(
                destination
            )
        ):
            try:
                _remove_owned_hard_link(
                    source=temporary,
                    destination=destination,
                )
            except Exception as exc:
                cleanup_errors.append(
                    exc
                )

        if (
            temporary_stat is not None
            and os.path.lexists(
                temporary
            )
        ):
            try:
                _remove_owned_file(
                    temporary,
                    device=(
                        temporary_stat.st_dev
                    ),
                    inode=(
                        temporary_stat.st_ino
                    ),
                )
            except Exception as exc:
                cleanup_errors.append(
                    exc
                )

        if cleanup_errors:
            raise MonthlyTaxonomyExecutionError(
                "authoritative publication failed and cleanup was incomplete"
            )

        raise

    if (
        temporary_stat is not None
        and os.path.lexists(
            temporary
        )
    ):
        _remove_owned_file(
            temporary,
            device=(
                temporary_stat.st_dev
            ),
            inode=(
                temporary_stat.st_ino
            ),
        )

        _fsync_directory(
            destination.parent
        )

    return observed


def _publish_bytes_to_key(
    *,
    payload: bytes,
    authoritative_root: Path,
    key: str,
) -> monthly_authoritative_storage.StoredObjectObservation:
    if not isinstance(
        payload,
        bytes,
    ):
        raise MonthlyTaxonomyExecutionError(
            "authoritative byte payload has wrong type"
        )

    if not payload:
        raise MonthlyTaxonomyExecutionError(
            "authoritative byte payload is empty"
        )

    destination = _storage_destination(
        authoritative_root,
        key,
    )

    digest = _sha256_bytes(
        payload
    )

    expected = (
        monthly_authoritative_storage
        .StoredObjectObservation(
            object_key=key,
            sha256=digest,
            size_bytes=len(
                payload
            ),
        )
    )

    if os.path.lexists(
        destination
    ):
        return _observe_key(
            authoritative_root,
            expected,
        )

    temporary = _temporary_storage_path(
        destination
    )

    temporary_stat = None
    linked = False

    try:
        _write_no_clobber(
            temporary,
            payload,
        )

        temporary_stat = (
            temporary.stat()
        )

        observed_temporary = (
            source_taxonomy_acquisition
            .file_identity(
                temporary
            )
        )

        if (
            observed_temporary.sha256
            != digest
            or observed_temporary.size_bytes
            != len(
                payload
            )
        ):
            raise MonthlyTaxonomyExecutionError(
                "temporary authoritative payload readback changed"
            )

        try:
            os.link(
                temporary,
                destination,
            )

            linked = True

        except FileExistsError:
            linked = False

        _fsync_directory(
            destination.parent
        )

        observed = _observe_key(
            authoritative_root,
            expected,
        )

    except Exception:
        cleanup_errors = []

        if (
            linked
            and os.path.lexists(
                destination
            )
        ):
            try:
                _remove_owned_hard_link(
                    source=temporary,
                    destination=destination,
                )
            except Exception as exc:
                cleanup_errors.append(
                    exc
                )

        if (
            temporary_stat is not None
            and os.path.lexists(
                temporary
            )
        ):
            try:
                _remove_owned_file(
                    temporary,
                    device=(
                        temporary_stat.st_dev
                    ),
                    inode=(
                        temporary_stat.st_ino
                    ),
                )
            except Exception as exc:
                cleanup_errors.append(
                    exc
                )

        if cleanup_errors:
            raise MonthlyTaxonomyExecutionError(
                "authoritative byte publication failed "
                "and cleanup was incomplete"
            )

        raise

    if (
        temporary_stat is not None
        and os.path.lexists(
            temporary
        )
    ):
        _remove_owned_file(
            temporary,
            device=(
                temporary_stat.st_dev
            ),
            inode=(
                temporary_stat.st_ino
            ),
        )

        _fsync_directory(
            destination.parent
        )

    return observed


def build_authenticated_upstream_context(
    *,
    source_snapshot_record_payload: bytes,
    raw_source_response_payload: bytes,
    expected_release_id: str,
    expected_source_snapshot_id: str,
    expected_source_snapshot_record_sha256: str,
    chromosome_integrity_decisions_sha256: str,
    chromosome_integrity_record_sha256: str,
    chromosome_integrity_completion_sha256: str,
    execution_git_commit: str,
) -> AuthenticatedMonthlyTaxonomyUpstream:
    """Bind wrapper-authenticated Stage 1 and Stage 6 identities."""

    source_payload = _require_bytes(
        source_snapshot_record_payload,
        label="source-snapshot record",
    )

    raw_payload = _require_bytes(
        raw_source_response_payload,
        label="raw source response",
    )

    release = _release_id(
        expected_release_id
    )

    snapshot = _nonempty_text(
        expected_source_snapshot_id,
        label="source snapshot ID",
    )

    record_sha = _sha256(
        expected_source_snapshot_record_sha256,
        label="source-snapshot record SHA256",
    )

    commit = _commit(
        execution_git_commit
    )

    try:
        source = (
            monthly_taxonomy_snapshot
            .build_monthly_taxonomy_source_context(
                source_payload,
                expected_source_snapshot_record_sha256=(
                    record_sha
                ),
                origin_git_commit=(
                    commit
                ),
            )
        )
    except Exception as exc:
        raise MonthlyTaxonomyExecutionError(
            "authenticated Stage 1 context could not be bound"
        ) from exc

    if source.release_id != release:
        raise MonthlyTaxonomyExecutionError(
            "authenticated Stage 1 release differs from Stage 6"
        )

    if source.source_snapshot_id != snapshot:
        raise MonthlyTaxonomyExecutionError(
            "authenticated Stage 1 snapshot differs from Stage 6"
        )

    observed_raw_sha = _sha256_bytes(
        raw_payload
    )

    if (
        observed_raw_sha
        != source.source_raw_response_sha256
    ):
        raise MonthlyTaxonomyExecutionError(
            "raw source response differs from authenticated Stage 1 record"
        )

    return AuthenticatedMonthlyTaxonomyUpstream(
        release_id=release,
        source_snapshot_id=snapshot,
        source_snapshot_record_payload=(
            source_payload
        ),
        source_snapshot_record_sha256=(
            record_sha
        ),
        raw_source_response_payload=(
            raw_payload
        ),
        source_raw_response_sha256=(
            observed_raw_sha
        ),
        chromosome_integrity_decisions_sha256=(
            _sha256(
                chromosome_integrity_decisions_sha256,
                label=(
                    "chromosome-integrity decisions SHA256"
                ),
            )
        ),
        chromosome_integrity_record_sha256=(
            _sha256(
                chromosome_integrity_record_sha256,
                label=(
                    "chromosome-integrity record SHA256"
                ),
            )
        ),
        chromosome_integrity_completion_sha256=(
            _sha256(
                chromosome_integrity_completion_sha256,
                label=(
                    "chromosome-integrity completion SHA256"
                ),
            )
        ),
        execution_git_commit=commit,
    )


def audit_authenticated_upstream_context(
    upstream: AuthenticatedMonthlyTaxonomyUpstream,
) -> AuthenticatedMonthlyTaxonomyUpstream:
    """Reconstruct internal Stage 1 bindings before operational use."""

    if not isinstance(
        upstream,
        AuthenticatedMonthlyTaxonomyUpstream,
    ):
        raise MonthlyTaxonomyExecutionError(
            "authenticated upstream context has wrong type"
        )

    source_payload = _require_bytes(
        upstream.source_snapshot_record_payload,
        label="source-snapshot record",
    )

    raw_payload = _require_bytes(
        upstream.raw_source_response_payload,
        label="raw source response",
    )

    record_sha = _sha256(
        upstream.source_snapshot_record_sha256,
        label="source-snapshot record SHA256",
    )

    if (
        _sha256_bytes(
            source_payload
        )
        != record_sha
    ):
        raise MonthlyTaxonomyExecutionError(
            "authenticated source-snapshot record bytes changed"
        )

    commit = _commit(
        upstream.execution_git_commit
    )

    try:
        source = (
            monthly_taxonomy_snapshot
            .build_monthly_taxonomy_source_context(
                source_payload,
                expected_source_snapshot_record_sha256=(
                    record_sha
                ),
                origin_git_commit=(
                    commit
                ),
            )
        )
    except Exception as exc:
        raise MonthlyTaxonomyExecutionError(
            "authenticated Stage 1 context failed reauthentication"
        ) from exc

    release = _release_id(
        upstream.release_id
    )

    snapshot = _nonempty_text(
        upstream.source_snapshot_id,
        label="source snapshot ID",
    )

    if source.release_id != release:
        raise MonthlyTaxonomyExecutionError(
            "authenticated upstream release binding changed"
        )

    if source.source_snapshot_id != snapshot:
        raise MonthlyTaxonomyExecutionError(
            "authenticated upstream source-snapshot binding changed"
        )

    declared_raw_sha = _sha256(
        upstream.source_raw_response_sha256,
        label="raw source response SHA256",
    )

    observed_raw_sha = _sha256_bytes(
        raw_payload
    )

    if (
        observed_raw_sha
        != declared_raw_sha
        or declared_raw_sha
        != source.source_raw_response_sha256
    ):
        raise MonthlyTaxonomyExecutionError(
            "raw source response differs from authenticated Stage 1 record"
        )

    decisions_sha = _sha256(
        upstream.chromosome_integrity_decisions_sha256,
        label="chromosome-integrity decisions SHA256",
    )

    record_identity = _sha256(
        upstream.chromosome_integrity_record_sha256,
        label="chromosome-integrity record SHA256",
    )

    completion_sha = _sha256(
        upstream.chromosome_integrity_completion_sha256,
        label="chromosome-integrity completion SHA256",
    )

    return AuthenticatedMonthlyTaxonomyUpstream(
        release_id=release,
        source_snapshot_id=snapshot,
        source_snapshot_record_payload=(
            source_payload
        ),
        source_snapshot_record_sha256=(
            record_sha
        ),
        raw_source_response_payload=(
            raw_payload
        ),
        source_raw_response_sha256=(
            observed_raw_sha
        ),
        chromosome_integrity_decisions_sha256=(
            decisions_sha
        ),
        chromosome_integrity_record_sha256=(
            record_identity
        ),
        chromosome_integrity_completion_sha256=(
            completion_sha
        ),
        execution_git_commit=commit,
    )


def build_acquisition_provenance(
    *,
    upstream: AuthenticatedMonthlyTaxonomyUpstream,
    validation_wrapper_sha256: str,
    execution_support_sha256: str,
    execution_method_sha256: str,
    source_taxonomy_sha256: str,
    acquisition_started_utc: str,
    acquisition_completed_utc: str,
    python_version: str,
    openssl_version: str,
    download: source_taxonomy_acquisition.DownloadIdentity,
    downloader_identity: str,
    archive_validation: source_taxonomy_acquisition.ArchiveValidation,
    archive_identity: source_taxonomy_acquisition.FileIdentity,
    member_identities: Mapping[
        str,
        source_taxonomy_acquisition.FileIdentity,
    ],
) -> dict[
    str,
    object,
]:
    """Build closed monthly taxonomy acquisition provenance."""

    upstream = audit_authenticated_upstream_context(
        upstream
    )

    started = _timestamp(
        acquisition_started_utc,
        label="taxonomy acquisition start",
    )

    completed = _timestamp(
        acquisition_completed_utc,
        label="taxonomy acquisition completion",
    )

    if completed < started:
        raise MonthlyTaxonomyExecutionError(
            "taxonomy acquisition completion precedes start"
        )

    if not isinstance(
        download,
        source_taxonomy_acquisition.DownloadIdentity,
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy download identity has wrong type"
        )

    if (
        download.requested_url
        != monthly_taxonomy_snapshot.TAXONOMY_URL
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy requested URL changed"
        )

    if (
        not isinstance(
            download.final_url,
            str,
        )
        or not download.final_url.startswith(
            "https://"
        )
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy final URL must use HTTPS"
        )

    if (
        isinstance(
            download.http_status,
            bool,
        )
        or not isinstance(
            download.http_status,
            int,
        )
        or download.http_status < 200
        or download.http_status >= 300
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy HTTP status is invalid"
        )

    _optional_header(
        download.etag,
        label="taxonomy ETag",
    )

    _optional_header(
        download.last_modified,
        label="taxonomy Last-Modified",
    )

    if not isinstance(
        archive_validation,
        source_taxonomy_acquisition.ArchiveValidation,
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy archive validation has wrong type"
        )

    if (
        isinstance(
            archive_validation.member_count,
            bool,
        )
        or not isinstance(
            archive_validation.member_count,
            int,
        )
        or archive_validation.member_count <= 0
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy archive member count is invalid"
        )

    if not isinstance(
        archive_identity,
        source_taxonomy_acquisition.FileIdentity,
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy archive identity has wrong type"
        )

    expected_members = {
        "nodes.dmp",
        "merged.dmp",
        "delnodes.dmp",
    }

    if set(
        member_identities
    ) != expected_members:
        raise MonthlyTaxonomyExecutionError(
            "taxonomy resolver-input identity set changed"
        )

    archive_sha = _sha256(
        archive_identity.sha256,
        label="taxonomy archive SHA256",
    )

    archive_size = _positive_size(
        archive_identity.size_bytes,
        label="taxonomy archive size",
    )

    if (
        archive_sha != download.sha256
        or archive_size
        != download.size_bytes
    ):
        raise MonthlyTaxonomyExecutionError(
            "accepted taxonomy archive differs from download"
        )

    checked_members = {}

    for name in (
        "nodes.dmp",
        "merged.dmp",
        "delnodes.dmp",
    ):
        identity = member_identities[
            name
        ]

        if not isinstance(
            identity,
            source_taxonomy_acquisition.FileIdentity,
        ):
            raise MonthlyTaxonomyExecutionError(
                f"{name} identity has wrong type"
            )

        checked_members[
            name
        ] = (
            _sha256(
                identity.sha256,
                label=f"{name} SHA256",
            ),
            _positive_size(
                identity.size_bytes,
                label=f"{name} size",
            ),
        )

    support_sha = _sha256(
        execution_support_sha256,
        label="execution-support module SHA256",
    )

    wrapper_sha = _sha256(
        validation_wrapper_sha256,
        label="validation-wrapper SHA256",
    )

    method_sha = _sha256(
        execution_method_sha256,
        label="execution-method SHA256",
    )

    if method_sha != EXECUTION_METHOD_SHA256:
        raise MonthlyTaxonomyExecutionError(
            "execution-method identity changed"
        )

    resolver_sha = _sha256(
        source_taxonomy_sha256,
        label="source_taxonomy.py SHA256",
    )

    if (
        resolver_sha
        != monthly_taxonomy_snapshot
        .SOURCE_TAXONOMY_SHA256
    ):
        raise MonthlyTaxonomyExecutionError(
            "frozen taxonomy resolver identity changed"
        )

    return {
        "schema_version":
            ACQUISITION_SCHEMA,
        "status":
            ACQUISITION_STATUS,
        "release_id":
            upstream.release_id,
        "source_snapshot_id":
            upstream.source_snapshot_id,
        "source_snapshot_record_sha256":
            upstream.source_snapshot_record_sha256,
        "source_raw_response_sha256":
            upstream.source_raw_response_sha256,
        "chromosome_integrity_completion_sha256":
            upstream.chromosome_integrity_completion_sha256,
        "execution_git_commit":
            upstream.execution_git_commit,
        "execution_support_module_sha256":
            support_sha,
        "validation_wrapper_sha256":
            wrapper_sha,
        "execution_method_sha256":
            method_sha,
        "source_taxonomy_sha256":
            resolver_sha,
        "requested_url":
            download.requested_url,
        "final_url":
            download.final_url,
        "http_status":
            download.http_status,
        "etag":
            download.etag,
        "last_modified":
            download.last_modified,
        "acquisition_started_utc":
            started,
        "acquisition_completed_utc":
            completed,
        "downloader_identity":
            _nonempty_text(
                downloader_identity,
                label="downloader identity",
            ),
        "python_version":
            _nonempty_text(
                python_version,
                label="Python version",
            ),
        "openssl_version":
            _nonempty_text(
                openssl_version,
                label="OpenSSL version",
            ),
        "archive_member_count":
            archive_validation.member_count,
        "archive_sha256":
            archive_sha,
        "archive_size_bytes":
            archive_size,
        "nodes_sha256":
            checked_members[
                "nodes.dmp"
            ][0],
        "nodes_size_bytes":
            checked_members[
                "nodes.dmp"
            ][1],
        "merged_sha256":
            checked_members[
                "merged.dmp"
            ][0],
        "merged_size_bytes":
            checked_members[
                "merged.dmp"
            ][1],
        "delnodes_sha256":
            checked_members[
                "delnodes.dmp"
            ][0],
        "delnodes_size_bytes":
            checked_members[
                "delnodes.dmp"
            ][1],
        "structural_validation_result":
            "PASS",
        "taxonomy_resolution_performed":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }


def serialize_acquisition_provenance(
    **kwargs,
) -> bytes:
    return _canonical_json(
        build_acquisition_provenance(
            **kwargs
        )
    )


def audit_acquisition_provenance(
    payload: bytes,
    **kwargs,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy acquisition provenance must be bytes"
        )

    try:
        record = json.loads(
            payload
        )
    except json.JSONDecodeError as exc:
        raise MonthlyTaxonomyExecutionError(
            "taxonomy acquisition provenance is invalid JSON"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy acquisition provenance must be an object"
        )

    if set(
        record
    ) != ACQUISITION_FIELDS:
        raise MonthlyTaxonomyExecutionError(
            "taxonomy acquisition provenance schema changed"
        )

    if (
        record.get(
            "schema_version"
        )
        != ACQUISITION_SCHEMA
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy acquisition provenance schema version changed"
        )

    if (
        record.get(
            "status"
        )
        != ACQUISITION_STATUS
    ):
        raise MonthlyTaxonomyExecutionError(
            "taxonomy acquisition provenance status changed"
        )

    for field in (
        "taxonomy_resolution_performed",
        "structural_features_calculated",
        "selector_outcomes_calculated",
    ):
        if record[
            field
        ] is not False:
            raise MonthlyTaxonomyExecutionError(
                f"{field} must remain false at Stage 7"
            )

    reconstruction_kwargs = dict(
        kwargs
    )

    recorded_python_version = _nonempty_text(
        record[
            "python_version"
        ],
        label="recorded Python version",
    )

    recorded_openssl_version = _nonempty_text(
        record[
            "openssl_version"
        ],
        label="recorded OpenSSL version",
    )

    for name, recorded_value in (
        (
            "python_version",
            recorded_python_version,
        ),
        (
            "openssl_version",
            recorded_openssl_version,
        ),
    ):
        if (
            name in reconstruction_kwargs
            and reconstruction_kwargs[
                name
            ] != recorded_value
        ):
            raise MonthlyTaxonomyExecutionError(
                f"recorded {name} differs from supplied acquisition evidence"
            )

        reconstruction_kwargs[
            name
        ] = recorded_value

    expected = (
        serialize_acquisition_provenance(
            **reconstruction_kwargs
        )
    )

    if payload != expected:
        raise MonthlyTaxonomyExecutionError(
            "taxonomy acquisition provenance differs "
            "from reconstructed execution evidence"
        )

    return record


def _promote_downloaded_archive(
    *,
    partial: Path,
    final: Path,
    expected_identity: (
        source_taxonomy_acquisition
        .DownloadIdentity
    ),
) -> source_taxonomy_acquisition.FileIdentity:
    partial_file = _require_regular_file(
        partial,
        label="partial taxonomy archive",
    )

    observed = (
        source_taxonomy_acquisition
        .file_identity(
            partial_file
        )
    )

    if (
        observed.sha256
        != expected_identity.sha256
        or observed.size_bytes
        != expected_identity.size_bytes
    ):
        raise MonthlyTaxonomyExecutionError(
            "partial taxonomy archive readback changed"
        )

    if os.path.lexists(
        final
    ):
        raise MonthlyTaxonomyExecutionError(
            "accepted taxonomy archive already exists"
        )

    os.link(
        partial,
        final,
    )

    _fsync_directory(
        final.parent
    )

    accepted = _require_regular_file(
        final,
        label="accepted taxonomy archive",
    )

    final_identity = (
        source_taxonomy_acquisition
        .file_identity(
            accepted
        )
    )

    if final_identity != observed:
        try:
            _remove_owned_hard_link(
                source=partial,
                destination=final,
            )
        finally:
            _fsync_directory(
                final.parent
            )

        raise MonthlyTaxonomyExecutionError(
            "accepted taxonomy archive readback changed"
        )

    partial.unlink()

    _fsync_directory(
        final.parent
    )

    return final_identity


def _authoritative_sources(
    workspace: Path,
) -> dict[
    str,
    Path,
]:
    return {
        f"{STAGE_ID}/{ARCHIVE_NAME}":
            workspace
            / ARCHIVE_NAME,
        f"{STAGE_ID}/nodes.dmp":
            workspace
            / "nodes.dmp",
        f"{STAGE_ID}/merged.dmp":
            workspace
            / "merged.dmp",
        f"{STAGE_ID}/delnodes.dmp":
            workspace
            / "delnodes.dmp",
        f"{STAGE_ID}/{ACQUISITION_PROVENANCE_NAME}":
            workspace
            / ACQUISITION_PROVENANCE_NAME,
        f"{STAGE_ID}/{CONTENT_MANIFEST_NAME}":
            workspace
            / CONTENT_MANIFEST_NAME,
        f"{STAGE_ID}/{RECORD_NAME}":
            workspace
            / RECORD_NAME,
    }


def _publish_authoritative_bundle(
    *,
    workspace: Path,
    authoritative_root: Path,
    upstream: AuthenticatedMonthlyTaxonomyUpstream,
) -> tuple[
    bytes,
    str,
    bytes,
    str,
]:
    sources = _authoritative_sources(
        workspace
    )

    if tuple(
        sources
    ) != AUTHORITATIVE_LOGICAL_PATHS:
        raise MonthlyTaxonomyExecutionError(
            "authoritative logical artifact order changed"
        )

    artifacts = tuple(
        monthly_authoritative_storage
        .artifact_from_file(
            logical_path,
            source,
        )
        for logical_path, source
        in sources.items()
    )

    manifest_payload = (
        monthly_authoritative_storage
        .serialize_authoritative_manifest(
            release_id=(
                upstream.release_id
            ),
            source_snapshot_id=(
                upstream.source_snapshot_id
            ),
            origin_git_commit=(
                upstream.execution_git_commit
            ),
            stage_id=STAGE_ID,
            artifacts=artifacts,
        )
    )

    monthly_authoritative_storage.audit_authoritative_manifest(
        manifest_payload
    )

    expected_objects = (
        monthly_authoritative_storage
        .expected_stored_objects(
            manifest_payload
        )
    )

    if (
        len(
            expected_objects
        )
        != EXPECTED_AUTHORITATIVE_VERIFIED_OBJECT_COUNT
    ):
        raise MonthlyTaxonomyExecutionError(
            "Stage 7 authoritative verified-object count changed"
        )

    manifest_record = (
        monthly_authoritative_storage
        .audit_authoritative_manifest(
            manifest_payload
        )
    )

    artifact_by_logical = {
        value[
            "logical_path"
        ]:
            value
        for value in manifest_record[
            "artifacts"
        ]
    }

    for logical_path, source in sources.items():
        artifact = artifact_by_logical[
            logical_path
        ]

        _publish_file_to_key(
            source=source,
            authoritative_root=(
                authoritative_root
            ),
            key=artifact[
                "object_key"
            ],
            expected_sha256=artifact[
                "sha256"
            ],
            expected_size_bytes=artifact[
                "size_bytes"
            ],
        )

    manifest_key = (
        monthly_authoritative_storage
        .authoritative_manifest_key(
            manifest_payload
        )
    )

    _publish_bytes_to_key(
        payload=manifest_payload,
        authoritative_root=(
            authoritative_root
        ),
        key=manifest_key,
    )

    observed_objects = tuple(
        _observe_key(
            authoritative_root,
            expected,
        )
        for expected in expected_objects
    )

    if observed_objects != expected_objects:
        raise MonthlyTaxonomyExecutionError(
            "authoritative stored-object readback changed"
        )

    receipt_payload = (
        monthly_authoritative_storage
        .serialize_authoritative_receipt(
            manifest_payload,
            observed_objects=(
                observed_objects
            ),
        )
    )

    receipt_record = (
        monthly_authoritative_storage
        .audit_authoritative_receipt(
            receipt_payload,
            manifest_payload=(
                manifest_payload
            ),
        )
    )

    if (
        receipt_record[
            "verified_object_count"
        ]
        != EXPECTED_AUTHORITATIVE_VERIFIED_OBJECT_COUNT
    ):
        raise MonthlyTaxonomyExecutionError(
            "authoritative receipt verified-object count changed"
        )

    receipt_key = (
        monthly_authoritative_storage
        .authoritative_receipt_key(
            receipt_payload,
            manifest_payload=(
                manifest_payload
            ),
        )
    )

    receipt_observation = (
        _publish_bytes_to_key(
            payload=receipt_payload,
            authoritative_root=(
                authoritative_root
            ),
            key=receipt_key,
        )
    )

    if (
        receipt_observation.sha256
        != _sha256_bytes(
            receipt_payload
        )
        or receipt_observation.size_bytes
        != len(
            receipt_payload
        )
    ):
        raise MonthlyTaxonomyExecutionError(
            "authoritative receipt readback changed"
        )

    stored_receipt = (
        _storage_destination(
            authoritative_root,
            receipt_key,
        )
        .read_bytes()
    )

    if stored_receipt != receipt_payload:
        raise MonthlyTaxonomyExecutionError(
            "stored authoritative receipt bytes changed"
        )

    monthly_authoritative_storage.audit_authoritative_receipt(
        stored_receipt,
        manifest_payload=(
            manifest_payload
        ),
    )

    return (
        manifest_payload,
        manifest_key,
        receipt_payload,
        receipt_key,
    )


def _validate_local_inventory(
    workspace: Path,
) -> None:
    observed = {
        child.name
        for child in workspace.iterdir()
    }

    if observed != LOCAL_STAGE_FILES:
        raise MonthlyTaxonomyExecutionError(
            "taxonomy support workspace inventory changed"
        )

    for name in LOCAL_STAGE_FILES:
        _require_regular_file(
            workspace
            / name,
            label=(
                f"taxonomy support artifact {name}"
            ),
        )


def execute_monthly_taxonomy_support(
    *,
    workspace: Path,
    authoritative_root: Path,
    upstream: AuthenticatedMonthlyTaxonomyUpstream,
    validation_wrapper_sha256: str,
    upstream_stability_check: Callable[
        [],
        None,
    ],
    opener: Callable[..., object] = urllib.request.urlopen,
    timestamp_provider: Callable[
        [],
        str,
    ] = _utc_now,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> MonthlyTaxonomySupportResult:
    """
    Acquire and durably store Stage 7 evidence in a fresh partial workspace.

    Canonical local stage publication and completion publication belong to the
    validation wrapper and are intentionally outside this support function.
    """

    work = _require_empty_workspace(
        Path(
            workspace
        )
    )

    authoritative = _require_real_directory(
        Path(
            authoritative_root
        ),
        label="authoritative root",
    )

    upstream = audit_authenticated_upstream_context(
        upstream
    )

    wrapper_sha = _sha256(
        validation_wrapper_sha256,
        label="validation-wrapper SHA256",
    )

    if not callable(
        upstream_stability_check
    ):
        raise MonthlyTaxonomyExecutionError(
            "upstream stability callback is not callable"
        )

    opener_identity = _callable_identity(
        opener
    )

    network_timeout = _timeout(
        timeout
    )

    if not callable(
        timestamp_provider
    ):
        raise MonthlyTaxonomyExecutionError(
            "timestamp provider is not callable"
        )

    try:
        support_sha = (
            execution_support_module_sha256()
        )

        resolver_sha = (
            source_taxonomy_acquisition
            .validate_resolver_identity()
        )

        if (
            resolver_sha
            != monthly_taxonomy_snapshot
            .SOURCE_TAXONOMY_SHA256
        ):
            raise MonthlyTaxonomyExecutionError(
                "frozen taxonomy resolver identity changed"
            )

        upstream_stability_check()

        started = _timestamp(
            timestamp_provider(),
            label="taxonomy acquisition start",
        )

        python_version = _nonempty_text(
            platform.python_version(),
            label="Python version",
        )

        openssl_version = _nonempty_text(
            ssl.OPENSSL_VERSION,
            label="OpenSSL version",
        )

        partial_archive = (
            work
            / PARTIAL_ARCHIVE_NAME
        )

        response = opener(
            monthly_taxonomy_snapshot.TAXONOMY_URL,
            timeout=network_timeout,
        )

        try:
            download = (
                source_taxonomy_acquisition
                .stream_http_response(
                    response,
                    partial_archive,
                    requested_url=(
                        monthly_taxonomy_snapshot
                        .TAXONOMY_URL
                    ),
                )
            )
        finally:
            close = getattr(
                response,
                "close",
                None,
            )

            if callable(
                close
            ):
                close()

        _fsync_file(
            partial_archive
        )

        partial_identity = (
            source_taxonomy_acquisition
            .file_identity(
                partial_archive
            )
        )

        if (
            partial_identity.sha256
            != download.sha256
            or partial_identity.size_bytes
            != download.size_bytes
        ):
            raise MonthlyTaxonomyExecutionError(
                "streamed taxonomy archive readback changed"
            )

        source_taxonomy_acquisition.validate_archive(
            partial_archive
        )

        archive_path = (
            work
            / ARCHIVE_NAME
        )

        archive_identity = (
            _promote_downloaded_archive(
                partial=(
                    partial_archive
                ),
                final=archive_path,
                expected_identity=(
                    download
                ),
            )
        )

        archive_validation = (
            source_taxonomy_acquisition
            .validate_archive(
                archive_path
            )
        )

        member_identities = (
            source_taxonomy_acquisition
            .extract_required_members(
                archive_path,
                work,
            )
        )

        archive_after_extraction = (
            source_taxonomy_acquisition
            .file_identity(
                archive_path
            )
        )

        if (
            archive_after_extraction
            != archive_identity
        ):
            raise MonthlyTaxonomyExecutionError(
                "taxonomy archive changed during extraction"
            )

        source_taxonomy_acquisition.structural_validate(
            work
        )

        completed = _timestamp(
            timestamp_provider(),
            label="taxonomy acquisition completion",
        )

        provenance_kwargs = {
            "upstream":
                upstream,
            "validation_wrapper_sha256":
                wrapper_sha,
            "execution_support_sha256":
                support_sha,
            "execution_method_sha256":
                EXECUTION_METHOD_SHA256,
            "source_taxonomy_sha256":
                resolver_sha,
            "acquisition_started_utc":
                started,
            "acquisition_completed_utc":
                completed,
            "python_version":
                python_version,
            "openssl_version":
                openssl_version,
            "download":
                download,
            "downloader_identity":
                opener_identity,
            "archive_validation":
                archive_validation,
            "archive_identity":
                archive_identity,
            "member_identities":
                member_identities,
        }

        provenance_payload = (
            serialize_acquisition_provenance(
                **provenance_kwargs
            )
        )

        provenance_path = (
            work
            / ACQUISITION_PROVENANCE_NAME
        )

        _write_no_clobber(
            provenance_path,
            provenance_payload,
        )

        _fsync_directory(
            work
        )

        provenance_readback = (
            _require_regular_file(
                provenance_path,
                label=(
                    "taxonomy acquisition provenance"
                ),
            )
            .read_bytes()
        )

        if (
            provenance_readback
            != provenance_payload
        ):
            raise MonthlyTaxonomyExecutionError(
                "taxonomy acquisition provenance readback changed"
            )

        audit_acquisition_provenance(
            provenance_readback,
            **provenance_kwargs,
        )

        provenance_sha = (
            _sha256_bytes(
                provenance_payload
            )
        )

        content_manifest_sha = (
            source_taxonomy_acquisition
            .write_content_manifest(
                work
            )
        )

        content_manifest_path = (
            work
            / CONTENT_MANIFEST_NAME
        )

        _fsync_file(
            content_manifest_path
        )

        _fsync_directory(
            work
        )

        content_manifest_readback_sha = (
            source_taxonomy_acquisition
            .sha256_file(
                content_manifest_path
            )
        )

        if (
            content_manifest_readback_sha
            != content_manifest_sha
        ):
            raise MonthlyTaxonomyExecutionError(
                "taxonomy content manifest readback changed"
            )

        pure_source = (
            monthly_taxonomy_snapshot
            .build_monthly_taxonomy_source_context(
                upstream
                .source_snapshot_record_payload,
                expected_source_snapshot_record_sha256=(
                    upstream
                    .source_snapshot_record_sha256
                ),
                origin_git_commit=(
                    upstream
                    .execution_git_commit
                ),
            )
        )

        evidence = (
            monthly_taxonomy_snapshot
            .MonthlyTaxonomyAcquisitionEvidence(
                acquisition_started_utc=(
                    started
                ),
                acquisition_completed_utc=(
                    completed
                ),
                requested_url=(
                    download.requested_url
                ),
                final_url=(
                    download.final_url
                ),
                archive_sha256=(
                    archive_identity.sha256
                ),
                archive_size_bytes=(
                    archive_identity.size_bytes
                ),
                nodes_sha256=(
                    member_identities[
                        "nodes.dmp"
                    ].sha256
                ),
                nodes_size_bytes=(
                    member_identities[
                        "nodes.dmp"
                    ].size_bytes
                ),
                merged_sha256=(
                    member_identities[
                        "merged.dmp"
                    ].sha256
                ),
                merged_size_bytes=(
                    member_identities[
                        "merged.dmp"
                    ].size_bytes
                ),
                delnodes_sha256=(
                    member_identities[
                        "delnodes.dmp"
                    ].sha256
                ),
                delnodes_size_bytes=(
                    member_identities[
                        "delnodes.dmp"
                    ].size_bytes
                ),
                acquisition_provenance_sha256=(
                    provenance_sha
                ),
                content_manifest_sha256=(
                    content_manifest_sha
                ),
                acquisition_implementation_sha256=(
                    support_sha
                ),
                source_taxonomy_sha256=(
                    resolver_sha
                ),
            )
        )

        build = (
            monthly_taxonomy_snapshot
            .build_monthly_taxonomy_snapshot(
                pure_source,
                evidence,
            )
        )

        record_payload = (
            monthly_taxonomy_snapshot
            .serialize_monthly_taxonomy_snapshot_record(
                build
            )
        )

        record_path = (
            work
            / RECORD_NAME
        )

        _write_no_clobber(
            record_path,
            record_payload,
        )

        _fsync_directory(
            work
        )

        record_readback = (
            _require_regular_file(
                record_path,
                label=(
                    "monthly taxonomy snapshot record"
                ),
            )
            .read_bytes()
        )

        if record_readback != record_payload:
            raise MonthlyTaxonomyExecutionError(
                "monthly taxonomy snapshot record readback changed"
            )

        monthly_taxonomy_snapshot.audit_monthly_taxonomy_snapshot_record(
            record_readback,
            source_snapshot_record_payload=(
                upstream
                .source_snapshot_record_payload
            ),
            expected_source_snapshot_record_sha256=(
                upstream
                .source_snapshot_record_sha256
            ),
            origin_git_commit=(
                upstream
                .execution_git_commit
            ),
        )

        (
            authoritative_manifest_payload,
            authoritative_manifest_key,
            authoritative_receipt_payload,
            authoritative_receipt_key,
        ) = _publish_authoritative_bundle(
            workspace=work,
            authoritative_root=(
                authoritative
            ),
            upstream=upstream,
        )

        _write_no_clobber(
            work
            / AUTHORITATIVE_MANIFEST_LOCAL_NAME,
            authoritative_manifest_payload,
        )

        _write_no_clobber(
            work
            / AUTHORITATIVE_RECEIPT_LOCAL_NAME,
            authoritative_receipt_payload,
        )

        _fsync_directory(
            work
        )

        _validate_local_inventory(
            work
        )

        local_manifest = (
            work
            / AUTHORITATIVE_MANIFEST_LOCAL_NAME
        ).read_bytes()

        local_receipt = (
            work
            / AUTHORITATIVE_RECEIPT_LOCAL_NAME
        ).read_bytes()

        if (
            local_manifest
            != authoritative_manifest_payload
            or local_receipt
            != authoritative_receipt_payload
        ):
            raise MonthlyTaxonomyExecutionError(
                "local authoritative metadata readback changed"
            )

        monthly_authoritative_storage.audit_authoritative_manifest(
            local_manifest
        )

        receipt_record = (
            monthly_authoritative_storage
            .audit_authoritative_receipt(
                local_receipt,
                manifest_payload=(
                    local_manifest
                ),
            )
        )

        if (
            receipt_record[
                "verified_object_count"
            ]
            != EXPECTED_AUTHORITATIVE_VERIFIED_OBJECT_COUNT
        ):
            raise MonthlyTaxonomyExecutionError(
                "local authoritative receipt count changed"
            )

        upstream_stability_check()

        return MonthlyTaxonomySupportResult(
            workspace=work,
            release_id=(
                upstream.release_id
            ),
            source_snapshot_id=(
                upstream.source_snapshot_id
            ),
            taxonomy_snapshot_id=(
                build.taxonomy_snapshot_id
            ),
            acquisition_provenance_sha256=(
                provenance_sha
            ),
            content_manifest_sha256=(
                content_manifest_sha
            ),
            record_sha256=(
                _sha256_bytes(
                    record_payload
                )
            ),
            archive_sha256=(
                archive_identity.sha256
            ),
            nodes_sha256=(
                member_identities[
                    "nodes.dmp"
                ].sha256
            ),
            merged_sha256=(
                member_identities[
                    "merged.dmp"
                ].sha256
            ),
            delnodes_sha256=(
                member_identities[
                    "delnodes.dmp"
                ].sha256
            ),
            authoritative_manifest_sha256=(
                _sha256_bytes(
                    authoritative_manifest_payload
                )
            ),
            authoritative_manifest_key=(
                authoritative_manifest_key
            ),
            authoritative_receipt_sha256=(
                _sha256_bytes(
                    authoritative_receipt_payload
                )
            ),
            authoritative_receipt_key=(
                authoritative_receipt_key
            ),
            authoritative_verified_object_count=(
                EXPECTED_AUTHORITATIVE_VERIFIED_OBJECT_COUNT
            ),
        )

    except MonthlyTaxonomyExecutionError:
        raise

    except Exception as exc:
        raise MonthlyTaxonomyExecutionError(
            "monthly taxonomy support execution failed"
        ) from exc
