"""Pure complete-universe composition helpers for BacSelect Stage 5A.

This module operates only on already-derived Stage 1-4 scientific decisions.
It performs no file I/O, baseline lookup, metadata reconstruction, structural
feature calculation, or selector-outcome calculation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping

from bacselect import source_chromosome_integrity
from bacselect import source_truth
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    BIOSAMPLE_NONREPRESENTATIVE,
    BIOSAMPLE_UNRESOLVED,
    CHROMOSOME_INTEGRITY_LAYER,
    ELIGIBLE,
    ELIGIBLE_LAYER,
    EXCLUDED,
    GCA_ACCESSION_RE,
    NONREPRESENTATIVE,
    REPEATED_BIOSAMPLE_LAYER,
    SOURCE_TRUTH_LAYER,
    TAXONOMY_LAYER,
    TAXONOMY_PASS,
    TAXONOMY_UNRESOLVED,
    WITHHELD_UNRESOLVED,
    BioSampleDecision,
    CompositionDecision,
    TaxonomyDecision,
    compose_candidate,
)
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


TERMINAL_COMPOSITION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "final_disposition",
    "terminal_layer",
    "terminal_status",
    "terminal_reason",
    "species_taxid",
)

COMPLETE_UNIVERSE_FIELDS = (
    "canonical_genbank_assembly_accession",
    "species_taxid",
)

ALLOWED_DISPOSITIONS = frozenset(
    {
        ELIGIBLE,
        EXCLUDED,
        WITHHELD_UNRESOLVED,
        NONREPRESENTATIVE,
    }
)

ALLOWED_TERMINAL_LAYERS = frozenset(
    {
        SOURCE_TRUTH_LAYER,
        REPEATED_BIOSAMPLE_LAYER,
        CHROMOSOME_INTEGRITY_LAYER,
        TAXONOMY_LAYER,
        ELIGIBLE_LAYER,
    }
)


class CompleteUniverseError(ValueError):
    """Raised when Stage 5A composition evidence is malformed."""


@dataclass(frozen=True)
class CandidateCompositionInput:
    """One candidate's already-derived Stage 1-4 decision evidence."""

    accession: str
    source_truth_status: str
    source_truth_reason: str
    biosample: BioSampleDecision | None = None
    chromosome: (
        source_chromosome_integrity.ChromosomeIntegrityDecision
        | None
    ) = None
    taxonomy: TaxonomyDecision | None = None


@dataclass(frozen=True)
class TerminalCompositionRecord:
    """One frozen terminal Stage 5A composition record."""

    accession: str
    final_disposition: str
    terminal_layer: str
    terminal_status: str
    terminal_reason: str
    species_taxid: int | None


@dataclass(frozen=True)
class CompleteUniverseRecord:
    """One eligible complete-universe member."""

    accession: str
    species_taxid: int


@dataclass(frozen=True)
class DispositionSummary:
    """Aggregate-only Stage 5A disposition accounting."""

    total: int
    eligible: int
    excluded: int
    withheld_unresolved: int
    nonrepresentative: int

    def as_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "ELIGIBLE": self.eligible,
            "EXCLUDED": self.excluded,
            "WITHHELD_UNRESOLVED": self.withheld_unresolved,
            "NONREPRESENTATIVE": self.nonrepresentative,
        }


