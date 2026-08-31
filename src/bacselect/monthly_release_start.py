"""Pure deterministic monthly BacSelect release-start/source-snapshot primitives."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


RELEASE_START_SCHEMA_VERSION = (
    "bacselect-monthly-release-start-v1"
)

SOURCE_SNAPSHOT_SCHEMA_VERSION = (
    "bacselect-monthly-source-snapshot-v1"
)

RELEASE_START_STATUS = (
    "MONTHLY_SOURCE_SNAPSHOT_NOT_YET_ACQUIRED"
)

SOURCE_SNAPSHOT_STATUS = (
    "MONTHLY_SOURCE_SNAPSHOT_ACQUIRED"
)

SELECTOR = "OPS"
SELECTOR_VERSION = "1.0.0"
ARCHITECTURE_SCHEMA_VERSION = 1

RETRIEVAL_INTERFACE = "NCBI Datasets"

SOURCE_QUERY_SPECIFICATION: Mapping[str, Any] = {
    "accession_prefix":
        "GCA_",
    "assembly_level":
        "Complete Genome",
    "assembly_source":
        "GenBank",
    "assembly_status_required":
        "current",
    "assembly_version":
        "current",
    "exclude_mags":
        True,
    "exclude_multi_isolate":
        True,
    "taxon":
        "Bacteria",
}

RELEASE_START_KEYS = frozenset(
    {
        "architecture_schema_version",
        "expected_git_commit",
        "ncbi_datasets_environment_sha256",
        "ncbi_datasets_version",
        "release_id",
        "schema_version",
        "selector",
        "selector_version",
        "snapshot_start_utc",
        "source_query_specification",
        "status",
    }
)

SOURCE_SNAPSHOT_KEYS = frozenset(
    {
        "architecture_schema_version",
        "expected_git_commit",
        "ncbi_datasets_environment_sha256",
        "ncbi_datasets_version",
        "raw_response_bytes",
        "raw_response_sha256",
        "release_id",
        "release_start_checkpoint_sha256",
        "schema_version",
        "selector",
        "selector_version",
        "snapshot_start_utc",
        "source_query_command",
        "source_query_completed_utc",
        "source_query_specification",
        "source_query_started_utc",
        "source_snapshot_id",
        "status",
    }
)

FORBIDDEN_HISTORICAL_BINDINGS = (
    "snapshot-20260825T132821Z",
    (
        "final-acquisition-manifests/"
        "a8f045506ac4a3f17034cd9170867995a87eb894/"
        "fresh-download-manifest.tsv"
    ),
    "external-decision-holdout",
    "stage7-selector-resolution-production",
    "stage7-selector-resolution-rebuild",
)

_UTC_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}"
    r"T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)

_RELEASE_RE = re.compile(
    r"^[0-9]{4}\.[0-9]{2}$"
)

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

_GIT_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)


class MonthlyReleaseStartError(ValueError):
    """Raised when the frozen monthly release-start contract is violated."""


def sha256_bytes(
    payload: bytes,
) -> str:
    """Return lowercase SHA256 for exact bytes."""
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "payload must be bytes"
        )

    return hashlib.sha256(
        payload
    ).hexdigest()


def validate_sha256(
    value: str,
    *,
    label: str,
) -> str:
    """Validate one lowercase SHA256 string."""
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
        raise MonthlyReleaseStartError(
            f"{label} must be a lowercase SHA256"
        )

    return value


def validate_git_commit(
    value: str,
    *,
    label: str,
) -> str:
    """Validate one exact lowercase 40-character Git commit."""
    if (
        not isinstance(
            value,
            str,
        )
        or _GIT_COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyReleaseStartError(
            f"{label} must be a lowercase 40-character Git commit"
        )

    return value


def validate_plain_text_identity(
    value: str,
    *,
    label: str,
) -> str:
    """Validate a non-empty one-line textual identity."""
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value != value.strip()
        or "\n" in value
        or "\r" in value
        or "\t" in value
    ):
        raise MonthlyReleaseStartError(
            f"{label} must be a non-empty single-line string"
        )

    require_no_historical_binding(
        value,
        label=label,
    )

    return value


def require_no_historical_binding(
    value: str,
    *,
    label: str,
) -> None:
    """Reject known selector-validation inputs from monthly production."""
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{label} must be text"
        )

    for token in FORBIDDEN_HISTORICAL_BINDINGS:
        if token in value:
            raise MonthlyReleaseStartError(
                f"{label} contains historical validation binding"
            )


def parse_utc_timestamp(
    value: str,
    *,
    label: str,
) -> datetime:
    """Parse one canonical whole-second UTC timestamp."""
    if (
        not isinstance(
            value,
            str,
        )
        or _UTC_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyReleaseStartError(
            f"{label} must use YYYY-MM-DDTHH:MM:SSZ"
        )

    try:
        parsed = datetime.strptime(
            value,
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise MonthlyReleaseStartError(
            f"{label} is not a valid UTC timestamp"
        ) from None

    return parsed


def derive_release_id(
    snapshot_start_utc: str,
) -> str:
    """Derive YYYY.MM, requiring the canonical source snapshot to start day 01."""
    started = parse_utc_timestamp(
        snapshot_start_utc,
        label="snapshot start UTC",
    )

    if started.day != 1:
        raise MonthlyReleaseStartError(
            "canonical monthly source snapshot must start on UTC day 01"
        )

    return started.strftime(
        "%Y.%m"
    )


def source_snapshot_id_from_start(
    snapshot_start_utc: str,
) -> str:
    """Derive deterministic monthly source-snapshot identity."""
    started = parse_utc_timestamp(
        snapshot_start_utc,
        label="snapshot start UTC",
    )

    release_id = derive_release_id(
        snapshot_start_utc
    )

    compact = started.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    return (
        f"bacselect-source-{release_id}-{compact}"
    )


def validate_release_id(
    value: str,
) -> str:
    """Validate YYYY.MM syntax only."""
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
        raise MonthlyReleaseStartError(
            "release identifier must use YYYY.MM"
        )

    month = int(
        value[
            5:
        ]
    )

    if not (
        1
        <= month
        <= 12
    ):
        raise MonthlyReleaseStartError(
            "release identifier contains invalid month"
        )

    return value


def source_query_specification() -> dict[str, Any]:
    """Return a mutable copy of the exact frozen logical source query."""
    return dict(
        SOURCE_QUERY_SPECIFICATION
    )


def audit_source_query_specification(
    value: Mapping[str, Any],
) -> None:
    """Require exact source-universe query semantics."""
    if not isinstance(
        value,
        Mapping,
    ):
        raise MonthlyReleaseStartError(
            "source query specification must be a mapping"
        )

    if dict(
        value
    ) != dict(
        SOURCE_QUERY_SPECIFICATION
    ):
        raise MonthlyReleaseStartError(
            "source query specification changed"
        )


def canonical_json_bytes(
    payload: Mapping[str, Any],
) -> bytes:
    """Serialize canonical deterministic JSON."""
    if not isinstance(
        payload,
        Mapping,
    ):
        raise TypeError(
            "JSON payload must be a mapping"
        )

    return (
        json.dumps(
            dict(
                payload
            ),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def _parse_canonical_json(
    payload: bytes,
    *,
    label: str,
) -> dict[str, Any]:
    """Parse UTF-8 JSON and require exact canonical serialization."""
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
    except UnicodeDecodeError:
        raise MonthlyReleaseStartError(
            f"{label} is not valid UTF-8"
        ) from None

    if (
        not text.endswith(
            "\n"
        )
        or text.endswith(
            "\n\n"
        )
    ):
        raise MonthlyReleaseStartError(
            f"{label} must end with exactly one final newline"
        )

    require_no_historical_binding(
        text,
        label=label,
    )

    try:
        value = json.loads(
            text
        )
    except json.JSONDecodeError:
        raise MonthlyReleaseStartError(
            f"{label} is not valid JSON"
        ) from None

    if not isinstance(
        value,
        dict,
    ):
        raise MonthlyReleaseStartError(
            f"{label} must contain a JSON object"
        )

    if canonical_json_bytes(
        value
    ) != payload:
        raise MonthlyReleaseStartError(
            f"{label} is not canonically serialized"
        )

    return value


def build_release_start_payload(
    *,
    snapshot_start_utc: str,
    expected_git_commit: str,
    ncbi_datasets_version: str,
    ncbi_datasets_environment_sha256: str,
) -> dict[str, Any]:
    """Build the immutable pre-query monthly release-start checkpoint."""
    release_id = derive_release_id(
        snapshot_start_utc
    )

    commit = validate_git_commit(
        expected_git_commit,
        label="expected Git commit",
    )

    datasets_version = validate_plain_text_identity(
        ncbi_datasets_version,
        label="NCBI Datasets version",
    )

    environment_sha = validate_sha256(
        ncbi_datasets_environment_sha256,
        label="NCBI Datasets environment SHA256",
    )

    payload = {
        "architecture_schema_version":
            ARCHITECTURE_SCHEMA_VERSION,
        "expected_git_commit":
            commit,
        "ncbi_datasets_environment_sha256":
            environment_sha,
        "ncbi_datasets_version":
            datasets_version,
        "release_id":
            release_id,
        "schema_version":
            RELEASE_START_SCHEMA_VERSION,
        "selector":
            SELECTOR,
        "selector_version":
            SELECTOR_VERSION,
        "snapshot_start_utc":
            snapshot_start_utc,
        "source_query_specification":
            source_query_specification(),
        "status":
            RELEASE_START_STATUS,
    }

    return payload


def serialize_release_start_checkpoint(
    *,
    snapshot_start_utc: str,
    expected_git_commit: str,
    ncbi_datasets_version: str,
    ncbi_datasets_environment_sha256: str,
) -> bytes:
    """Serialize the immutable pre-query release-start checkpoint."""
    return canonical_json_bytes(
        build_release_start_payload(
            snapshot_start_utc=snapshot_start_utc,
            expected_git_commit=expected_git_commit,
            ncbi_datasets_version=ncbi_datasets_version,
            ncbi_datasets_environment_sha256=(
                ncbi_datasets_environment_sha256
            ),
        )
    )


def audit_release_start_checkpoint(
    payload: bytes,
    *,
    expected_git_commit: str | None = None,
) -> dict[str, Any]:
    """Audit exact release-start checkpoint semantics."""
    record = _parse_canonical_json(
        payload,
        label="release-start checkpoint",
    )

    if set(
        record
    ) != RELEASE_START_KEYS:
        raise MonthlyReleaseStartError(
            "release-start checkpoint key set changed"
        )

    if record.get(
        "schema_version"
    ) != RELEASE_START_SCHEMA_VERSION:
        raise MonthlyReleaseStartError(
            "release-start schema version changed"
        )

    if record.get(
        "status"
    ) != RELEASE_START_STATUS:
        raise MonthlyReleaseStartError(
            "release-start status changed"
        )

    if record.get(
        "selector"
    ) != SELECTOR:
        raise MonthlyReleaseStartError(
            "monthly selector must be exactly OPS"
        )

    if record.get(
        "selector_version"
    ) != SELECTOR_VERSION:
        raise MonthlyReleaseStartError(
            "selector version changed"
        )

    if record.get(
        "architecture_schema_version"
    ) != ARCHITECTURE_SCHEMA_VERSION:
        raise MonthlyReleaseStartError(
            "architecture schema version changed"
        )

    derived = derive_release_id(
        record.get(
            "snapshot_start_utc"
        )
    )

    if record.get(
        "release_id"
    ) != derived:
        raise MonthlyReleaseStartError(
            "release identifier does not match snapshot-start UTC"
        )

    validate_release_id(
        record[
            "release_id"
        ]
    )

    commit = validate_git_commit(
        record.get(
            "expected_git_commit"
        ),
        label="release-start expected Git commit",
    )

    if (
        expected_git_commit is not None
        and commit
        != validate_git_commit(
            expected_git_commit,
            label="expected Git commit",
        )
    ):
        raise MonthlyReleaseStartError(
            "release-start expected Git commit mismatch"
        )

    validate_plain_text_identity(
        record.get(
            "ncbi_datasets_version"
        ),
        label="release-start NCBI Datasets version",
    )

    validate_sha256(
        record.get(
            "ncbi_datasets_environment_sha256"
        ),
        label="release-start NCBI Datasets environment SHA256",
    )

    audit_source_query_specification(
        record.get(
            "source_query_specification"
        )
    )

    return record


def validate_query_command(
    command: Sequence[str],
) -> tuple[str, ...]:
    """Validate an explicitly recorded external source-query command."""
    if isinstance(
        command,
        (
            str,
            bytes,
        ),
    ):
        raise TypeError(
            "source query command must be a sequence of argument strings"
        )

    values = tuple(
        command
    )

    if not values:
        raise MonthlyReleaseStartError(
            "source query command must not be empty"
        )

    validated: list[str] = []

    for argument in values:
        validated.append(
            validate_plain_text_identity(
                argument,
                label="source query command argument",
            )
        )

    return tuple(
        validated
    )


def build_source_snapshot_payload(
    *,
    release_start_checkpoint: bytes,
    source_query_started_utc: str,
    source_query_completed_utc: str,
    source_query_command: Sequence[str],
    raw_response: bytes,
) -> dict[str, Any]:
    """Build immutable source-snapshot provenance after the raw query completes."""
    start_record = audit_release_start_checkpoint(
        release_start_checkpoint
    )

    query_started = parse_utc_timestamp(
        source_query_started_utc,
        label="source query started UTC",
    )

    query_completed = parse_utc_timestamp(
        source_query_completed_utc,
        label="source query completed UTC",
    )

    snapshot_started = parse_utc_timestamp(
        start_record[
            "snapshot_start_utc"
        ],
        label="snapshot start UTC",
    )

    if query_started < snapshot_started:
        raise MonthlyReleaseStartError(
            "source query cannot start before release-start checkpoint time"
        )

    if query_completed < query_started:
        raise MonthlyReleaseStartError(
            "source query completion cannot precede query start"
        )

    command = validate_query_command(
        source_query_command
    )

    if not isinstance(
        raw_response,
        bytes,
    ):
        raise TypeError(
            "raw source response must be bytes"
        )

    if not raw_response:
        raise MonthlyReleaseStartError(
            "raw source response must not be empty"
        )

    return {
        "architecture_schema_version":
            ARCHITECTURE_SCHEMA_VERSION,
        "expected_git_commit":
            start_record[
                "expected_git_commit"
            ],
        "ncbi_datasets_environment_sha256":
            start_record[
                "ncbi_datasets_environment_sha256"
            ],
        "ncbi_datasets_version":
            start_record[
                "ncbi_datasets_version"
            ],
        "raw_response_bytes":
            len(
                raw_response
            ),
        "raw_response_sha256":
            sha256_bytes(
                raw_response
            ),
        "release_id":
            start_record[
                "release_id"
            ],
        "release_start_checkpoint_sha256":
            sha256_bytes(
                release_start_checkpoint
            ),
        "schema_version":
            SOURCE_SNAPSHOT_SCHEMA_VERSION,
        "selector":
            SELECTOR,
        "selector_version":
            SELECTOR_VERSION,
        "snapshot_start_utc":
            start_record[
                "snapshot_start_utc"
            ],
        "source_query_command":
            list(
                command
            ),
        "source_query_completed_utc":
            source_query_completed_utc,
        "source_query_specification":
            source_query_specification(),
        "source_query_started_utc":
            source_query_started_utc,
        "source_snapshot_id":
            source_snapshot_id_from_start(
                start_record[
                    "snapshot_start_utc"
                ]
            ),
        "status":
            SOURCE_SNAPSHOT_STATUS,
    }


def serialize_source_snapshot_record(
    *,
    release_start_checkpoint: bytes,
    source_query_started_utc: str,
    source_query_completed_utc: str,
    source_query_command: Sequence[str],
    raw_response: bytes,
) -> bytes:
    """Serialize immutable source-snapshot provenance."""
    return canonical_json_bytes(
        build_source_snapshot_payload(
            release_start_checkpoint=release_start_checkpoint,
            source_query_started_utc=source_query_started_utc,
            source_query_completed_utc=source_query_completed_utc,
            source_query_command=source_query_command,
            raw_response=raw_response,
        )
    )


def audit_source_snapshot_record(
    payload: bytes,
    *,
    release_start_checkpoint: bytes,
    raw_response: bytes | None = None,
) -> dict[str, Any]:
    """Audit exact source-snapshot provenance against its pre-query checkpoint."""
    record = _parse_canonical_json(
        payload,
        label="source-snapshot record",
    )

    if set(
        record
    ) != SOURCE_SNAPSHOT_KEYS:
        raise MonthlyReleaseStartError(
            "source-snapshot record key set changed"
        )

    if record.get(
        "schema_version"
    ) != SOURCE_SNAPSHOT_SCHEMA_VERSION:
        raise MonthlyReleaseStartError(
            "source-snapshot schema version changed"
        )

    if record.get(
        "status"
    ) != SOURCE_SNAPSHOT_STATUS:
        raise MonthlyReleaseStartError(
            "source-snapshot status changed"
        )

    if record.get(
        "selector"
    ) != SELECTOR:
        raise MonthlyReleaseStartError(
            "source-snapshot selector changed"
        )

    if record.get(
        "selector_version"
    ) != SELECTOR_VERSION:
        raise MonthlyReleaseStartError(
            "source-snapshot selector version changed"
        )

    if record.get(
        "architecture_schema_version"
    ) != ARCHITECTURE_SCHEMA_VERSION:
        raise MonthlyReleaseStartError(
            "source-snapshot architecture schema changed"
        )

    start_record = audit_release_start_checkpoint(
        release_start_checkpoint
    )

    if record.get(
        "release_start_checkpoint_sha256"
    ) != sha256_bytes(
        release_start_checkpoint
    ):
        raise MonthlyReleaseStartError(
            "source-snapshot release-start checkpoint fingerprint changed"
        )

    for key in (
        "expected_git_commit",
        "ncbi_datasets_environment_sha256",
        "ncbi_datasets_version",
        "release_id",
        "snapshot_start_utc",
    ):
        if record.get(
            key
        ) != start_record.get(
            key
        ):
            raise MonthlyReleaseStartError(
                f"source-snapshot inherited binding changed: {key}"
            )

    audit_source_query_specification(
        record.get(
            "source_query_specification"
        )
    )

    query_started = parse_utc_timestamp(
        record.get(
            "source_query_started_utc"
        ),
        label="source query started UTC",
    )

    query_completed = parse_utc_timestamp(
        record.get(
            "source_query_completed_utc"
        ),
        label="source query completed UTC",
    )

    snapshot_started = parse_utc_timestamp(
        record.get(
            "snapshot_start_utc"
        ),
        label="snapshot start UTC",
    )

    if query_started < snapshot_started:
        raise MonthlyReleaseStartError(
            "source query began before snapshot start"
        )

    if query_completed < query_started:
        raise MonthlyReleaseStartError(
            "source query completed before it started"
        )

    validate_query_command(
        record.get(
            "source_query_command"
        )
    )

    expected_snapshot_id = source_snapshot_id_from_start(
        record[
            "snapshot_start_utc"
        ]
    )

    if record.get(
        "source_snapshot_id"
    ) != expected_snapshot_id:
        raise MonthlyReleaseStartError(
            "source snapshot identifier changed"
        )

    validate_sha256(
        record.get(
            "raw_response_sha256"
        ),
        label="raw source response SHA256",
    )

    observed_bytes = record.get(
        "raw_response_bytes"
    )

    if (
        isinstance(
            observed_bytes,
            bool,
        )
        or not isinstance(
            observed_bytes,
            int,
        )
        or observed_bytes <= 0
    ):
        raise MonthlyReleaseStartError(
            "raw source response byte count must be a positive integer"
        )

    if raw_response is not None:
        if not isinstance(
            raw_response,
            bytes,
        ):
            raise TypeError(
                "raw source response must be bytes"
            )

        if not raw_response:
            raise MonthlyReleaseStartError(
                "raw source response must not be empty"
            )

        if record[
            "raw_response_sha256"
        ] != sha256_bytes(
            raw_response
        ):
            raise MonthlyReleaseStartError(
                "raw source response SHA256 mismatch"
            )

        if record[
            "raw_response_bytes"
        ] != len(
            raw_response
        ):
            raise MonthlyReleaseStartError(
                "raw source response byte count mismatch"
            )

    return record


def require_current_assembly_status(
    value: str,
) -> str:
    """Require the returned monthly assembly status to be exactly current."""
    if value != "current":
        raise MonthlyReleaseStartError(
            "assembly status must be exactly current"
        )

    return value


def validate_canonical_gca(
    value: str,
) -> str:
    """Validate one canonical GenBank assembly accession.version."""
    if (
        not isinstance(
            value,
            str,
        )
        or _GCA_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyReleaseStartError(
            "assembly accession must be canonical GCA accession.version"
        )

    return value
