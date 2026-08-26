"""Pure post-sequence eligibility composition for BacSelect selector-v1.

The execution order is prospectively frozen as:

    source truth
    -> repeated-BioSample reconciliation
    -> chromosome integrity
    -> taxonomy
    -> eligible

This module performs no file I/O, network access, historical-artifact lookup,
taxonomy acquisition, structural-feature calculation, or selector-outcome
calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, Sequence

from bacselect import source_chromosome_integrity
from bacselect import source_truth


ELIGIBLE = "ELIGIBLE"
EXCLUDED = "EXCLUDED"
WITHHELD_UNRESOLVED = "WITHHELD_UNRESOLVED"
NONREPRESENTATIVE = "NONREPRESENTATIVE"

SOURCE_TRUTH_LAYER = "source_truth"
REPEATED_BIOSAMPLE_LAYER = "repeated_biosample"
CHROMOSOME_INTEGRITY_LAYER = "chromosome_integrity"
TAXONOMY_LAYER = "taxonomy"
ELIGIBLE_LAYER = "eligible"

BIOSAMPLE_CONTINUE = "CONTINUE"
BIOSAMPLE_NONREPRESENTATIVE = "NONREPRESENTATIVE"
BIOSAMPLE_UNRESOLVED = "REVIEW_UNRESOLVED"
BIOSAMPLE_NOT_APPLICABLE = "NOT_APPLICABLE"

TAXONOMY_PASS = "PASS"
TAXONOMY_UNRESOLVED = "REVIEW_UNRESOLVED"

GCA_ACCESSION_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

NORMALIZE_STATUSES = frozenset(
    {
        "PASS",
        "MERGED_CYCLE",
        "DELETED",
        "MISSING",
    }
)

SPECIES_STATUSES = frozenset(
    {
        "PASS",
        "LINEAGE_CYCLE",
        "MISSING_NODE",
        "NO_SPECIES_ANCESTOR",
    }
)


class CompositionError(ValueError):
    """Raised when post-sequence composition evidence is malformed."""


class TaxonomyResolver(Protocol):
    """Minimal frozen taxonomy interface consumed by this module."""

    def normalize(
        self,
        taxid: int,
    ) -> tuple[
        int | None,
        str,
        int,
    ]:
        ...

    def species_ancestor(
        self,
        taxid: int,
    ) -> tuple[
        int | None,
        str,
    ]:
        ...


@dataclass(frozen=True)
class BioSampleMember:
    """Evidence needed for prospective repeated-BioSample reconciliation."""

    accession: str
    biosample: str
    source_truth_status: str
    assembly_fingerprint: str | None


@dataclass(frozen=True)
class BioSampleDecision:
    """Repeated-BioSample decision for one candidate."""

    status: str
    reason: str


@dataclass(frozen=True)
class TaxonomyDecision:
    """Candidate-level species-taxonomy resolution result."""

    status: str
    reason: str
    normalized_taxid: int | None
    species_taxid: int | None


@dataclass(frozen=True)
class CompositionDecision:
    """Terminal post-sequence eligibility result for one candidate."""

    disposition: str
    terminal_layer: str
    terminal_status: str
    reason: str
    species_taxid: int | None


def _nonempty_text(
    value: object,
    *,
    label: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise CompositionError(
            f"{label} must be a string"
        )

    cleaned = value.strip()

    if not cleaned:
        raise CompositionError(
            f"{label} must not be empty"
        )

    return cleaned


def _canonical_accession(
    value: object,
) -> str:
    accession = _nonempty_text(
        value,
        label="canonical accession",
    )

    if not GCA_ACCESSION_RE.fullmatch(
        accession
    ):
        raise CompositionError(
            "canonical accession must be a versioned GCA accession"
        )

    return accession


def _fingerprint(
    value: object,
) -> str:
    fingerprint = _nonempty_text(
        value,
        label="assembly fingerprint",
    )

    if not LOWER_SHA256_RE.fullmatch(
        fingerprint
    ):
        raise CompositionError(
            "assembly fingerprint must be lowercase SHA256"
        )

    return fingerprint


def _positive_taxid(
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
        raise CompositionError(
            f"{label} must be a positive integer"
        )

    return value


def reconcile_repeated_biosamples(
    members: Sequence[
        BioSampleMember
    ],
) -> dict[
    str,
    BioSampleDecision,
]:
    """Reconcile BioSamples after source-truth classification.

    Source-truth terminal candidates never participate in fingerprint
    comparison or representative selection.
    """

    if isinstance(
        members,
        (
            str,
            bytes,
        ),
    ):
        raise CompositionError(
            "members must be a sequence of BioSampleMember records"
        )

    if not members:
        raise CompositionError(
            "members must not be empty"
        )

    decisions: dict[
        str,
        BioSampleDecision,
    ] = {}

    continuing: dict[
        str,
        list[
            tuple[
                str,
                str,
            ]
        ],
    ] = {}

    seen_accessions: set[
        str
    ] = set()

    for index, member in enumerate(
        members,
        start=1,
    ):
        if not isinstance(
            member,
            BioSampleMember,
        ):
            raise CompositionError(
                f"member {index} has unexpected type"
            )

        accession = _canonical_accession(
            member.accession
        )

        if accession in seen_accessions:
            raise CompositionError(
                f"duplicate candidate accession: {accession}"
            )

        seen_accessions.add(
            accession
        )

        biosample = _nonempty_text(
            member.biosample,
            label=f"{accession} BioSample",
        )

        status = _nonempty_text(
            member.source_truth_status,
            label=f"{accession} source-truth status",
        )

        if status == source_truth.EXCLUDE:
            decisions[
                accession
            ] = BioSampleDecision(
                status=BIOSAMPLE_NOT_APPLICABLE,
                reason="SOURCE_TRUTH_EXCLUDED",
            )
            continue

        if status == source_truth.UNRESOLVED:
            decisions[
                accession
            ] = BioSampleDecision(
                status=BIOSAMPLE_NOT_APPLICABLE,
                reason="SOURCE_TRUTH_UNRESOLVED",
            )
            continue

        if status != source_truth.SUITABLE:
            raise CompositionError(
                f"unknown source-truth status: {status}"
            )

        # Fingerprint evidence is deliberately inspected only after
        # source truth has established that the candidate may continue.
        fingerprint = _fingerprint(
            member.assembly_fingerprint
        )

        continuing.setdefault(
            biosample,
            [],
        ).append(
            (
                accession,
                fingerprint,
            )
        )

    for biosample_members in continuing.values():
        if len(
            biosample_members
        ) == 1:
            accession = biosample_members[
                0
            ][0]

            decisions[
                accession
            ] = BioSampleDecision(
                status=BIOSAMPLE_CONTINUE,
                reason="BIOSAMPLE_SINGLETON",
            )

            continue

        fingerprints = {
            fingerprint
            for _, fingerprint in biosample_members
        }

        if len(
            fingerprints
        ) >= 2:
            for accession, _ in biosample_members:
                decisions[
                    accession
                ] = BioSampleDecision(
                    status=BIOSAMPLE_UNRESOLVED,
                    reason="BIOSAMPLE_FINGERPRINTS_DIFFER",
                )

            continue

        representative = min(
            accession
            for accession, _ in biosample_members
        )

        for accession, _ in biosample_members:
            if accession == representative:
                decisions[
                    accession
                ] = BioSampleDecision(
                    status=BIOSAMPLE_CONTINUE,
                    reason=(
                        "BIOSAMPLE_IDENTICAL_REPRESENTATIVE"
                    ),
                )
            else:
                decisions[
                    accession
                ] = BioSampleDecision(
                    status=BIOSAMPLE_NONREPRESENTATIVE,
                    reason=(
                        "BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE"
                    ),
                )

    if set(
        decisions
    ) != seen_accessions:
        raise AssertionError(
            "repeated-BioSample reconciliation did not classify every member"
        )

    return decisions


def resolve_taxonomy(
    taxonomy: TaxonomyResolver,
    organism_taxid: int,
) -> TaxonomyDecision:
    """Resolve frozen organism TaxID to the first species ancestor."""

    query_taxid = _positive_taxid(
        organism_taxid,
        label="organism TaxID",
    )

    normalized, normalize_status, _ = taxonomy.normalize(
        query_taxid
    )

    if normalize_status not in NORMALIZE_STATUSES:
        raise CompositionError(
            "unknown taxonomy normalization status"
        )

    if normalize_status != "PASS":
        if normalized is not None:
            raise CompositionError(
                "unresolved taxonomy normalization returned a TaxID"
            )

        return TaxonomyDecision(
            status=TAXONOMY_UNRESOLVED,
            reason=(
                "TAXONOMY_NORMALIZE_"
                f"{normalize_status}"
            ),
            normalized_taxid=None,
            species_taxid=None,
        )

    normalized_taxid = _positive_taxid(
        normalized,
        label="normalized TaxID",
    )

    species_taxid, species_status = taxonomy.species_ancestor(
        normalized_taxid
    )

    if species_status not in SPECIES_STATUSES:
        raise CompositionError(
            "unknown species-ancestor status"
        )

    if species_status != "PASS":
        if species_taxid is not None:
            raise CompositionError(
                "unresolved species ancestry returned a TaxID"
            )

        return TaxonomyDecision(
            status=TAXONOMY_UNRESOLVED,
            reason=(
                "TAXONOMY_SPECIES_"
                f"{species_status}"
            ),
            normalized_taxid=normalized_taxid,
            species_taxid=None,
        )

    resolved_species = _positive_taxid(
        species_taxid,
        label="species TaxID",
    )

    return TaxonomyDecision(
        status=TAXONOMY_PASS,
        reason="TAXONOMY_SPECIES_RESOLVED",
        normalized_taxid=normalized_taxid,
        species_taxid=resolved_species,
    )


def compose_candidate(
    *,
    source_truth_status: str,
    source_truth_reason: str,
    biosample: BioSampleDecision | None = None,
    chromosome: (
        source_chromosome_integrity.ChromosomeIntegrityDecision
        | None
    ) = None,
    taxonomy: TaxonomyDecision | None = None,
) -> CompositionDecision:
    """Compose one candidate using the prospectively frozen precedence.

    Evidence belonging to a later layer is not inspected once an earlier
    terminal state has been reached.
    """

    truth_status = _nonempty_text(
        source_truth_status,
        label="source-truth status",
    )

    truth_reason = _nonempty_text(
        source_truth_reason,
        label="source-truth reason",
    )

    if truth_status == source_truth.EXCLUDE:
        return CompositionDecision(
            disposition=EXCLUDED,
            terminal_layer=SOURCE_TRUTH_LAYER,
            terminal_status=truth_status,
            reason=truth_reason,
            species_taxid=None,
        )

    if truth_status == source_truth.UNRESOLVED:
        return CompositionDecision(
            disposition=WITHHELD_UNRESOLVED,
            terminal_layer=SOURCE_TRUTH_LAYER,
            terminal_status=truth_status,
            reason=truth_reason,
            species_taxid=None,
        )

    if truth_status != source_truth.SUITABLE:
        raise CompositionError(
            f"unknown source-truth status: {truth_status}"
        )

    if not isinstance(
        biosample,
        BioSampleDecision,
    ):
        raise CompositionError(
            "continuing candidate requires a BioSample decision"
        )

    biosample_status = _nonempty_text(
        biosample.status,
        label="BioSample status",
    )

    biosample_reason = _nonempty_text(
        biosample.reason,
        label="BioSample reason",
    )

    if biosample_status == BIOSAMPLE_NONREPRESENTATIVE:
        return CompositionDecision(
            disposition=NONREPRESENTATIVE,
            terminal_layer=REPEATED_BIOSAMPLE_LAYER,
            terminal_status=biosample_status,
            reason=biosample_reason,
            species_taxid=None,
        )

    if biosample_status == BIOSAMPLE_UNRESOLVED:
        return CompositionDecision(
            disposition=WITHHELD_UNRESOLVED,
            terminal_layer=REPEATED_BIOSAMPLE_LAYER,
            terminal_status=biosample_status,
            reason=biosample_reason,
            species_taxid=None,
        )

    if biosample_status == BIOSAMPLE_NOT_APPLICABLE:
        raise CompositionError(
            "source-truth-suitable candidate cannot have "
            "NOT_APPLICABLE BioSample status"
        )

    if biosample_status != BIOSAMPLE_CONTINUE:
        raise CompositionError(
            f"unknown BioSample status: {biosample_status}"
        )

    if not isinstance(
        chromosome,
        source_chromosome_integrity.ChromosomeIntegrityDecision,
    ):
        raise CompositionError(
            "continuing candidate requires a chromosome-integrity decision"
        )

    chromosome_status = _nonempty_text(
        chromosome.status,
        label="chromosome-integrity status",
    )

    chromosome_reason = _nonempty_text(
        chromosome.reason,
        label="chromosome-integrity reason",
    )

    if chromosome_status == source_chromosome_integrity.EXCLUDE:
        return CompositionDecision(
            disposition=EXCLUDED,
            terminal_layer=CHROMOSOME_INTEGRITY_LAYER,
            terminal_status=chromosome_status,
            reason=chromosome_reason,
            species_taxid=None,
        )

    if chromosome_status == source_chromosome_integrity.UNRESOLVED:
        return CompositionDecision(
            disposition=WITHHELD_UNRESOLVED,
            terminal_layer=CHROMOSOME_INTEGRITY_LAYER,
            terminal_status=chromosome_status,
            reason=chromosome_reason,
            species_taxid=None,
        )

    if chromosome_status != source_chromosome_integrity.PASS:
        raise CompositionError(
            "unknown chromosome-integrity status"
        )

    if not isinstance(
        taxonomy,
        TaxonomyDecision,
    ):
        raise CompositionError(
            "continuing candidate requires a taxonomy decision"
        )

    taxonomy_status = _nonempty_text(
        taxonomy.status,
        label="taxonomy status",
    )

    taxonomy_reason = _nonempty_text(
        taxonomy.reason,
        label="taxonomy reason",
    )

    if taxonomy_status == TAXONOMY_UNRESOLVED:
        if taxonomy.species_taxid is not None:
            raise CompositionError(
                "unresolved taxonomy decision contains a species TaxID"
            )

        return CompositionDecision(
            disposition=WITHHELD_UNRESOLVED,
            terminal_layer=TAXONOMY_LAYER,
            terminal_status=taxonomy_status,
            reason=taxonomy_reason,
            species_taxid=None,
        )

    if taxonomy_status != TAXONOMY_PASS:
        raise CompositionError(
            f"unknown taxonomy status: {taxonomy_status}"
        )

    species_taxid = _positive_taxid(
        taxonomy.species_taxid,
        label="species TaxID",
    )

    return CompositionDecision(
        disposition=ELIGIBLE,
        terminal_layer=ELIGIBLE_LAYER,
        terminal_status="PASS",
        reason="POST_SEQUENCE_ELIGIBLE",
        species_taxid=species_taxid,
    )
