"""Pure monthly BacSelect metadata-eligibility evidence contract."""

from __future__ import annotations

from collections.abc import (
    Mapping,
    Sequence,
)
import hashlib
import json
import re
from typing import Any

from bacselect import source_eligibility
from bacselect.source_eligibility import (
    EXCLUDE,
    RETAIN,
    WITHHOLD,
    MetadataAssessment,
)


MONTHLY_METADATA_ASSESSMENT_SCHEMA = (
    "bacselect-monthly-metadata-assessment-v1"
)

MONTHLY_METADATA_SUMMARY_SCHEMA = (
    "bacselect-monthly-metadata-summary-v1"
)

MONTHLY_METADATA_RECORD_SCHEMA = (
    "bacselect-monthly-metadata-eligibility-record-v1"
)

MONTHLY_METADATA_STATUS = (
    "METADATA_ELIGIBILITY_COMPLETE"
)

LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

ALLOWED_DECISIONS = frozenset(
    {
        RETAIN,
        EXCLUDE,
        WITHHOLD,
    }
)


class MonthlyMetadataEligibilityError(
    ValueError
):
    """Raised when monthly metadata evidence fails closed."""


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
        raise MonthlyMetadataEligibilityError(
            f"{label} must be lowercase SHA256"
        )

    return value


def _identity(
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
        or value != value.strip()
        or any(
            character.isspace()
            for character in value
        )
    ):
        raise MonthlyMetadataEligibilityError(
            f"{label} must be normalized non-whitespace text"
        )

    return value


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
            dict(
                payload
            ),
            indent=2,
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )


