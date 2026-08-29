"""Pure BacSelect Stage 5B holdout-composition helpers.

This module implements only deterministic membership reconstruction,
complete-universe intersection, output-row serialization, membership
fingerprints, and the frozen holdout adequacy gate.

It performs no file I/O and does not load the raw metadata snapshot,
baseline matrix, Stage 5A universe artifact, structural features,
selector distances, panels, or selector outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping, Sequence

from bacselect.source_eligibility import CANONICAL_GCA_RE
from bacselect.source_membership import (
    MembershipSummary,
    compare_membership,
)
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


RECONSTRUCTED_ABSENCE_FIELDS = (
    "canonical_genbank_assembly_accession",
)

EXTERNAL_HOLDOUT_FIELDS = (
    "canonical_genbank_assembly_accession",
    "species_taxid",
)

ADEQUACY_PASS = "ADEQUACY_PASS"
ADEQUACY_FAIL = "ADEQUACY_FAIL_NO_SELECTOR_DECISION"

ADEQUACY_MIN_GENOMES = 1_000
ADEQUACY_MIN_SPECIES = 200

HISTORICAL_BASELINE_ACCESSIONS = 55_306
HISTORICAL_METADATA_RETAINED = 70_477
HISTORICAL_PRESENT_IN_BASELINE = 55_032
HISTORICAL_ABSENT_FROM_BASELINE = 15_445
HISTORICAL_BASELINE_NOT_METADATA_RETAINED = 274

LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class HoldoutError(ValueError):
    """Raised when Stage 5B membership composition fails closed."""


@dataclass(frozen=True)
class HistoricalReconstruction:
    """Exact reconstructed historical absence membership."""

    summary: MembershipSummary
    retained_absent_from_baseline: tuple[str, ...]
    membership_sha256: str


@dataclass(frozen=True)
class CompleteUniverseMember:
    """One immutable Stage 5A complete-universe member."""

    accession: str
    species_taxid: int


@dataclass(frozen=True)
class HoldoutMember:
    """One external decision-holdout member."""

    accession: str
    species_taxid: int


@dataclass(frozen=True)
class HoldoutSummary:
    """Aggregate-only external holdout summary."""

    genome_count: int
    distinct_species_count: int
    membership_sha256: str

    def as_dict(self) -> dict[str, int | str]:
        return {
            "genome_count":
                self.genome_count,
            "distinct_species_count":
                self.distinct_species_count,
            "membership_sha256":
                self.membership_sha256,
        }


@dataclass(frozen=True)
class AdequacyResult:
    """Frozen adequacy-gate result for one fixed holdout."""

    status: str
    genome_count: int
    distinct_species_count: int
    minimum_genomes: int
    minimum_species: int

    @property
    def passed(self) -> bool:
        return self.status == ADEQUACY_PASS

    def as_dict(self) -> dict[str, int | str | bool]:
        return {
            "status":
                self.status,
            "passed":
                self.passed,
            "genome_count":
                self.genome_count,
            "distinct_species_count":
                self.distinct_species_count,
            "minimum_genomes":
                self.minimum_genomes,
            "minimum_species":
                self.minimum_species,
        }


FROZEN_HISTORICAL_MEMBERSHIP_SUMMARY = MembershipSummary(
    baseline_accessions=HISTORICAL_BASELINE_ACCESSIONS,
    metadata_retained=HISTORICAL_METADATA_RETAINED,
    retained_present_in_baseline=HISTORICAL_PRESENT_IN_BASELINE,
    retained_absent_from_baseline=HISTORICAL_ABSENT_FROM_BASELINE,
    baseline_not_in_metadata_retained=(
        HISTORICAL_BASELINE_NOT_METADATA_RETAINED
    ),
)


def _nonempty_text(
    value: object,
    *,
    label: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise HoldoutError(
            f"{label} must be a string"
        )

    cleaned = value.strip()

    if not cleaned:
        raise HoldoutError(
            f"{label} must not be empty"
        )

    return cleaned


def _canonical_accession(
    value: object,
    *,
    label: str,
) -> str:
    accession = _nonempty_text(
        value,
        label=label,
    )

    if CANONICAL_GCA_RE.fullmatch(
        accession
    ) is None:
        raise HoldoutError(
            f"{label} must be a versioned canonical GCA accession"
        )

    return accession


def _positive_taxid(
    value: object,
    *,
    label: str,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        raise HoldoutError(
            f"{label} must be a positive integer"
        )

    try:
        taxid = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HoldoutError(
            f"{label} must be a positive integer"
        ) from exc

    if taxid <= 0:
        raise HoldoutError(
            f"{label} must be a positive integer"
        )

    return taxid


def _lower_sha256(
    value: object,
    *,
    label: str,
) -> str:
    text = _nonempty_text(
        value,
        label=label,
    )

    if LOWER_SHA256_RE.fullmatch(
        text
    ) is None:
        raise HoldoutError(
            f"{label} must be lowercase SHA256"
        )

    return text


def canonical_accession_set(
    values: Iterable[str],
    *,
    label: str,
) -> frozenset[str]:
    """Validate one unique canonical accession membership."""

    observed: set[str] = set()

    for raw in values:
        accession = _canonical_accession(
            raw,
            label=label,
        )

        if accession in observed:
            raise HoldoutError(
                f"duplicate accession in {label}"
            )

        observed.add(
            accession
        )

    return frozenset(
        observed
    )


def reconstruct_retained_absent_from_baseline(
    baseline_accessions: Iterable[str],
    retained_accessions: Iterable[str],
    *,
    expected_summary: MembershipSummary = (
        FROZEN_HISTORICAL_MEMBERSHIP_SUMMARY
    ),
) -> HistoricalReconstruction:
    """Reconstruct the frozen historical absent-from-baseline membership."""

    baseline = canonical_accession_set(
        baseline_accessions,
        label="baseline membership",
    )

    retained = canonical_accession_set(
        retained_accessions,
        label="metadata-retained membership",
    )

    try:
        summary = compare_membership(
            baseline,
            retained,
        )
    except (
        ValueError,
        RuntimeError,
    ) as exc:
        raise HoldoutError(
            "historical membership comparison failed"
        ) from exc

    if summary != expected_summary:
        raise HoldoutError(
            "historical aggregate membership does not reproduce frozen result"
        )

    absent = tuple(
        sorted(
            retained
            - baseline
        )
    )

    if len(
        absent
    ) != expected_summary.retained_absent_from_baseline:
        raise HoldoutError(
            "reconstructed absence count mismatch"
        )

    membership_sha = accession_membership_sha256(
        absent
    )

    return HistoricalReconstruction(
        summary=summary,
        retained_absent_from_baseline=absent,
        membership_sha256=membership_sha,
    )


def validate_complete_universe(
    members: Iterable[CompleteUniverseMember],
    *,
    expected_count: int | None = None,
    expected_species_count: int | None = None,
    expected_membership_sha256: str | None = None,
) -> tuple[CompleteUniverseMember, ...]:
    """Validate an immutable complete-universe membership."""

    by_accession: dict[
        str,
        CompleteUniverseMember
    ] = {}

    for item in members:
        if not isinstance(
            item,
            CompleteUniverseMember,
        ):
            raise HoldoutError(
                "unexpected complete-universe member type"
            )

        accession = _canonical_accession(
            item.accession,
            label="complete-universe accession",
        )

        species_taxid = _positive_taxid(
            item.species_taxid,
            label="complete-universe species TaxID",
        )

        if accession in by_accession:
            raise HoldoutError(
                "duplicate complete-universe accession"
            )

        by_accession[
            accession
        ] = CompleteUniverseMember(
            accession=accession,
            species_taxid=species_taxid,
        )

    ordered = tuple(
        by_accession[
            accession
        ]
        for accession in sorted(
            by_accession
        )
    )

    if (
        expected_count is not None
        and len(
            ordered
        ) != expected_count
    ):
        raise HoldoutError(
            "complete-universe count mismatch"
        )

    species_count = len(
        {
            item.species_taxid
            for item in ordered
        }
    )

    if (
        expected_species_count is not None
        and species_count
        != expected_species_count
    ):
        raise HoldoutError(
            "complete-universe species count mismatch"
        )

    membership_sha = accession_membership_sha256(
        item.accession
        for item in ordered
    )

    if expected_membership_sha256 is not None:
        expected_sha = _lower_sha256(
            expected_membership_sha256,
            label="expected complete-universe membership SHA256",
        )

        if membership_sha != expected_sha:
            raise HoldoutError(
                "complete-universe membership SHA256 mismatch"
            )

    return ordered


def derive_external_holdout(
    complete_universe: Iterable[CompleteUniverseMember],
    reconstructed_absent_accessions: Iterable[str],
) -> tuple[HoldoutMember, ...]:
    """Intersect the frozen complete universe with reconstructed absence."""

    universe = validate_complete_universe(
        complete_universe
    )

    absent = canonical_accession_set(
        reconstructed_absent_accessions,
        label="reconstructed absent membership",
    )

    holdout = tuple(
        HoldoutMember(
            accession=item.accession,
            species_taxid=item.species_taxid,
        )
        for item in universe
        if item.accession in absent
    )

    if any(
        item.accession not in absent
        for item in holdout
    ):
        raise HoldoutError(
            "holdout contains accession absent from reconstructed membership"
        )

    universe_map = {
        item.accession:
            item.species_taxid
        for item in universe
    }

    for item in holdout:
        if universe_map.get(
            item.accession
        ) != item.species_taxid:
            raise HoldoutError(
                "holdout species TaxID differs from complete universe"
            )

    return holdout


def holdout_membership_sha256(
    holdout: Iterable[HoldoutMember],
) -> str:
    """Return the frozen accession membership fingerprint for a holdout."""

    validated = validate_holdout(
        holdout
    )

    return accession_membership_sha256(
        item.accession
        for item in validated
    )


def validate_holdout(
    holdout: Iterable[HoldoutMember],
) -> tuple[HoldoutMember, ...]:
    """Validate and deterministically order one external holdout."""

    by_accession: dict[
        str,
        HoldoutMember
    ] = {}

    for item in holdout:
        if not isinstance(
            item,
            HoldoutMember,
        ):
            raise HoldoutError(
                "unexpected holdout member type"
            )

        accession = _canonical_accession(
            item.accession,
            label="holdout accession",
        )

        species_taxid = _positive_taxid(
            item.species_taxid,
            label="holdout species TaxID",
        )

        if accession in by_accession:
            raise HoldoutError(
                "duplicate holdout accession"
            )

        by_accession[
            accession
        ] = HoldoutMember(
            accession=accession,
            species_taxid=species_taxid,
        )

    return tuple(
        by_accession[
            accession
        ]
        for accession in sorted(
            by_accession
        )
    )


def summarize_holdout(
    holdout: Iterable[HoldoutMember],
) -> HoldoutSummary:
    """Return aggregate-only holdout accounting."""

    validated = validate_holdout(
        holdout
    )

    membership_sha = accession_membership_sha256(
        item.accession
        for item in validated
    )

    return HoldoutSummary(
        genome_count=len(
            validated
        ),
        distinct_species_count=len(
            {
                item.species_taxid
                for item in validated
            }
        ),
        membership_sha256=membership_sha,
    )


def evaluate_adequacy(
    holdout: Iterable[HoldoutMember],
    *,
    minimum_genomes: int = ADEQUACY_MIN_GENOMES,
    minimum_species: int = ADEQUACY_MIN_SPECIES,
) -> AdequacyResult:
    """Evaluate the already-frozen selector-v1 holdout adequacy gate."""

    if (
        not isinstance(
            minimum_genomes,
            int,
        )
        or isinstance(
            minimum_genomes,
            bool,
        )
        or minimum_genomes <= 0
    ):
        raise HoldoutError(
            "minimum genome threshold must be a positive integer"
        )

    if (
        not isinstance(
            minimum_species,
            int,
        )
        or isinstance(
            minimum_species,
            bool,
        )
        or minimum_species <= 0
    ):
        raise HoldoutError(
            "minimum species threshold must be a positive integer"
        )

    summary = summarize_holdout(
        holdout
    )

    passed = (
        summary.genome_count
        >= minimum_genomes
        and summary.distinct_species_count
        >= minimum_species
    )

    return AdequacyResult(
        status=(
            ADEQUACY_PASS
            if passed
            else ADEQUACY_FAIL
        ),
        genome_count=summary.genome_count,
        distinct_species_count=(
            summary.distinct_species_count
        ),
        minimum_genomes=minimum_genomes,
        minimum_species=minimum_species,
    )


def reconstructed_absence_rows(
    reconstruction: HistoricalReconstruction,
) -> tuple[Mapping[str, object], ...]:
    """Serialize reconstructed absence membership deterministically."""

    if not isinstance(
        reconstruction,
        HistoricalReconstruction,
    ):
        raise HoldoutError(
            "unexpected historical reconstruction type"
        )

    accessions = canonical_accession_set(
        reconstruction.retained_absent_from_baseline,
        label="reconstructed absence rows",
    )

    expected_sha = _lower_sha256(
        reconstruction.membership_sha256,
        label="reconstructed absence membership SHA256",
    )

    observed_sha = accession_membership_sha256(
        accessions
    )

    if observed_sha != expected_sha:
        raise HoldoutError(
            "reconstructed absence membership fingerprint mismatch"
        )

    return tuple(
        {
            "canonical_genbank_assembly_accession":
                accession,
        }
        for accession in sorted(
            accessions
        )
    )


def external_holdout_rows(
    holdout: Iterable[HoldoutMember],
) -> tuple[Mapping[str, object], ...]:
    """Serialize the external decision holdout deterministically."""

    validated = validate_holdout(
        holdout
    )

    return tuple(
        {
            "canonical_genbank_assembly_accession":
                item.accession,
            "species_taxid":
                str(
                    item.species_taxid
                ),
        }
        for item in validated
    )
