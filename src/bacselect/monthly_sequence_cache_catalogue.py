"""Pure cumulative sequence-cache catalogue contract for BacSelect."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
from io import StringIO
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from bacselect.monthly_sequence_validation import (
    CANDIDATE_AUDIT_FIELDS,
    COMPONENT_AUDIT_FIELDS,
    PACKAGE_FILE_FIELDS,
)
from bacselect.source_eligibility import (
    BIOSAMPLE_RE,
    CANONICAL_GCA_RE,
)


MONTHLY_SEQUENCE_CACHE_CATALOGUE_SCHEMA = (
    "bacselect-monthly-sequence-cache-catalogue-v1"
)

MONTHLY_SEQUENCE_CACHE_CATALOGUE_STATUS = (
    "SEQUENCE_CACHE_CATALOGUE_COMPLETE"
)

MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_SCHEMA = (
    "bacselect-monthly-sequence-acquisition-completion-v1"
)

MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_STATUS = (
    "SEQUENCE_ACQUISITION_COMPLETE"
)

GENESIS = "GENESIS"
CHAINED = "CHAINED"

SEQUENCE_ELIGIBLE = "eligible"
SEQUENCE_INELIGIBLE = "ineligible"

SEQUENCE_EXCLUSION_REASON_ORDER = (
    "ambiguous_nucleotide",
    "unresolved_topology",
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

GIT_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

RELEASE_ID_RE = re.compile(
    r"^[0-9]{4}\.(0[1-9]|1[0-2])$"
)

BATCH_ID_RE = re.compile(
    r"^batch-[0-9]{5}$"
)


class MonthlySequenceCacheCatalogueError(
    ValueError
):
    """Raised when cumulative cache-catalogue evidence is invalid."""


@dataclass(
    frozen=True,
)
class CompletedSequenceCacheBatchEvidence:
    """Exact completed Stage 3B evidence used to derive catalogue entries."""

    batch_id: str
    summary_payload: bytes
    candidate_audit_payload: bytes
    component_audit_payload: bytes
    package_files_payload: bytes


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


def _canonical_list_payload(
    *,
    schema_version: str,
    field: str,
    values: Sequence[
        Mapping[
            str,
            object,
        ]
    ],
) -> bytes:
    return _canonical_json_bytes(
        {
            field:
                list(
                    values
                ),
            "schema_version":
                schema_version,
        }
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
        raise MonthlySequenceCacheCatalogueError(
            f"{label} must be a lowercase SHA256"
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
        or value.strip()
        != value
    ):
        raise MonthlySequenceCacheCatalogueError(
            f"{label} must be non-empty normalized text"
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
        raise MonthlySequenceCacheCatalogueError(
            f"{label} must be a non-negative integer"
        )

    return value


def _positive_int(
    value: object,
    *,
    label: str,
) -> int:
    result = _nonnegative_int(
        value,
        label=label,
    )

    if result == 0:
        raise MonthlySequenceCacheCatalogueError(
            f"{label} must be positive"
        )

    return result


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
        raise MonthlySequenceCacheCatalogueError(
            "release ID must have YYYY.MM form"
        )

    return value


def _release_ordinal(
    release_id: str,
) -> int:
    year_text, month_text = (
        release_id.split(
            ".",
            1,
        )
    )

    return (
        int(
            year_text
        )
        * 12
        + int(
            month_text
        )
    )


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
        raise MonthlySequenceCacheCatalogueError(
            "origin Git commit must be a lowercase 40-character SHA"
        )

    return value


def _accession(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or CANONICAL_GCA_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlySequenceCacheCatalogueError(
            "canonical GenBank assembly accession is invalid"
        )

    return value


def _biosample(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or BIOSAMPLE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlySequenceCacheCatalogueError(
            "BioSample accession is invalid"
        )

    return value


def _sequence_eligibility(
    value: object,
) -> str:
    if value not in {
        SEQUENCE_ELIGIBLE,
        SEQUENCE_INELIGIBLE,
    }:
        raise MonthlySequenceCacheCatalogueError(
            "origin sequence eligibility is invalid"
        )

    return value


def _sequence_exclusion_reasons(
    value: object,
) -> tuple[
    str,
    ...,
]:
    text = _nonempty_text(
        value,
        label="origin sequence exclusion reasons",
    )

    if text == "none":
        return ()

    values = tuple(
        text.split(
            "|"
        )
    )

    if (
        not values
        or len(
            values
        )
        != len(
            set(
                values
            )
        )
        or any(
            reason
            not in SEQUENCE_EXCLUSION_REASON_ORDER
            for reason in values
        )
    ):
        raise MonthlySequenceCacheCatalogueError(
            "origin sequence exclusion reasons are invalid"
        )

    expected = tuple(
        reason
        for reason in SEQUENCE_EXCLUSION_REASON_ORDER
        if reason in values
    )

    if values != expected:
        raise MonthlySequenceCacheCatalogueError(
            "origin sequence exclusion-reason order changed"
        )

    return values


def _validate_sequence_eligibility_pair(
    *,
    eligibility: str,
    reasons: Sequence[
        str
    ],
) -> None:
    if (
        eligibility == SEQUENCE_ELIGIBLE
        and reasons
    ):
        raise MonthlySequenceCacheCatalogueError(
            "eligible origin sequence evidence "
            "cannot contain exclusion reasons"
        )

    if (
        eligibility == SEQUENCE_INELIGIBLE
        and not reasons
    ):
        raise MonthlySequenceCacheCatalogueError(
            "ineligible origin sequence evidence "
            "must contain an exclusion reason"
        )


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
        raise MonthlySequenceCacheCatalogueError(
            "Stage 3B batch ID is invalid"
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
        raise MonthlySequenceCacheCatalogueError(
            "source snapshot ID is invalid"
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
        + "(?:[01][0-9]|2[0-3])"
        + "[0-5][0-9]"
        + "[0-5][0-9]"
        + "Z$"
    )

    if pattern.fullmatch(
        value
    ) is None:
        raise MonthlySequenceCacheCatalogueError(
            "source snapshot ID does not match release identity"
        )

    return value


def _safe_relative_path(
    value: object,
    *,
    label: str,
) -> str:
    path = _nonempty_text(
        value,
        label=label,
    )

    if "\\" in path:
        raise MonthlySequenceCacheCatalogueError(
            f"{label} must use POSIX separators"
        )

    if path.startswith(
        "/"
    ):
        raise MonthlySequenceCacheCatalogueError(
            f"{label} must be relative"
        )

    parts = path.split(
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
        raise MonthlySequenceCacheCatalogueError(
            f"{label} is unsafe"
        )

    return path


def _serialize_tsv(
    rows: Sequence[
        Mapping[
            str,
            str,
        ]
    ],
    fields: Sequence[
        str
    ],
) -> bytes:
    buffer = StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        buffer,
        fieldnames=list(
            fields
        ),
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )

    writer.writeheader()

    for row in rows:
        writer.writerow(
            {
                field:
                    row[
                        field
                    ]
                for field in fields
            }
        )

    return buffer.getvalue().encode(
        "utf-8"
    )


def _parse_tsv(
    payload: bytes,
    *,
    fields: Sequence[
        str
    ],
    label: str,
) -> tuple[
    dict[
        str,
        str,
    ],
    ...,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            f"{label} must be bytes"
        )

    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise MonthlySequenceCacheCatalogueError(
            f"{label} is not UTF-8"
        ) from exc

    reader = csv.DictReader(
        StringIO(
            text,
            newline="",
        ),
        delimiter="\t",
    )

    if tuple(
        reader.fieldnames
        or ()
    ) != tuple(
        fields
    ):
        raise MonthlySequenceCacheCatalogueError(
            f"{label} field schema changed"
        )

    rows: list[
        dict[
            str,
            str,
        ]
    ] = []

    for row in reader:
        if (
            None in row
            or any(
                value is None
                for value in row.values()
            )
        ):
            raise MonthlySequenceCacheCatalogueError(
                f"{label} contains malformed TSV rows"
            )

        rows.append(
            {
                field:
                    str(
                        row[
                            field
                        ]
                    )
                for field in fields
            }
        )

    result = tuple(
        rows
    )

    if _serialize_tsv(
        result,
        fields,
    ) != payload:
        raise MonthlySequenceCacheCatalogueError(
            f"{label} is not canonical TSV"
        )

    return result


def _artifact_reference(
    *,
    logical_path: str,
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
            "artifact payload must be bytes"
        )

    return {
        "logical_path":
            _safe_relative_path(
                logical_path,
                label="logical artifact path",
            ),
        "sha256":
            hashlib.sha256(
                payload
            ).hexdigest(),
        "size_bytes":
            len(
                payload
            ),
    }


def _audit_artifact_reference(
    value: object,
    *,
    label: str,
) -> dict[
    str,
    object,
]:
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
        }
    ):
        raise MonthlySequenceCacheCatalogueError(
            f"{label} artifact reference schema changed"
        )

    return {
        "logical_path":
            _safe_relative_path(
                value[
                    "logical_path"
                ],
                label=f"{label} logical path",
            ),
        "sha256":
            _sha256(
                value[
                    "sha256"
                ],
                label=f"{label} SHA256",
            ),
        "size_bytes":
            _nonnegative_int(
                value[
                    "size_bytes"
                ],
                label=f"{label} size",
            ),
    }


def _package_artifact(
    row: Mapping[
        str,
        str,
    ],
    *,
    batch_id: str,
) -> dict[
    str,
    object,
]:
    path = _safe_relative_path(
        row[
            "path"
        ],
        label="package path",
    )

    batch = _batch_id(
        batch_id
    )

    logical_path = _safe_relative_path(
        (
            f"sequence-acquisition/{batch}/"
            f"package/{path}"
        ),
        label="package logical artifact path",
    )

    try:
        size = int(
            row[
                "size_bytes"
            ]
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlySequenceCacheCatalogueError(
            "package size is invalid"
        ) from exc

    return {
        "logical_path":
            logical_path,
        "package_path":
            path,
        "sha256":
            _sha256(
                row[
                    "sha256"
                ],
                label="package file SHA256",
            ),
        "size_bytes":
            _nonnegative_int(
                size,
                label="package size",
            ),
    }


def _audit_package_artifact(
    value: object,
    *,
    accession: str,
    batch_id: str,
) -> dict[
    str,
    object,
]:
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
            "package_path",
            "sha256",
            "size_bytes",
        }
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue package-artifact schema changed"
        )

    path = _safe_relative_path(
        value[
            "package_path"
        ],
        label="catalogue package path",
    )

    prefix = (
        f"ncbi_dataset/data/"
        f"{accession}/"
    )

    if not path.startswith(
        prefix
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue package artifact belongs to another accession"
        )

    if path == prefix:
        raise MonthlySequenceCacheCatalogueError(
            "catalogue package artifact lacks a filename"
        )

    batch = _batch_id(
        batch_id
    )

    logical_path = _safe_relative_path(
        value[
            "logical_path"
        ],
        label="catalogue package logical path",
    )

    expected_logical_path = (
        f"sequence-acquisition/{batch}/"
        f"package/{path}"
    )

    if logical_path != expected_logical_path:
        raise MonthlySequenceCacheCatalogueError(
            "catalogue package logical path "
            "does not match origin batch and package path"
        )

    return {
        "logical_path":
            logical_path,
        "package_path":
            path,
        "sha256":
            _sha256(
                value[
                    "sha256"
                ],
                label="catalogue package SHA256",
            ),
        "size_bytes":
            _nonnegative_int(
                value[
                    "size_bytes"
                ],
                label="catalogue package size",
            ),
    }


_COMPLETION_KEYS = {
    "batches",
    "completed_accession_count",
    "completed_batch_count",
    "environment_explicit_sha256",
    "expected_batch_count",
    "fresh_acquisition_count",
    "fresh_batch_size",
    "origin_git_commit",
    "schema_version",
    "source_snapshot_id",
    "source_snapshot_record_sha256",
    "stage2_fresh_target_manifest_sha256",
    "stage2_sequence_plan_record_sha256",
    "status",
}

_COMPLETION_BATCH_KEYS = {
    "accessions_sha256",
    "batch_id",
    "batch_index",
    "batch_summary_sha256",
    "batch_target_manifest_sha256",
    "candidate_sequence_audit_sha256",
    "component_sequence_audit_sha256",
    "fetch_entries",
    "first_accession",
    "last_accession",
    "package_file_readback_count",
    "package_file_readback_sha256",
    "package_files",
    "package_files_sha256",
    "requested_accessions",
}


def _audit_completion_record(
    payload: bytes,
    *,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
) -> dict[
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
        raise MonthlySequenceCacheCatalogueError(
            "invalid sequence-acquisition completion JSON"
        ) from exc

    if (
        not isinstance(
            value,
            dict,
        )
        or set(
            value
        )
        != _COMPLETION_KEYS
    ):
        raise MonthlySequenceCacheCatalogueError(
            "sequence-acquisition completion schema changed"
        )

    if _canonical_json_bytes(
        value
    ) != payload:
        raise MonthlySequenceCacheCatalogueError(
            "sequence-acquisition completion is not canonical JSON"
        )

    if value[
        "schema_version"
    ] != MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_SCHEMA:
        raise MonthlySequenceCacheCatalogueError(
            "sequence-acquisition completion schema version changed"
        )

    if value[
        "status"
    ] != MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_STATUS:
        raise MonthlySequenceCacheCatalogueError(
            "sequence-acquisition completion status changed"
        )

    if value[
        "source_snapshot_id"
    ] != source_snapshot_id:
        raise MonthlySequenceCacheCatalogueError(
            "sequence-acquisition completion source snapshot changed"
        )

    if value[
        "origin_git_commit"
    ] != origin_git_commit:
        raise MonthlySequenceCacheCatalogueError(
            "sequence-acquisition completion Git commit changed"
        )

    _source_snapshot_id(
        value[
            "source_snapshot_id"
        ],
        release_id=release_id,
    )

    _git_commit(
        value[
            "origin_git_commit"
        ]
    )

    for field in (
        "environment_explicit_sha256",
        "source_snapshot_record_sha256",
        "stage2_fresh_target_manifest_sha256",
        "stage2_sequence_plan_record_sha256",
    ):
        _sha256(
            value[
                field
            ],
            label=field,
        )

    fresh_count = _nonnegative_int(
        value[
            "fresh_acquisition_count"
        ],
        label="completion fresh-acquisition count",
    )

    completed_count = _nonnegative_int(
        value[
            "completed_accession_count"
        ],
        label="completion completed-accession count",
    )

    if fresh_count != completed_count:
        raise MonthlySequenceCacheCatalogueError(
            "completion accession accounting changed"
        )

    completed_batches = _nonnegative_int(
        value[
            "completed_batch_count"
        ],
        label="completion completed-batch count",
    )

    expected_batches = _nonnegative_int(
        value[
            "expected_batch_count"
        ],
        label="completion expected-batch count",
    )

    if completed_batches != expected_batches:
        raise MonthlySequenceCacheCatalogueError(
            "completion batch accounting changed"
        )

    _positive_int(
        value[
            "fresh_batch_size"
        ],
        label="completion fresh-batch size",
    )

    batches = value[
        "batches"
    ]

    if not isinstance(
        batches,
        list,
    ):
        raise MonthlySequenceCacheCatalogueError(
            "completion batches must be a list"
        )

    if len(
        batches
    ) != completed_batches:
        raise MonthlySequenceCacheCatalogueError(
            "completion batch list count changed"
        )

    requested_total = 0

    for index, row in enumerate(
        batches,
        1,
    ):
        if (
            not isinstance(
                row,
                dict,
            )
            or set(
                row
            )
            != _COMPLETION_BATCH_KEYS
        ):
            raise MonthlySequenceCacheCatalogueError(
                "completion batch-row schema changed"
            )

        expected_id = (
            f"batch-{index:05d}"
        )

        if _batch_id(
            row[
                "batch_id"
            ]
        ) != expected_id:
            raise MonthlySequenceCacheCatalogueError(
                "completion batch ordering changed"
            )

        if row[
            "batch_index"
        ] != index:
            raise MonthlySequenceCacheCatalogueError(
                "completion batch index changed"
            )

        for field in (
            "accessions_sha256",
            "batch_summary_sha256",
            "batch_target_manifest_sha256",
            "candidate_sequence_audit_sha256",
            "component_sequence_audit_sha256",
            "package_file_readback_sha256",
            "package_files_sha256",
        ):
            _sha256(
                row[
                    field
                ],
                label=f"completion {field}",
            )

        _accession(
            row[
                "first_accession"
            ]
        )

        _accession(
            row[
                "last_accession"
            ]
        )

        requested = _positive_int(
            row[
                "requested_accessions"
            ],
            label="completion batch requested-accession count",
        )

        _nonnegative_int(
            row[
                "fetch_entries"
            ],
            label="completion fetch-entry count",
        )

        package_files = _positive_int(
            row[
                "package_files"
            ],
            label="completion package-file count",
        )

        readback_count = _positive_int(
            row[
                "package_file_readback_count"
            ],
            label="completion package read-back count",
        )

        if package_files != readback_count:
            raise MonthlySequenceCacheCatalogueError(
                "completion package read-back accounting changed"
            )

        requested_total += (
            requested
        )

    if requested_total != fresh_count:
        raise MonthlySequenceCacheCatalogueError(
            "completion requested-accession accounting changed"
        )

    return value


def _batch_provenance_payload(
    row: Mapping[
        str,
        object,
    ],
) -> bytes:
    return _canonical_json_bytes(
        {
            "accessions_sha256":
                row[
                    "accessions_sha256"
                ],
            "batch_id":
                row[
                    "batch_id"
                ],
            "batch_summary":
                row[
                    "batch_summary"
                ],
            "cache_origin_git_commit":
                row[
                    "cache_origin_git_commit"
                ],
            "cache_origin_release_id":
                row[
                    "cache_origin_release_id"
                ],
            "cache_origin_source_snapshot_id":
                row[
                    "cache_origin_source_snapshot_id"
                ],
            "candidate_audit":
                row[
                    "candidate_audit"
                ],
            "component_audit":
                row[
                    "component_audit"
                ],
            "origin_package_file_readback_sha256":
                row[
                    "origin_package_file_readback_sha256"
                ],
            "origin_sequence_acquisition_completion_sha256":
                row[
                    "origin_sequence_acquisition_completion_sha256"
                ],
            "package_files_manifest":
                row[
                    "package_files_manifest"
                ],
            "requested_accessions":
                row[
                    "requested_accessions"
                ],
            "schema_version":
                "bacselect-monthly-sequence-cache-batch-provenance-v1",
        }
    )


def _entry_payload(
    row: Mapping[
        str,
        object,
    ],
) -> bytes:
    return _canonical_json_bytes(
        {
            "biosample":
                row[
                    "biosample"
                ],
            "canonical_genbank_assembly_accession":
                row[
                    "canonical_genbank_assembly_accession"
                ],
            "origin_batch_provenance_sha256":
                row[
                    "origin_batch_provenance_sha256"
                ],
            "origin_sequence_eligibility":
                row[
                    "origin_sequence_eligibility"
                ],
            "origin_sequence_exclusion_reasons":
                row[
                    "origin_sequence_exclusion_reasons"
                ],
            "package_artifacts":
                row[
                    "package_artifacts"
                ],
            "schema_version":
                "bacselect-monthly-sequence-cache-entry-v1",
        }
    )


def _audit_batch_provenance_row(
    value: object,
) -> dict[
    str,
    object,
]:
    expected_keys = {
        "accessions_sha256",
        "batch_id",
        "batch_provenance_sha256",
        "batch_summary",
        "cache_origin_git_commit",
        "cache_origin_release_id",
        "cache_origin_source_snapshot_id",
        "candidate_audit",
        "component_audit",
        "origin_package_file_readback_sha256",
        "origin_sequence_acquisition_completion_sha256",
        "package_files_manifest",
        "requested_accessions",
    }

    if (
        not isinstance(
            value,
            dict,
        )
        or set(
            value
        )
        != expected_keys
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue batch-provenance schema changed"
        )

    release = _release_id(
        value[
            "cache_origin_release_id"
        ]
    )

    snapshot = _source_snapshot_id(
        value[
            "cache_origin_source_snapshot_id"
        ],
        release_id=release,
    )

    commit = _git_commit(
        value[
            "cache_origin_git_commit"
        ]
    )

    batch = _batch_id(
        value[
            "batch_id"
        ]
    )

    summary = _audit_artifact_reference(
        value[
            "batch_summary"
        ],
        label="batch summary",
    )

    candidate = _audit_artifact_reference(
        value[
            "candidate_audit"
        ],
        label="candidate audit",
    )

    component = _audit_artifact_reference(
        value[
            "component_audit"
        ],
        label="component audit",
    )

    package = _audit_artifact_reference(
        value[
            "package_files_manifest"
        ],
        label="package-files manifest",
    )

    prefix = (
        f"sequence-acquisition/{batch}/"
    )

    expected_paths = {
        "batch-summary.json":
            summary[
                "logical_path"
            ],
        "candidate-sequence-audit.tsv":
            candidate[
                "logical_path"
            ],
        "component-sequence-audit.tsv":
            component[
                "logical_path"
            ],
        "package-files.tsv":
            package[
                "logical_path"
            ],
    }

    for filename, observed in expected_paths.items():
        if observed != (
            prefix
            + filename
        ):
            raise MonthlySequenceCacheCatalogueError(
                "catalogue batch artifact logical path changed"
            )

    row = {
        "accessions_sha256":
            _sha256(
                value[
                    "accessions_sha256"
                ],
                label="batch accessions SHA256",
            ),
        "batch_id":
            batch,
        "batch_summary":
            summary,
        "cache_origin_git_commit":
            commit,
        "cache_origin_release_id":
            release,
        "cache_origin_source_snapshot_id":
            snapshot,
        "candidate_audit":
            candidate,
        "component_audit":
            component,
        "origin_package_file_readback_sha256":
            _sha256(
                value[
                    "origin_package_file_readback_sha256"
                ],
                label="origin package read-back SHA256",
            ),
        "origin_sequence_acquisition_completion_sha256":
            _sha256(
                value[
                    "origin_sequence_acquisition_completion_sha256"
                ],
                label="origin completion SHA256",
            ),
        "package_files_manifest":
            package,
        "requested_accessions":
            _positive_int(
                value[
                    "requested_accessions"
                ],
                label="batch requested-accession count",
            ),
    }

    digest = hashlib.sha256(
        _batch_provenance_payload(
            row
        )
    ).hexdigest()

    if value[
        "batch_provenance_sha256"
    ] != digest:
        raise MonthlySequenceCacheCatalogueError(
            "catalogue batch-provenance SHA256 changed"
        )

    return {
        **row,
        "batch_provenance_sha256":
            digest,
    }


def _audit_entry(
    value: object,
    *,
    batch_id_by_provenance_sha: Mapping[
        str,
        str,
    ],
) -> dict[
    str,
    object,
]:
    expected_keys = {
        "biosample",
        "canonical_genbank_assembly_accession",
        "entry_sha256",
        "origin_batch_provenance_sha256",
        "origin_sequence_eligibility",
        "origin_sequence_exclusion_reasons",
        "package_artifacts",
    }

    if (
        not isinstance(
            value,
            dict,
        )
        or set(
            value
        )
        != expected_keys
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue entry schema changed"
        )

    accession = _accession(
        value[
            "canonical_genbank_assembly_accession"
        ]
    )

    biosample = _biosample(
        value[
            "biosample"
        ]
    )

    origin = _sha256(
        value[
            "origin_batch_provenance_sha256"
        ],
        label="origin batch-provenance SHA256",
    )

    origin_batch_id = (
        batch_id_by_provenance_sha.get(
            origin
        )
    )

    if origin_batch_id is None:
        raise MonthlySequenceCacheCatalogueError(
            "catalogue entry references missing "
            "batch provenance"
        )

    sequence_eligibility = _sequence_eligibility(
        value[
            "origin_sequence_eligibility"
        ]
    )

    sequence_exclusion_text = _nonempty_text(
        value[
            "origin_sequence_exclusion_reasons"
        ],
        label="origin sequence exclusion reasons",
    )

    sequence_exclusion_reasons = (
        _sequence_exclusion_reasons(
            sequence_exclusion_text
        )
    )

    _validate_sequence_eligibility_pair(
        eligibility=sequence_eligibility,
        reasons=sequence_exclusion_reasons,
    )

    artifacts_value = value[
        "package_artifacts"
    ]

    if (
        not isinstance(
            artifacts_value,
            list,
        )
        or not artifacts_value
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue entry must contain accession-scoped package artifacts"
        )

    artifacts = tuple(
        _audit_package_artifact(
            item,
            accession=accession,
            batch_id=origin_batch_id,
        )
        for item in artifacts_value
    )

    paths = tuple(
        item[
            "package_path"
        ]
        for item in artifacts
    )

    if paths != tuple(
        sorted(
            paths
        )
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue package artifacts are not sorted"
        )

    if len(
        paths
    ) != len(
        set(
            paths
        )
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue package artifacts contain duplicate paths"
        )

    row = {
        "biosample":
            biosample,
        "canonical_genbank_assembly_accession":
            accession,
        "origin_batch_provenance_sha256":
            origin,
        "origin_sequence_eligibility":
            sequence_eligibility,
        "origin_sequence_exclusion_reasons":
            sequence_exclusion_text,
        "package_artifacts":
            list(
                artifacts
            ),
    }

    digest = hashlib.sha256(
        _entry_payload(
            row
        )
    ).hexdigest()

    if value[
        "entry_sha256"
    ] != digest:
        raise MonthlySequenceCacheCatalogueError(
            "catalogue entry SHA256 changed"
        )

    return {
        **row,
        "entry_sha256":
            digest,
    }


def _derive_current_batch(
    *,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    completion_sha256: str,
    completion_row: Mapping[
        str,
        object,
    ],
    evidence: CompletedSequenceCacheBatchEvidence,
) -> tuple[
    dict[
        str,
        object,
    ],
    tuple[
        dict[
            str,
            object,
        ],
        ...,
    ],
]:
    if not isinstance(
        evidence,
        CompletedSequenceCacheBatchEvidence,
    ):
        raise TypeError(
            "current batch evidence has wrong type"
        )

    batch = _batch_id(
        evidence.batch_id
    )

    if completion_row[
        "batch_id"
    ] != batch:
        raise MonthlySequenceCacheCatalogueError(
            "current batch evidence ID differs from completion"
        )

    for payload, label in (
        (
            evidence.summary_payload,
            "batch summary",
        ),
        (
            evidence.candidate_audit_payload,
            "candidate audit",
        ),
        (
            evidence.component_audit_payload,
            "component audit",
        ),
        (
            evidence.package_files_payload,
            "package-files manifest",
        ),
    ):
        if not isinstance(
            payload,
            bytes,
        ):
            raise TypeError(
                f"{label} payload must be bytes"
            )

    observed_pairs = (
        (
            evidence.summary_payload,
            completion_row[
                "batch_summary_sha256"
            ],
            "batch summary",
        ),
        (
            evidence.candidate_audit_payload,
            completion_row[
                "candidate_sequence_audit_sha256"
            ],
            "candidate audit",
        ),
        (
            evidence.component_audit_payload,
            completion_row[
                "component_sequence_audit_sha256"
            ],
            "component audit",
        ),
        (
            evidence.package_files_payload,
            completion_row[
                "package_files_sha256"
            ],
            "package-files manifest",
        ),
    )

    for payload, expected, label in observed_pairs:
        observed = hashlib.sha256(
            payload
        ).hexdigest()

        if observed != expected:
            raise MonthlySequenceCacheCatalogueError(
                f"{label} identity differs from completion"
            )

    candidate_rows = _parse_tsv(
        evidence.candidate_audit_payload,
        fields=CANDIDATE_AUDIT_FIELDS,
        label="candidate audit",
    )

    component_rows = _parse_tsv(
        evidence.component_audit_payload,
        fields=COMPONENT_AUDIT_FIELDS,
        label="component audit",
    )

    package_rows = _parse_tsv(
        evidence.package_files_payload,
        fields=PACKAGE_FILE_FIELDS,
        label="package-files manifest",
    )

    requested = _positive_int(
        completion_row[
            "requested_accessions"
        ],
        label="completion requested-accession count",
    )

    if len(
        candidate_rows
    ) != requested:
        raise MonthlySequenceCacheCatalogueError(
            "candidate audit count differs from completion"
        )

    if len(
        package_rows
    ) != completion_row[
        "package_files"
    ]:
        raise MonthlySequenceCacheCatalogueError(
            "package-files row count differs from completion"
        )

    candidate_accessions: list[
        str
    ] = []

    candidate_by_accession: dict[
        str,
        Mapping[
            str,
            str,
        ]
    ] = {}

    primary_counts: dict[
        str,
        int,
    ] = {}

    sequence_eligibility_by_accession: dict[
        str,
        str,
    ] = {}

    sequence_exclusion_reasons_by_accession: dict[
        str,
        tuple[
            str,
            ...,
        ],
    ] = {}

    sequence_exclusion_text_by_accession: dict[
        str,
        str,
    ] = {}

    for row in candidate_rows:
        accession = _accession(
            row[
                "canonical_genbank_assembly_accession"
            ]
        )

        if accession in candidate_by_accession:
            raise MonthlySequenceCacheCatalogueError(
                "duplicate accession in candidate audit"
            )

        expected_biosample = _biosample(
            row[
                "expected_biosample"
            ]
        )

        observed_biosample = _biosample(
            row[
                "observed_biosample"
            ]
        )

        if expected_biosample != observed_biosample:
            raise MonthlySequenceCacheCatalogueError(
                "candidate BioSample evidence disagrees"
            )

        if row[
            "result"
        ] != "PASS":
            raise MonthlySequenceCacheCatalogueError(
                "candidate audit does not contain PASS evidence"
            )

        sequence_eligibility = (
            _sequence_eligibility(
                row[
                    "sequence_eligibility"
                ]
            )
        )

        sequence_exclusion_text = (
            _nonempty_text(
                row[
                    "exclusion_reasons"
                ],
                label="candidate exclusion reasons",
            )
        )

        sequence_exclusion_reasons = (
            _sequence_exclusion_reasons(
                sequence_exclusion_text
            )
        )

        _validate_sequence_eligibility_pair(
            eligibility=sequence_eligibility,
            reasons=sequence_exclusion_reasons,
        )

        sequence_eligibility_by_accession[
            accession
        ] = sequence_eligibility

        sequence_exclusion_reasons_by_accession[
            accession
        ] = sequence_exclusion_reasons

        sequence_exclusion_text_by_accession[
            accession
        ] = sequence_exclusion_text

        _sha256(
            row[
                "fasta_sha256"
            ],
            label="candidate FASTA SHA256",
        )

        fasta_file = _nonempty_text(
            row[
                "fasta_file"
            ],
            label="candidate FASTA file",
        )

        if (
            "/"
            in fasta_file
            or "\\"
            in fasta_file
        ):
            raise MonthlySequenceCacheCatalogueError(
                "candidate FASTA file must be a basename"
            )

        try:
            primary = int(
                row[
                    "primary_assembly_records"
                ]
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise MonthlySequenceCacheCatalogueError(
                "candidate primary-assembly count is invalid"
            ) from exc

        primary_counts[
            accession
        ] = _positive_int(
            primary,
            label="candidate primary-assembly count",
        )

        candidate_accessions.append(
            accession
        )

        candidate_by_accession[
            accession
        ] = row

    if candidate_accessions != sorted(
        candidate_accessions
    ):
        raise MonthlySequenceCacheCatalogueError(
            "candidate audit accession order changed"
        )

    derived_accessions_sha = hashlib.sha256(
        "".join(
            accession
            + "\n"
            for accession in candidate_accessions
        ).encode(
            "ascii"
        )
    ).hexdigest()

    if (
        derived_accessions_sha
        != completion_row[
            "accessions_sha256"
        ]
    ):
        raise MonthlySequenceCacheCatalogueError(
            "candidate audit accession-list SHA256 "
            "differs from completion"
        )

    if candidate_accessions[
        0
    ] != completion_row[
        "first_accession"
    ]:
        raise MonthlySequenceCacheCatalogueError(
            "candidate audit first accession differs from completion"
        )

    if candidate_accessions[
        -1
    ] != completion_row[
        "last_accession"
    ]:
        raise MonthlySequenceCacheCatalogueError(
            "candidate audit last accession differs from completion"
        )

    component_counts = {
        accession:
            0
        for accession in candidate_accessions
    }

    component_ambiguous_counts = {
        accession:
            0
        for accession in candidate_accessions
    }

    component_unspecified_counts = {
        accession:
            0
        for accession in candidate_accessions
    }

    component_order: list[
        tuple[
            str,
            str,
        ]
    ] = []

    for row in component_rows:
        accession = _accession(
            row[
                "canonical_genbank_assembly_accession"
            ]
        )

        if accession not in component_counts:
            raise MonthlySequenceCacheCatalogueError(
                "component audit contains accession absent from candidate audit"
            )

        component_accession = _nonempty_text(
            row[
                "component_genbank_accession"
            ],
            label="component GenBank accession",
        )

        component_order.append(
            (
                accession,
                component_accession,
            )
        )

        try:
            length = int(
                row[
                    "length"
                ]
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise MonthlySequenceCacheCatalogueError(
                "component length is invalid"
            ) from exc

        _positive_int(
            length,
            label="component length",
        )

        topology = row[
            "topology"
        ]

        if topology not in {
            "circular",
            "linear",
            "unspecified",
        }:
            raise MonthlySequenceCacheCatalogueError(
                "component topology is invalid"
            )

        try:
            ambiguous_count = int(
                row[
                    "ambiguous_base_count"
                ]
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise MonthlySequenceCacheCatalogueError(
                "component ambiguous-base count is invalid"
            ) from exc

        ambiguous_count = _nonnegative_int(
            ambiguous_count,
            label="component ambiguous-base count",
        )

        _sha256(
            row[
                "sequence_sha256"
            ],
            label="component sequence SHA256",
        )

        component_counts[
            accession
        ] += 1

        component_ambiguous_counts[
            accession
        ] += ambiguous_count

        if topology == "unspecified":
            component_unspecified_counts[
                accession
            ] += 1

    if component_order != sorted(
        component_order
    ):
        raise MonthlySequenceCacheCatalogueError(
            "component audit order changed"
        )

    if len(
        component_order
    ) != len(
        set(
            component_order
        )
    ):
        raise MonthlySequenceCacheCatalogueError(
            "component audit contains duplicate component evidence"
        )

    for accession in candidate_accessions:
        if (
            component_counts[
                accession
            ]
            != primary_counts[
                accession
            ]
        ):
            raise MonthlySequenceCacheCatalogueError(
                "component audit count differs from candidate primary count"
            )

        derived_reasons: list[
            str
        ] = []

        if component_ambiguous_counts[
            accession
        ] > 0:
            derived_reasons.append(
                "ambiguous_nucleotide"
            )

        if component_unspecified_counts[
            accession
        ] > 0:
            derived_reasons.append(
                "unresolved_topology"
            )

        expected_reasons = tuple(
            derived_reasons
        )

        if (
            sequence_exclusion_reasons_by_accession[
                accession
            ]
            != expected_reasons
        ):
            raise MonthlySequenceCacheCatalogueError(
                "candidate sequence exclusion reasons "
                "differ from component evidence"
            )

        expected_eligibility = (
            SEQUENCE_ELIGIBLE
            if not expected_reasons
            else SEQUENCE_INELIGIBLE
        )

        if (
            sequence_eligibility_by_accession[
                accession
            ]
            != expected_eligibility
        ):
            raise MonthlySequenceCacheCatalogueError(
                "candidate sequence eligibility "
                "differs from component evidence"
            )

    package_by_path: dict[
        str,
        dict[
            str,
            object,
        ]
    ] = {}

    package_order: list[
        str
    ] = []

    for row in package_rows:
        artifact = _package_artifact(
            row,
            batch_id=batch,
        )

        path = artifact[
            "package_path"
        ]

        if path in package_by_path:
            raise MonthlySequenceCacheCatalogueError(
                "duplicate package path"
            )

        package_by_path[
            path
        ] = artifact

        package_order.append(
            path
        )

    if package_order != sorted(
        package_order
    ):
        raise MonthlySequenceCacheCatalogueError(
            "package-files manifest path order changed"
        )

    entries: list[
        dict[
            str,
            object,
        ]
    ] = []

    provenance_base = {
        "accessions_sha256":
            completion_row[
                "accessions_sha256"
            ],
        "batch_id":
            batch,
        "batch_summary":
            _artifact_reference(
                logical_path=(
                    f"sequence-acquisition/{batch}/"
                    "batch-summary.json"
                ),
                payload=(
                    evidence.summary_payload
                ),
            ),
        "cache_origin_git_commit":
            origin_git_commit,
        "cache_origin_release_id":
            release_id,
        "cache_origin_source_snapshot_id":
            source_snapshot_id,
        "candidate_audit":
            _artifact_reference(
                logical_path=(
                    f"sequence-acquisition/{batch}/"
                    "candidate-sequence-audit.tsv"
                ),
                payload=(
                    evidence.candidate_audit_payload
                ),
            ),
        "component_audit":
            _artifact_reference(
                logical_path=(
                    f"sequence-acquisition/{batch}/"
                    "component-sequence-audit.tsv"
                ),
                payload=(
                    evidence.component_audit_payload
                ),
            ),
        "origin_package_file_readback_sha256":
            completion_row[
                "package_file_readback_sha256"
            ],
        "origin_sequence_acquisition_completion_sha256":
            completion_sha256,
        "package_files_manifest":
            _artifact_reference(
                logical_path=(
                    f"sequence-acquisition/{batch}/"
                    "package-files.tsv"
                ),
                payload=(
                    evidence.package_files_payload
                ),
            ),
        "requested_accessions":
            requested,
    }

    provenance_sha = hashlib.sha256(
        _batch_provenance_payload(
            provenance_base
        )
    ).hexdigest()

    provenance = {
        **provenance_base,
        "batch_provenance_sha256":
            provenance_sha,
    }

    for accession in candidate_accessions:
        prefix = (
            f"ncbi_dataset/data/"
            f"{accession}/"
        )

        scoped = tuple(
            sorted(
                (
                    artifact
                    for path, artifact
                    in package_by_path.items()
                    if path.startswith(
                        prefix
                    )
                    and path != prefix
                ),
                key=lambda item:
                    item[
                        "package_path"
                    ],
            )
        )

        if not scoped:
            raise MonthlySequenceCacheCatalogueError(
                "candidate has no accession-scoped package artifacts"
            )

        candidate_row = candidate_by_accession[
            accession
        ]

        fasta_file = candidate_row[
            "fasta_file"
        ]

        fasta_basename = fasta_file.split(
            "/"
        )[
            -1
        ]

        fasta_sha = candidate_row[
            "fasta_sha256"
        ]

        exact = tuple(
            item
            for item in scoped
            if (
                item[
                    "package_path"
                ]
                == fasta_file
                and item[
                    "sha256"
                ]
                == fasta_sha
            )
        )

        basename = tuple(
            item
            for item in scoped
            if (
                item[
                    "package_path"
                ].split(
                    "/"
                )[
                    -1
                ]
                == fasta_basename
                and item[
                    "sha256"
                ]
                == fasta_sha
            )
        )

        matches = (
            exact
            if exact
            else basename
        )

        if len(
            matches
        ) != 1:
            raise MonthlySequenceCacheCatalogueError(
                "candidate FASTA is not uniquely bound to accession package artifacts"
            )

        entry_base = {
            "biosample":
                candidate_row[
                    "expected_biosample"
                ],
            "canonical_genbank_assembly_accession":
                accession,
            "origin_batch_provenance_sha256":
                provenance_sha,
            "origin_sequence_eligibility":
                sequence_eligibility_by_accession[
                    accession
                ],
            "origin_sequence_exclusion_reasons":
                sequence_exclusion_text_by_accession[
                    accession
                ],
            "package_artifacts":
                list(
                    scoped
                ),
        }

        entries.append(
            {
                **entry_base,
                "entry_sha256":
                    hashlib.sha256(
                        _entry_payload(
                            entry_base
                        )
                    ).hexdigest(),
            }
        )

    return (
        provenance,
        tuple(
            entries
        ),
    )


_CATALOGUE_KEYS = {
    "batch_provenance",
    "batch_provenance_count",
    "batch_provenance_sha256",
    "carried_forward_entry_count",
    "catalogue_entry_count",
    "catalogue_mode",
    "current_acquisition_count",
    "entries",
    "entries_sha256",
    "new_entry_count",
    "origin_git_commit",
    "previous_catalogue_entry_count",
    "previous_catalogue_release_id",
    "previous_catalogue_sha256",
    "release_id",
    "replaced_entry_count",
    "schema_version",
    "sequence_acquisition_completion_sha256",
    "sequence_acquisition_fresh_count",
    "source_snapshot_id",
    "status",
}


def audit_sequence_cache_catalogue(
    payload: bytes,
) -> dict[
    str,
    object,
]:
    """Audit one catalogue from its own deterministic bytes."""

    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "sequence-cache catalogue must be bytes"
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
        raise MonthlySequenceCacheCatalogueError(
            "invalid sequence-cache catalogue JSON"
        ) from exc

    if (
        not isinstance(
            value,
            dict,
        )
        or set(
            value
        )
        != _CATALOGUE_KEYS
    ):
        raise MonthlySequenceCacheCatalogueError(
            "sequence-cache catalogue schema changed"
        )

    if _canonical_json_bytes(
        value
    ) != payload:
        raise MonthlySequenceCacheCatalogueError(
            "sequence-cache catalogue is not canonical JSON"
        )

    if value[
        "schema_version"
    ] != MONTHLY_SEQUENCE_CACHE_CATALOGUE_SCHEMA:
        raise MonthlySequenceCacheCatalogueError(
            "sequence-cache catalogue schema version changed"
        )

    if value[
        "status"
    ] != MONTHLY_SEQUENCE_CACHE_CATALOGUE_STATUS:
        raise MonthlySequenceCacheCatalogueError(
            "sequence-cache catalogue status changed"
        )

    release = _release_id(
        value[
            "release_id"
        ]
    )

    snapshot = _source_snapshot_id(
        value[
            "source_snapshot_id"
        ],
        release_id=release,
    )

    commit = _git_commit(
        value[
            "origin_git_commit"
        ]
    )

    completion_sha = _sha256(
        value[
            "sequence_acquisition_completion_sha256"
        ],
        label="sequence-acquisition completion SHA256",
    )

    fresh_count = _nonnegative_int(
        value[
            "sequence_acquisition_fresh_count"
        ],
        label="sequence-acquisition fresh count",
    )

    mode = value[
        "catalogue_mode"
    ]

    previous_release = value[
        "previous_catalogue_release_id"
    ]

    previous_sha = value[
        "previous_catalogue_sha256"
    ]

    previous_count = _nonnegative_int(
        value[
            "previous_catalogue_entry_count"
        ],
        label="previous catalogue entry count",
    )

    if mode == GENESIS:
        if (
            previous_release is not None
            or previous_sha is not None
            or previous_count != 0
        ):
            raise MonthlySequenceCacheCatalogueError(
                "genesis catalogue contains previous-catalogue provenance"
            )

    elif mode == CHAINED:
        previous_release = _release_id(
            previous_release
        )

        previous_sha = _sha256(
            previous_sha,
            label="previous catalogue SHA256",
        )

        if (
            _release_ordinal(
                previous_release
            )
            >= _release_ordinal(
                release
            )
        ):
            raise MonthlySequenceCacheCatalogueError(
                "previous catalogue release is not earlier than current release"
            )

    else:
        raise MonthlySequenceCacheCatalogueError(
            "catalogue mode is invalid"
        )

    batch_values = value[
        "batch_provenance"
    ]

    if not isinstance(
        batch_values,
        list,
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue batch provenance must be a list"
        )

    batches = tuple(
        _audit_batch_provenance_row(
            item
        )
        for item in batch_values
    )

    batch_hashes = tuple(
        item[
            "batch_provenance_sha256"
        ]
        for item in batches
    )

    if batch_hashes != tuple(
        sorted(
            batch_hashes
        )
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue batch provenance is not sorted"
        )

    if len(
        batch_hashes
    ) != len(
        set(
            batch_hashes
        )
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue contains duplicate batch provenance"
        )

    batch_count = _nonnegative_int(
        value[
            "batch_provenance_count"
        ],
        label="catalogue batch-provenance count",
    )

    if batch_count != len(
        batches
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue batch-provenance count changed"
        )

    expected_batch_sha = hashlib.sha256(
        _canonical_list_payload(
            schema_version=(
                "bacselect-monthly-sequence-cache-"
                "batch-provenance-set-v1"
            ),
            field="batch_provenance",
            values=batches,
        )
    ).hexdigest()

    if value[
        "batch_provenance_sha256"
    ] != expected_batch_sha:
        raise MonthlySequenceCacheCatalogueError(
            "catalogue batch-provenance set SHA256 changed"
        )

    batch_id_by_provenance_sha = {
        item[
            "batch_provenance_sha256"
        ]:
            item[
                "batch_id"
            ]
        for item in batches
    }

    entry_values = value[
        "entries"
    ]

    if not isinstance(
        entry_values,
        list,
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue entries must be a list"
        )

    entries = tuple(
        _audit_entry(
            item,
            batch_id_by_provenance_sha=(
                batch_id_by_provenance_sha
            ),
        )
        for item in entry_values
    )

    accessions = tuple(
        item[
            "canonical_genbank_assembly_accession"
        ]
        for item in entries
    )

    if accessions != tuple(
        sorted(
            accessions
        )
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue entries are not sorted by accession"
        )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue contains duplicate accessions"
        )

    batch_hash_set = set(
        batch_hashes
    )

    referenced = {
        item[
            "origin_batch_provenance_sha256"
        ]
        for item in entries
    }

    if referenced != batch_hash_set:
        raise MonthlySequenceCacheCatalogueError(
            "catalogue batch provenance is missing, dangling, or unreferenced"
        )

    entry_count = _nonnegative_int(
        value[
            "catalogue_entry_count"
        ],
        label="catalogue entry count",
    )

    if entry_count != len(
        entries
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue entry count changed"
        )

    expected_entries_sha = hashlib.sha256(
        _canonical_list_payload(
            schema_version=(
                "bacselect-monthly-sequence-cache-entry-set-v1"
            ),
            field="entries",
            values=entries,
        )
    ).hexdigest()

    if value[
        "entries_sha256"
    ] != expected_entries_sha:
        raise MonthlySequenceCacheCatalogueError(
            "catalogue entry-set SHA256 changed"
        )

    carried = _nonnegative_int(
        value[
            "carried_forward_entry_count"
        ],
        label="carried-forward entry count",
    )

    new = _nonnegative_int(
        value[
            "new_entry_count"
        ],
        label="new entry count",
    )

    replaced = _nonnegative_int(
        value[
            "replaced_entry_count"
        ],
        label="replaced entry count",
    )

    current = _nonnegative_int(
        value[
            "current_acquisition_count"
        ],
        label="current acquisition count",
    )

    if current != (
        new
        + replaced
    ):
        raise MonthlySequenceCacheCatalogueError(
            "current acquisition accounting changed"
        )

    if current != fresh_count:
        raise MonthlySequenceCacheCatalogueError(
            "catalogue current acquisition count differs from completion"
        )

    if previous_count != (
        carried
        + replaced
    ):
        raise MonthlySequenceCacheCatalogueError(
            "previous catalogue accounting changed"
        )

    if entry_count != (
        carried
        + new
        + replaced
    ):
        raise MonthlySequenceCacheCatalogueError(
            "catalogue merge accounting changed"
        )

    if (
        mode == GENESIS
        and (
            carried != 0
            or replaced != 0
        )
    ):
        raise MonthlySequenceCacheCatalogueError(
            "genesis catalogue cannot carry or replace previous entries"
        )

    return {
        "batch_provenance":
            list(
                batches
            ),
        "batch_provenance_count":
            batch_count,
        "batch_provenance_sha256":
            expected_batch_sha,
        "carried_forward_entry_count":
            carried,
        "catalogue_entry_count":
            entry_count,
        "catalogue_mode":
            mode,
        "current_acquisition_count":
            current,
        "entries":
            list(
                entries
            ),
        "entries_sha256":
            expected_entries_sha,
        "new_entry_count":
            new,
        "origin_git_commit":
            commit,
        "previous_catalogue_entry_count":
            previous_count,
        "previous_catalogue_release_id":
            previous_release,
        "previous_catalogue_sha256":
            previous_sha,
        "release_id":
            release,
        "replaced_entry_count":
            replaced,
        "schema_version":
            MONTHLY_SEQUENCE_CACHE_CATALOGUE_SCHEMA,
        "sequence_acquisition_completion_sha256":
            completion_sha,
        "sequence_acquisition_fresh_count":
            fresh_count,
        "source_snapshot_id":
            snapshot,
        "status":
            MONTHLY_SEQUENCE_CACHE_CATALOGUE_STATUS,
    }


def build_sequence_cache_catalogue(
    *,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    sequence_acquisition_completion_payload: bytes,
    current_batches: Iterable[
        CompletedSequenceCacheBatchEvidence
    ],
    previous_catalogue_payload: bytes | None = None,
) -> dict[
    str,
    object,
]:
    """Build the deterministic cumulative monthly sequence-cache catalogue."""

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

    completion = _audit_completion_record(
        sequence_acquisition_completion_payload,
        release_id=release,
        source_snapshot_id=snapshot,
        origin_git_commit=commit,
    )

    completion_sha = hashlib.sha256(
        sequence_acquisition_completion_payload
    ).hexdigest()

    evidence_values = tuple(
        current_batches
    )

    if any(
        not isinstance(
            item,
            CompletedSequenceCacheBatchEvidence,
        )
        for item in evidence_values
    ):
        raise TypeError(
            "current batch evidence has wrong type"
        )

    evidence_by_id: dict[
        str,
        CompletedSequenceCacheBatchEvidence,
    ] = {}

    for item in evidence_values:
        batch = _batch_id(
            item.batch_id
        )

        if batch in evidence_by_id:
            raise MonthlySequenceCacheCatalogueError(
                "duplicate current batch evidence"
            )

        evidence_by_id[
            batch
        ] = item

    completion_batches = tuple(
        completion[
            "batches"
        ]
    )

    expected_ids = tuple(
        row[
            "batch_id"
        ]
        for row in completion_batches
    )

    if tuple(
        sorted(
            evidence_by_id
        )
    ) != expected_ids:
        raise MonthlySequenceCacheCatalogueError(
            "current batch evidence set differs from completion"
        )

    current_provenance: list[
        dict[
            str,
            object,
        ]
    ] = []

    current_entries: list[
        dict[
            str,
            object,
        ]
    ] = []

    current_accessions: set[
        str
    ] = set()

    for completion_row in completion_batches:
        batch = completion_row[
            "batch_id"
        ]

        provenance, entries = (
            _derive_current_batch(
                release_id=release,
                source_snapshot_id=snapshot,
                origin_git_commit=commit,
                completion_sha256=(
                    completion_sha
                ),
                completion_row=(
                    completion_row
                ),
                evidence=(
                    evidence_by_id[
                        batch
                    ]
                ),
            )
        )

        current_provenance.append(
            provenance
        )

        for entry in entries:
            accession = entry[
                "canonical_genbank_assembly_accession"
            ]

            if accession in current_accessions:
                raise MonthlySequenceCacheCatalogueError(
                    "current Stage 3B batches contain duplicate accession"
                )

            current_accessions.add(
                accession
            )

            current_entries.append(
                entry
            )

    if len(
        current_entries
    ) != completion[
        "fresh_acquisition_count"
    ]:
        raise MonthlySequenceCacheCatalogueError(
            "derived current catalogue population differs from completion"
        )

    if previous_catalogue_payload is None:
        mode = GENESIS
        previous_record = None
        previous_sha = None
        previous_release = None
        previous_entries: tuple[
            Mapping[
                str,
                object,
            ],
            ...,
        ] = ()
        previous_batches: tuple[
            Mapping[
                str,
                object,
            ],
            ...,
        ] = ()

    else:
        if not isinstance(
            previous_catalogue_payload,
            bytes,
        ):
            raise TypeError(
                "previous catalogue must be bytes or None"
            )

        previous_record = (
            audit_sequence_cache_catalogue(
                previous_catalogue_payload
            )
        )

        previous_release = (
            previous_record[
                "release_id"
            ]
        )

        if (
            _release_ordinal(
                previous_release
            )
            >= _release_ordinal(
                release
            )
        ):
            raise MonthlySequenceCacheCatalogueError(
                "previous catalogue release is not earlier than current release"
            )

        mode = CHAINED

        previous_sha = hashlib.sha256(
            previous_catalogue_payload
        ).hexdigest()

        previous_entries = tuple(
            previous_record[
                "entries"
            ]
        )

        previous_batches = tuple(
            previous_record[
                "batch_provenance"
            ]
        )

    previous_by_accession = {
        entry[
            "canonical_genbank_assembly_accession"
        ]:
            entry
        for entry in previous_entries
    }

    current_by_accession = {
        entry[
            "canonical_genbank_assembly_accession"
        ]:
            entry
        for entry in current_entries
    }

    replaced_accessions = (
        set(
            previous_by_accession
        )
        & set(
            current_by_accession
        )
    )

    new_accessions = (
        set(
            current_by_accession
        )
        - set(
            previous_by_accession
        )
    )

    carried_accessions = (
        set(
            previous_by_accession
        )
        - set(
            current_by_accession
        )
    )

    merged_entries = tuple(
        sorted(
            (
                *(
                    previous_by_accession[
                        accession
                    ]
                    for accession in carried_accessions
                ),
                *current_by_accession.values(),
            ),
            key=lambda item:
                item[
                    "canonical_genbank_assembly_accession"
                ],
        )
    )

    provenance_by_sha: dict[
        str,
        Mapping[
            str,
            object,
        ]
    ] = {}

    for row in (
        *previous_batches,
        *current_provenance,
    ):
        digest = row[
            "batch_provenance_sha256"
        ]

        existing = provenance_by_sha.get(
            digest
        )

        if (
            existing is not None
            and existing != row
        ):
            raise MonthlySequenceCacheCatalogueError(
                "batch-provenance SHA256 collision has inconsistent content"
            )

        provenance_by_sha[
            digest
        ] = row

    referenced_provenance = {
        entry[
            "origin_batch_provenance_sha256"
        ]
        for entry in merged_entries
    }

    missing_provenance = (
        referenced_provenance
        - set(
            provenance_by_sha
        )
    )

    if missing_provenance:
        raise MonthlySequenceCacheCatalogueError(
            "merged catalogue entry lacks batch provenance"
        )

    merged_batches = tuple(
        sorted(
            (
                provenance_by_sha[
                    digest
                ]
                for digest in referenced_provenance
            ),
            key=lambda item:
                item[
                    "batch_provenance_sha256"
                ],
        )
    )

    batch_set_sha = hashlib.sha256(
        _canonical_list_payload(
            schema_version=(
                "bacselect-monthly-sequence-cache-"
                "batch-provenance-set-v1"
            ),
            field="batch_provenance",
            values=merged_batches,
        )
    ).hexdigest()

    entry_set_sha = hashlib.sha256(
        _canonical_list_payload(
            schema_version=(
                "bacselect-monthly-sequence-cache-entry-set-v1"
            ),
            field="entries",
            values=merged_entries,
        )
    ).hexdigest()

    record = {
        "batch_provenance":
            list(
                merged_batches
            ),
        "batch_provenance_count":
            len(
                merged_batches
            ),
        "batch_provenance_sha256":
            batch_set_sha,
        "carried_forward_entry_count":
            len(
                carried_accessions
            ),
        "catalogue_entry_count":
            len(
                merged_entries
            ),
        "catalogue_mode":
            mode,
        "current_acquisition_count":
            len(
                current_entries
            ),
        "entries":
            list(
                merged_entries
            ),
        "entries_sha256":
            entry_set_sha,
        "new_entry_count":
            len(
                new_accessions
            ),
        "origin_git_commit":
            commit,
        "previous_catalogue_entry_count":
            len(
                previous_entries
            ),
        "previous_catalogue_release_id":
            previous_release,
        "previous_catalogue_sha256":
            previous_sha,
        "release_id":
            release,
        "replaced_entry_count":
            len(
                replaced_accessions
            ),
        "schema_version":
            MONTHLY_SEQUENCE_CACHE_CATALOGUE_SCHEMA,
        "sequence_acquisition_completion_sha256":
            completion_sha,
        "sequence_acquisition_fresh_count":
            completion[
                "fresh_acquisition_count"
            ],
        "source_snapshot_id":
            snapshot,
        "status":
            MONTHLY_SEQUENCE_CACHE_CATALOGUE_STATUS,
    }

    # A standalone audit must reproduce every deterministic identity.
    audit_sequence_cache_catalogue(
        _canonical_json_bytes(
            record
        )
    )

    return record


def serialize_sequence_cache_catalogue(
    **kwargs,
) -> bytes:
    return _canonical_json_bytes(
        build_sequence_cache_catalogue(
            **kwargs
        )
    )
