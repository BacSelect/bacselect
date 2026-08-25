"""Frozen BacSelect source-metadata eligibility helpers.

This module implements only the metadata layer of the prospectively frozen
BacSelect selector-v1 source eligibility procedure. Sequence, repeated-
BioSample, source-truth, taxonomy, and selector-outcome stages remain separate.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Iterable, Iterator, Mapping, Sequence


DATASETS_VERSION = "18.35.0"
ASCII_WHITESPACE = " \t\n\r\v\f"

CANONICAL_GCA_RE = re.compile(r"^GCA_[0-9]+\.[0-9]+$")
BIOSAMPLE_RE = re.compile(
    r"^(?:SAMN[0-9]+|SAMEA[0-9]+|SAMD[0-9]+)$"
)

AUTOMATIC_WARNING_EXCLUSIONS = frozenset(
    {
        "chimeric",
        "contaminated",
        "mixed culture",
    }
)

DISCOVERY_ARGS = (
    "summary",
    "genome",
    "taxon",
    "2",
    "--assembly-source",
    "GenBank",
    "--assembly-level",
    "complete",
    "--assembly-version",
    "current",
    "--mag",
    "exclude",
    "--exclude-multi-isolate",
    "--limit",
    "all",
    "--as-json-lines",
)

RETAIN = "RETAIN_METADATA"
EXCLUDE = "EXCLUDE_METADATA"
WITHHOLD = "WITHHOLD_UNRESOLVED"


@dataclass(frozen=True)
class MetadataAssessment:
    """Deterministic metadata-only assessment of one NCBI assembly record."""

    accession: str
    biosample: str | None
    decision: str
    reasons: tuple[str, ...]
    normalized_warnings: tuple[str, ...]


def normalize_warning(value: object) -> str:
    """Normalize one frozen NCBI atypical warning exactly as specified."""

    if not isinstance(value, str):
        raise ValueError("atypical warning must be a string")

    return value.strip(ASCII_WHITESPACE).casefold()


def validate_datasets_version_text(
    text: str,
    expected: str = DATASETS_VERSION,
) -> None:
    """Fail unless Datasets version output reports the frozen version."""

    marker = f"datasets version: {expected}"

    if marker not in text.splitlines():
        raise ValueError(
            f"expected NCBI Datasets {expected}; observed {text!r}"
        )


def validate_discovery_args(args: Sequence[str]) -> None:
    """Fail unless the scientific discovery arguments are exactly frozen."""

    observed = tuple(args)

    if observed != DISCOVERY_ARGS:
        raise ValueError(
            "NCBI Datasets discovery arguments differ from frozen method"
        )


def _mapping(
    value: object,
    *,
    field: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")

    return value


def assess_summary_record(
    record: Mapping[str, object],
) -> MetadataAssessment:
    """Assess the metadata-visible eligibility of one summary JSONL record.

    This function deliberately does not decide sequence eligibility, repeated
    BioSample reconciliation, source structural integrity, taxonomy resolution,
    baseline membership, or selector coverage.
    """

    if not isinstance(record, Mapping):
        raise TypeError("record must be a mapping")

    accession_obj = record.get("accession")
    accession = accession_obj if isinstance(accession_obj, str) else ""

    exclude_reasons: list[str] = []
    unresolved_reasons: list[str] = []

    if not CANONICAL_GCA_RE.fullmatch(accession):
        exclude_reasons.append("invalid_canonical_GCA_accession")

    current = record.get("current_accession")
    if current != accession:
        exclude_reasons.append("current_accession_mismatch")

    if record.get("source_database") != "SOURCE_DATABASE_GENBANK":
        exclude_reasons.append("source_database_not_GenBank")

    assembly_info_obj = record.get("assembly_info")
    if not isinstance(assembly_info_obj, Mapping):
        return MetadataAssessment(
            accession=accession,
            biosample=None,
            decision=WITHHOLD,
            reasons=("assembly_info_missing_or_malformed",),
            normalized_warnings=(),
        )

    assembly_info = assembly_info_obj

    if assembly_info.get("assembly_status") != "current":
        exclude_reasons.append("assembly_status_not_current")

    if assembly_info.get("assembly_level") != "Complete Genome":
        exclude_reasons.append("assembly_level_not_Complete_Genome")

    biosample: str | None = None
    biosample_obj = assembly_info.get("biosample")

    if not isinstance(biosample_obj, Mapping):
        exclude_reasons.append("biosample_object_missing_or_malformed")
    else:
        accession_value = biosample_obj.get("accession")

        if (
            isinstance(accession_value, str)
            and BIOSAMPLE_RE.fullmatch(accession_value)
        ):
            biosample = accession_value
        else:
            exclude_reasons.append("biosample_accession_missing_or_malformed")

    normalized_warnings: list[str] = []
    atypical_obj = assembly_info.get("atypical")

    if atypical_obj is not None:
        if not isinstance(atypical_obj, Mapping):
            unresolved_reasons.append("atypical_object_malformed")
        else:
            warnings_obj = atypical_obj.get("warnings", [])

            if warnings_obj is None:
                warnings_obj = []

            if not isinstance(warnings_obj, list):
                unresolved_reasons.append("atypical_warnings_not_list")
            else:
                for warning in warnings_obj:
                    try:
                        normalized = normalize_warning(warning)
                    except ValueError:
                        unresolved_reasons.append(
                            "atypical_warning_non_string"
                        )
                        continue

                    normalized_warnings.append(normalized)

                    if normalized in AUTOMATIC_WARNING_EXCLUSIONS:
                        exclude_reasons.append(
                            f"automatic_atypical_exclusion:{normalized}"
                        )

    reasons = tuple(
        sorted(set(unresolved_reasons + exclude_reasons))
    )

    if unresolved_reasons:
        decision = WITHHOLD
    elif exclude_reasons:
        decision = EXCLUDE
    else:
        decision = RETAIN

    return MetadataAssessment(
        accession=accession,
        biosample=biosample,
        decision=decision,
        reasons=reasons,
        normalized_warnings=tuple(normalized_warnings),
    )


def iter_jsonl_records(path: Path | str) -> Iterator[Mapping[str, object]]:
    """Yield JSON objects from a frozen NCBI JSONL file."""

    source = Path(path)

    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue

            value = json.loads(line)

            if not isinstance(value, Mapping):
                raise ValueError(
                    f"line {line_number}: JSON value must be an object"
                )

            yield value


def assess_records(
    records: Iterable[Mapping[str, object]],
) -> list[MetadataAssessment]:
    """Assess records and fail if canonical accessions are duplicated."""

    assessments: list[MetadataAssessment] = []
    seen: set[str] = set()

    for record in records:
        assessment = assess_summary_record(record)

        if assessment.accession in seen:
            raise ValueError(
                "duplicate canonical accession in source snapshot: "
                f"{assessment.accession}"
            )

        seen.add(assessment.accession)
        assessments.append(assessment)

    return assessments


def blinded_metadata_summary(
    assessments: Iterable[MetadataAssessment],
) -> dict[str, object]:
    """Return aggregate counts without accession or BioSample identities."""

    decision_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    warning_counts: Counter[str] = Counter()
    total = 0

    for assessment in assessments:
        total += 1
        decision_counts[assessment.decision] += 1
        reason_counts.update(assessment.reasons)
        warning_counts.update(assessment.normalized_warnings)

    return {
        "records": total,
        "decision_counts": dict(sorted(decision_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "warning_counts": dict(sorted(warning_counts.items())),
    }
