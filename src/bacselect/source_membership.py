"""Frozen BacSelect baseline-membership helpers.

This module compares metadata-retained fresh-source accessions with the frozen
55,306-genome BacSelect baseline membership. It performs no sequence,
taxonomy, structural-feature, or selector-coverage analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
from pathlib import Path
import re
from typing import Iterable

from bacselect.source_eligibility import (
    CANONICAL_GCA_RE,
    MetadataAssessment,
    RETAIN,
)


BASELINE_ACCESSION_COLUMN = "canonical_genbank_assembly_accession"
BASELINE_EXPECTED_ROWS = 55_306
BASELINE_RAW_SHA256 = (
    "86c0c3d49317dfc3cc452114e3863666fe2112b6a3ae8dae2090b60a2a598948"
)


@dataclass(frozen=True)
class MembershipSummary:
    """Aggregate-only baseline-membership result."""

    baseline_accessions: int
    metadata_retained: int
    retained_present_in_baseline: int
    retained_absent_from_baseline: int
    baseline_not_in_metadata_retained: int

    def as_dict(self) -> dict[str, int]:
        return {
            "baseline_accessions": self.baseline_accessions,
            "metadata_retained": self.metadata_retained,
            "retained_present_in_baseline": self.retained_present_in_baseline,
            "retained_absent_from_baseline": self.retained_absent_from_baseline,
            "baseline_not_in_metadata_retained": (
                self.baseline_not_in_metadata_retained
            ),
        }


def sha256_file(path: Path | str) -> str:
    """Return SHA256 for one file."""

    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def load_baseline_accessions(
    path: Path | str,
    *,
    expected_sha256: str = BASELINE_RAW_SHA256,
    expected_rows: int = BASELINE_EXPECTED_ROWS,
) -> frozenset[str]:
    """Load the frozen baseline accession set fail-closed.

    The accession field is identified by its frozen column name, never by
    positional index.
    """

    source = Path(path)

    observed_sha = sha256_file(source)
    if observed_sha != expected_sha256:
        raise ValueError(
            "baseline raw matrix SHA256 mismatch: "
            f"{observed_sha} != {expected_sha256}"
        )

    accessions: set[str] = set()

    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")

        if reader.fieldnames is None:
            raise ValueError("baseline matrix header is missing")

        if BASELINE_ACCESSION_COLUMN not in reader.fieldnames:
            raise ValueError(
                "baseline matrix lacks frozen accession column "
                f"{BASELINE_ACCESSION_COLUMN!r}"
            )

        row_count = 0

        for row_count, row in enumerate(reader, start=1):
            accession = row.get(BASELINE_ACCESSION_COLUMN)

            if not isinstance(accession, str) or not CANONICAL_GCA_RE.fullmatch(
                accession
            ):
                raise ValueError(
                    f"baseline row {row_count}: invalid canonical GCA accession"
                )

            if accession in accessions:
                raise ValueError(
                    f"baseline row {row_count}: duplicate canonical accession"
                )

            accessions.add(accession)

    if row_count != expected_rows:
        raise ValueError(
            f"expected {expected_rows} baseline rows; observed {row_count}"
        )

    if len(accessions) != expected_rows:
        raise ValueError(
            "baseline unique accession count differs from frozen row count"
        )

    return frozenset(accessions)


def metadata_retained_accessions(
    assessments: Iterable[MetadataAssessment],
) -> frozenset[str]:
    """Return unique canonical accessions retained at the metadata stage."""

    retained: set[str] = set()

    for assessment in assessments:
        if assessment.decision != RETAIN:
            continue

        accession = assessment.accession

        if not CANONICAL_GCA_RE.fullmatch(accession):
            raise ValueError(
                "metadata-retained record has invalid canonical GCA accession"
            )

        if accession in retained:
            raise ValueError(
                "duplicate metadata-retained canonical accession"
            )

        retained.add(accession)

    return frozenset(retained)


def compare_membership(
    baseline_accessions: frozenset[str],
    retained_accessions: frozenset[str],
) -> MembershipSummary:
    """Compare retained fresh-source membership against the frozen baseline."""

    if any(
        not CANONICAL_GCA_RE.fullmatch(accession)
        for accession in baseline_accessions
    ):
        raise ValueError("baseline membership contains invalid accession")

    if any(
        not CANONICAL_GCA_RE.fullmatch(accession)
        for accession in retained_accessions
    ):
        raise ValueError("retained membership contains invalid accession")

    present = retained_accessions & baseline_accessions
    absent = retained_accessions - baseline_accessions
    baseline_missing = baseline_accessions - retained_accessions

    summary = MembershipSummary(
        baseline_accessions=len(baseline_accessions),
        metadata_retained=len(retained_accessions),
        retained_present_in_baseline=len(present),
        retained_absent_from_baseline=len(absent),
        baseline_not_in_metadata_retained=len(baseline_missing),
    )

    if (
        summary.retained_present_in_baseline
        + summary.retained_absent_from_baseline
        != summary.metadata_retained
    ):
        raise RuntimeError("retained membership partition is inconsistent")

    if (
        summary.retained_present_in_baseline
        + summary.baseline_not_in_metadata_retained
        != summary.baseline_accessions
    ):
        raise RuntimeError("baseline membership partition is inconsistent")

    return summary


def blinded_membership_summary(
    baseline_accessions: frozenset[str],
    assessments: Iterable[MetadataAssessment],
) -> dict[str, int]:
    """Return aggregate-only membership counts.

    No accession, BioSample, organism, TaxID, or other record identity is
    returned.
    """

    retained = metadata_retained_accessions(assessments)
    return compare_membership(
        baseline_accessions,
        retained,
    ).as_dict()
