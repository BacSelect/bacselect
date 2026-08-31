"""Pure BacSelect monthly taxonomy-snapshot provenance contract.

This module freezes the monthly Stage 7 taxonomy-snapshot identity and
provenance model.

It performs no network access, archive extraction, filesystem publication,
taxonomy resolution, structural-feature computation, or selector analysis.

The historical selector-v1 taxonomy acquisition execution is not a production
dependency of this module.

This pure contract does not independently establish that supplied Stage 1
source-snapshot bytes are the canonical production artefact. The monthly
Stage 7 executor must reconstruct and authenticate the canonical Stage 1
evidence chain before supplying the source-snapshot record bytes and their
expected SHA256 to this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Mapping

from bacselect import monthly_release_start


SCHEMA_VERSION = (
    "bacselect-monthly-taxonomy-snapshot-v1"
)

STATUS = (
    "MONTHLY_TAXONOMY_SNAPSHOT_FROZEN"
)

TAXONOMY_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/"
    "new_taxdump/new_taxdump.tar.gz"
)

SOURCE_TAXONOMY_SHA256 = (
    "9c8c4149c5db2a757e8c201a6523bdb1"
    "13511b5f72a4dd2893572dd8c7928e4d"
)

_RELEASE_RE = re.compile(
    r"^[0-9]{4}\.[0-9]{2}$"
)

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

TIMESTAMP_FORMAT = (
    "%Y-%m-%dT%H:%M:%SZ"
)

RECORD_FIELDS = frozenset({
    "schema_version",
    "status",
    "release_id",
    "source_snapshot_id",
    "origin_git_commit",
    "source_snapshot_record_sha256",
    "source_raw_response_sha256",
    "taxonomy_snapshot_id",
    "taxonomy_acquisition_started_utc",
    "taxonomy_acquisition_completed_utc",
    "taxonomy_requested_url",
    "taxonomy_final_url",
    "taxonomy_archive_sha256",
    "taxonomy_archive_size_bytes",
    "taxonomy_nodes_sha256",
    "taxonomy_nodes_size_bytes",
    "taxonomy_merged_sha256",
    "taxonomy_merged_size_bytes",
    "taxonomy_delnodes_sha256",
    "taxonomy_delnodes_size_bytes",
    "taxonomy_acquisition_provenance_sha256",
    "taxonomy_content_manifest_sha256",
    "taxonomy_acquisition_implementation_sha256",
    "source_taxonomy_sha256",
    "taxonomy_resolution_performed",
    "structural_features_calculated",
    "selector_outcomes_calculated",
})


class MonthlyTaxonomySnapshotError(
    RuntimeError
):
    """Raised when monthly taxonomy-snapshot evidence fails closed."""


@dataclass(
    frozen=True
)
class MonthlyTaxonomySourceContext:
    """Authenticated identity of the current monthly source snapshot."""

    release_id: str
    source_snapshot_id: str
    origin_git_commit: str
    source_snapshot_record_sha256: str
    source_raw_response_sha256: str


@dataclass(
    frozen=True
)
class MonthlyTaxonomyAcquisitionEvidence:
    """Identity-bearing evidence produced by a future Stage 7 executor."""

    acquisition_started_utc: str
    acquisition_completed_utc: str

    requested_url: str
    final_url: str

    archive_sha256: str
    archive_size_bytes: int

    nodes_sha256: str
    nodes_size_bytes: int

    merged_sha256: str
    merged_size_bytes: int

    delnodes_sha256: str
    delnodes_size_bytes: int

    acquisition_provenance_sha256: str
    content_manifest_sha256: str
    acquisition_implementation_sha256: str

    source_taxonomy_sha256: str


@dataclass(
    frozen=True
)
class MonthlyTaxonomySnapshotBuild:
    """Validated monthly taxonomy snapshot before serialization."""

    source: MonthlyTaxonomySourceContext
    evidence: MonthlyTaxonomyAcquisitionEvidence
    taxonomy_snapshot_id: str


def _sha256_bytes(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def _canonical_json(
    payload: Mapping[
        str,
        object,
    ],
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


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
        raise MonthlyTaxonomySnapshotError(
            f"{label} must be non-empty canonical text"
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
        or _RELEASE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyTaxonomySnapshotError(
            "release_id must use YYYY.MM"
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
        or _SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyTaxonomySnapshotError(
            f"{label} must be lowercase SHA256"
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
        or _COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyTaxonomySnapshotError(
            "origin_git_commit must be lowercase 40-hex Git identity"
        )

    return value


def _positive_size(
    value: object,
    *,
    label: str,
) -> int:
    if (
        not isinstance(
            value,
            int,
        )
        or isinstance(
            value,
            bool,
        )
        or value <= 0
    ):
        raise MonthlyTaxonomySnapshotError(
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
        raise MonthlyTaxonomySnapshotError(
            f"{label} must use UTC YYYY-MM-DDTHH:MM:SSZ"
        ) from exc

    if parsed.strftime(
        TIMESTAMP_FORMAT
    ) != text:
        raise MonthlyTaxonomySnapshotError(
            f"{label} is not canonical UTC"
        )

    return text


def _source_snapshot_record(
    payload: bytes,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot record must be bytes"
        )

    try:
        record = json.loads(
            payload
        )
    except json.JSONDecodeError as exc:
        raise MonthlyTaxonomySnapshotError(
            "source snapshot record is invalid JSON"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot record must be a JSON object"
        )

    if set(
        record
    ) != set(
        monthly_release_start
        .SOURCE_SNAPSHOT_KEYS
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot record schema changed"
        )

    if (
        record[
            "schema_version"
        ]
        != monthly_release_start
        .SOURCE_SNAPSHOT_SCHEMA_VERSION
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot schema version changed"
        )

    if (
        record[
            "status"
        ]
        != monthly_release_start
        .SOURCE_SNAPSHOT_STATUS
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot is not acquired"
        )

    if (
        record[
            "selector"
        ]
        != monthly_release_start.SELECTOR
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot selector changed"
        )

    if (
        record[
            "selector_version"
        ]
        != monthly_release_start
        .SELECTOR_VERSION
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot selector version changed"
        )

    if (
        record[
            "architecture_schema_version"
        ]
        != monthly_release_start
        .ARCHITECTURE_SCHEMA_VERSION
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot architecture schema changed"
        )

    _sha256(
        record[
            "ncbi_datasets_environment_sha256"
        ],
        label="NCBI Datasets environment SHA256",
    )

    _sha256(
        record[
            "release_start_checkpoint_sha256"
        ],
        label="release-start checkpoint SHA256",
    )

    _sha256(
        record[
            "raw_response_sha256"
        ],
        label="raw source response SHA256",
    )

    _positive_size(
        record[
            "raw_response_bytes"
        ],
        label="raw source response size",
    )

    snapshot_start = _timestamp(
        record[
            "snapshot_start_utc"
        ],
        label="source snapshot start",
    )

    query_start = _timestamp(
        record[
            "source_query_started_utc"
        ],
        label="source query start",
    )

    query_complete = _timestamp(
        record[
            "source_query_completed_utc"
        ],
        label="source query completion",
    )

    if not (
        snapshot_start
        <= query_start
        <= query_complete
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot timestamps are out of order"
        )

    command = record[
        "source_query_command"
    ]

    if (
        not isinstance(
            command,
            list,
        )
        or not command
        or any(
            not isinstance(
                value,
                str,
            )
            or not value
            for value in command
        )
    ):
        raise MonthlyTaxonomySnapshotError(
            "source query command is invalid"
        )

    if not isinstance(
        record[
            "source_query_specification"
        ],
        dict,
    ):
        raise MonthlyTaxonomySnapshotError(
            "source query specification must be an object"
        )

    _nonempty_text(
        record[
            "ncbi_datasets_version"
        ],
        label="NCBI Datasets version",
    )

    return record


def build_monthly_taxonomy_source_context(
    source_snapshot_record_payload: bytes,
    *,
    expected_source_snapshot_record_sha256: str,
    origin_git_commit: str,
) -> MonthlyTaxonomySourceContext:
    """Bind a caller-authenticated Stage 1 record entering monthly Stage 7.

    The caller must reconstruct and authenticate the canonical Stage 1
    evidence chain before supplying these bytes and their expected SHA256.
    This pure function validates the supplied record structure and binds its
    exact byte identity; it is not the authority that determines which
    Stage 1 artefact is canonical production evidence.
    """

    expected_record_sha = _sha256(
        expected_source_snapshot_record_sha256,
        label="source snapshot record SHA256",
    )

    observed_record_sha = _sha256_bytes(
        source_snapshot_record_payload
    )

    if observed_record_sha != expected_record_sha:
        raise MonthlyTaxonomySnapshotError(
            "source snapshot record SHA256 mismatch"
        )

    record = _source_snapshot_record(
        source_snapshot_record_payload
    )

    release = _release_id(
        record[
            "release_id"
        ]
    )

    commit = _commit(
        origin_git_commit
    )

    if (
        record[
            "expected_git_commit"
        ]
        != commit
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot Git commit differs from Stage 7 origin"
        )

    snapshot_start = _timestamp(
        record[
            "snapshot_start_utc"
        ],
        label="source snapshot start",
    )

    try:
        expected_snapshot_id = (
            monthly_release_start
            .source_snapshot_id_from_start(
                snapshot_start
            )
        )
    except Exception as exc:
        raise MonthlyTaxonomySnapshotError(
            "source snapshot ID could not be reconstructed"
        ) from exc

    source_snapshot_id = _nonempty_text(
        record[
            "source_snapshot_id"
        ],
        label="source snapshot ID",
    )

    if (
        source_snapshot_id
        != expected_snapshot_id
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot ID does not match its frozen start"
        )

    expected_prefix = (
        f"bacselect-source-{release}-"
    )

    if not source_snapshot_id.startswith(
        expected_prefix
    ):
        raise MonthlyTaxonomySnapshotError(
            "source snapshot ID does not match release"
        )

    return MonthlyTaxonomySourceContext(
        release_id=release,
        source_snapshot_id=(
            source_snapshot_id
        ),
        origin_git_commit=commit,
        source_snapshot_record_sha256=(
            expected_record_sha
        ),
        source_raw_response_sha256=(
            _sha256(
                record[
                    "raw_response_sha256"
                ],
                label="raw source response SHA256",
            )
        ),
    )


def taxonomy_snapshot_id_from_evidence(
    *,
    release_id: str,
    acquisition_started_utc: str,
    archive_sha256: str,
) -> str:
    """Derive monthly taxonomy identity from release, time and content."""

    release = _release_id(
        release_id
    )

    started = _timestamp(
        acquisition_started_utc,
        label="taxonomy acquisition start",
    )

    archive = _sha256(
        archive_sha256,
        label="taxonomy archive SHA256",
    )

    compact = (
        started
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
        f"bacselect-taxonomy-{release}-"
        f"{compact}-{archive}"
    )


def build_monthly_taxonomy_snapshot(
    source: MonthlyTaxonomySourceContext,
    evidence: MonthlyTaxonomyAcquisitionEvidence,
) -> MonthlyTaxonomySnapshotBuild:
    """Validate one monthly taxonomy-snapshot evidence bundle."""

    if not isinstance(
        source,
        MonthlyTaxonomySourceContext,
    ):
        raise MonthlyTaxonomySnapshotError(
            "source context has wrong type"
        )

    if not isinstance(
        evidence,
        MonthlyTaxonomyAcquisitionEvidence,
    ):
        raise MonthlyTaxonomySnapshotError(
            "taxonomy acquisition evidence has wrong type"
        )

    release = _release_id(
        source.release_id
    )

    _nonempty_text(
        source.source_snapshot_id,
        label="source snapshot ID",
    )

    _commit(
        source.origin_git_commit
    )

    _sha256(
        source.source_snapshot_record_sha256,
        label="source snapshot record SHA256",
    )

    _sha256(
        source.source_raw_response_sha256,
        label="raw source response SHA256",
    )

    started = _timestamp(
        evidence.acquisition_started_utc,
        label="taxonomy acquisition start",
    )

    completed = _timestamp(
        evidence.acquisition_completed_utc,
        label="taxonomy acquisition completion",
    )

    if completed < started:
        raise MonthlyTaxonomySnapshotError(
            "taxonomy acquisition completion precedes start"
        )

    requested_url = _nonempty_text(
        evidence.requested_url,
        label="taxonomy requested URL",
    )

    if requested_url != TAXONOMY_URL:
        raise MonthlyTaxonomySnapshotError(
            "taxonomy requested URL changed"
        )

    final_url = _nonempty_text(
        evidence.final_url,
        label="taxonomy final URL",
    )

    if not final_url.startswith(
        "https://"
    ):
        raise MonthlyTaxonomySnapshotError(
            "taxonomy final URL must use HTTPS"
        )

    archive_sha = _sha256(
        evidence.archive_sha256,
        label="taxonomy archive SHA256",
    )

    _positive_size(
        evidence.archive_size_bytes,
        label="taxonomy archive size",
    )

    _sha256(
        evidence.nodes_sha256,
        label="nodes.dmp SHA256",
    )

    _positive_size(
        evidence.nodes_size_bytes,
        label="nodes.dmp size",
    )

    _sha256(
        evidence.merged_sha256,
        label="merged.dmp SHA256",
    )

    _positive_size(
        evidence.merged_size_bytes,
        label="merged.dmp size",
    )

    _sha256(
        evidence.delnodes_sha256,
        label="delnodes.dmp SHA256",
    )

    _positive_size(
        evidence.delnodes_size_bytes,
        label="delnodes.dmp size",
    )

    _sha256(
        evidence.acquisition_provenance_sha256,
        label="taxonomy acquisition provenance SHA256",
    )

    _sha256(
        evidence.content_manifest_sha256,
        label="taxonomy content manifest SHA256",
    )

    _sha256(
        evidence.acquisition_implementation_sha256,
        label="taxonomy acquisition implementation SHA256",
    )

    resolver_sha = _sha256(
        evidence.source_taxonomy_sha256,
        label="source_taxonomy.py SHA256",
    )

    if resolver_sha != SOURCE_TAXONOMY_SHA256:
        raise MonthlyTaxonomySnapshotError(
            "frozen taxonomy resolver identity changed"
        )

    snapshot_id = (
        taxonomy_snapshot_id_from_evidence(
            release_id=release,
            acquisition_started_utc=started,
            archive_sha256=archive_sha,
        )
    )

    return MonthlyTaxonomySnapshotBuild(
        source=source,
        evidence=evidence,
        taxonomy_snapshot_id=(
            snapshot_id
        ),
    )


def _record_from_build(
    build: MonthlyTaxonomySnapshotBuild,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        build,
        MonthlyTaxonomySnapshotBuild,
    ):
        raise MonthlyTaxonomySnapshotError(
            "taxonomy snapshot build has wrong type"
        )

    source = build.source
    evidence = build.evidence

    expected_snapshot_id = (
        taxonomy_snapshot_id_from_evidence(
            release_id=(
                source.release_id
            ),
            acquisition_started_utc=(
                evidence
                .acquisition_started_utc
            ),
            archive_sha256=(
                evidence.archive_sha256
            ),
        )
    )

    if (
        build.taxonomy_snapshot_id
        != expected_snapshot_id
    ):
        raise MonthlyTaxonomySnapshotError(
            "taxonomy snapshot ID changed after validation"
        )

    return {
        "schema_version":
            SCHEMA_VERSION,
        "status":
            STATUS,
        "release_id":
            source.release_id,
        "source_snapshot_id":
            source.source_snapshot_id,
        "origin_git_commit":
            source.origin_git_commit,
        "source_snapshot_record_sha256":
            source.source_snapshot_record_sha256,
        "source_raw_response_sha256":
            source.source_raw_response_sha256,
        "taxonomy_snapshot_id":
            build.taxonomy_snapshot_id,
        "taxonomy_acquisition_started_utc":
            evidence.acquisition_started_utc,
        "taxonomy_acquisition_completed_utc":
            evidence.acquisition_completed_utc,
        "taxonomy_requested_url":
            evidence.requested_url,
        "taxonomy_final_url":
            evidence.final_url,
        "taxonomy_archive_sha256":
            evidence.archive_sha256,
        "taxonomy_archive_size_bytes":
            evidence.archive_size_bytes,
        "taxonomy_nodes_sha256":
            evidence.nodes_sha256,
        "taxonomy_nodes_size_bytes":
            evidence.nodes_size_bytes,
        "taxonomy_merged_sha256":
            evidence.merged_sha256,
        "taxonomy_merged_size_bytes":
            evidence.merged_size_bytes,
        "taxonomy_delnodes_sha256":
            evidence.delnodes_sha256,
        "taxonomy_delnodes_size_bytes":
            evidence.delnodes_size_bytes,
        "taxonomy_acquisition_provenance_sha256":
            evidence.acquisition_provenance_sha256,
        "taxonomy_content_manifest_sha256":
            evidence.content_manifest_sha256,
        "taxonomy_acquisition_implementation_sha256":
            evidence.acquisition_implementation_sha256,
        "source_taxonomy_sha256":
            evidence.source_taxonomy_sha256,
        "taxonomy_resolution_performed":
            False,
        "structural_features_calculated":
            False,
        "selector_outcomes_calculated":
            False,
    }


def serialize_monthly_taxonomy_snapshot_record(
    build: MonthlyTaxonomySnapshotBuild,
) -> bytes:
    """Serialize one deterministic monthly Stage 7 record."""

    return _canonical_json(
        _record_from_build(
            build
        )
    )


def audit_monthly_taxonomy_snapshot_record(
    payload: bytes,
    *,
    source_snapshot_record_payload: bytes,
    expected_source_snapshot_record_sha256: str,
    origin_git_commit: str,
) -> dict[
    str,
    object,
]:
    """Reconstruct and audit a serialized monthly Stage 7 record."""

    if not isinstance(
        payload,
        bytes,
    ):
        raise MonthlyTaxonomySnapshotError(
            "taxonomy snapshot record must be bytes"
        )

    try:
        record = json.loads(
            payload
        )
    except json.JSONDecodeError as exc:
        raise MonthlyTaxonomySnapshotError(
            "taxonomy snapshot record is invalid JSON"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise MonthlyTaxonomySnapshotError(
            "taxonomy snapshot record must be a JSON object"
        )

    if set(
        record
    ) != RECORD_FIELDS:
        raise MonthlyTaxonomySnapshotError(
            "taxonomy snapshot record schema changed"
        )

    if record[
        "schema_version"
    ] != SCHEMA_VERSION:
        raise MonthlyTaxonomySnapshotError(
            "taxonomy snapshot schema changed"
        )

    if record[
        "status"
    ] != STATUS:
        raise MonthlyTaxonomySnapshotError(
            "taxonomy snapshot status changed"
        )

    for field in (
        "taxonomy_resolution_performed",
        "structural_features_calculated",
        "selector_outcomes_calculated",
    ):
        if record[
            field
        ] is not False:
            raise MonthlyTaxonomySnapshotError(
                f"{field} must remain false at Stage 7"
            )

    source = (
        build_monthly_taxonomy_source_context(
            source_snapshot_record_payload,
            expected_source_snapshot_record_sha256=(
                expected_source_snapshot_record_sha256
            ),
            origin_git_commit=(
                origin_git_commit
            ),
        )
    )

    evidence = (
        MonthlyTaxonomyAcquisitionEvidence(
            acquisition_started_utc=(
                record[
                    "taxonomy_acquisition_started_utc"
                ]
            ),
            acquisition_completed_utc=(
                record[
                    "taxonomy_acquisition_completed_utc"
                ]
            ),
            requested_url=(
                record[
                    "taxonomy_requested_url"
                ]
            ),
            final_url=(
                record[
                    "taxonomy_final_url"
                ]
            ),
            archive_sha256=(
                record[
                    "taxonomy_archive_sha256"
                ]
            ),
            archive_size_bytes=(
                record[
                    "taxonomy_archive_size_bytes"
                ]
            ),
            nodes_sha256=(
                record[
                    "taxonomy_nodes_sha256"
                ]
            ),
            nodes_size_bytes=(
                record[
                    "taxonomy_nodes_size_bytes"
                ]
            ),
            merged_sha256=(
                record[
                    "taxonomy_merged_sha256"
                ]
            ),
            merged_size_bytes=(
                record[
                    "taxonomy_merged_size_bytes"
                ]
            ),
            delnodes_sha256=(
                record[
                    "taxonomy_delnodes_sha256"
                ]
            ),
            delnodes_size_bytes=(
                record[
                    "taxonomy_delnodes_size_bytes"
                ]
            ),
            acquisition_provenance_sha256=(
                record[
                    "taxonomy_acquisition_provenance_sha256"
                ]
            ),
            content_manifest_sha256=(
                record[
                    "taxonomy_content_manifest_sha256"
                ]
            ),
            acquisition_implementation_sha256=(
                record[
                    "taxonomy_acquisition_implementation_sha256"
                ]
            ),
            source_taxonomy_sha256=(
                record[
                    "source_taxonomy_sha256"
                ]
            ),
        )
    )

    build = (
        build_monthly_taxonomy_snapshot(
            source,
            evidence,
        )
    )

    expected = (
        serialize_monthly_taxonomy_snapshot_record(
            build
        )
    )

    if payload != expected:
        raise MonthlyTaxonomySnapshotError(
            "taxonomy snapshot record differs from reconstructed contract"
        )

    return record
