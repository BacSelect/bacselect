"""BacSelect selector-v1 taxonomy snapshot acquisition primitives.

The prospective acquisition method is frozen at:

    validation/selector-v1/
    prospective-taxonomy-snapshot-acquisition-method.md

This module contains archive validation, controlled extraction, provenance
construction, and the network acquisition entry point.

Importing this module performs no network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import ssl
import tarfile
from typing import BinaryIO, Callable, Mapping
import urllib.request

from bacselect import source_taxonomy


TAXONOMY_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/"
    "new_taxdump/new_taxdump.tar.gz"
)

ARCHIVE_NAME = "new_taxdump.tar.gz"

REQUIRED_MEMBERS = (
    "nodes.dmp",
    "merged.dmp",
    "delnodes.dmp",
)

ACQUISITION_PROVENANCE_NAME = (
    "taxonomy-acquisition.json"
)

CONTENT_MANIFEST_NAME = (
    "taxonomy-content-sha256.tsv"
)

FREEZE_RECORD_NAME = (
    "taxonomy-snapshot-freeze.json"
)

ACQUISITION_METHOD_SHA256 = (
    "4cdf7347be4e660e8ed8ea94bfe7a0e6"
    "c36b06c25f1ff399bd264eaf7c841f88"
)

SOURCE_TAXONOMY_SHA256 = (
    "9c8c4149c5db2a757e8c201a6523bdb1"
    "13511b5f72a4dd2893572dd8c7928e4d"
)

SOURCE_SNAPSHOT_ID = (
    "snapshot-20260825T132821Z"
)

SOURCE_SNAPSHOT_COMMIT = (
    "c19094a053482b8c2ecfbe0977d22f834e8dd159"
)

SOURCE_RAW_SHA256 = (
    "b1b016891ae4e976d03606dfb2f35f74"
    "b03d21cf3ec82832f77f4d113bd622d5"
)

SOURCE_ACQUISITION_SHA256 = (
    "6a1a9b35ee2590b7cd6eac1b087e8325"
    "4c1acbe9af912475bd9c9c1494ef8741"
)

LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

GIT_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

UTC_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)


class TaxonomyAcquisitionError(RuntimeError):
    """Raised when taxonomy snapshot acquisition fails closed."""


@dataclass(frozen=True)
class FileIdentity:
    """SHA256 and byte count for one immutable file."""

    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ArchiveMemberIdentity:
    """Validated identity of one required tar member."""

    name: str
    size_bytes: int


@dataclass(frozen=True)
class ArchiveValidation:
    """Result of validating one complete new_taxdump archive."""

    required_members: tuple[
        ArchiveMemberIdentity,
        ...
    ]
    member_count: int


@dataclass(frozen=True)
class DownloadIdentity:
    """Identity and HTTP metadata for one completed response body."""

    requested_url: str
    final_url: str
    http_status: int
    etag: str | None
    last_modified: str | None
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class SnapshotAcquisitionResult:
    """Immutable identities of one successfully frozen taxonomy snapshot."""

    snapshot_dir: Path
    snapshot_id: str
    archive_sha256: str
    nodes_sha256: str
    merged_sha256: str
    delnodes_sha256: str
    acquisition_provenance_sha256: str
    content_manifest_sha256: str
    freeze_record_sha256: str


def sha256_file(
    path: Path,
    block_size: int = 8 * 1024 * 1024,
) -> str:
    """Return streaming SHA256 for one regular file."""

    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise TaxonomyAcquisitionError(
            f"expected regular file: {path}"
        )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                block_size
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def file_identity(
    path: Path,
) -> FileIdentity:
    """Return SHA256 and byte count for one regular file."""

    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise TaxonomyAcquisitionError(
            f"expected regular file: {path}"
        )

    return FileIdentity(
        sha256=sha256_file(
            path
        ),
        size_bytes=path.stat().st_size,
    )


def utc_now() -> str:
    """Return current UTC time in the frozen provenance format."""

    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def validate_utc_timestamp(
    value: object,
    *,
    label: str,
) -> str:
    """Validate one canonical UTC timestamp."""

    if (
        not isinstance(
            value,
            str,
        )
        or not UTC_TIMESTAMP_RE.fullmatch(
            value
        )
    ):
        raise TaxonomyAcquisitionError(
            f"{label} is not a canonical UTC timestamp"
        )

    return value


def validate_git_commit(
    value: object,
) -> str:
    """Validate one full lowercase Git commit identity."""

    if (
        not isinstance(
            value,
            str,
        )
        or not GIT_COMMIT_RE.fullmatch(
            value
        )
    ):
        raise TaxonomyAcquisitionError(
            "BacSelect Git commit must be 40 lowercase hex characters"
        )

    return value


def validate_sha256(
    value: object,
    *,
    label: str,
) -> str:
    """Validate one lowercase SHA256 string."""

    if (
        not isinstance(
            value,
            str,
        )
        or not LOWER_SHA256_RE.fullmatch(
            value
        )
    ):
        raise TaxonomyAcquisitionError(
            f"{label} must be lowercase SHA256"
        )

    return value


def validate_resolver_identity() -> str:
    """Verify the frozen source_taxonomy.py implementation identity."""

    path = Path(
        source_taxonomy.__file__
    ).resolve()

    observed = sha256_file(
        path
    )

    if observed != SOURCE_TAXONOMY_SHA256:
        raise TaxonomyAcquisitionError(
            "source_taxonomy.py SHA256 mismatch: "
            f"{observed}"
        )

    return observed


def _validate_member_name(
    name: object,
) -> str:
    """Fail closed on unsafe POSIX tar member paths."""

    if (
        not isinstance(
            name,
            str,
        )
        or not name
    ):
        raise TaxonomyAcquisitionError(
            "archive member has empty or invalid name"
        )

    if "\x00" in name:
        raise TaxonomyAcquisitionError(
            "archive member contains NUL"
        )

    if "\\" in name:
        raise TaxonomyAcquisitionError(
            "archive member contains backslash"
        )

    path = PurePosixPath(
        name
    )

    if (
        path.is_absolute()
        or name.startswith("/")
        or any(
            part == ".."
            for part in path.parts
        )
    ):
        raise TaxonomyAcquisitionError(
            f"unsafe archive member path: {name!r}"
        )

    if (
        path.parts
        and path.parts[
            0
        ].endswith(":")
    ):
        raise TaxonomyAcquisitionError(
            f"unsafe archive member path: {name!r}"
        )

    return name


def _read_gzip_to_eof(
    path: Path,
    block_size: int = 8 * 1024 * 1024,
) -> None:
    """Force complete gzip decompression so CRC/truncation errors surface."""

    try:
        with gzip.open(
            path,
            "rb",
        ) as handle:
            while handle.read(
                block_size
            ):
                pass
    except (
        OSError,
        EOFError,
    ) as exc:
        raise TaxonomyAcquisitionError(
            "taxonomy archive failed gzip integrity validation"
        ) from exc


def validate_archive(
    archive_path: Path,
) -> ArchiveValidation:
    """Validate archive integrity, paths, and required-member structure."""

    if (
        not archive_path.is_file()
        or archive_path.is_symlink()
    ):
        raise TaxonomyAcquisitionError(
            f"taxonomy archive is not a regular file: {archive_path}"
        )

    _read_gzip_to_eof(
        archive_path
    )

    required: dict[
        str,
        list[
            tarfile.TarInfo
        ],
    ] = {
        name: []
        for name in REQUIRED_MEMBERS
    }

    member_count = 0

    try:
        with tarfile.open(
            archive_path,
            mode="r:gz",
        ) as archive:
            for member in archive:
                member_count += 1

                name = _validate_member_name(
                    member.name
                )

                if name in required:
                    required[
                        name
                    ].append(
                        member
                    )

    except (
        tarfile.TarError,
        OSError,
        EOFError,
    ) as exc:
        raise TaxonomyAcquisitionError(
            "taxonomy archive failed tar validation"
        ) from exc

    identities = []

    for name in REQUIRED_MEMBERS:
        matches = required[
            name
        ]

        if len(
            matches
        ) != 1:
            raise TaxonomyAcquisitionError(
                "required taxonomy archive member must occur "
                f"exactly once: {name} | observed={len(matches)}"
            )

        member = matches[
            0
        ]

        if not member.isfile():
            raise TaxonomyAcquisitionError(
                "required taxonomy archive member is not a "
                f"regular file: {name}"
            )

        if member.size < 0:
            raise TaxonomyAcquisitionError(
                f"required taxonomy member has invalid size: {name}"
            )

        identities.append(
            ArchiveMemberIdentity(
                name=name,
                size_bytes=member.size,
            )
        )

    return ArchiveValidation(
        required_members=tuple(
            identities
        ),
        member_count=member_count,
    )


def extract_required_members(
    archive_path: Path,
    output_dir: Path,
) -> dict[
    str,
    FileIdentity,
]:
    """Extract required members without extractall or path-derived targets."""

    validation = validate_archive(
        archive_path
    )

    expected_sizes = {
        item.name: item.size_bytes
        for item in validation.required_members
    }

    results: dict[
        str,
        FileIdentity,
    ] = {}

    try:
        with tarfile.open(
            archive_path,
            mode="r:gz",
        ) as archive:
            members = archive.getmembers()

            by_name = {
                name: [
                    member
                    for member in members
                    if member.name == name
                ]
                for name in REQUIRED_MEMBERS
            }

            for name in REQUIRED_MEMBERS:
                matches = by_name[
                    name
                ]

                if len(
                    matches
                ) != 1:
                    raise TaxonomyAcquisitionError(
                        "required taxonomy member changed "
                        f"during extraction: {name}"
                    )

                member = matches[
                    0
                ]

                if not member.isfile():
                    raise TaxonomyAcquisitionError(
                        f"required taxonomy member is not regular: {name}"
                    )

                source = archive.extractfile(
                    member
                )

                if source is None:
                    raise TaxonomyAcquisitionError(
                        f"could not read required taxonomy member: {name}"
                    )

                destination = (
                    output_dir
                    / name
                )

                digest = hashlib.sha256()
                written = 0

                try:
                    with destination.open(
                        "xb"
                    ) as target:
                        while True:
                            block = source.read(
                                1024 * 1024
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
                finally:
                    source.close()

                if written != expected_sizes[
                    name
                ]:
                    raise TaxonomyAcquisitionError(
                        "extracted taxonomy member size mismatch: "
                        f"{name} | expected={expected_sizes[name]} "
                        f"observed={written}"
                    )

                results[
                    name
                ] = FileIdentity(
                    sha256=digest.hexdigest(),
                    size_bytes=written,
                )

    except TaxonomyAcquisitionError:
        raise
    except (
        tarfile.TarError,
        OSError,
        EOFError,
    ) as exc:
        raise TaxonomyAcquisitionError(
            "controlled taxonomy extraction failed"
        ) from exc

    return results


def structural_validate(
    output_dir: Path,
) -> None:
    """Instantiate the frozen resolver without resolving candidate TaxIDs."""

    validate_resolver_identity()

    try:
        source_taxonomy.Taxonomy(
            nodes_path=(
                output_dir
                / "nodes.dmp"
            ),
            merged_path=(
                output_dir
                / "merged.dmp"
            ),
            delnodes_path=(
                output_dir
                / "delnodes.dmp"
            ),
        )
    except Exception as exc:
        raise TaxonomyAcquisitionError(
            "taxonomy structural validation failed"
        ) from exc


def write_json_new(
    path: Path,
    payload: Mapping[
        str,
        object,
    ],
) -> None:
    """Write deterministic JSON without overwriting existing evidence."""

    encoded = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    try:
        with path.open(
            "xb"
        ) as handle:
            handle.write(
                encoded
            )
    except FileExistsError as exc:
        raise TaxonomyAcquisitionError(
            f"refusing to overwrite existing evidence: {path}"
        ) from exc


def snapshot_id_from_started_utc(
    started_utc: str,
) -> str:
    """Derive deterministic taxonomy snapshot ID from acquisition start."""

    timestamp = validate_utc_timestamp(
        started_utc,
        label="acquisition start",
    )

    compact = (
        timestamp
        .replace(
            "-",
            "",
        )
        .replace(
            ":",
            "",
        )
    )

    return (
        "taxonomy-"
        + compact
    )


def stream_http_response(
    response: object,
    partial_path: Path,
    *,
    requested_url: str,
) -> DownloadIdentity:
    """Stream one successful HTTP response body to a new partial file."""

    status = getattr(
        response,
        "status",
        None,
    )

    if (
        not isinstance(
            status,
            int,
        )
        or isinstance(
            status,
            bool,
        )
        or status < 200
        or status >= 300
    ):
        raise TaxonomyAcquisitionError(
            f"taxonomy download returned non-success HTTP status: {status!r}"
        )

    geturl = getattr(
        response,
        "geturl",
        None,
    )

    if not callable(
        geturl
    ):
        raise TaxonomyAcquisitionError(
            "taxonomy HTTP response does not expose final URL"
        )

    final_url = geturl()

    if (
        not isinstance(
            final_url,
            str,
        )
        or not final_url.startswith(
            "https://"
        )
    ):
        raise TaxonomyAcquisitionError(
            "taxonomy download final URL is not HTTPS"
        )

    headers = getattr(
        response,
        "headers",
        None,
    )

    etag = None
    last_modified = None

    if headers is not None:
        getter = getattr(
            headers,
            "get",
            None,
        )

        if callable(
            getter
        ):
            etag = getter(
                "ETag"
            )
            last_modified = getter(
                "Last-Modified"
            )

            if etag is not None:
                etag = str(
                    etag
                )

            if last_modified is not None:
                last_modified = str(
                    last_modified
                )

    digest = hashlib.sha256()
    size_bytes = 0

    try:
        with partial_path.open(
            "xb"
        ) as handle:
            while True:
                block = response.read(
                    1024 * 1024
                )

                if not block:
                    break

                if not isinstance(
                    block,
                    bytes,
                ):
                    raise TaxonomyAcquisitionError(
                        "taxonomy HTTP response yielded non-byte content"
                    )

                handle.write(
                    block
                )

                digest.update(
                    block
                )

                size_bytes += len(
                    block
                )
    except FileExistsError as exc:
        raise TaxonomyAcquisitionError(
            f"refusing to overwrite partial archive: {partial_path}"
        ) from exc

    if size_bytes <= 0:
        raise TaxonomyAcquisitionError(
            "taxonomy HTTP response body is empty"
        )

    return DownloadIdentity(
        requested_url=requested_url,
        final_url=final_url,
        http_status=status,
        etag=etag,
        last_modified=last_modified,
        sha256=digest.hexdigest(),
        size_bytes=size_bytes,
    )


def write_content_manifest(
    snapshot_dir: Path,
) -> str:
    """Write deterministic content manifest and return its SHA256."""

    paths = (
        ARCHIVE_NAME,
        "nodes.dmp",
        "merged.dmp",
        "delnodes.dmp",
        ACQUISITION_PROVENANCE_NAME,
    )

    rows = [
        "sha256\tsize_bytes\tpath"
    ]

    for relative in paths:
        path = (
            snapshot_dir
            / relative
        )

        identity = file_identity(
            path
        )

        rows.append(
            "\t".join(
                (
                    identity.sha256,
                    str(
                        identity.size_bytes
                    ),
                    relative,
                )
            )
        )

    manifest = (
        snapshot_dir
        / CONTENT_MANIFEST_NAME
    )

    payload = (
        "\n".join(
            rows
        )
        + "\n"
    ).encode(
        "ascii"
    )

    try:
        with manifest.open(
            "xb"
        ) as handle:
            handle.write(
                payload
            )
    except FileExistsError as exc:
        raise TaxonomyAcquisitionError(
            f"refusing to overwrite content manifest: {manifest}"
        ) from exc

    return sha256_file(
        manifest
    )


def acquire_taxonomy_snapshot(
    snapshot_dir: Path,
    *,
    bacselect_git_commit: str,
    opener: Callable[..., object] = urllib.request.urlopen,
    timestamp_provider: Callable[[], str] = utc_now,
    timeout_seconds: int = 120,
) -> SnapshotAcquisitionResult:
    """Acquire, validate, extract, structurally check, and freeze taxonomy.

    The default opener performs the real HTTPS request. Tests must inject a
    synthetic/local opener until the implementation is frozen in Git.
    """

    commit = validate_git_commit(
        bacselect_git_commit
    )

    if (
        not isinstance(
            timeout_seconds,
            int,
        )
        or isinstance(
            timeout_seconds,
            bool,
        )
        or timeout_seconds <= 0
    ):
        raise TaxonomyAcquisitionError(
            "timeout_seconds must be a positive integer"
        )

    requested_url = TAXONOMY_URL

    if not requested_url.startswith(
        "https://"
    ):
        raise TaxonomyAcquisitionError(
            "prospective taxonomy URL is not HTTPS"
        )

    validate_resolver_identity()

    implementation_path = Path(
        __file__
    ).resolve()

    implementation_sha256 = sha256_file(
        implementation_path
    )

    method_sha256 = validate_sha256(
        ACQUISITION_METHOD_SHA256,
        label="taxonomy acquisition method SHA256",
    )

    started_utc = validate_utc_timestamp(
        timestamp_provider(),
        label="acquisition start",
    )

    snapshot_id = snapshot_id_from_started_utc(
        started_utc
    )

    try:
        snapshot_dir.mkdir(
            parents=True,
            exist_ok=False,
        )
    except FileExistsError as exc:
        raise TaxonomyAcquisitionError(
            f"refusing to reuse taxonomy snapshot directory: {snapshot_dir}"
        ) from exc

    partial_path = (
        snapshot_dir
        / (
            ARCHIVE_NAME
            + ".partial"
        )
    )

    archive_path = (
        snapshot_dir
        / ARCHIVE_NAME
    )

    try:
        try:
            response = opener(
                requested_url,
                timeout=timeout_seconds,
            )
        except Exception as exc:
            raise TaxonomyAcquisitionError(
                "taxonomy HTTPS request failed"
            ) from exc

        try:
            download = stream_http_response(
                response,
                partial_path,
                requested_url=requested_url,
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

        validation = validate_archive(
            partial_path
        )

        observed_partial = file_identity(
            partial_path
        )

        if (
            observed_partial.sha256
            != download.sha256
            or observed_partial.size_bytes
            != download.size_bytes
        ):
            raise TaxonomyAcquisitionError(
                "downloaded taxonomy archive changed before acceptance"
            )

        os.replace(
            partial_path,
            archive_path,
        )

        archive_identity = file_identity(
            archive_path
        )

        if archive_identity != observed_partial:
            raise TaxonomyAcquisitionError(
                "taxonomy archive identity changed during final promotion"
            )

        extracted = extract_required_members(
            archive_path,
            snapshot_dir,
        )

        archive_after_extraction = file_identity(
            archive_path
        )

        if archive_after_extraction != archive_identity:
            raise TaxonomyAcquisitionError(
                "taxonomy archive changed during extraction"
            )

        structural_validate(
            snapshot_dir
        )

        completed_utc = validate_utc_timestamp(
            timestamp_provider(),
            label="acquisition completion",
        )

        provenance = {
            "schema_version": 1,
            "bacselect_git_commit": commit,
            "taxonomy_snapshot_id": snapshot_id,
            "bound_source_snapshot_id": SOURCE_SNAPSHOT_ID,
            "bound_source_snapshot_commit": SOURCE_SNAPSHOT_COMMIT,
            "bound_source_raw_report_sha256": SOURCE_RAW_SHA256,
            "bound_source_acquisition_sha256": SOURCE_ACQUISITION_SHA256,
            "taxonomy_acquisition_method_sha256": method_sha256,
            "taxonomy_acquisition_implementation_sha256":
                implementation_sha256,
            "source_taxonomy_sha256": SOURCE_TAXONOMY_SHA256,
            "requested_url": download.requested_url,
            "final_url": download.final_url,
            "http_status": download.http_status,
            "etag": download.etag,
            "last_modified": download.last_modified,
            "started_utc": started_utc,
            "completed_utc": completed_utc,
            "downloader": "python-urllib.request",
            "python_version": platform.python_version(),
            "openssl_version": ssl.OPENSSL_VERSION,
            "archive_member_count": validation.member_count,
            "archive_size_bytes": archive_identity.size_bytes,
            "archive_sha256": archive_identity.sha256,
            "nodes_size_bytes": extracted["nodes.dmp"].size_bytes,
            "nodes_sha256": extracted["nodes.dmp"].sha256,
            "merged_size_bytes": extracted["merged.dmp"].size_bytes,
            "merged_sha256": extracted["merged.dmp"].sha256,
            "delnodes_size_bytes": extracted["delnodes.dmp"].size_bytes,
            "delnodes_sha256": extracted["delnodes.dmp"].sha256,
            "structural_validation": "pass",
            "taxonomy_resolution_performed": False,
            "structural_features_calculated": False,
            "selector_outcomes_calculated": False,
        }

        provenance_path = (
            snapshot_dir
            / ACQUISITION_PROVENANCE_NAME
        )

        write_json_new(
            provenance_path,
            provenance,
        )

        provenance_sha256 = sha256_file(
            provenance_path
        )

        manifest_sha256 = write_content_manifest(
            snapshot_dir
        )

        freeze = {
            "schema_version": 1,
            "snapshot_id": snapshot_id,
            "snapshot_status": "FROZEN_TAXONOMY_INPUT",
            "bacselect_git_commit": commit,
            "bound_source_snapshot_id": SOURCE_SNAPSHOT_ID,
            "bound_source_raw_report_sha256": SOURCE_RAW_SHA256,
            "bound_source_acquisition_sha256": SOURCE_ACQUISITION_SHA256,
            "taxonomy_acquisition_method_sha256": method_sha256,
            "taxonomy_acquisition_implementation_sha256":
                implementation_sha256,
            "source_taxonomy_sha256": SOURCE_TAXONOMY_SHA256,
            "requested_url": download.requested_url,
            "final_url": download.final_url,
            "archive_size_bytes": archive_identity.size_bytes,
            "archive_sha256": archive_identity.sha256,
            "nodes_sha256": extracted["nodes.dmp"].sha256,
            "merged_sha256": extracted["merged.dmp"].sha256,
            "delnodes_sha256": extracted["delnodes.dmp"].sha256,
            "acquisition_provenance_sha256": provenance_sha256,
            "content_manifest_sha256": manifest_sha256,
            "structural_validation": "pass",
            "taxonomy_resolution_performed": False,
            "structural_features_calculated": False,
            "selector_outcomes_calculated": False,
        }

        freeze_path = (
            snapshot_dir
            / FREEZE_RECORD_NAME
        )

        write_json_new(
            freeze_path,
            freeze,
        )

        freeze_sha256 = sha256_file(
            freeze_path
        )

        return SnapshotAcquisitionResult(
            snapshot_dir=snapshot_dir,
            snapshot_id=snapshot_id,
            archive_sha256=archive_identity.sha256,
            nodes_sha256=extracted["nodes.dmp"].sha256,
            merged_sha256=extracted["merged.dmp"].sha256,
            delnodes_sha256=extracted["delnodes.dmp"].sha256,
            acquisition_provenance_sha256=provenance_sha256,
            content_manifest_sha256=manifest_sha256,
            freeze_record_sha256=freeze_sha256,
        )

    except Exception:
        # A failed attempt is never left looking like an accepted snapshot.
        if partial_path.exists():
            try:
                partial_path.unlink()
            except OSError:
                pass

        raise
