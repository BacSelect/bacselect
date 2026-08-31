"""Portable BacSelect monthly sequence-acquisition planning.

This module contains only the deterministic monthly Stage 2 partition.

It consumes current monthly metadata assessments plus cache evidence that has
already been verified for the same monthly source snapshot. It performs no
network access and contains no historical selector-v1 population bindings.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable

from bacselect.source_eligibility import (
    BIOSAMPLE_RE,
    CANONICAL_GCA_RE,
    RETAIN,
)


LOWER_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

FRESH_BATCH_SIZE = 500

NO_VERIFIED_CACHE = "no_verified_cache"
CACHE_NOT_CURRENT = "cache_not_verified_for_current_snapshot"
CACHE_METADATA_MISMATCH = "cache_metadata_mismatch"

FRESH_TARGET_FIELDS = (
    "canonical_genbank_assembly_accession",
    "source_biosample",
    "acquisition_reason",
)


@dataclass(frozen=True)
class VerifiedMonthlyCacheEvidence:
    """One cache record already verified for monthly reuse consideration.

    The verification layer, not this planner, is responsible for proving the
    underlying persisted files and scientific evidence. The planner requires
    cryptographic identities sufficient to make accidental accession-only
    reuse impossible.
    """

    canonical_genbank_assembly_accession: str
    biosample: str
    verified_source_snapshot_id: str

    component_identity_sha256: str
    assembly_fingerprint: str
    source_evidence_sha256: str
    package_manifest_sha256: str
    verification_record_sha256: str


@dataclass(frozen=True)
class MonthlyFreshAcquisitionTarget:
    """One current monthly source requiring fresh sequence acquisition."""

    canonical_genbank_assembly_accession: str
    source_biosample: str
    acquisition_reason: str


@dataclass(frozen=True)
class MonthlySequencePlan:
    """Deterministic monthly cache/fresh partition."""

    source_snapshot_id: str
    retained_accessions: tuple[str, ...]
    cache_reuse_accessions: tuple[str, ...]
    fresh_acquisition_targets: tuple[
        MonthlyFreshAcquisitionTarget,
        ...,
    ]
    fresh_acquisition_accessions: tuple[str, ...]
    fresh_reasons: tuple[tuple[str, str], ...]
    fresh_batches: tuple[tuple[str, ...], ...]


def _nonempty_text(
    value: object,
    *,
    label: str,
) -> str:
    text = str(value)

    if not text or text != text.strip():
        raise ValueError(
            f"{label} must be non-empty normalized text"
        )

    if any(character.isspace() for character in text):
        raise ValueError(
            f"{label} must not contain whitespace"
        )

    return text


def _sha256(
    value: object,
    *,
    label: str,
) -> str:
    text = str(value)

    if LOWER_SHA256_RE.fullmatch(text) is None:
        raise ValueError(
            f"{label} must be lowercase SHA256"
        )

    return text


def _validate_cache_evidence(
    evidence: VerifiedMonthlyCacheEvidence,
) -> None:
    accession = (
        evidence.canonical_genbank_assembly_accession
    )

    if CANONICAL_GCA_RE.fullmatch(accession) is None:
        raise ValueError(
            "verified cache evidence has invalid canonical GCA accession"
        )

    if BIOSAMPLE_RE.fullmatch(evidence.biosample) is None:
        raise ValueError(
            "verified cache evidence has invalid BioSample"
        )

    _nonempty_text(
        evidence.verified_source_snapshot_id,
        label="verified source snapshot ID",
    )

    for label, value in (
        (
            "component identity SHA256",
            evidence.component_identity_sha256,
        ),
        (
            "assembly fingerprint",
            evidence.assembly_fingerprint,
        ),
        (
            "source evidence SHA256",
            evidence.source_evidence_sha256,
        ),
        (
            "package manifest SHA256",
            evidence.package_manifest_sha256,
        ),
        (
            "verification record SHA256",
            evidence.verification_record_sha256,
        ),
    ):
        _sha256(
            value,
            label=label,
        )


def _retained_metadata(
    assessments: Iterable[object],
) -> dict[str, str]:
    retained: dict[str, str] = {}

    for assessment in assessments:
        if getattr(
            assessment,
            "decision",
            None,
        ) != RETAIN:
            continue

        accession = str(
            getattr(
                assessment,
                "accession",
                "",
            )
        )

        biosample = str(
            getattr(
                assessment,
                "biosample",
                "",
            )
        )

        if CANONICAL_GCA_RE.fullmatch(accession) is None:
            raise ValueError(
                "metadata-retained record has invalid canonical GCA accession"
            )

        if BIOSAMPLE_RE.fullmatch(biosample) is None:
            raise ValueError(
                "metadata-retained record has invalid BioSample"
            )

        if accession in retained:
            raise ValueError(
                "duplicate metadata-retained canonical accession"
            )

        retained[accession] = biosample

    return retained


def batch_accessions(
    accessions: Iterable[str],
    *,
    batch_size: int = FRESH_BATCH_SIZE,
) -> tuple[tuple[str, ...], ...]:
    """Return deterministic lexicographic fresh-acquisition batches."""

    if batch_size <= 0:
        raise ValueError(
            "batch size must be positive"
        )

    values = tuple(accessions)

    if values != tuple(sorted(values)):
        raise ValueError(
            "fresh acquisition accessions must be sorted"
        )

    if len(values) != len(set(values)):
        raise ValueError(
            "fresh acquisition accessions must be unique"
        )

    for accession in values:
        if CANONICAL_GCA_RE.fullmatch(accession) is None:
            raise ValueError(
                "fresh acquisition list contains invalid canonical GCA accession"
            )

    return tuple(
        values[start:start + batch_size]
        for start in range(
            0,
            len(values),
            batch_size,
        )
    )


def accession_manifest_bytes(
    accessions: Iterable[str],
) -> bytes:
    """Return canonical NCBI Datasets accession-input bytes."""

    values = tuple(accessions)

    if values != tuple(sorted(values)):
        raise ValueError(
            "manifest accessions must be sorted"
        )

    if len(values) != len(set(values)):
        raise ValueError(
            "manifest accessions must be unique"
        )

    for accession in values:
        if CANONICAL_GCA_RE.fullmatch(accession) is None:
            raise ValueError(
                "manifest contains invalid canonical GCA accession"
            )

    return "".join(
        f"{accession}\n"
        for accession in values
    ).encode("ascii")


def accession_manifest_sha256(
    accessions: Iterable[str],
) -> str:
    """Return SHA256 of canonical accession-manifest bytes."""

    return hashlib.sha256(
        accession_manifest_bytes(
            accessions
        )
    ).hexdigest()


def build_monthly_sequence_plan(
    assessments: Iterable[object],
    verified_cache: Iterable[
        VerifiedMonthlyCacheEvidence
    ],
    *,
    source_snapshot_id: str,
    batch_size: int = FRESH_BATCH_SIZE,
) -> MonthlySequencePlan:
    """Partition the current monthly retained universe fail-closed.

    Cache reuse is allowed only from cache evidence explicitly verified for the
    current source snapshot. A missing, stale or metadata-mismatched cache
    record causes fresh acquisition rather than scientific exclusion.
    """

    current_snapshot = _nonempty_text(
        source_snapshot_id,
        label="source snapshot ID",
    )

    retained = _retained_metadata(
        assessments
    )

    cache_by_accession: dict[
        str,
        VerifiedMonthlyCacheEvidence,
    ] = {}

    for evidence in verified_cache:
        _validate_cache_evidence(
            evidence
        )

        accession = (
            evidence.canonical_genbank_assembly_accession
        )

        if accession in cache_by_accession:
            raise ValueError(
                "duplicate accession in verified monthly cache evidence"
            )

        cache_by_accession[
            accession
        ] = evidence

    cache_reuse: list[str] = []
    fresh: list[str] = []
    fresh_targets: list[
        MonthlyFreshAcquisitionTarget
    ] = []
    reasons: list[tuple[str, str]] = []

    def mark_fresh(
        accession: str,
        biosample: str,
        reason: str,
    ) -> None:
        fresh.append(
            accession
        )
        reasons.append(
            (
                accession,
                reason,
            )
        )
        fresh_targets.append(
            MonthlyFreshAcquisitionTarget(
                canonical_genbank_assembly_accession=(
                    accession
                ),
                source_biosample=biosample,
                acquisition_reason=reason,
            )
        )

    for accession in sorted(retained):
        biosample = retained[accession]

        evidence = cache_by_accession.get(
            accession
        )

        if evidence is None:
            mark_fresh(
                accession,
                biosample,
                NO_VERIFIED_CACHE,
            )
            continue

        if (
            evidence.verified_source_snapshot_id
            != current_snapshot
        ):
            mark_fresh(
                accession,
                biosample,
                CACHE_NOT_CURRENT,
            )
            continue

        if evidence.biosample != biosample:
            mark_fresh(
                accession,
                biosample,
                CACHE_METADATA_MISMATCH,
            )
            continue

        cache_reuse.append(
            accession
        )

    retained_accessions = tuple(
        sorted(retained)
    )

    cache_reuse_accessions = tuple(
        cache_reuse
    )

    fresh_acquisition_accessions = tuple(
        fresh
    )

    if set(
        cache_reuse_accessions
    ) & set(
        fresh_acquisition_accessions
    ):
        raise RuntimeError(
            "monthly cache/fresh partition overlaps"
        )

    if (
        set(cache_reuse_accessions)
        | set(fresh_acquisition_accessions)
        != set(retained_accessions)
    ):
        raise RuntimeError(
            "monthly cache/fresh partition is not exhaustive"
        )

    return MonthlySequencePlan(
        source_snapshot_id=current_snapshot,
        retained_accessions=retained_accessions,
        cache_reuse_accessions=(
            cache_reuse_accessions
        ),
        fresh_acquisition_targets=tuple(
            fresh_targets
        ),
        fresh_acquisition_accessions=(
            fresh_acquisition_accessions
        ),
        fresh_reasons=tuple(
            reasons
        ),
        fresh_batches=batch_accessions(
            fresh_acquisition_accessions,
            batch_size=batch_size,
        ),
    )


def fresh_target_manifest_bytes(
    plan: MonthlySequencePlan,
) -> bytes:
    """Return canonical monthly fresh-target TSV bytes."""

    target_accessions = tuple(
        target.canonical_genbank_assembly_accession
        for target in plan.fresh_acquisition_targets
    )

    if (
        target_accessions
        != plan.fresh_acquisition_accessions
    ):
        raise ValueError(
            "fresh target rows do not match fresh acquisition accessions"
        )

    allowed_reasons = {
        NO_VERIFIED_CACHE,
        CACHE_NOT_CURRENT,
        CACHE_METADATA_MISMATCH,
    }

    rows = [
        "\t".join(
            FRESH_TARGET_FIELDS
        )
        + "\n"
    ]

    for target in plan.fresh_acquisition_targets:
        accession = (
            target.canonical_genbank_assembly_accession
        )

        if CANONICAL_GCA_RE.fullmatch(accession) is None:
            raise ValueError(
                "fresh target has invalid canonical GCA accession"
            )

        if BIOSAMPLE_RE.fullmatch(
            target.source_biosample
        ) is None:
            raise ValueError(
                "fresh target has invalid source BioSample"
            )

        if target.acquisition_reason not in allowed_reasons:
            raise ValueError(
                "fresh target has invalid acquisition reason"
            )

        rows.append(
            f"{accession}\t"
            f"{target.source_biosample}\t"
            f"{target.acquisition_reason}\n"
        )

    return "".join(
        rows
    ).encode("ascii")


def fresh_target_manifest_sha256(
    plan: MonthlySequencePlan,
) -> str:
    """Return SHA256 of canonical monthly fresh-target TSV."""

    return hashlib.sha256(
        fresh_target_manifest_bytes(
            plan
        )
    ).hexdigest()


def blinded_plan_summary(
    plan: MonthlySequencePlan,
    *,
    batch_size: int = FRESH_BATCH_SIZE,
) -> dict[str, int]:
    """Return aggregate-only monthly Stage 2 counts."""

    return {
        "metadata_retained": len(
            plan.retained_accessions
        ),
        "cache_reuse": len(
            plan.cache_reuse_accessions
        ),
        "fresh_acquisition": len(
            plan.fresh_acquisition_accessions
        ),
        "fresh_batch_size": batch_size,
        "fresh_batches": len(
            plan.fresh_batches
        ),
    }


MONTHLY_SEQUENCE_PLAN_RECORD_SCHEMA = (
    "bacselect-monthly-sequence-plan-v1"
)


def _canonical_json_bytes(
    payload: object,
) -> bytes:
    """Serialize canonical newline-terminated JSON."""

    return (
        json.dumps(
            payload,
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


def _accession_sha256(
    accessions: tuple[str, ...],
) -> str:
    return hashlib.sha256(
        accession_manifest_bytes(
            accessions
        )
    ).hexdigest()


def build_monthly_sequence_plan_record(
    plan: MonthlySequencePlan,
    *,
    source_snapshot_record_sha256: str,
) -> dict[str, object]:
    """Build immutable Stage 2 provenance binding Stage 1 to Stage 3."""

    snapshot_record_sha = _sha256(
        source_snapshot_record_sha256,
        label="source snapshot record SHA256",
    )

    source_snapshot_id = _nonempty_text(
        plan.source_snapshot_id,
        label="source snapshot ID",
    )

    retained = tuple(
        plan.retained_accessions
    )

    cache_reuse = tuple(
        plan.cache_reuse_accessions
    )

    fresh = tuple(
        plan.fresh_acquisition_accessions
    )

    if (
        tuple(
            target.canonical_genbank_assembly_accession
            for target in plan.fresh_acquisition_targets
        )
        != fresh
    ):
        raise ValueError(
            "fresh acquisition target identity changed"
        )

    if set(
        cache_reuse
    ) & set(
        fresh
    ):
        raise ValueError(
            "cache-reuse and fresh accessions overlap"
        )

    if set(
        cache_reuse
    ) | set(
        fresh
    ) != set(
        retained
    ):
        raise ValueError(
            "Stage 2 partition is not exhaustive"
        )

    fresh_manifest = (
        fresh_target_manifest_bytes(
            plan
        )
    )

    reason_counts: dict[
        str,
        int,
    ] = {}

    for target in plan.fresh_acquisition_targets:
        reason_counts[
            target.acquisition_reason
        ] = (
            reason_counts.get(
                target.acquisition_reason,
                0,
            )
            + 1
        )

    return {
        "schema_version":
            MONTHLY_SEQUENCE_PLAN_RECORD_SCHEMA,
        "source_snapshot_id":
            source_snapshot_id,
        "source_snapshot_record_sha256":
            snapshot_record_sha,
        "retained_count":
            len(
                retained
            ),
        "cache_reuse_count":
            len(
                cache_reuse
            ),
        "fresh_acquisition_count":
            len(
                fresh
            ),
        "retained_accessions_sha256":
            _accession_sha256(
                retained
            ),
        "cache_reuse_accessions_sha256":
            _accession_sha256(
                cache_reuse
            ),
        "fresh_acquisition_accessions_sha256":
            _accession_sha256(
                fresh
            ),
        "fresh_target_manifest_sha256":
            hashlib.sha256(
                fresh_manifest
            ).hexdigest(),
        "fresh_batch_size":
            FRESH_BATCH_SIZE,
        "fresh_batch_count":
            len(
                plan.fresh_batches
            ),
        "fresh_acquisition_reason_counts":
            dict(
                sorted(
                    reason_counts.items()
                )
            ),
    }


def serialize_monthly_sequence_plan_record(
    plan: MonthlySequencePlan,
    *,
    source_snapshot_record_sha256: str,
) -> bytes:
    """Serialize immutable canonical Stage 2 provenance."""

    return _canonical_json_bytes(
        build_monthly_sequence_plan_record(
            plan,
            source_snapshot_record_sha256=(
                source_snapshot_record_sha256
            ),
        )
    )


def _audit_fresh_target_manifest_bytes(
    payload: bytes,
) -> tuple[
    tuple[str, ...],
    dict[str, int],
]:
    """Audit exact Stage 2 fresh-target TSV content."""

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
        raise ValueError(
            "fresh-target manifest must be ASCII"
        ) from exc

    if not text.endswith(
        "\n"
    ):
        raise ValueError(
            "fresh-target manifest must be newline terminated"
        )

    lines = text.splitlines()

    if not lines:
        raise ValueError(
            "fresh-target manifest is empty"
        )

    expected_header = "\t".join(
        FRESH_TARGET_FIELDS
    )

    if lines[0] != expected_header:
        raise ValueError(
            "fresh-target manifest schema changed"
        )

    accessions: list[str] = []
    reasons: dict[str, int] = {}

    allowed_reasons = {
        NO_VERIFIED_CACHE,
        CACHE_NOT_CURRENT,
        CACHE_METADATA_MISMATCH,
    }

    for line_number, line in enumerate(
        lines[1:],
        2,
    ):
        fields = line.split(
            "\t"
        )

        if len(
            fields
        ) != 3:
            raise ValueError(
                "fresh-target manifest row does not "
                f"have three fields at line {line_number}"
            )

        (
            accession,
            biosample,
            reason,
        ) = fields

        if CANONICAL_GCA_RE.fullmatch(
            accession
        ) is None:
            raise ValueError(
                "fresh-target manifest contains invalid "
                f"canonical GCA at line {line_number}"
            )

        if BIOSAMPLE_RE.fullmatch(
            biosample
        ) is None:
            raise ValueError(
                "fresh-target manifest contains invalid "
                f"BioSample at line {line_number}"
            )

        if reason not in allowed_reasons:
            raise ValueError(
                "fresh-target manifest contains invalid "
                f"acquisition reason at line {line_number}"
            )

        accessions.append(
            accession
        )

        reasons[
            reason
        ] = (
            reasons.get(
                reason,
                0,
            )
            + 1
        )

    accession_tuple = tuple(
        accessions
    )

    if accession_tuple != tuple(
        sorted(
            accession_tuple
        )
    ):
        raise ValueError(
            "fresh-target manifest accessions are not "
            "lexicographically sorted"
        )

    if len(
        accession_tuple
    ) != len(
        set(
            accession_tuple
        )
    ):
        raise ValueError(
            "fresh-target manifest contains duplicate accessions"
        )

    return (
        accession_tuple,
        dict(
            sorted(
                reasons.items()
            )
        ),
    )


def audit_monthly_sequence_plan_record(
    payload: bytes,
    *,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    fresh_target_manifest: bytes,
) -> dict[str, object]:
    """Audit Stage 2 provenance against Stage 1 and exact Stage 2 TSV."""

    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "monthly sequence-plan record must be bytes"
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
        raise ValueError(
            "invalid monthly sequence-plan record"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise ValueError(
            "monthly sequence-plan record must be a JSON object"
        )

    if _canonical_json_bytes(
        record
    ) != payload:
        raise ValueError(
            "monthly sequence-plan record is not canonical JSON"
        )

    expected_keys = {
        "schema_version",
        "source_snapshot_id",
        "source_snapshot_record_sha256",
        "retained_count",
        "cache_reuse_count",
        "fresh_acquisition_count",
        "retained_accessions_sha256",
        "cache_reuse_accessions_sha256",
        "fresh_acquisition_accessions_sha256",
        "fresh_target_manifest_sha256",
        "fresh_batch_size",
        "fresh_batch_count",
        "fresh_acquisition_reason_counts",
    }

    if set(
        record
    ) != expected_keys:
        raise ValueError(
            "monthly sequence-plan record key set changed"
        )

    if record.get(
        "schema_version"
    ) != MONTHLY_SEQUENCE_PLAN_RECORD_SCHEMA:
        raise ValueError(
            "monthly sequence-plan record schema changed"
        )

    expected_snapshot_id = _nonempty_text(
        source_snapshot_id,
        label="source snapshot ID",
    )

    if record.get(
        "source_snapshot_id"
    ) != expected_snapshot_id:
        raise ValueError(
            "monthly sequence-plan source snapshot changed"
        )

    expected_snapshot_record_sha = _sha256(
        source_snapshot_record_sha256,
        label="source snapshot record SHA256",
    )

    if record.get(
        "source_snapshot_record_sha256"
    ) != expected_snapshot_record_sha:
        raise ValueError(
            "monthly sequence-plan source-snapshot record fingerprint changed"
        )

    if not isinstance(
        fresh_target_manifest,
        bytes,
    ):
        raise TypeError(
            "fresh-target manifest must be bytes"
        )

    expected_manifest_sha = hashlib.sha256(
        fresh_target_manifest
    ).hexdigest()

    if record.get(
        "fresh_target_manifest_sha256"
    ) != expected_manifest_sha:
        raise ValueError(
            "monthly sequence-plan fresh-target manifest fingerprint changed"
        )

    (
        manifest_accessions,
        manifest_reason_counts,
    ) = _audit_fresh_target_manifest_bytes(
        fresh_target_manifest
    )

    manifest_fresh_count = len(
        manifest_accessions
    )

    if record.get(
        "fresh_acquisition_count"
    ) != manifest_fresh_count:
        raise ValueError(
            "monthly sequence-plan fresh count does not "
            "match fresh-target manifest"
        )

    manifest_accessions_sha = _accession_sha256(
        manifest_accessions
    )

    if record.get(
        "fresh_acquisition_accessions_sha256"
    ) != manifest_accessions_sha:
        raise ValueError(
            "monthly sequence-plan fresh accession fingerprint "
            "does not match fresh-target manifest"
        )

    if record.get(
        "fresh_acquisition_reason_counts"
    ) != manifest_reason_counts:
        raise ValueError(
            "monthly sequence-plan acquisition-reason counts "
            "do not match fresh-target manifest"
        )

    if record.get(
        "fresh_batch_size"
    ) != FRESH_BATCH_SIZE:
        raise ValueError(
            "monthly sequence-plan batch size changed"
        )

    fresh_count = record.get(
        "fresh_acquisition_count"
    )

    batch_count = record.get(
        "fresh_batch_count"
    )

    if (
        isinstance(
            fresh_count,
            bool,
        )
        or not isinstance(
            fresh_count,
            int,
        )
        or fresh_count < 0
    ):
        raise ValueError(
            "monthly sequence-plan fresh count is invalid"
        )

    if (
        isinstance(
            batch_count,
            bool,
        )
        or not isinstance(
            batch_count,
            int,
        )
        or batch_count < 0
    ):
        raise ValueError(
            "monthly sequence-plan batch count is invalid"
        )

    expected_batch_count = (
        (
            fresh_count
            + FRESH_BATCH_SIZE
            - 1
        )
        // FRESH_BATCH_SIZE
        if fresh_count
        else 0
    )

    if batch_count != expected_batch_count:
        raise ValueError(
            "monthly sequence-plan batch count does not match fresh count"
        )

    for field in (
        "retained_accessions_sha256",
        "cache_reuse_accessions_sha256",
        "fresh_acquisition_accessions_sha256",
    ):
        _sha256(
            record.get(
                field
            ),
            label=field,
        )

    return record