def _nonempty_text(
    value: object,
    *,
    label: str,
) -> str:
    if not isinstance(value, str):
        raise CompleteUniverseError(
            f"{label} must be a string"
        )

    cleaned = value.strip()

    if not cleaned:
        raise CompleteUniverseError(
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
        raise CompleteUniverseError(
            "canonical accession must be a versioned GCA accession"
        )

    return accession


def _positive_taxid(
    value: object,
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise CompleteUniverseError(
            "species TaxID must be a positive integer"
        )

    return value


def _validate_terminal_record(
    record: TerminalCompositionRecord,
) -> TerminalCompositionRecord:
    if not isinstance(
        record,
        TerminalCompositionRecord,
    ):
        raise CompleteUniverseError(
            "terminal record has unexpected type"
        )

    accession = _canonical_accession(
        record.accession
    )

    disposition = _nonempty_text(
        record.final_disposition,
        label="final disposition",
    )

    layer = _nonempty_text(
        record.terminal_layer,
        label="terminal layer",
    )

    status = _nonempty_text(
        record.terminal_status,
        label="terminal status",
    )

    reason = _nonempty_text(
        record.terminal_reason,
        label="terminal reason",
    )

    if disposition not in ALLOWED_DISPOSITIONS:
        raise CompleteUniverseError(
            "unknown final disposition"
        )

    if layer not in ALLOWED_TERMINAL_LAYERS:
        raise CompleteUniverseError(
            "unknown terminal layer"
        )

    expected_status: str

    if disposition == ELIGIBLE:
        if layer != ELIGIBLE_LAYER:
            raise CompleteUniverseError(
                "eligible record has unexpected terminal layer"
            )

        expected_status = "PASS"

        if reason != "POST_SEQUENCE_ELIGIBLE":
            raise CompleteUniverseError(
                "eligible record has unexpected terminal reason"
            )

        species_taxid = _positive_taxid(
            record.species_taxid
        )

    else:
        if record.species_taxid is not None:
            raise CompleteUniverseError(
                "non-eligible record contains species TaxID"
            )

        species_taxid = None

        expected_by_state = {
            (
                EXCLUDED,
                SOURCE_TRUTH_LAYER,
            ): source_truth.EXCLUDE,
            (
                EXCLUDED,
                CHROMOSOME_INTEGRITY_LAYER,
            ): source_chromosome_integrity.EXCLUDE,
            (
                WITHHELD_UNRESOLVED,
                SOURCE_TRUTH_LAYER,
            ): source_truth.UNRESOLVED,
            (
                WITHHELD_UNRESOLVED,
                REPEATED_BIOSAMPLE_LAYER,
            ): BIOSAMPLE_UNRESOLVED,
            (
                WITHHELD_UNRESOLVED,
                CHROMOSOME_INTEGRITY_LAYER,
            ): source_chromosome_integrity.UNRESOLVED,
            (
                WITHHELD_UNRESOLVED,
                TAXONOMY_LAYER,
            ): TAXONOMY_UNRESOLVED,
            (
                NONREPRESENTATIVE,
                REPEATED_BIOSAMPLE_LAYER,
            ): BIOSAMPLE_NONREPRESENTATIVE,
        }

        try:
            expected_status = expected_by_state[
                (
                    disposition,
                    layer,
                )
            ]
        except KeyError as exc:
            raise CompleteUniverseError(
                "impossible disposition/terminal-layer combination"
            ) from exc

    if status != expected_status:
        raise CompleteUniverseError(
            "terminal status is inconsistent with final disposition"
        )

    return TerminalCompositionRecord(
        accession=accession,
        final_disposition=disposition,
        terminal_layer=layer,
        terminal_status=status,
        terminal_reason=reason,
        species_taxid=species_taxid,
    )


def compose_terminal_record(
    evidence: CandidateCompositionInput,
) -> TerminalCompositionRecord:
    """Compose one candidate using the frozen post-sequence primitive."""

    if not isinstance(
        evidence,
        CandidateCompositionInput,
    ):
        raise CompleteUniverseError(
            "candidate evidence has unexpected type"
        )

    accession = _canonical_accession(
        evidence.accession
    )

    try:
        decision = compose_candidate(
            source_truth_status=evidence.source_truth_status,
            source_truth_reason=evidence.source_truth_reason,
            biosample=evidence.biosample,
            chromosome=evidence.chromosome,
            taxonomy=evidence.taxonomy,
        )
    except ValueError as exc:
        raise CompleteUniverseError(
            "candidate composition failed validation"
        ) from exc

    if not isinstance(
        decision,
        CompositionDecision,
    ):
        raise CompleteUniverseError(
            "composition primitive returned unexpected type"
        )

    return _validate_terminal_record(
        TerminalCompositionRecord(
            accession=accession,
            final_disposition=decision.disposition,
            terminal_layer=decision.terminal_layer,
            terminal_status=decision.terminal_status,
            terminal_reason=decision.reason,
            species_taxid=decision.species_taxid,
        )
    )


def finalize_terminal_composition(
    evidence: Iterable[CandidateCompositionInput],
) -> tuple[TerminalCompositionRecord, ...]:
    """Compose, validate, uniquely key, and sort candidate records."""

    records: list[
        TerminalCompositionRecord
    ] = []

    seen: set[str] = set()

    for item in evidence:
        record = compose_terminal_record(
            item
        )

        if record.accession in seen:
            raise CompleteUniverseError(
                "duplicate candidate accession"
            )

        seen.add(
            record.accession
        )

        records.append(
            record
        )

    return tuple(
        sorted(
            records,
            key=lambda item: item.accession,
        )
    )


def validate_terminal_composition(
    records: Iterable[
        TerminalCompositionRecord
    ],
) -> tuple[
    TerminalCompositionRecord,
    ...,
]:
    """Validate a terminal composition without recomposing it."""

    normalized: list[
        TerminalCompositionRecord
    ] = []

    seen: set[str] = set()

    for item in records:
        record = _validate_terminal_record(
            item
        )

        if record.accession in seen:
            raise CompleteUniverseError(
                "duplicate candidate accession"
            )

        seen.add(
            record.accession
        )

        normalized.append(
            record
        )

    return tuple(
        sorted(
            normalized,
            key=lambda item: item.accession,
        )
    )


def disposition_summary(
    records: Iterable[
        TerminalCompositionRecord
    ],
) -> DispositionSummary:
    """Return identity-safe aggregate disposition counts."""

    normalized = validate_terminal_composition(
        records
    )

    counts = Counter(
        record.final_disposition
        for record in normalized
    )

    return DispositionSummary(
        total=len(normalized),
        eligible=counts[ELIGIBLE],
        excluded=counts[EXCLUDED],
        withheld_unresolved=counts[
            WITHHELD_UNRESOLVED
        ],
        nonrepresentative=counts[
            NONREPRESENTATIVE
        ],
    )


def require_expected_accounting(
    summary: DispositionSummary,
    *,
    expected_total: int,
    expected_eligible: int,
    expected_excluded: int,
    expected_withheld_unresolved: int,
    expected_nonrepresentative: int,
) -> None:
    """Fail unless Stage 5A aggregate accounting is exactly expected."""

    if not isinstance(
        summary,
        DispositionSummary,
    ):
        raise CompleteUniverseError(
            "disposition summary has unexpected type"
        )

    expected = {
        "total": expected_total,
        "ELIGIBLE": expected_eligible,
        "EXCLUDED": expected_excluded,
        "WITHHELD_UNRESOLVED":
            expected_withheld_unresolved,
        "NONREPRESENTATIVE":
            expected_nonrepresentative,
    }

    for label, value in expected.items():
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
        ):
            raise CompleteUniverseError(
                f"expected {label} count must be a non-negative integer"
            )

    if (
        expected_eligible
        + expected_excluded
        + expected_withheld_unresolved
        + expected_nonrepresentative
        != expected_total
    ):
        raise CompleteUniverseError(
            "expected disposition accounting does not close"
        )

    if summary.as_dict() != expected:
        raise CompleteUniverseError(
            "observed disposition accounting differs from frozen expectation"
        )


def derive_complete_universe(
    records: Iterable[
        TerminalCompositionRecord
    ],
) -> tuple[
    CompleteUniverseRecord,
    ...,
]:
    """Derive the complete eligible fresh universe only from ELIGIBLE rows."""

    normalized = validate_terminal_composition(
        records
    )

    universe = tuple(
        CompleteUniverseRecord(
            accession=record.accession,
            species_taxid=_positive_taxid(
                record.species_taxid
            ),
        )
        for record in normalized
        if record.final_disposition == ELIGIBLE
    )

    if len(
        universe
    ) != len(
        {
            record.accession
            for record in universe
        }
    ):
        raise CompleteUniverseError(
            "complete universe contains duplicate accession"
        )

    return universe


def require_complete_universe(
    universe: Iterable[
        CompleteUniverseRecord
    ],
    *,
    expected_count: int,
    expected_species_count: int,
) -> tuple[
    CompleteUniverseRecord,
    ...,
]:
    """Validate exact eligible-universe count, taxonomy, order, and uniqueness."""

    if (
        not isinstance(expected_count, int)
        or isinstance(expected_count, bool)
        or expected_count < 0
    ):
        raise CompleteUniverseError(
            "expected universe count must be a non-negative integer"
        )

    if (
        not isinstance(expected_species_count, int)
        or isinstance(expected_species_count, bool)
        or expected_species_count < 0
    ):
        raise CompleteUniverseError(
            "expected species count must be a non-negative integer"
        )

    normalized: list[
        CompleteUniverseRecord
    ] = []

    seen: set[str] = set()

    for item in universe:
        if not isinstance(
            item,
            CompleteUniverseRecord,
        ):
            raise CompleteUniverseError(
                "complete-universe record has unexpected type"
            )

        accession = _canonical_accession(
            item.accession
        )

        species_taxid = _positive_taxid(
            item.species_taxid
        )

        if accession in seen:
            raise CompleteUniverseError(
                "complete universe contains duplicate accession"
            )

        seen.add(
            accession
        )

        normalized.append(
            CompleteUniverseRecord(
                accession=accession,
                species_taxid=species_taxid,
            )
        )

    ordered = tuple(
        sorted(
            normalized,
            key=lambda item: item.accession,
        )
    )

    if len(ordered) != expected_count:
        raise CompleteUniverseError(
            "complete-universe count differs from frozen expectation"
        )

    species_count = len(
        {
            item.species_taxid
            for item in ordered
        }
    )

    if species_count != expected_species_count:
        raise CompleteUniverseError(
            "complete-universe species count differs from frozen expectation"
        )

    return ordered


def complete_universe_membership_sha256(
    universe: Iterable[
        CompleteUniverseRecord
    ],
) -> str:
    """Hash exact complete-universe accession membership."""

    records = tuple(
        universe
    )

    return accession_membership_sha256(
        record.accession
        for record in records
    )


def terminal_composition_rows(
    records: Iterable[
        TerminalCompositionRecord
    ],
) -> tuple[
    Mapping[str, str],
    ...,
]:
    """Return deterministic TSV-ready terminal-composition rows."""

    normalized = validate_terminal_composition(
        records
    )

    return tuple(
        {
            "canonical_genbank_assembly_accession":
                record.accession,
            "final_disposition":
                record.final_disposition,
            "terminal_layer":
                record.terminal_layer,
            "terminal_status":
                record.terminal_status,
            "terminal_reason":
                record.terminal_reason,
            "species_taxid":
                (
                    ""
                    if record.species_taxid is None
                    else str(record.species_taxid)
                ),
        }
        for record in normalized
    )


def complete_universe_rows(
    universe: Iterable[
        CompleteUniverseRecord
    ],
) -> tuple[
    Mapping[str, str],
    ...,
]:
    """Return deterministic TSV-ready complete-universe rows."""

    normalized: list[
        CompleteUniverseRecord
    ] = []

    seen: set[str] = set()

    for item in universe:
        if not isinstance(
            item,
            CompleteUniverseRecord,
        ):
            raise CompleteUniverseError(
                "complete-universe record has unexpected type"
            )

        accession = _canonical_accession(
            item.accession
        )

        species_taxid = _positive_taxid(
            item.species_taxid
        )

        if accession in seen:
            raise CompleteUniverseError(
                "complete universe contains duplicate accession"
            )

        seen.add(
            accession
        )

        normalized.append(
            CompleteUniverseRecord(
                accession=accession,
                species_taxid=species_taxid,
            )
        )

    ordered = tuple(
        sorted(
            normalized,
            key=lambda item: item.accession,
        )
    )

    return tuple(
        {
            "canonical_genbank_assembly_accession":
                record.accession,
            "species_taxid":
                str(record.species_taxid),
        }
        for record in ordered
    )