def _canonical_json_line(
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
            "canonical JSONL row must be a mapping"
        )

    return (
        json.dumps(
            dict(
                payload
            ),
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            allow_nan=False,
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )


def _parse_raw_records(
    raw_response: bytes,
) -> tuple[
    Mapping[
        str,
        object,
    ],
    ...,
]:
    if not isinstance(
        raw_response,
        bytes,
    ):
        raise TypeError(
            "raw source response must be bytes"
        )

    if not raw_response:
        raise MonthlyMetadataEligibilityError(
            "raw source response is empty"
        )

    try:
        text = raw_response.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise MonthlyMetadataEligibilityError(
            "raw source response is not UTF-8"
        ) from exc

    rows = []

    for line_number, line in enumerate(
        text.splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            value = json.loads(
                line
            )
        except json.JSONDecodeError as exc:
            raise MonthlyMetadataEligibilityError(
                f"raw source response line {line_number} is invalid JSON"
            ) from exc

        if not isinstance(
            value,
            Mapping,
        ):
            raise MonthlyMetadataEligibilityError(
                f"raw source response line {line_number} is not an object"
            )

        rows.append(
            value
        )

    if not rows:
        raise MonthlyMetadataEligibilityError(
            "raw source response contains no JSON objects"
        )

    return tuple(
        rows
    )


def _audit_assessment(
    value: MetadataAssessment,
) -> MetadataAssessment:
    if not isinstance(
        value,
        MetadataAssessment,
    ):
        raise TypeError(
            "metadata assessment has wrong type"
        )

    accession = value.accession

    if not isinstance(
        accession,
        str,
    ):
        raise MonthlyMetadataEligibilityError(
            "metadata assessment accession must be text"
        )

    biosample = value.biosample

    if (
        biosample is not None
        and (
            not isinstance(
                biosample,
                str,
            )
            or source_eligibility.BIOSAMPLE_RE.fullmatch(
                biosample
            )
            is None
        )
    ):
        raise MonthlyMetadataEligibilityError(
            "metadata assessment BioSample is invalid"
        )

    if value.decision not in ALLOWED_DECISIONS:
        raise MonthlyMetadataEligibilityError(
            "metadata assessment decision is invalid"
        )

    if value.decision == RETAIN:
        if (
            source_eligibility.CANONICAL_GCA_RE.fullmatch(
                accession
            )
            is None
            or biosample is None
        ):
            raise MonthlyMetadataEligibilityError(
                "metadata-retained assessment lacks canonical identity"
            )

    reasons = value.reasons

    if (
        not isinstance(
            reasons,
            tuple,
        )
        or not all(
            isinstance(
                reason,
                str,
            )
            for reason in reasons
        )
        or reasons
        != tuple(
            sorted(
                set(
                    reasons
                )
            )
        )
    ):
        raise MonthlyMetadataEligibilityError(
            "metadata assessment reasons are not canonical"
        )

    warnings = (
        value.normalized_warnings
    )

    if (
        not isinstance(
            warnings,
            tuple,
        )
        or not all(
            isinstance(
                warning,
                str,
            )
            for warning in warnings
        )
    ):
        raise MonthlyMetadataEligibilityError(
            "metadata assessment warnings are invalid"
        )

    for warning in warnings:
        try:
            normalized = (
                source_eligibility.normalize_warning(
                    warning
                )
            )
        except ValueError as exc:
            raise MonthlyMetadataEligibilityError(
                "metadata assessment warning is invalid"
            ) from exc

        if normalized != warning:
            raise MonthlyMetadataEligibilityError(
                "metadata assessment warning is not normalized"
            )

    return value


def assess_monthly_source_metadata(
    raw_response: bytes,
) -> tuple[
    MetadataAssessment,
    ...,
]:
    """Run the frozen metadata parser on exact Stage 1 raw bytes."""

    records = _parse_raw_records(
        raw_response
    )

    try:
        assessments = (
            source_eligibility.assess_records(
                records
            )
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlyMetadataEligibilityError(
            "frozen source-metadata eligibility assessment failed"
        ) from exc

    checked = tuple(
        _audit_assessment(
            value
        )
        for value in assessments
    )

    return tuple(
        sorted(
            checked,
            key=lambda value:
                value.accession,
        )
    )


def _assessment_record(
    value: MetadataAssessment,
) -> dict[
    str,
    object,
]:
    assessment = _audit_assessment(
        value
    )

    return {
        "accession":
            assessment.accession,
        "biosample":
            assessment.biosample,
        "decision":
            assessment.decision,
        "normalized_warnings":
            list(
                assessment.normalized_warnings
            ),
        "reasons":
            list(
                assessment.reasons
            ),
        "schema_version":
            MONTHLY_METADATA_ASSESSMENT_SCHEMA,
    }


def serialize_metadata_assessments(
    assessments: Sequence[
        MetadataAssessment
    ],
) -> bytes:
    """Serialize sorted canonical monthly assessment JSONL."""

    if (
        isinstance(
            assessments,
            (
                str,
                bytes,
            ),
        )
        or not isinstance(
            assessments,
            Sequence,
        )
    ):
        raise TypeError(
            "metadata assessments must be a sequence"
        )

    checked = tuple(
        _audit_assessment(
            value
        )
        for value in assessments
    )

    if not checked:
        raise MonthlyMetadataEligibilityError(
            "metadata assessment set is empty"
        )

    ordered = tuple(
        sorted(
            checked,
            key=lambda value:
                value.accession,
        )
    )

    accessions = tuple(
        value.accession
        for value in ordered
    )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlyMetadataEligibilityError(
            "metadata assessment accessions are duplicated"
        )

    return b"".join(
        _canonical_json_line(
            _assessment_record(
                value
            )
        )
        for value in ordered
    )


def audit_metadata_assessments(
    payload: bytes,
) -> tuple[
    MetadataAssessment,
    ...,
]:
    """Audit exact canonical monthly assessment JSONL."""

    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "metadata assessment payload must be bytes"
        )

    if (
        not payload
        or not payload.endswith(
            b"\n"
        )
    ):
        raise MonthlyMetadataEligibilityError(
            "metadata assessment JSONL must be nonempty and newline terminated"
        )

    try:
        text = payload.decode(
            "ascii"
        )
    except UnicodeDecodeError as exc:
        raise MonthlyMetadataEligibilityError(
            "metadata assessment JSONL must be ASCII"
        ) from exc

    assessments = []

    for line_number, line in enumerate(
        text.splitlines(),
        start=1,
    ):
        if not line:
            raise MonthlyMetadataEligibilityError(
                "metadata assessment JSONL contains a blank line"
            )

        try:
            record = json.loads(
                line
            )
        except json.JSONDecodeError as exc:
            raise MonthlyMetadataEligibilityError(
                f"metadata assessment line {line_number} is invalid JSON"
            ) from exc

        if (
            not isinstance(
                record,
                dict,
            )
            or set(
                record
            )
            != {
                "accession",
                "biosample",
                "decision",
                "normalized_warnings",
                "reasons",
                "schema_version",
            }
        ):
            raise MonthlyMetadataEligibilityError(
                "metadata assessment row schema changed"
            )

        if record[
            "schema_version"
        ] != MONTHLY_METADATA_ASSESSMENT_SCHEMA:
            raise MonthlyMetadataEligibilityError(
                "metadata assessment schema version changed"
            )

        if (
            _canonical_json_line(
                record
            )
            != (
                line
                + "\n"
            ).encode(
                "ascii"
            )
        ):
            raise MonthlyMetadataEligibilityError(
                "metadata assessment row is not canonical JSON"
            )

        reasons = record[
            "reasons"
        ]

        warnings = record[
            "normalized_warnings"
        ]

        if (
            not isinstance(
                reasons,
                list,
            )
            or not isinstance(
                warnings,
                list,
            )
        ):
            raise MonthlyMetadataEligibilityError(
                "metadata assessment list fields changed"
            )

        assessment = MetadataAssessment(
            accession=record[
                "accession"
            ],
            biosample=record[
                "biosample"
            ],
            decision=record[
                "decision"
            ],
            reasons=tuple(
                reasons
            ),
            normalized_warnings=tuple(
                warnings
            ),
        )

        assessments.append(
            _audit_assessment(
                assessment
            )
        )

    ordered = tuple(
        assessments
    )

    accessions = tuple(
        value.accession
        for value in ordered
    )

    if accessions != tuple(
        sorted(
            accessions
        )
    ):
        raise MonthlyMetadataEligibilityError(
            "metadata assessment rows are not accession sorted"
        )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlyMetadataEligibilityError(
            "metadata assessment accessions are duplicated"
        )

    if serialize_metadata_assessments(
        ordered
    ) != payload:
        raise MonthlyMetadataEligibilityError(
            "metadata assessment derived identity changed"
        )

    return ordered


def build_metadata_summary(
    assessments: Sequence[
        MetadataAssessment
    ],
) -> dict[
    str,
    object,
]:
    """Build blinded canonical aggregate metadata summary."""

    checked = tuple(
        _audit_assessment(
            value
        )
        for value in assessments
    )

    summary = (
        source_eligibility.blinded_metadata_summary(
            checked
        )
    )

    return {
        "decision_counts":
            summary[
                "decision_counts"
            ],
        "reason_counts":
            summary[
                "reason_counts"
            ],
        "records":
            summary[
                "records"
            ],
        "schema_version":
            MONTHLY_METADATA_SUMMARY_SCHEMA,
        "warning_counts":
            summary[
                "warning_counts"
            ],
    }


def serialize_metadata_summary(
    assessments: Sequence[
        MetadataAssessment
    ],
) -> bytes:
    return _canonical_json_bytes(
        build_metadata_summary(
            assessments
        )
    )


def audit_metadata_summary(
    payload: bytes,
    *,
    assessments_payload: bytes,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "metadata summary must be bytes"
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
        raise MonthlyMetadataEligibilityError(
            "invalid metadata summary JSON"
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
        raise MonthlyMetadataEligibilityError(
            "metadata summary is not canonical JSON"
        )

    if set(
        record
    ) != {
        "decision_counts",
        "reason_counts",
        "records",
        "schema_version",
        "warning_counts",
    }:
        raise MonthlyMetadataEligibilityError(
            "metadata summary key set changed"
        )

    if record[
        "schema_version"
    ] != MONTHLY_METADATA_SUMMARY_SCHEMA:
        raise MonthlyMetadataEligibilityError(
            "metadata summary schema changed"
        )

    assessments = (
        audit_metadata_assessments(
            assessments_payload
        )
    )

    expected = build_metadata_summary(
        assessments
    )

    if record != expected:
        raise MonthlyMetadataEligibilityError(
            "metadata summary derived identity changed"
        )

    return record


def build_metadata_eligibility_record(
    *,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    raw_response: bytes,
    assessments_payload: bytes,
    summary_payload: bytes,
    source_eligibility_sha256: str,
) -> dict[
    str,
    object,
]:
    """Build provenance after independently reconstructing raw assessments."""

    snapshot_id = _identity(
        source_snapshot_id,
        label="source snapshot ID",
    )

    snapshot_sha = _sha256(
        source_snapshot_record_sha256,
        label="source snapshot record SHA256",
    )

    parser_sha = _sha256(
        source_eligibility_sha256,
        label="source eligibility implementation SHA256",
    )

    expected_assessments = (
        serialize_metadata_assessments(
            assess_monthly_source_metadata(
                raw_response
            )
        )
    )

    if (
        assessments_payload
        != expected_assessments
    ):
        raise MonthlyMetadataEligibilityError(
            "metadata assessments do not match exact raw source response"
        )

    assessments = (
        audit_metadata_assessments(
            assessments_payload
        )
    )

    audit_metadata_summary(
        summary_payload,
        assessments_payload=(
            assessments_payload
        ),
    )

    expected_summary = (
        serialize_metadata_summary(
            assessments
        )
    )

    if summary_payload != expected_summary:
        raise MonthlyMetadataEligibilityError(
            "metadata summary does not match exact assessments"
        )

    summary = json.loads(
        summary_payload.decode(
            "ascii"
        )
    )

    decision_counts = (
        summary[
            "decision_counts"
        ]
    )

    return {
        "assessment_count":
            len(
                assessments
            ),
        "assessments_sha256":
            hashlib.sha256(
                assessments_payload
            ).hexdigest(),
        "excluded_count":
            decision_counts.get(
                EXCLUDE,
                0,
            ),
        "raw_response_bytes":
            len(
                raw_response
            ),
        "raw_response_sha256":
            hashlib.sha256(
                raw_response
            ).hexdigest(),
        "retained_count":
            decision_counts.get(
                RETAIN,
                0,
            ),
        "schema_version":
            MONTHLY_METADATA_RECORD_SCHEMA,
        "source_eligibility_sha256":
            parser_sha,
        "source_snapshot_id":
            snapshot_id,
        "source_snapshot_record_sha256":
            snapshot_sha,
        "status":
            MONTHLY_METADATA_STATUS,
        "summary_sha256":
            hashlib.sha256(
                summary_payload
            ).hexdigest(),
        "withheld_count":
            decision_counts.get(
                WITHHOLD,
                0,
            ),
    }


def serialize_metadata_eligibility_record(
    **kwargs: Any,
) -> bytes:
    return _canonical_json_bytes(
        build_metadata_eligibility_record(
            **kwargs
        )
    )


def audit_metadata_eligibility_record(
    payload: bytes,
    *,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    raw_response: bytes,
    assessments_payload: bytes,
    summary_payload: bytes,
    source_eligibility_sha256: str,
) -> dict[
    str,
    object,
]:
    """Audit the record against all independently supplied evidence."""

    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "metadata eligibility record must be bytes"
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
        raise MonthlyMetadataEligibilityError(
            "invalid metadata eligibility record JSON"
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
        raise MonthlyMetadataEligibilityError(
            "metadata eligibility record is not canonical JSON"
        )

    expected_keys = {
        "assessment_count",
        "assessments_sha256",
        "excluded_count",
        "raw_response_bytes",
        "raw_response_sha256",
        "retained_count",
        "schema_version",
        "source_eligibility_sha256",
        "source_snapshot_id",
        "source_snapshot_record_sha256",
        "status",
        "summary_sha256",
        "withheld_count",
    }

    if set(
        record
    ) != expected_keys:
        raise MonthlyMetadataEligibilityError(
            "metadata eligibility record key set changed"
        )

    if record[
        "schema_version"
    ] != MONTHLY_METADATA_RECORD_SCHEMA:
        raise MonthlyMetadataEligibilityError(
            "metadata eligibility record schema changed"
        )

    if record[
        "status"
    ] != MONTHLY_METADATA_STATUS:
        raise MonthlyMetadataEligibilityError(
            "metadata eligibility record status changed"
        )

    rebuilt = (
        build_metadata_eligibility_record(
            source_snapshot_id=(
                source_snapshot_id
            ),
            source_snapshot_record_sha256=(
                source_snapshot_record_sha256
            ),
            raw_response=raw_response,
            assessments_payload=(
                assessments_payload
            ),
            summary_payload=(
                summary_payload
            ),
            source_eligibility_sha256=(
                source_eligibility_sha256
            ),
        )
    )

    if rebuilt != record:
        raise MonthlyMetadataEligibilityError(
            "metadata eligibility record derived identity changed"
        )

    return record
