"""Portable BacSelect monthly Stage 3B sequence-transport primitives.

This module defines deterministic transport inputs, NCBI Datasets command
construction, dehydrated-package extraction, hydration completeness checks and
pre-network provenance.

It does not execute commands or perform network retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import re
import zipfile
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from bacselect.monthly_sequence_plan import (
    CACHE_METADATA_MISMATCH,
    CACHE_NOT_CURRENT,
    FRESH_BATCH_SIZE,
    FRESH_TARGET_FIELDS,
    NO_VERIFIED_CACHE,
    MonthlyFreshAcquisitionTarget,
    accession_manifest_bytes,
)
from bacselect.source_eligibility import (
    BIOSAMPLE_RE,
    CANONICAL_GCA_RE,
    DATASETS_VERSION,
)


REHYDRATE_WORKERS = 10
TARGETED_RETRY_ROUNDS = 2

INCLUDE_VALUE = "genome,gbff,seq-report"
ASSEMBLY_SOURCE = "GenBank"

LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

GIT_SHA_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

ALLOWED_ACQUISITION_REASONS = frozenset(
    (
        NO_VERIFIED_CACHE,
        CACHE_NOT_CURRENT,
        CACHE_METADATA_MISMATCH,
    )
)


class MonthlySequenceTransportError(
    ValueError
):
    """Raised when monthly transport evidence fails closed."""


@dataclass(frozen=True)
class FetchEntry:
    """One NCBI Datasets hydration entry."""

    url: str
    expected_size: int
    relative_path: str
    accession: str


@dataclass(frozen=True)
class MonthlyTransportBatch:
    """One deterministic Stage 3B batch contract."""

    source_snapshot_id: str
    source_snapshot_record_sha256: str
    stage2_sequence_plan_record_sha256: str
    stage2_fresh_target_manifest_sha256: str
    batch_index: int
    batch_count: int
    batch_size: int
    full_target_count: int
    targets: tuple[
        MonthlyFreshAcquisitionTarget,
        ...,
    ]


def _normalized_token(
    value: object,
    *,
    label: str,
) -> str:
    text = str(
        value
    )

    if (
        not text
        or text != text.strip()
        or any(
            character.isspace()
            for character in text
        )
    ):
        raise MonthlySequenceTransportError(
            f"{label} must be non-empty normalized text"
        )

    return text


def _sha256(
    value: object,
    *,
    label: str,
) -> str:
    text = str(
        value
    )

    if LOWER_SHA256_RE.fullmatch(
        text
    ) is None:
        raise MonthlySequenceTransportError(
            f"{label} must be lowercase SHA256"
        )

    return text


def _git_sha(
    value: object,
) -> str:
    text = str(
        value
    )

    if GIT_SHA_RE.fullmatch(
        text
    ) is None:
        raise MonthlySequenceTransportError(
            "origin Git commit must be 40 lowercase hexadecimal characters"
        )

    return text


def _validate_target(
    target: MonthlyFreshAcquisitionTarget,
) -> None:
    accession = (
        target.canonical_genbank_assembly_accession
    )

    if CANONICAL_GCA_RE.fullmatch(
        accession
    ) is None:
        raise MonthlySequenceTransportError(
            "transport target has invalid canonical GCA accession"
        )

    if BIOSAMPLE_RE.fullmatch(
        target.source_biosample
    ) is None:
        raise MonthlySequenceTransportError(
            f"{accession}: invalid source BioSample"
        )

    if (
        target.acquisition_reason
        not in ALLOWED_ACQUISITION_REASONS
    ):
        raise MonthlySequenceTransportError(
            f"{accession}: unsupported acquisition reason "
            f"{target.acquisition_reason!r}"
        )


def validate_batch_contract(
    batch: MonthlyTransportBatch,
) -> None:
    """Validate one dynamic monthly Stage 3B batch."""

    _normalized_token(
        batch.source_snapshot_id,
        label="source snapshot ID",
    )

    _sha256(
        batch.source_snapshot_record_sha256,
        label="source snapshot record SHA256",
    )

    _sha256(
        batch.stage2_sequence_plan_record_sha256,
        label="Stage 2 sequence-plan record SHA256",
    )

    _sha256(
        batch.stage2_fresh_target_manifest_sha256,
        label="Stage 2 fresh-target manifest SHA256",
    )

    if batch.batch_size <= 0:
        raise MonthlySequenceTransportError(
            "batch size must be positive"
        )

    if batch.full_target_count <= 0:
        raise MonthlySequenceTransportError(
            "full fresh-target count must be positive"
        )

    expected_batch_count = (
        batch.full_target_count
        + batch.batch_size
        - 1
    ) // batch.batch_size

    if batch.batch_count != expected_batch_count:
        raise MonthlySequenceTransportError(
            "batch count does not match dynamic "
            "fresh-target population"
        )

    if not (
        1
        <= batch.batch_index
        <= batch.batch_count
    ):
        raise MonthlySequenceTransportError(
            "batch index is outside dynamic batch range"
        )

    expected_count = (
        batch.batch_size
        if batch.batch_index < batch.batch_count
        else (
            batch.full_target_count
            - batch.batch_size
            * (
                batch.batch_count
                - 1
            )
        )
    )

    if len(
        batch.targets
    ) != expected_count:
        raise MonthlySequenceTransportError(
            "batch target count does not match "
            "dynamic batch position"
        )

    accessions: list[str] = []

    for target in batch.targets:
        _validate_target(
            target
        )

        accessions.append(
            target.canonical_genbank_assembly_accession
        )

    if accessions != sorted(
        accessions
    ):
        raise MonthlySequenceTransportError(
            "batch targets must be lexicographically sorted"
        )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlySequenceTransportError(
            "batch target accessions must be unique"
        )


def batch_target_manifest_bytes(
    targets: Iterable[
        MonthlyFreshAcquisitionTarget
    ],
) -> bytes:
    """Return canonical identity-bearing Stage 3B batch TSV."""

    values = tuple(
        targets
    )

    if not values:
        raise MonthlySequenceTransportError(
            "batch target manifest is empty"
        )

    accessions = []

    rows = [
        "\t".join(
            FRESH_TARGET_FIELDS
        )
        + "\n"
    ]

    for target in values:
        _validate_target(
            target
        )

        accession = (
            target.canonical_genbank_assembly_accession
        )

        accessions.append(
            accession
        )

        rows.append(
            f"{accession}\t"
            f"{target.source_biosample}\t"
            f"{target.acquisition_reason}\n"
        )

    if accessions != sorted(
        accessions
    ):
        raise MonthlySequenceTransportError(
            "batch target manifest must be lexicographically sorted"
        )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlySequenceTransportError(
            "batch target manifest contains duplicate accessions"
        )

    return "".join(
        rows
    ).encode(
        "ascii"
    )


def batch_target_manifest_sha256(
    targets: Iterable[
        MonthlyFreshAcquisitionTarget
    ],
) -> str:
    return hashlib.sha256(
        batch_target_manifest_bytes(
            targets
        )
    ).hexdigest()


def batch_accession_bytes(
    targets: Iterable[
        MonthlyFreshAcquisitionTarget
    ],
) -> bytes:
    values = tuple(
        targets
    )

    return accession_manifest_bytes(
        tuple(
            target.canonical_genbank_assembly_accession
            for target in values
        )
    )


def safe_extract(
    zip_path: Path,
    destination: Path,
) -> None:
    """Extract a Datasets ZIP after CRC and traversal checks."""

    try:
        with zipfile.ZipFile(
            zip_path
        ) as archive:
            root = (
                destination.resolve()
            )

            bad_member = (
                archive.testzip()
            )

            if bad_member is not None:
                raise MonthlySequenceTransportError(
                    "ZIP CRC validation failed: "
                    f"{bad_member}"
                )

            for member in archive.infolist():
                target = (
                    destination
                    / member.filename
                ).resolve()

                if (
                    target != root
                    and root
                    not in target.parents
                ):
                    raise MonthlySequenceTransportError(
                        "unsafe path in ZIP archive: "
                        f"{member.filename!r}"
                    )

            archive.extractall(
                destination
            )

    except zipfile.BadZipFile as exc:
        raise MonthlySequenceTransportError(
            f"invalid ZIP archive: {exc}"
        ) from exc


def parse_fetch_txt(
    package: Path,
    expected_accessions: Iterable[str],
) -> tuple[
    Path,
    tuple[FetchEntry, ...],
    Mapping[str, tuple[FetchEntry, ...]],
]:
    """Parse and audit the NCBI Datasets hydration manifest."""

    expected_values = tuple(
        expected_accessions
    )

    if not expected_values:
        raise MonthlySequenceTransportError(
            "expected accession set is empty"
        )

    if expected_values != tuple(
        sorted(
            expected_values
        )
    ):
        raise MonthlySequenceTransportError(
            "expected accessions must be sorted"
        )

    if len(
        expected_values
    ) != len(
        set(
            expected_values
        )
    ):
        raise MonthlySequenceTransportError(
            "expected accessions must be unique"
        )

    for accession in expected_values:
        if CANONICAL_GCA_RE.fullmatch(
            accession
        ) is None:
            raise MonthlySequenceTransportError(
                "expected accessions contain invalid "
                "canonical GCA accession"
            )

    expected = set(
        expected_values
    )

    fetch_path = (
        package
        / "ncbi_dataset"
        / "fetch.txt"
    )

    if not fetch_path.is_file():
        raise MonthlySequenceTransportError(
            "dehydrated package lacks ncbi_dataset/fetch.txt"
        )

    entries: list[
        FetchEntry
    ] = []

    seen_paths: set[str] = set()

    with fetch_path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.reader(
            handle,
            delimiter="\t",
        )

        for line_number, row in enumerate(
            reader,
            1,
        ):
            if len(
                row
            ) != 3:
                raise MonthlySequenceTransportError(
                    f"{fetch_path}: expected 3 fields "
                    f"on line {line_number}, got {len(row)}"
                )

            (
                url,
                raw_size,
                relative,
            ) = row

            try:
                expected_size = int(
                    raw_size
                )
            except ValueError as exc:
                raise MonthlySequenceTransportError(
                    f"{fetch_path}: invalid size "
                    f"on line {line_number}"
                ) from exc

            if expected_size < 0:
                raise MonthlySequenceTransportError(
                    f"{fetch_path}: negative size "
                    f"on line {line_number}"
                )

            rel = Path(
                relative
            )

            if (
                rel.is_absolute()
                or ".." in rel.parts
            ):
                raise MonthlySequenceTransportError(
                    f"{fetch_path}: unsafe destination "
                    f"{relative!r}"
                )

            if relative in seen_paths:
                raise MonthlySequenceTransportError(
                    f"{fetch_path}: duplicate destination "
                    f"{relative!r}"
                )

            seen_paths.add(
                relative
            )

            parts = (
                rel.parts
            )

            if (
                len(
                    parts
                ) < 3
                or parts[0]
                != "data"
            ):
                raise MonthlySequenceTransportError(
                    f"{fetch_path}: unexpected destination "
                    f"{relative!r}"
                )

            accession = (
                parts[1]
            )

            if accession not in expected:
                raise MonthlySequenceTransportError(
                    f"{fetch_path}: destination belongs "
                    "to unexpected accession "
                    f"{accession!r}"
                )

            entries.append(
                FetchEntry(
                    url=url,
                    expected_size=expected_size,
                    relative_path=relative,
                    accession=accession,
                )
            )

    by_accession_lists: dict[
        str,
        list[FetchEntry],
    ] = {
        accession: []
        for accession in expected_values
    }

    for entry in entries:
        by_accession_lists[
            entry.accession
        ].append(
            entry
        )

    missing = [
        accession
        for accession, values
        in by_accession_lists.items()
        if not values
    ]

    if missing:
        raise MonthlySequenceTransportError(
            "fetch.txt has no hydrated payload "
            f"entries for {missing!r}"
        )

    by_accession = {
        accession:
            tuple(
                values
            )
        for accession, values
        in by_accession_lists.items()
    }

    return (
        fetch_path,
        tuple(
            entries
        ),
        by_accession,
    )


def fetch_entry_problem(
    package: Path,
    entry: FetchEntry,
) -> str | None:
    path = (
        package
        / "ncbi_dataset"
        / entry.relative_path
    )

    if not path.is_file():
        return "missing"

    size = (
        path.stat().st_size
    )

    if size <= 0:
        return "empty"

    if (
        entry.expected_size > 0
        and size
        != entry.expected_size
    ):
        return (
            "size_mismatch:"
            f"{size}!="
            f"{entry.expected_size}"
        )

    return None


def unresolved_fetches(
    package: Path,
    by_accession: Mapping[
        str,
        Sequence[FetchEntry],
    ],
) -> Mapping[
    str,
    tuple[
        tuple[str, str],
        ...,
    ],
]:
    unresolved: dict[
        str,
        tuple[
            tuple[str, str],
            ...,
        ],
    ] = {}

    for accession, entries in (
        by_accession.items()
    ):
        problems: list[
            tuple[str, str]
        ] = []

        for entry in entries:
            problem = (
                fetch_entry_problem(
                    package,
                    entry,
                )
            )

            if problem is not None:
                problems.append(
                    (
                        entry.relative_path,
                        problem,
                    )
                )

        if problems:
            unresolved[
                accession
            ] = tuple(
                problems
            )

    return unresolved


def remove_fetch_destinations(
    package: Path,
    entries: Sequence[
        FetchEntry
    ],
) -> None:
    """Remove only Datasets destinations for one targeted retry."""

    for entry in entries:
        path = (
            package
            / "ncbi_dataset"
            / entry.relative_path
        )

        if path.is_file():
            path.unlink()


def _datasets_executable(
    path: Path,
) -> str:
    resolved = (
        path.resolve()
    )

    if not path.is_absolute():
        raise MonthlySequenceTransportError(
            "datasets executable must be an absolute path"
        )

    if resolved.name != "datasets":
        raise MonthlySequenceTransportError(
            "datasets executable basename must be 'datasets'"
        )

    return str(
        resolved
    )


def build_download_command(
    *,
    datasets_executable: Path,
    accessions_path: Path,
    partial_zip_path: Path,
) -> tuple[str, ...]:
    return (
        _datasets_executable(
            datasets_executable
        ),
        "download",
        "genome",
        "accession",
        "--inputfile",
        str(
            accessions_path
        ),
        "--include",
        INCLUDE_VALUE,
        "--dehydrated",
        "--filename",
        str(
            partial_zip_path
        ),
        "--no-progressbar",
    )


def build_rehydrate_command(
    *,
    datasets_executable: Path,
    package: Path,
    workers: int = REHYDRATE_WORKERS,
) -> tuple[str, ...]:
    if workers <= 0:
        raise MonthlySequenceTransportError(
            "rehydrate worker count must be positive"
        )

    return (
        _datasets_executable(
            datasets_executable
        ),
        "rehydrate",
        "--directory",
        str(
            package
        ),
        "--max-workers",
        str(
            workers
        ),
        "--no-progressbar",
    )


def build_targeted_rehydrate_command(
    *,
    datasets_executable: Path,
    package: Path,
    accession: str,
) -> tuple[str, ...]:
    if CANONICAL_GCA_RE.fullmatch(
        accession
    ) is None:
        raise MonthlySequenceTransportError(
            "targeted rehydrate accession is invalid"
        )

    return (
        _datasets_executable(
            datasets_executable
        ),
        "rehydrate",
        "--directory",
        str(
            package
        ),
        "--match",
        accession,
        "--max-workers",
        "1",
        "--no-progressbar",
    )


def build_pre_network_attempt_record(
    batch: MonthlyTransportBatch,
    *,
    recorded_at_utc: str,
    origin_git_commit: str,
    environment_explicit_sha256: str,
    datasets_executable: Path,
    transport_implementation_sha256: str,
) -> Mapping[str, object]:
    """Build immutable identity recorded before Stage 3B network access."""

    validate_batch_contract(
        batch
    )

    timestamp = _normalized_token(
        recorded_at_utc,
        label="recorded-at UTC",
    )

    git_commit = _git_sha(
        origin_git_commit
    )

    environment_sha = _sha256(
        environment_explicit_sha256,
        label="environment explicit SHA256",
    )

    implementation_sha = _sha256(
        transport_implementation_sha256,
        label="transport implementation SHA256",
    )

    batch_manifest_sha = (
        batch_target_manifest_sha256(
            batch.targets
        )
    )

    accessions = tuple(
        target.canonical_genbank_assembly_accession
        for target in batch.targets
    )

    accessions_sha = (
        hashlib.sha256(
            batch_accession_bytes(
                batch.targets
            )
        ).hexdigest()
    )

    return {
        "schema":
            "bacselect-monthly-sequence-transport-attempt-v1",
        "recorded_at_utc":
            timestamp,
        "created_before_network_retrieval":
            True,
        "source_snapshot_id":
            batch.source_snapshot_id,
        "source_snapshot_record_sha256":
            batch.source_snapshot_record_sha256,
        "stage2_sequence_plan_record_sha256":
            batch.stage2_sequence_plan_record_sha256,
        "stage2_fresh_target_manifest_sha256":
            batch.stage2_fresh_target_manifest_sha256,
        "batch_target_manifest_sha256":
            batch_manifest_sha,
        "accessions_sha256":
            accessions_sha,
        "origin_git_commit":
            git_commit,
        "transport_implementation_sha256":
            implementation_sha,
        "environment_explicit_sha256":
            environment_sha,
        "datasets_version":
            DATASETS_VERSION,
        "datasets_executable":
            _datasets_executable(
                datasets_executable
            ),
        "full_target_count":
            batch.full_target_count,
        "batch_index":
            batch.batch_index,
        "batch_count":
            batch.batch_count,
        "batch_size":
            batch.batch_size,
        "requested_accessions":
            len(
                accessions
            ),
        "first_accession":
            accessions[0],
        "last_accession":
            accessions[-1],
        "include":
            (
                "genome",
                "gbff",
                "seq-report",
            ),
        "assembly_source":
            ASSEMBLY_SOURCE,
        "rehydrate_workers":
            REHYDRATE_WORKERS,
        "targeted_retry_rounds":
            TARGETED_RETRY_ROUNDS,
        "dehydrated_zip_sha256":
            None,
    }
