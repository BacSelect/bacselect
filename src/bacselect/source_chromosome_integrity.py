"""Chromosome-integrity primitives for BacSelect selector-v1.

This module implements the prospectively frozen chromosome-integrity trigger,
closure predicate, and historical-adjudication reuse semantics.

It performs no file I/O, network access, historical-artifact lookup,
structural-feature calculation, or selector-outcome calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence


PASS = "PASS"
EXCLUDE = "EXCLUDE_SOURCE_REPLICON_INTEGRITY"
UNRESOLVED = "REVIEW_UNRESOLVED"

HISTORICAL_RETAIN = "RETAIN_CONFIRMED_MULTIPARTITE"
HISTORICAL_EXCLUDE = "EXCLUDE_FRAGMENTED_CHROMOSOME_SET"
HISTORICAL_UNRESOLVED = "UNRESOLVED"

VALID_HISTORICAL_OUTCOMES = frozenset(
    {
        HISTORICAL_RETAIN,
        HISTORICAL_EXCLUDE,
        HISTORICAL_UNRESOLVED,
    }
)

VALID_CACHE_STATES = frozenset(
    {
        "pass",
        "fallback_to_fresh",
    }
)

GCA_ACCESSION_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

COMPLETE_WORD_RE = re.compile(
    r"\bcomplete\b",
    flags=re.IGNORECASE,
)


class ChromosomeIntegrityError(ValueError):
    """Raised when chromosome-integrity evidence is malformed."""


@dataclass(frozen=True)
class PrimaryComponentEvidence:
    """Relevant evidence for one Primary Assembly component."""

    molecule_class: str
    topology: str
    definition: str


@dataclass(frozen=True)
class TriggerAssessment:
    """Deterministic chromosome-integrity trigger assessment."""

    triggered: bool
    chromosome_component_count: int
    closure_supported_chromosome_count: int
    closure_unsupported_chromosome_count: int


@dataclass(frozen=True)
class HistoricalReuseEvidence:
    """Evidence required for exact Project Finch adjudication reuse."""

    uses_historical_project_finch_package: bool
    cache_content_verification: str | None
    adjudication_accession: str | None
    adjudication_outcome: str | None


@dataclass(frozen=True)
class ChromosomeIntegrityDecision:
    """Outcome of the BacSelect chromosome-integrity layer."""

    status: str
    reason: str
    triggered: bool
    historical_adjudication_reused: bool


def _nonempty_text(
    value: object,
    *,
    label: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ChromosomeIntegrityError(
            f"{label} must be a string"
        )

    cleaned = value.strip()

    if not cleaned:
        raise ChromosomeIntegrityError(
            f"{label} must not be empty"
        )

    return cleaned


def _canonical_accession(
    accession: object,
    *,
    label: str,
) -> str:
    cleaned = _nonempty_text(
        accession,
        label=label,
    )

    if not GCA_ACCESSION_RE.fullmatch(
        cleaned
    ):
        raise ChromosomeIntegrityError(
            f"{label} is not a canonical versioned GCA accession"
        )

    return cleaned


def closure_supported(
    topology: str,
    definition: str,
) -> bool:
    """Return whether frozen BacSelect closure evidence is present.

    Closure evidence is present when topology is circular or the GenBank
    definition contains the standalone word ``complete``, case-insensitively.

    Substrings within another word, including ``incomplete`` and
    ``incompletely``, do not qualify.
    """

    clean_topology = _nonempty_text(
        topology,
        label="GenBank topology",
    ).lower()

    clean_definition = _nonempty_text(
        definition,
        label="GenBank definition",
    )

    return (
        clean_topology == "circular"
        or COMPLETE_WORD_RE.search(
            clean_definition
        )
        is not None
    )


def assess_trigger(
    components: Sequence[
        PrimaryComponentEvidence
    ],
) -> TriggerAssessment:
    """Assess the frozen chromosome-integrity review trigger."""

    if isinstance(
        components,
        (
            str,
            bytes,
        ),
    ):
        raise ChromosomeIntegrityError(
            "components must be a sequence of component evidence"
        )

    if not components:
        raise ChromosomeIntegrityError(
            "Primary Assembly component evidence must not be empty"
        )

    chromosome_count = 0
    supported_count = 0
    unsupported_count = 0

    for index, component in enumerate(
        components,
        start=1,
    ):
        if not isinstance(
            component,
            PrimaryComponentEvidence,
        ):
            raise ChromosomeIntegrityError(
                f"component {index} has unexpected type"
            )

        molecule_class = _nonempty_text(
            component.molecule_class,
            label=f"component {index} molecule class",
        )

        if molecule_class != "Chromosome":
            continue

        chromosome_count += 1

        if closure_supported(
            component.topology,
            component.definition,
        ):
            supported_count += 1
        else:
            unsupported_count += 1

    triggered = (
        chromosome_count >= 2
        and unsupported_count >= 1
    )

    return TriggerAssessment(
        triggered=triggered,
        chromosome_component_count=chromosome_count,
        closure_supported_chromosome_count=supported_count,
        closure_unsupported_chromosome_count=unsupported_count,
    )


def _unresolved(
    *,
    reason: str,
) -> ChromosomeIntegrityDecision:
    return ChromosomeIntegrityDecision(
        status=UNRESOLVED,
        reason=reason,
        triggered=True,
        historical_adjudication_reused=False,
    )


def evaluate(
    *,
    accession: str,
    components: Sequence[
        PrimaryComponentEvidence
    ],
    historical: HistoricalReuseEvidence | None = None,
) -> ChromosomeIntegrityDecision:
    """Evaluate one candidate under the frozen BacSelect rule.

    Triggering is assessed before any historical adjudication evidence is
    consulted. Non-triggered candidates therefore pass without historical
    manual adjudication.
    """

    current_accession = _canonical_accession(
        accession,
        label="current accession",
    )

    trigger = assess_trigger(
        components
    )

    if not trigger.triggered:
        return ChromosomeIntegrityDecision(
            status=PASS,
            reason="NO_CHROMOSOME_INTEGRITY_TRIGGER",
            triggered=False,
            historical_adjudication_reused=False,
        )

    if historical is None:
        return _unresolved(
            reason="NO_REUSABLE_HISTORICAL_ADJUDICATION"
        )

    if not isinstance(
        historical,
        HistoricalReuseEvidence,
    ):
        raise ChromosomeIntegrityError(
            "historical reuse evidence has unexpected type"
        )

    if not isinstance(
        historical.uses_historical_project_finch_package,
        bool,
    ):
        raise ChromosomeIntegrityError(
            "historical package flag must be boolean"
        )

    if not historical.uses_historical_project_finch_package:
        return _unresolved(
            reason="NOT_HISTORICAL_PROJECT_FINCH_PACKAGE"
        )

    cache_state = _nonempty_text(
        historical.cache_content_verification,
        label="cache content verification",
    )

    if cache_state not in VALID_CACHE_STATES:
        raise ChromosomeIntegrityError(
            "unknown cache content verification state"
        )

    if cache_state != "pass":
        return _unresolved(
            reason="HISTORICAL_CACHE_NOT_VERIFIED"
        )

    adjudication_accession = (
        historical.adjudication_accession
    )

    adjudication_outcome = (
        historical.adjudication_outcome
    )

    if (
        adjudication_accession is None
        and adjudication_outcome is None
    ):
        return _unresolved(
            reason="HISTORICAL_ADJUDICATION_ABSENT"
        )

    if (
        adjudication_accession is None
        or adjudication_outcome is None
    ):
        raise ChromosomeIntegrityError(
            "historical adjudication evidence is incomplete"
        )

    historical_accession = _canonical_accession(
        adjudication_accession,
        label="historical adjudication accession",
    )

    if historical_accession != current_accession:
        return _unresolved(
            reason="HISTORICAL_ACCESSION_MISMATCH"
        )

    outcome = _nonempty_text(
        adjudication_outcome,
        label="historical adjudication outcome",
    )

    if outcome not in VALID_HISTORICAL_OUTCOMES:
        raise ChromosomeIntegrityError(
            "unknown historical adjudication outcome"
        )

    if outcome == HISTORICAL_RETAIN:
        return ChromosomeIntegrityDecision(
            status=PASS,
            reason="HISTORICAL_RETAIN_CONFIRMED_MULTIPARTITE",
            triggered=True,
            historical_adjudication_reused=True,
        )

    if outcome == HISTORICAL_EXCLUDE:
        return ChromosomeIntegrityDecision(
            status=EXCLUDE,
            reason="HISTORICAL_FRAGMENTED_CHROMOSOME_SET",
            triggered=True,
            historical_adjudication_reused=True,
        )

    if outcome == HISTORICAL_UNRESOLVED:
        return ChromosomeIntegrityDecision(
            status=UNRESOLVED,
            reason="HISTORICAL_UNRESOLVED",
            triggered=True,
            historical_adjudication_reused=True,
        )

    raise AssertionError(
        "unreachable historical adjudication outcome"
    )
