"""Pure BacSelect monthly sequence-acquisition completion contract.

This module seals the release-level completeness of already completed monthly
Stage 3B sequence-transport batches.

It performs no filesystem access, network access, external process execution,
archive retrieval, cache discovery, taxonomy, structural-feature analysis,
or selector analysis.

A filesystem executor must independently discover and re-hash persisted batch
evidence before constructing the observations accepted here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
import re
from typing import Iterable, Mapping, Sequence

from bacselect.monthly_sequence_plan import (
    FRESH_BATCH_SIZE,
    FRESH_TARGET_FIELDS,
    MonthlyFreshAcquisitionTarget,
    audit_monthly_sequence_plan_record,
)
from bacselect.monthly_sequence_transport import (
    TARGETED_RETRY_ROUNDS,
    MonthlySequenceTransportError,
    batch_accession_bytes,
    batch_target_manifest_sha256,
)
from bacselect.monthly_sequence_validation import (
    PACKAGE_FILE_FIELDS,
)
from bacselect.source_eligibility import (
    BIOSAMPLE_RE,
    CANONICAL_GCA_RE,
    DATASETS_VERSION,
)


MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_SCHEMA = (
    "bacselect-monthly-sequence-acquisition-completion-v1"
)

MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_STATUS = (
    "SEQUENCE_ACQUISITION_COMPLETE"
)

TRANSPORT_SUMMARY_SCHEMA = (
    "bacselect-monthly-sequence-transport-summary-v1"
)

PACKAGE_READBACK_SCHEMA = (
    "bacselect-monthly-sequence-package-readback-v1"
)

BATCH_ID_RE = re.compile(
    r"^batch-[0-9]{5}$"
)

LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

GIT_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)


TRANSPORT_SUMMARY_KEYS = frozenset(
    (
        "schema",
        "result",
        "source_snapshot_id",
        "source_snapshot_record_sha256",
        "stage2_sequence_plan_record_sha256",
        "stage2_fresh_target_manifest_sha256",
        "origin_git_commit",
        "datasets_version",
        "environment_explicit_sha256",
        "batch_index",
        "batch_count",
        "batch_size",
        "full_target_count",
        "requested_accessions",
        "first_accession",
        "last_accession",
        "batch_target_manifest_sha256",
        "accessions_sha256",
        "dehydrated_zip_sha256",
        "fetch_txt_sha256",
        "fetch_entries",
        "initial_unresolved_accessions",
        "broad_rehydrate_exit_code",
        "targeted_retry_rounds",
        "targeted_retry_events",
        "candidate_records",
        "component_records",
        "package_files",
        "candidate_sequence_audit_sha256",
        "component_sequence_audit_sha256",
        "package_files_sha256",
        "attempt_origin_sha256",
        "execution_completed_at_utc",
    )
)


class MonthlySequenceAcquisitionCompletionError(
    ValueError
):
    """Raised when release-level Stage 3B completion fails closed."""


@dataclass(frozen=True)
class PackageFileReadbackObservation:
    """One independently re-hashed persisted Stage 3B package file."""

    path: str
    observed_size_bytes: int
    observed_sha256: str


@dataclass(frozen=True)
class CompletedTransportBatchEvidence:
    """One discovered final Stage 3B batch and independently re-hashed evidence."""

    batch_id: str
    summary_payload: bytes

    observed_batch_target_manifest_sha256: str
    observed_accessions_sha256: str

    observed_dehydrated_zip_sha256: str
    observed_fetch_txt_sha256: str
    observed_attempt_origin_sha256: str

    observed_candidate_audit_sha256: str
    observed_component_audit_sha256: str

    package_files_payload: bytes
    package_file_observations: tuple[
        PackageFileReadbackObservation,
        ...,
    ]


def _canonical_json_bytes(
    value: object,
) -> bytes:
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlySequenceAcquisitionCompletionError(
            "completion evidence is not JSON serializable"
        ) from exc

    return (
        text
        + "\n"
    ).encode(
        "ascii"
    )


def _transport_json_bytes(
    value: object,
) -> bytes:
    """Return the frozen Stage 3B summary JSON representation."""

    try:
        text = json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlySequenceAcquisitionCompletionError(
            "transport summary is not JSON serializable"
        ) from exc

    return (
        text
        + "\n"
    ).encode(
        "utf-8"
    )


def _normalized_text(
    value: object,
    *,
    label: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            f"{label} must be text"
        )

    if (
        not value
        or value != value.strip()
        or any(
            character.isspace()
            for character in value
        )
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            f"{label} must be normalized non-empty text"
        )

    return value


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
        or LOWER_SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            f"{label} must be lowercase SHA256"
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
        raise MonthlySequenceAcquisitionCompletionError(
            "origin Git commit must be 40 lowercase hexadecimal characters"
        )

    return value


def _nonnegative_int(
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
        raise MonthlySequenceAcquisitionCompletionError(
            f"{label} must be a non-negative integer"
        )

    return value


def _positive_int(
    value: object,
    *,
    label: str,
) -> int:
    parsed = _nonnegative_int(
        value,
        label=label,
    )

    if parsed == 0:
        raise MonthlySequenceAcquisitionCompletionError(
            f"{label} must be positive"
        )

    return parsed


def _batch_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or BATCH_ID_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "invalid Stage 3B batch ID"
        )

    return value


def _package_path(
    value: object,
) -> str:
    text = _normalized_text(
        value,
        label="package path",
    )

    if "\\" in text:
        raise MonthlySequenceAcquisitionCompletionError(
            "package path must use POSIX separators"
        )

    path = PurePosixPath(
        text
    )

    if (
        path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or path.as_posix() != text
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "package path is unsafe or non-canonical"
        )

    return text


def _audit_package_files_manifest(
    payload: bytes,
) -> tuple[
    tuple[
        str,
        int,
        str,
    ],
    ...,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "package-files manifest must be bytes"
        )

    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise MonthlySequenceAcquisitionCompletionError(
            "package-files manifest must be UTF-8"
        ) from exc

    if not text.endswith(
        "\n"
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "package-files manifest must be newline terminated"
        )

    lines = text.splitlines()

    expected_header = "\t".join(
        PACKAGE_FILE_FIELDS
    )

    if (
        not lines
        or lines[
            0
        ]
        != expected_header
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "package-files manifest schema changed"
        )

    rows = []

    for line_number, line in enumerate(
        lines[
            1:
        ],
        2,
    ):
        fields = line.split(
            "\t"
        )

        if len(
            fields
        ) != 3:
            raise MonthlySequenceAcquisitionCompletionError(
                "package-files manifest row shape changed "
                f"at line {line_number}"
            )

        path_value, size_value, sha_value = fields

        path = _package_path(
            path_value
        )

        try:
            size = int(
                size_value
            )
        except ValueError:
            raise MonthlySequenceAcquisitionCompletionError(
                "package-files manifest contains invalid size"
            ) from None

        if (
            size < 0
            or str(
                size
            )
            != size_value
        ):
            raise MonthlySequenceAcquisitionCompletionError(
                "package-files manifest contains non-canonical size"
            )

        sha = _sha256(
            sha_value,
            label="package-files manifest SHA256",
        )

        rows.append(
            (
                path,
                size,
                sha,
            )
        )

    if not rows:
        raise MonthlySequenceAcquisitionCompletionError(
            "package-files manifest contains no files"
        )

    paths = tuple(
        row[
            0
        ]
        for row in rows
    )

    if paths != tuple(
        sorted(
            paths
        )
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "package-files manifest is not path sorted"
        )

    if len(
        paths
    ) != len(
        set(
            paths
        )
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "package-files manifest contains duplicate path"
        )

    return tuple(
        rows
    )


def _audit_package_readback(
    manifest_rows: Sequence[
        tuple[
            str,
            int,
            str,
        ]
    ],
    observations: Sequence[
        PackageFileReadbackObservation
    ],
) -> tuple[
    int,
    str,
]:
    values = tuple(
        observations
    )

    if any(
        not isinstance(
            value,
            PackageFileReadbackObservation,
        )
        for value in values
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "package-file readback observation has wrong type"
        )

    observed = {}

    for value in values:
        path = _package_path(
            value.path
        )

        if path in observed:
            raise MonthlySequenceAcquisitionCompletionError(
                "duplicate package-file readback path"
            )

        size = _nonnegative_int(
            value.observed_size_bytes,
            label="observed package-file size",
        )

        sha = _sha256(
            value.observed_sha256,
            label="observed package-file SHA256",
        )

        observed[
            path
        ] = PackageFileReadbackObservation(
            path=path,
            observed_size_bytes=size,
            observed_sha256=sha,
        )

    expected_paths = {
        row[
            0
        ]
        for row in manifest_rows
    }

    if set(
        observed
    ) != expected_paths:
        raise MonthlySequenceAcquisitionCompletionError(
            "package-file readback set differs from package-files manifest"
        )

    canonical_rows = []

    for path, expected_size, expected_sha in manifest_rows:
        value = observed[
            path
        ]

        if (
            value.observed_size_bytes
            != expected_size
        ):
            raise MonthlySequenceAcquisitionCompletionError(
                "package-file size changed during independent readback"
            )

        if (
            value.observed_sha256
            != expected_sha
        ):
            raise MonthlySequenceAcquisitionCompletionError(
                "package-file SHA256 changed during independent readback"
            )

        canonical_rows.append(
            {
                "path":
                    path,
                "sha256":
                    expected_sha,
                "size_bytes":
                    expected_size,
            }
        )

    readback_payload = (
        _canonical_json_bytes(
            {
                "files":
                    canonical_rows,
                "schema_version":
                    PACKAGE_READBACK_SCHEMA,
            }
        )
    )

    return (
        len(
            canonical_rows
        ),
        hashlib.sha256(
            readback_payload
        ).hexdigest(),
    )


def _parse_fresh_targets(
    payload: bytes,
) -> tuple[
    MonthlyFreshAcquisitionTarget,
    ...,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "fresh-target manifest must be bytes"
        )

    try:
        text = payload.decode(
            "ascii"
        )
    except UnicodeDecodeError as exc:
        raise MonthlySequenceAcquisitionCompletionError(
            "fresh-target manifest must be ASCII"
        ) from exc

    if not text.endswith(
        "\n"
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "fresh-target manifest must be newline terminated"
        )

    lines = text.splitlines()

    expected_header = "\t".join(
        FRESH_TARGET_FIELDS
    )

    if (
        not lines
        or lines[
            0
        ]
        != expected_header
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "fresh-target manifest schema changed"
        )

    values: list[
        MonthlyFreshAcquisitionTarget
    ] = []

    for line_number, line in enumerate(
        lines[
            1:
        ],
        2,
    ):
        fields = line.split(
            "\t"
        )

        if len(
            fields
        ) != 3:
            raise MonthlySequenceAcquisitionCompletionError(
                "fresh-target manifest row shape changed "
                f"at line {line_number}"
            )

        accession, biosample, reason = fields

        if CANONICAL_GCA_RE.fullmatch(
            accession
        ) is None:
            raise MonthlySequenceAcquisitionCompletionError(
                "fresh-target manifest contains invalid GCA"
            )

        if BIOSAMPLE_RE.fullmatch(
            biosample
        ) is None:
            raise MonthlySequenceAcquisitionCompletionError(
                "fresh-target manifest contains invalid BioSample"
            )

        values.append(
            MonthlyFreshAcquisitionTarget(
                canonical_genbank_assembly_accession=(
                    accession
                ),
                source_biosample=(
                    biosample
                ),
                acquisition_reason=(
                    reason
                ),
            )
        )

    return tuple(
        values
    )


def _audit_transport_summary(
    payload: bytes,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "batch summary must be bytes"
        )

    try:
        value = json.loads(
            payload.decode(
                "utf-8"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlySequenceAcquisitionCompletionError(
            "invalid Stage 3B batch summary"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "Stage 3B batch summary must be a JSON object"
        )

    if set(
        value
    ) != TRANSPORT_SUMMARY_KEYS:
        raise MonthlySequenceAcquisitionCompletionError(
            "Stage 3B batch-summary schema changed"
        )

    if _transport_json_bytes(
        value
    ) != payload:
        raise MonthlySequenceAcquisitionCompletionError(
            "Stage 3B batch summary is not canonical JSON"
        )

    if value[
        "schema"
    ] != TRANSPORT_SUMMARY_SCHEMA:
        raise MonthlySequenceAcquisitionCompletionError(
            "Stage 3B batch-summary schema version changed"
        )

    if value[
        "result"
    ] != "PASS":
        raise MonthlySequenceAcquisitionCompletionError(
            "Stage 3B batch summary is not PASS"
        )

    return value


def _validate_discovery(
    *,
    expected_batch_ids: Sequence[
        str
    ],
    discovered_final_batch_ids: Sequence[
        str
    ],
    discovered_partial_batch_ids: Sequence[
        str
    ],
    unexpected_batch_entries: Sequence[
        str
    ],
) -> tuple[
    str,
    ...,
]:
    expected = tuple(
        expected_batch_ids
    )

    finals = tuple(
        _batch_id(
            value
        )
        for value
        in discovered_final_batch_ids
    )

    if len(
        finals
    ) != len(
        set(
            finals
        )
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "duplicate discovered final Stage 3B batch"
        )

    if tuple(
        sorted(
            finals
        )
    ) != expected:
        raise MonthlySequenceAcquisitionCompletionError(
            "discovered final Stage 3B batch set is incomplete or contains extras"
        )

    partials = tuple(
        discovered_partial_batch_ids
    )

    if partials:
        raise MonthlySequenceAcquisitionCompletionError(
            "partial Stage 3B batch exists"
        )

    unexpected = tuple(
        unexpected_batch_entries
    )

    if unexpected:
        raise MonthlySequenceAcquisitionCompletionError(
            "unexpected Stage 3B batch-like entry exists"
        )

    return tuple(
        sorted(
            finals
        )
    )


def _summary_sha256(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def _expected_batch_id(
    index: int,
) -> str:
    return (
        f"batch-{index:05d}"
    )


def build_sequence_acquisition_completion_record(
    *,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    stage2_sequence_plan_record: bytes,
    stage2_fresh_target_manifest: bytes,
    origin_git_commit: str,
    environment_explicit_sha256: str,
    batches: Iterable[
        CompletedTransportBatchEvidence
    ],
    discovered_final_batch_ids: Sequence[
        str
    ],
    discovered_partial_batch_ids: Sequence[
        str
    ] = (),
    unexpected_batch_entries: Sequence[
        str
    ] = (),
) -> dict[
    str,
    object,
]:
    """Build one deterministic release-level Stage 3B completion seal."""

    snapshot = _normalized_text(
        source_snapshot_id,
        label="source snapshot ID",
    )

    snapshot_record_sha = _sha256(
        source_snapshot_record_sha256,
        label="source-snapshot-record SHA256",
    )

    commit = _git_commit(
        origin_git_commit
    )

    environment_sha = _sha256(
        environment_explicit_sha256,
        label="NCBI environment SHA256",
    )

    if not isinstance(
        stage2_sequence_plan_record,
        bytes,
    ):
        raise TypeError(
            "Stage 2 sequence-plan record must be bytes"
        )

    if not isinstance(
        stage2_fresh_target_manifest,
        bytes,
    ):
        raise TypeError(
            "Stage 2 fresh-target manifest must be bytes"
        )

    try:
        plan = (
            audit_monthly_sequence_plan_record(
                stage2_sequence_plan_record,
                source_snapshot_id=(
                    snapshot
                ),
                source_snapshot_record_sha256=(
                    snapshot_record_sha
                ),
                fresh_target_manifest=(
                    stage2_fresh_target_manifest
                ),
            )
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlySequenceAcquisitionCompletionError(
            "Stage 2 sequence-plan provenance audit failed"
        ) from exc

    targets = _parse_fresh_targets(
        stage2_fresh_target_manifest
    )

    fresh_count = _nonnegative_int(
        plan[
            "fresh_acquisition_count"
        ],
        label="Stage 2 fresh-acquisition count",
    )

    expected_batch_count = _nonnegative_int(
        plan[
            "fresh_batch_count"
        ],
        label="Stage 2 fresh-batch count",
    )

    if len(
        targets
    ) != fresh_count:
        raise MonthlySequenceAcquisitionCompletionError(
            "Stage 2 target population changed after audit"
        )

    expected_ids = tuple(
        _expected_batch_id(
            index
        )
        for index in range(
            1,
            expected_batch_count
            + 1,
        )
    )

    discovered = _validate_discovery(
        expected_batch_ids=(
            expected_ids
        ),
        discovered_final_batch_ids=(
            discovered_final_batch_ids
        ),
        discovered_partial_batch_ids=(
            discovered_partial_batch_ids
        ),
        unexpected_batch_entries=(
            unexpected_batch_entries
        ),
    )

    batch_values = tuple(
        batches
    )

    if any(
        not isinstance(
            value,
            CompletedTransportBatchEvidence,
        )
        for value in batch_values
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "completed batch evidence has wrong type"
        )

    evidence_ids = tuple(
        value.batch_id
        for value in batch_values
    )

    for value in evidence_ids:
        _batch_id(
            value
        )

    if len(
        evidence_ids
    ) != len(
        set(
            evidence_ids
        )
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "duplicate completed Stage 3B batch evidence"
        )

    if tuple(
        sorted(
            evidence_ids
        )
    ) != expected_ids:
        raise MonthlySequenceAcquisitionCompletionError(
            "completed Stage 3B evidence set is incomplete or contains extras"
        )

    if discovered != expected_ids:
        raise RuntimeError(
            "validated Stage 3B discovery became inconsistent"
        )

    plan_sha = hashlib.sha256(
        stage2_sequence_plan_record
    ).hexdigest()

    manifest_sha = hashlib.sha256(
        stage2_fresh_target_manifest
    ).hexdigest()

    completion_rows: list[
        dict[
            str,
            object,
        ]
    ] = []

    completed_accessions = 0

    by_id = {
        value.batch_id:
            value
        for value in batch_values
    }

    for batch_index, expected_id in enumerate(
        expected_ids,
        1,
    ):
        evidence = by_id[
            expected_id
        ]

        summary = _audit_transport_summary(
            evidence.summary_payload
        )

        if summary[
            "source_snapshot_id"
        ] != snapshot:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch source snapshot ID changed"
            )

        if summary[
            "source_snapshot_record_sha256"
        ] != snapshot_record_sha:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch source-snapshot-record SHA256 changed"
            )

        if summary[
            "stage2_sequence_plan_record_sha256"
        ] != plan_sha:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch Stage 2 sequence-plan identity changed"
            )

        if summary[
            "stage2_fresh_target_manifest_sha256"
        ] != manifest_sha:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch Stage 2 fresh-target identity changed"
            )

        if summary[
            "origin_git_commit"
        ] != commit:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch origin Git commit changed"
            )

        if summary[
            "datasets_version"
        ] != DATASETS_VERSION:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch NCBI Datasets version changed"
            )

        if summary[
            "environment_explicit_sha256"
        ] != environment_sha:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch NCBI environment identity changed"
            )

        if summary[
            "batch_index"
        ] != batch_index:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch index changed"
            )

        if summary[
            "batch_count"
        ] != expected_batch_count:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch count changed"
            )

        if summary[
            "batch_size"
        ] != FRESH_BATCH_SIZE:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch size changed"
            )

        if summary[
            "full_target_count"
        ] != fresh_count:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch full-target count changed"
            )

        start = (
            batch_index
            - 1
        ) * FRESH_BATCH_SIZE

        stop = min(
            start
            + FRESH_BATCH_SIZE,
            fresh_count,
        )

        expected_targets = targets[
            start:
            stop
        ]

        if not expected_targets:
            raise MonthlySequenceAcquisitionCompletionError(
                "expected Stage 3B batch has no targets"
            )

        expected_requested = len(
            expected_targets
        )

        if summary[
            "requested_accessions"
        ] != expected_requested:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch requested-accession count changed"
            )

        first_accession = (
            expected_targets[
                0
            ].canonical_genbank_assembly_accession
        )

        last_accession = (
            expected_targets[
                -1
            ].canonical_genbank_assembly_accession
        )

        if summary[
            "first_accession"
        ] != first_accession:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch first accession changed"
            )

        if summary[
            "last_accession"
        ] != last_accession:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch last accession changed"
            )

        try:
            expected_target_sha = (
                batch_target_manifest_sha256(
                    expected_targets
                )
            )

            expected_accessions_sha = (
                hashlib.sha256(
                    batch_accession_bytes(
                        expected_targets
                    )
                ).hexdigest()
            )
        except MonthlySequenceTransportError as exc:
            raise MonthlySequenceAcquisitionCompletionError(
                "unable to derive frozen Stage 3B batch identity"
            ) from exc

        observed_target_sha = _sha256(
            evidence.observed_batch_target_manifest_sha256,
            label="observed batch-target manifest SHA256",
        )

        observed_accessions_sha = _sha256(
            evidence.observed_accessions_sha256,
            label="observed batch accession-list SHA256",
        )

        if (
            summary[
                "batch_target_manifest_sha256"
            ]
            != expected_target_sha
            or observed_target_sha
            != expected_target_sha
        ):
            raise MonthlySequenceAcquisitionCompletionError(
                "batch-target manifest identity changed"
            )

        if (
            summary[
                "accessions_sha256"
            ]
            != expected_accessions_sha
            or observed_accessions_sha
            != expected_accessions_sha
        ):
            raise MonthlySequenceAcquisitionCompletionError(
                "batch accession-list identity changed"
            )

        artifact_pairs = (
            (
                "dehydrated_zip_sha256",
                evidence.observed_dehydrated_zip_sha256,
                "dehydrated ZIP",
            ),
            (
                "fetch_txt_sha256",
                evidence.observed_fetch_txt_sha256,
                "fetch.txt",
            ),
            (
                "attempt_origin_sha256",
                evidence.observed_attempt_origin_sha256,
                "attempt-origin",
            ),
            (
                "candidate_sequence_audit_sha256",
                evidence.observed_candidate_audit_sha256,
                "candidate audit",
            ),
            (
                "component_sequence_audit_sha256",
                evidence.observed_component_audit_sha256,
                "component audit",
            ),
        )

        for field, observed_value, label in artifact_pairs:
            summary_sha = _sha256(
                summary[
                    field
                ],
                label=f"summary {label} SHA256",
            )

            observed_sha = _sha256(
                observed_value,
                label=f"observed {label} SHA256",
            )

            if observed_sha != summary_sha:
                raise MonthlySequenceAcquisitionCompletionError(
                    f"{label} identity changed after Stage 3B completion"
                )

        if not isinstance(
            evidence.package_files_payload,
            bytes,
        ):
            raise TypeError(
                "package-files manifest must be bytes"
            )

        observed_package_manifest_sha = (
            hashlib.sha256(
                evidence.package_files_payload
            ).hexdigest()
        )

        summary_package_manifest_sha = (
            _sha256(
                summary[
                    "package_files_sha256"
                ],
                label="summary package-files manifest SHA256",
            )
        )

        if (
            observed_package_manifest_sha
            != summary_package_manifest_sha
        ):
            raise MonthlySequenceAcquisitionCompletionError(
                "package-files manifest identity changed after Stage 3B completion"
            )

        package_manifest_rows = (
            _audit_package_files_manifest(
                evidence.package_files_payload
            )
        )

        package_file_count = _positive_int(
            summary[
                "package_files"
            ],
            label="batch package-file count",
        )

        if (
            len(
                package_manifest_rows
            )
            != package_file_count
        ):
            raise MonthlySequenceAcquisitionCompletionError(
                "package-files manifest row count changed"
            )

        (
            package_readback_count,
            package_readback_sha,
        ) = _audit_package_readback(
            package_manifest_rows,
            evidence.package_file_observations,
        )

        if (
            package_readback_count
            != package_file_count
        ):
            raise RuntimeError(
                "verified package-file population became inconsistent"
            )

        candidate_records = _nonnegative_int(
            summary[
                "candidate_records"
            ],
            label="batch candidate-record count",
        )

        if candidate_records != expected_requested:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch candidate-record count changed"
            )

        component_records = _nonnegative_int(
            summary[
                "component_records"
            ],
            label="batch component-record count",
        )

        if component_records < candidate_records:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch component-record count is impossible"
            )

        fetch_entries = _nonnegative_int(
            summary[
                "fetch_entries"
            ],
            label="batch fetch-entry count",
        )

        _nonnegative_int(
            summary[
                "initial_unresolved_accessions"
            ],
            label="batch initial unresolved-accession count",
        )

        broad_exit = summary[
            "broad_rehydrate_exit_code"
        ]

        if (
            broad_exit is not None
            and (
                isinstance(
                    broad_exit,
                    bool,
                )
                or not isinstance(
                    broad_exit,
                    int,
                )
            )
        ):
            raise MonthlySequenceAcquisitionCompletionError(
                "batch broad-rehydrate exit code is invalid"
            )

        if summary[
            "targeted_retry_rounds"
        ] != TARGETED_RETRY_ROUNDS:
            raise MonthlySequenceAcquisitionCompletionError(
                "batch targeted-retry bound changed"
            )

        if not isinstance(
            summary[
                "targeted_retry_events"
            ],
            list,
        ):
            raise MonthlySequenceAcquisitionCompletionError(
                "batch targeted-retry events changed type"
            )

        _normalized_text(
            summary[
                "execution_completed_at_utc"
            ],
            label="batch execution-completed timestamp",
        )

        completed_accessions += (
            expected_requested
        )

        completion_rows.append(
            {
                "accessions_sha256":
                    expected_accessions_sha,
                "batch_id":
                    expected_id,
                "batch_index":
                    batch_index,
                "batch_summary_sha256":
                    _summary_sha256(
                        evidence.summary_payload
                    ),
                "batch_target_manifest_sha256":
                    expected_target_sha,
                "candidate_sequence_audit_sha256":
                    summary[
                        "candidate_sequence_audit_sha256"
                    ],
                "component_sequence_audit_sha256":
                    summary[
                        "component_sequence_audit_sha256"
                    ],
                "fetch_entries":
                    fetch_entries,
                "first_accession":
                    first_accession,
                "last_accession":
                    last_accession,
                "package_file_readback_count":
                    package_readback_count,
                "package_file_readback_sha256":
                    package_readback_sha,
                "package_files":
                    package_file_count,
                "package_files_sha256":
                    summary[
                        "package_files_sha256"
                    ],
                "requested_accessions":
                    expected_requested,
            }
        )

    if completed_accessions != fresh_count:
        raise MonthlySequenceAcquisitionCompletionError(
            "completed accession count does not equal Stage 2 fresh population"
        )

    if len(
        completion_rows
    ) != expected_batch_count:
        raise MonthlySequenceAcquisitionCompletionError(
            "completed batch count does not equal Stage 2 expectation"
        )

    return {
        "batches":
            completion_rows,
        "completed_accession_count":
            completed_accessions,
        "completed_batch_count":
            len(
                completion_rows
            ),
        "environment_explicit_sha256":
            environment_sha,
        "expected_batch_count":
            expected_batch_count,
        "fresh_acquisition_count":
            fresh_count,
        "fresh_batch_size":
            FRESH_BATCH_SIZE,
        "origin_git_commit":
            commit,
        "schema_version":
            MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_SCHEMA,
        "source_snapshot_id":
            snapshot,
        "source_snapshot_record_sha256":
            snapshot_record_sha,
        "stage2_fresh_target_manifest_sha256":
            manifest_sha,
        "stage2_sequence_plan_record_sha256":
            plan_sha,
        "status":
            MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_STATUS,
    }


def serialize_sequence_acquisition_completion_record(
    **kwargs,
) -> bytes:
    return _canonical_json_bytes(
        build_sequence_acquisition_completion_record(
            **kwargs
        )
    )


def audit_sequence_acquisition_completion_record(
    payload: bytes,
    **kwargs,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "sequence-acquisition completion record must be bytes"
        )

    expected = (
        serialize_sequence_acquisition_completion_record(
            **kwargs
        )
    )

    if payload != expected:
        raise MonthlySequenceAcquisitionCompletionError(
            "sequence-acquisition completion record derived identity changed"
        )

    try:
        value = json.loads(
            payload.decode(
                "ascii"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlySequenceAcquisitionCompletionError(
            "sequence-acquisition completion record is invalid"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise MonthlySequenceAcquisitionCompletionError(
            "sequence-acquisition completion record must be an object"
        )

    return value
