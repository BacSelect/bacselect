"""Recovery-aware monthly sequence-acquisition completion contract v2."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Iterable
from typing import Mapping

from bacselect.monthly_sequence_acquisition_completion import (
    _parse_fresh_targets,
)
from bacselect.monthly_sequence_plan import (
    FRESH_BATCH_SIZE,
    audit_monthly_sequence_plan_record,
)
from bacselect.monthly_sequence_transport import (
    MonthlySequenceTransportError,
    batch_accession_bytes,
    batch_target_manifest_sha256,
)


MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_V2_SCHEMA = (
    "bacselect-monthly-sequence-acquisition-completion-v2"
)

MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_STATUS = (
    "SEQUENCE_ACQUISITION_COMPLETE"
)

SOURCE_CLASS_FRESH = "fresh"
SOURCE_CLASS_FRESH_RECOVERY = "fresh-recovery"

RECOVERY_CLASS_MISSING_DATASETS_GBFF = (
    "datasets_manifest_omits_requested_gbff"
)

RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION = (
    "post_snapshot_accession_supersession"
)

RECOGNIZED_RECOVERY_CLASSES = frozenset(
    {
        RECOVERY_CLASS_MISSING_DATASETS_GBFF,
        RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION,
    }
)

FRESH_PROVIDER_SUMMARY_NAME = "batch-summary.json"
RECOVERY_PROVIDER_SUMMARY_NAME = "recovery-summary.json"

FRESH_PACKAGE_MANIFEST_NAME = "package-files.tsv"
RECOVERY_PACKAGE_MANIFEST_NAME = (
    "recovery-package-files.tsv"
)

_BATCH_RE = re.compile(
    r"^batch-[0-9]{5}$"
)

_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class MonthlySequenceAcquisitionCompletionV2Error(
    RuntimeError
):
    """Raised when recovery-aware completion evidence is inconsistent."""


@dataclass(
    frozen=True,
)
class AuthoritativeCompletedBatchEvidence:
    """
    One already-audited authoritative Stage 3B provider.

    Filesystem discovery and scientific/provider revalidation happen in
    the execution wrapper. This pure contract records only deterministic,
    independently verified identities.
    """

    batch_id: str
    source_class: str
    recovery_class: str | None

    requested_accessions: int
    first_accession: str
    last_accession: str

    observed_batch_target_manifest_sha256: str
    observed_accessions_sha256: str
    observed_candidate_audit_sha256: str
    observed_component_audit_sha256: str

    provider_summary_name: str
    provider_summary_sha256: str

    package_manifest_name: str
    package_manifest_sha256: str

    package_file_count: int
    package_file_readback_count: int
    package_file_readback_sha256: str

    source_partial_name: str | None = None
    recovery_commit: str | None = None

    source_batch_sha256: str | None = None
    source_package_sha256: str | None = None
    recovery_package_sha256: str | None = None

    recovery_summary_sha256: str | None = None
    cause_evidence_sha256: str | None = None
    transport_record_sha256: str | None = None


def _fail(
    message: str,
) -> None:
    raise MonthlySequenceAcquisitionCompletionV2Error(
        message
    )


def _text(
    value: object,
    *,
    label: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        _fail(
            f"{label} must be text"
        )

    normalized = value.strip()

    if (
        not normalized
        or normalized != value
    ):
        _fail(
            f"{label} is invalid"
        )

    return normalized


def _sha256(
    value: object,
    *,
    label: str,
) -> str:
    text = _text(
        value,
        label=label,
    )

    if not _SHA256_RE.fullmatch(
        text
    ):
        _fail(
            f"{label} is not a SHA256"
        )

    return text


def _commit(
    value: object,
    *,
    label: str,
) -> str:
    text = _text(
        value,
        label=label,
    )

    if not _COMMIT_RE.fullmatch(
        text
    ):
        _fail(
            f"{label} is not a Git commit"
        )

    return text


def _batch_id(
    value: object,
) -> str:
    text = _text(
        value,
        label="batch ID",
    )

    if not _BATCH_RE.fullmatch(
        text
    ):
        _fail(
            "batch ID is invalid"
        )

    return text


def _positive_int(
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
        _fail(
            f"{label} must be a positive integer"
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
        _fail(
            f"{label} must be a nonnegative integer"
        )

    return value


def _optional_sha256(
    value: object,
    *,
    label: str,
) -> str | None:
    if value is None:
        return None

    return _sha256(
        value,
        label=label,
    )


def _optional_commit(
    value: object,
    *,
    label: str,
) -> str | None:
    if value is None:
        return None

    return _commit(
        value,
        label=label,
    )


def _optional_text(
    value: object,
    *,
    label: str,
) -> str | None:
    if value is None:
        return None

    return _text(
        value,
        label=label,
    )


def _canonical_json_bytes(
    value: object,
) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )


def _expected_batch_id(
    index: int,
) -> str:
    return (
        f"batch-{index:05d}"
    )


def _audit_source_class(
    evidence: AuthoritativeCompletedBatchEvidence,
) -> dict[
    str,
    object,
]:
    source_class = _text(
        evidence.source_class,
        label="source class",
    )

    recovery_class = (
        _optional_text(
            evidence.recovery_class,
            label="recovery class",
        )
    )

    provider_summary_name = _text(
        evidence.provider_summary_name,
        label="provider summary name",
    )

    provider_summary_sha = _sha256(
        evidence.provider_summary_sha256,
        label="provider summary SHA256",
    )

    package_manifest_name = _text(
        evidence.package_manifest_name,
        label="package manifest name",
    )

    package_manifest_sha = _sha256(
        evidence.package_manifest_sha256,
        label="package manifest SHA256",
    )

    source_partial_name = (
        _optional_text(
            evidence.source_partial_name,
            label="source partial name",
        )
    )

    recovery_commit = (
        _optional_commit(
            evidence.recovery_commit,
            label="recovery commit",
        )
    )

    source_batch_sha = (
        _optional_sha256(
            evidence.source_batch_sha256,
            label="source batch SHA256",
        )
    )

    source_package_sha = (
        _optional_sha256(
            evidence.source_package_sha256,
            label="source package SHA256",
        )
    )

    recovery_package_sha = (
        _optional_sha256(
            evidence.recovery_package_sha256,
            label="recovery package SHA256",
        )
    )

    recovery_summary_sha = (
        _optional_sha256(
            evidence.recovery_summary_sha256,
            label="recovery summary SHA256",
        )
    )

    cause_evidence_sha = (
        _optional_sha256(
            evidence.cause_evidence_sha256,
            label="cause evidence SHA256",
        )
    )

    transport_record_sha = (
        _optional_sha256(
            evidence.transport_record_sha256,
            label="transport record SHA256",
        )
    )

    recovery_values = (
        source_partial_name,
        recovery_commit,
        source_batch_sha,
        source_package_sha,
        recovery_package_sha,
        recovery_summary_sha,
        cause_evidence_sha,
        transport_record_sha,
    )

    if source_class == SOURCE_CLASS_FRESH:
        if recovery_class is not None:
            _fail(
                "fresh provider cannot carry a recovery class"
            )

        if (
            provider_summary_name
            != FRESH_PROVIDER_SUMMARY_NAME
        ):
            _fail(
                "fresh provider summary name changed"
            )

        if (
            package_manifest_name
            != FRESH_PACKAGE_MANIFEST_NAME
        ):
            _fail(
                "fresh package manifest name changed"
            )

        if any(
            value is not None
            for value in recovery_values
        ):
            _fail(
                "fresh provider carries recovery-only evidence"
            )

    elif (
        source_class
        == SOURCE_CLASS_FRESH_RECOVERY
    ):
        if (
            recovery_class
            not in RECOGNIZED_RECOVERY_CLASSES
        ):
            _fail(
                "fresh-recovery provider has unknown recovery class"
            )

        if (
            provider_summary_name
            != RECOVERY_PROVIDER_SUMMARY_NAME
        ):
            _fail(
                "fresh-recovery provider summary name changed"
            )

        if (
            package_manifest_name
            != RECOVERY_PACKAGE_MANIFEST_NAME
        ):
            _fail(
                "fresh-recovery package manifest name changed"
            )

        required = (
            (
                source_partial_name,
                "source partial name",
            ),
            (
                recovery_commit,
                "recovery commit",
            ),
            (
                source_batch_sha,
                "source batch SHA256",
            ),
            (
                source_package_sha,
                "source package SHA256",
            ),
            (
                recovery_package_sha,
                "recovery package SHA256",
            ),
            (
                recovery_summary_sha,
                "recovery summary SHA256",
            ),
            (
                cause_evidence_sha,
                "cause evidence SHA256",
            ),
        )

        for value, label in required:
            if value is None:
                _fail(
                    "fresh-recovery provider is missing "
                    f"{label}"
                )

        expected_partial = (
            evidence.batch_id
            + ".partial"
        )

        if (
            source_partial_name
            != expected_partial
        ):
            _fail(
                "fresh-recovery source partial name changed"
            )

        if (
            provider_summary_sha
            != recovery_summary_sha
        ):
            _fail(
                "fresh-recovery provider summary SHA256 "
                "does not equal recovery-summary SHA256"
            )

        if (
            package_manifest_sha
            != recovery_package_sha
        ):
            _fail(
                "fresh-recovery package manifest SHA256 "
                "does not equal recovery-package SHA256"
            )

        if (
            recovery_class
            == RECOVERY_CLASS_MISSING_DATASETS_GBFF
        ):
            if transport_record_sha is not None:
                _fail(
                    "missing-Datasets-GBFF provider unexpectedly "
                    "carries a supersession transport record"
                )

        elif (
            recovery_class
            == RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION
        ):
            if transport_record_sha is None:
                _fail(
                    "post-snapshot supersession provider is missing "
                    "transport record SHA256"
                )

    else:
        _fail(
            f"unknown authoritative source class: "
            f"{source_class!r}"
        )

    return {
        "cause_evidence_sha256":
            cause_evidence_sha,
        "package_manifest_name":
            package_manifest_name,
        "package_manifest_sha256":
            package_manifest_sha,
        "provider_summary_name":
            provider_summary_name,
        "provider_summary_sha256":
            provider_summary_sha,
        "recovery_class":
            recovery_class,
        "recovery_commit":
            recovery_commit,
        "recovery_package_sha256":
            recovery_package_sha,
        "recovery_summary_sha256":
            recovery_summary_sha,
        "source_batch_sha256":
            source_batch_sha,
        "source_class":
            source_class,
        "source_package_sha256":
            source_package_sha,
        "source_partial_name":
            source_partial_name,
        "transport_record_sha256":
            transport_record_sha,
    }


def build_sequence_acquisition_completion_v2_record(
    *,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    stage2_sequence_plan_record: bytes,
    stage2_fresh_target_manifest: bytes,
    source_production_commit: str,
    completion_execution_commit: str,
    environment_explicit_sha256: str,
    batches: Iterable[
        AuthoritativeCompletedBatchEvidence
    ],
) -> dict[
    str,
    object,
]:
    """
    Build deterministic recovery-aware completion evidence.

    The input batch sequence must already come from the authoritative
    provider resolver in exact Stage 2 order.
    """

    snapshot = _text(
        source_snapshot_id,
        label="source snapshot ID",
    )

    snapshot_record_sha = _sha256(
        source_snapshot_record_sha256,
        label="source-snapshot-record SHA256",
    )

    source_commit = _commit(
        source_production_commit,
        label="source production commit",
    )

    completion_commit = _commit(
        completion_execution_commit,
        label="completion execution commit",
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
        raise MonthlySequenceAcquisitionCompletionV2Error(
            "Stage 2 sequence-plan provenance audit failed"
        ) from exc

    try:
        targets = _parse_fresh_targets(
            stage2_fresh_target_manifest
        )

    except Exception as exc:
        raise MonthlySequenceAcquisitionCompletionV2Error(
            "Stage 2 fresh-target manifest could not be reconstructed"
        ) from exc

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

    if (
        plan[
            "fresh_batch_size"
        ]
        != FRESH_BATCH_SIZE
    ):
        _fail(
            "Stage 2 fresh batch size changed"
        )

    if len(
        targets
    ) != fresh_count:
        _fail(
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

    batch_values = tuple(
        batches
    )

    if any(
        not isinstance(
            value,
            AuthoritativeCompletedBatchEvidence,
        )
        for value in batch_values
    ):
        _fail(
            "authoritative batch evidence has wrong type"
        )

    evidence_ids = tuple(
        _batch_id(
            value.batch_id
        )
        for value in batch_values
    )

    if evidence_ids != expected_ids:
        _fail(
            "authoritative provider sequence is incomplete, "
            "contains extras, or is out of Stage 2 order"
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
    fresh_batches = 0
    recovery_batches = 0

    for batch_index, evidence in enumerate(
        batch_values,
        1,
    ):
        expected_id = expected_ids[
            batch_index
            - 1
        ]

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
            _fail(
                "expected Stage 3B batch has no targets"
            )

        expected_requested = len(
            expected_targets
        )

        if (
            _positive_int(
                evidence.requested_accessions,
                label="requested-accession count",
            )
            != expected_requested
        ):
            _fail(
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

        if (
            _text(
                evidence.first_accession,
                label="first accession",
            )
            != first_accession
        ):
            _fail(
                "batch first accession changed"
            )

        if (
            _text(
                evidence.last_accession,
                label="last accession",
            )
            != last_accession
        ):
            _fail(
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
            raise MonthlySequenceAcquisitionCompletionV2Error(
                "unable to derive frozen Stage 3B batch identity"
            ) from exc

        observed_target_sha = _sha256(
            evidence.observed_batch_target_manifest_sha256,
            label="observed batch-target manifest SHA256",
        )

        observed_accessions_sha = _sha256(
            evidence.observed_accessions_sha256,
            label="observed accession-list SHA256",
        )

        if (
            observed_target_sha
            != expected_target_sha
        ):
            _fail(
                "batch-target manifest identity changed"
            )

        if (
            observed_accessions_sha
            != expected_accessions_sha
        ):
            _fail(
                "batch accession-list identity changed"
            )

        candidate_sha = _sha256(
            evidence.observed_candidate_audit_sha256,
            label="candidate audit SHA256",
        )

        component_sha = _sha256(
            evidence.observed_component_audit_sha256,
            label="component audit SHA256",
        )

        package_file_count = _positive_int(
            evidence.package_file_count,
            label="package-file count",
        )

        package_readback_count = _positive_int(
            evidence.package_file_readback_count,
            label="package-file readback count",
        )

        if (
            package_readback_count
            != package_file_count
        ):
            _fail(
                "package-file readback count changed"
            )

        package_readback_sha = _sha256(
            evidence.package_file_readback_sha256,
            label="package-file readback SHA256",
        )

        source = _audit_source_class(
            evidence
        )

        if (
            source[
                "source_class"
            ]
            == SOURCE_CLASS_FRESH
        ):
            fresh_batches += 1

        else:
            recovery_batches += 1

        completion_rows.append(
            {
                "accessions_sha256":
                    expected_accessions_sha,
                "batch_id":
                    expected_id,
                "batch_index":
                    batch_index,
                "batch_target_manifest_sha256":
                    expected_target_sha,
                "candidate_sequence_audit_sha256":
                    candidate_sha,
                "cause_evidence_sha256":
                    source[
                        "cause_evidence_sha256"
                    ],
                "component_sequence_audit_sha256":
                    component_sha,
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
                "package_manifest_name":
                    source[
                        "package_manifest_name"
                    ],
                "package_manifest_sha256":
                    source[
                        "package_manifest_sha256"
                    ],
                "provider_summary_name":
                    source[
                        "provider_summary_name"
                    ],
                "provider_summary_sha256":
                    source[
                        "provider_summary_sha256"
                    ],
                "recovery_class":
                    source[
                        "recovery_class"
                    ],
                "recovery_commit":
                    source[
                        "recovery_commit"
                    ],
                "recovery_package_sha256":
                    source[
                        "recovery_package_sha256"
                    ],
                "recovery_summary_sha256":
                    source[
                        "recovery_summary_sha256"
                    ],
                "requested_accessions":
                    expected_requested,
                "source_batch_sha256":
                    source[
                        "source_batch_sha256"
                    ],
                "source_class":
                    source[
                        "source_class"
                    ],
                "source_package_sha256":
                    source[
                        "source_package_sha256"
                    ],
                "source_partial_name":
                    source[
                        "source_partial_name"
                    ],
                "transport_record_sha256":
                    source[
                        "transport_record_sha256"
                    ],
            }
        )

        completed_accessions += (
            expected_requested
        )

    if (
        completed_accessions
        != fresh_count
    ):
        _fail(
            "completed accession count does not equal "
            "Stage 2 fresh population"
        )

    if (
        len(
            completion_rows
        )
        != expected_batch_count
    ):
        _fail(
            "completed batch count does not equal "
            "Stage 2 expectation"
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
        "completion_execution_commit":
            completion_commit,
        "environment_explicit_sha256":
            environment_sha,
        "expected_batch_count":
            expected_batch_count,
        "fresh_acquisition_count":
            fresh_count,
        "fresh_batch_size":
            FRESH_BATCH_SIZE,
        "schema_version":
            MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_V2_SCHEMA,
        "source_class_counts":
            {
                SOURCE_CLASS_FRESH:
                    fresh_batches,
                SOURCE_CLASS_FRESH_RECOVERY:
                    recovery_batches,
            },
        "source_production_commit":
            source_commit,
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


def serialize_sequence_acquisition_completion_v2_record(
    **kwargs,
) -> bytes:
    return _canonical_json_bytes(
        build_sequence_acquisition_completion_v2_record(
            **kwargs
        )
    )


def audit_sequence_acquisition_completion_v2_record(
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
            "sequence-acquisition completion v2 record "
            "must be bytes"
        )

    expected = (
        serialize_sequence_acquisition_completion_v2_record(
            **kwargs
        )
    )

    if payload != expected:
        _fail(
            "sequence-acquisition completion v2 "
            "derived identity changed"
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
        raise MonthlySequenceAcquisitionCompletionV2Error(
            "sequence-acquisition completion v2 record "
            "is invalid"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        _fail(
            "sequence-acquisition completion v2 record "
            "must be an object"
        )

    return value
