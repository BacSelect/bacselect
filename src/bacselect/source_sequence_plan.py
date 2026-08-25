"""Prospective BacSelect cache-reuse sequence-acquisition planning.

This module partitions the complete metadata-retained fresh universe into
historical-cache candidates and fresh-download targets. It performs no network
access, sequence validation, structural-feature calculation, or selector
comparison.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Mapping, Sequence

from bacselect.source_eligibility import (
    CANONICAL_GCA_RE,
    MetadataAssessment,
    RETAIN,
)


EXPECTED_METADATA_RETAINED = 70_477
EXPECTED_CACHE_CANDIDATES = 55_151
EXPECTED_UNCACHED = 15_326

FRESH_BATCH_SIZE = 500
EXPECTED_FRESH_BATCHES = 31

DATASETS_VERSION = "18.35.0"
DATASETS_ENV_LOCK_SHA256 = (
    "6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd"
)

SEQUENCE_INCLUDE = (
    "genome",
    "gbff",
    "seq-report",
)

DOWNLOAD_ARGS = (
    "download",
    "genome",
    "accession",
    "--inputfile",
    "accessions.txt",
    "--include",
    "genome,gbff,seq-report",
    "--dehydrated",
    "--no-progressbar",
    "--filename",
    "dehydrated.zip",
)

REHYDRATE_ARGS = (
    "rehydrate",
    "--directory",
    "package",
    "--max-workers",
    "10",
    "--no-progressbar",
)


@dataclass(frozen=True)
class SequencePlan:
    """Identity-bearing cache/fresh acquisition partition."""

    cache_candidates: tuple[str, ...]
    fresh_downloads: tuple[str, ...]


def retained_accessions(
    assessments: Iterable[MetadataAssessment],
) -> tuple[str, ...]:
    """Return every metadata-retained accession, sorted and unique."""

    values: list[str] = []
    seen: set[str] = set()

    for assessment in assessments:
        if assessment.decision != RETAIN:
            continue

        accession = assessment.accession

        if not CANONICAL_GCA_RE.fullmatch(accession):
            raise ValueError(
                "metadata-retained record has invalid canonical GCA accession"
            )

        if accession in seen:
            raise ValueError(
                "duplicate metadata-retained canonical accession"
            )

        seen.add(accession)
        values.append(accession)

    return tuple(sorted(values))


def build_sequence_plan(
    assessments: Iterable[MetadataAssessment],
    historical_accessions: Iterable[str],
    *,
    expected_retained: int | None = None,
) -> SequencePlan:
    """Partition retained fresh accessions by historical-cache membership.

    Baseline membership is deliberately not an argument. The historical cache
    is an operational source-evidence cache, not the scientific holdout
    boundary.
    """

    retained = retained_accessions(assessments)

    if expected_retained is not None and len(retained) != expected_retained:
        raise ValueError(
            f"expected {expected_retained} metadata-retained accessions; "
            f"observed {len(retained)}"
        )

    historical: set[str] = set()

    for accession in historical_accessions:
        if not CANONICAL_GCA_RE.fullmatch(accession):
            raise ValueError(
                "historical cache contains invalid canonical GCA accession"
            )

        if accession in historical:
            raise ValueError(
                "duplicate canonical accession in historical cache"
            )

        historical.add(accession)

    cache = tuple(
        accession for accession in retained
        if accession in historical
    )
    fresh = tuple(
        accession for accession in retained
        if accession not in historical
    )

    if len(cache) + len(fresh) != len(retained):
        raise RuntimeError("cache/fresh partition is inconsistent")

    return SequencePlan(
        cache_candidates=cache,
        fresh_downloads=fresh,
    )


def batch_accessions(
    accessions: Sequence[str],
    *,
    batch_size: int = FRESH_BATCH_SIZE,
) -> tuple[tuple[str, ...], ...]:
    """Partition a sorted fresh-download accession list deterministically."""

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    values = tuple(accessions)

    if values != tuple(sorted(values)):
        raise ValueError("accessions must be lexicographically sorted")

    if len(values) != len(set(values)):
        raise ValueError("accessions must be unique")

    return tuple(
        values[start:start + batch_size]
        for start in range(0, len(values), batch_size)
    )


def accession_manifest_bytes(
    accessions: Sequence[str],
) -> bytes:
    """Return exact newline-delimited ASCII bytes for NCBI --inputfile."""

    values = tuple(accessions)

    if values != tuple(sorted(values)):
        raise ValueError("manifest accessions must be sorted")

    if len(values) != len(set(values)):
        raise ValueError("manifest accessions must be unique")

    for accession in values:
        if not CANONICAL_GCA_RE.fullmatch(accession):
            raise ValueError("manifest contains invalid canonical GCA accession")

    return "".join(
        f"{accession}\n"
        for accession in values
    ).encode("ascii")


def manifest_sha256(
    accessions: Sequence[str],
) -> str:
    """Return SHA256 of exact accession-manifest bytes."""

    return hashlib.sha256(
        accession_manifest_bytes(accessions)
    ).hexdigest()


def blinded_plan_summary(
    plan: SequencePlan,
    *,
    fresh_batch_size: int = FRESH_BATCH_SIZE,
) -> dict[str, int]:
    """Return aggregate-only acquisition-plan counts."""

    batches = batch_accessions(
        plan.fresh_downloads,
        batch_size=fresh_batch_size,
    )

    return {
        "metadata_retained": (
            len(plan.cache_candidates)
            + len(plan.fresh_downloads)
        ),
        "cache_candidates": len(plan.cache_candidates),
        "fresh_downloads": len(plan.fresh_downloads),
        "fresh_batch_size": fresh_batch_size,
        "fresh_batches": len(batches),
    }


def cache_reuse_eligible(
    *,
    fresh_biosample: str,
    historical_row: Mapping[str, str],
    package_integrity_verified: bool,
) -> bool:
    """Return whether historical evidence may be reused for one accession.

    This is deliberately strict. A false result means fresh acquisition is
    required; it is not itself a scientific exclusion.
    """

    accession = historical_row.get(
        "canonical_genbank_assembly_accession",
        "",
    )

    if not CANONICAL_GCA_RE.fullmatch(accession):
        return False

    if historical_row.get("current_accession") != accession:
        return False

    if historical_row.get("assembly_status") != "current":
        return False

    if historical_row.get("assembly_level") != "Complete Genome":
        return False

    if historical_row.get("expected_biosample") != fresh_biosample:
        return False

    if historical_row.get("observed_biosample") != fresh_biosample:
        return False

    if not package_integrity_verified:
        return False

    return True


def validate_operational_constants() -> None:
    """Fail if prospective acquisition constants drift."""

    if FRESH_BATCH_SIZE != 500:
        raise RuntimeError("unexpected fresh acquisition batch size")

    expected_batches = (
        EXPECTED_UNCACHED
        + FRESH_BATCH_SIZE
        - 1
    ) // FRESH_BATCH_SIZE

    if expected_batches != EXPECTED_FRESH_BATCHES:
        raise RuntimeError("fresh batch count is internally inconsistent")

    if SEQUENCE_INCLUDE != ("genome", "gbff", "seq-report"):
        raise RuntimeError("unexpected sequence include bundle")
