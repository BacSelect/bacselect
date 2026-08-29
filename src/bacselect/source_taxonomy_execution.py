"""Evidence-bound taxonomy execution helpers for BacSelect Stage 4.

This module adds no taxonomy scientific decision rule.

It verifies and filters a frozen Stage 3 decision table, reconstructs the
canonical assembly-accession to organism-TaxID mapping from a verified frozen
NCBI source JSONL, and delegates species resolution to the already-frozen
BacSelect taxonomy composition primitive.

Production provenance, scratch output, content manifests and atomic
finalization belong to the separately frozen Stage 4 production wrapper.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
import csv
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from bacselect import source_chromosome_integrity
from bacselect.source_eligibility import (
    CANONICAL_GCA_RE,
    iter_jsonl_records,
)
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    CompositionError,
    TAXONOMY_PASS,
    TAXONOMY_UNRESOLVED,
    TaxonomyDecision,
    TaxonomyResolver,
    resolve_taxonomy,
)
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


LOWER_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

STAGE3_DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "source_evidence_sha256",
    "stage2_status",
    "chromosome_component_count",
    "closure_supported_chromosome_count",
    "closure_unsupported_chromosome_count",
    "chromosome_integrity_triggered",
    "historical_adjudication_reused",
    "stage3_status",
    "stage3_reason",
)

STAGE4_DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "organism_taxid",
    "normalized_organism_taxid",
    "species_taxid",
    "stage4_status",
    "stage4_reason",
)

STAGE3_ALLOWED_STATUSES = frozenset(
    {
        source_chromosome_integrity.PASS,
        source_chromosome_integrity.EXCLUDE,
        source_chromosome_integrity.UNRESOLVED,
    }
)

NORMALIZATION_UNRESOLVED_REASONS = frozenset(
    {
        "TAXONOMY_NORMALIZE_MERGED_CYCLE",
        "TAXONOMY_NORMALIZE_DELETED",
        "TAXONOMY_NORMALIZE_MISSING",
    }
)

SPECIES_UNRESOLVED_REASONS = frozenset(
    {
        "TAXONOMY_SPECIES_LINEAGE_CYCLE",
        "TAXONOMY_SPECIES_MISSING_NODE",
        "TAXONOMY_SPECIES_NO_SPECIES_ANCESTOR",
    }
)

ALL_UNRESOLVED_REASONS = (
    NORMALIZATION_UNRESOLVED_REASONS
    | SPECIES_UNRESOLVED_REASONS
)


class Stage4ExecutionError(RuntimeError):
    """Raised when frozen Stage 4 execution evidence is inconsistent."""


@dataclass(frozen=True)
class Stage3Population:
    """Verified Stage 3 population and exact Stage 4 PASS membership."""

    all_accessions: tuple[str, ...]
    pass_accessions: tuple[str, ...]
    all_membership_sha256: str
    pass_membership_sha256: str
    status_counts: Mapping[str, int]
    reason_counts: Mapping[str, int]
    decision_artifact_sha256: str


@dataclass(frozen=True)
class SourceTaxidBundle:
    """Verified source TaxIDs for exactly the Stage 4 candidate membership."""

    taxid_by_accession: Mapping[str, int]
    source_record_count: int
    source_sha256: str
    unique_selected_taxid_count: int


@dataclass(frozen=True)
class Stage4CandidateEvaluation:
    """One candidate bound to its frozen source TaxID and taxonomy decision."""

    accession: str
    organism_taxid: int
    decision: TaxonomyDecision


@dataclass(frozen=True)
class Stage4DecisionBuild:
    """Deterministic Stage 4 rows plus non-identity-bearing aggregates."""

    rows: tuple[dict[str, str], ...]
    status_counts: Mapping[str, int]
    reason_counts: Mapping[str, int]
    unique_organism_taxid_count: int
    resolved_distinct_species_taxid_count: int


def sha256_file(
    path: Path,
    block_size: int = 8 * 1024 * 1024,
) -> str:
    """Return streaming SHA256 for one regular file."""

    source = Path(path)

    if (
        not source.is_file()
        or source.is_symlink()
    ):
        raise Stage4ExecutionError(
            "required regular file missing"
        )

    digest = hashlib.sha256()

    with source.open(
        "rb"
    ) as handle:
        for block in iter(
            lambda: handle.read(block_size),
            b"",
        ):
            digest.update(
                block
            )

    return digest.hexdigest()


def _lower_sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or LOWER_SHA256_RE.fullmatch(value) is None
    ):
        raise Stage4ExecutionError(
            f"{label} must be lowercase SHA256"
        )

    return value


def _require_sha256(
    path: Path,
    expected: object,
    *,
    label: str,
) -> str:
    expected_sha = _lower_sha256(
        expected,
        label=f"{label} expected SHA256",
    )

    observed = sha256_file(
        path
    )

    if observed != expected_sha:
        raise Stage4ExecutionError(
            f"{label} SHA256 mismatch"
        )

    return observed


def _accession(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or CANONICAL_GCA_RE.fullmatch(value) is None
    ):
        raise Stage4ExecutionError(
            f"{label} contains invalid canonical GCA accession"
        )

    return value


def _nonempty_text(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise Stage4ExecutionError(
            f"{label} must be nonempty canonical text"
        )

    return value


def _positive_taxid(
    value: object,
    *,
    label: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise Stage4ExecutionError(
            f"{label} must be a positive integer"
        )

    return value


def _nonnegative_int_text(
    value: object,
    *,
    label: str,
) -> int:
    if (
        not isinstance(value, str)
        or not value
    ):
        raise Stage4ExecutionError(
            f"{label} must be a nonnegative integer"
        )

    try:
        parsed = int(
            value
        )
    except ValueError:
        raise Stage4ExecutionError(
            f"{label} must be a nonnegative integer"
        ) from None

    if (
        parsed < 0
        or str(parsed) != value
    ):
        raise Stage4ExecutionError(
            f"{label} must be a nonnegative integer"
        )

    return parsed


def _bool01(
    value: object,
    *,
    label: str,
) -> bool:
    if value == "0":
        return False

    if value == "1":
        return True

    raise Stage4ExecutionError(
        f"{label} must be 0 or 1"
    )


def _normalized_counts(
    values: Mapping[str, int],
    *,
    label: str,
) -> dict[str, int]:
    if not isinstance(
        values,
        Mapping,
    ):
        raise Stage4ExecutionError(
            f"{label} must be a mapping"
        )

    result: dict[str, int] = {}

    for key, value in values.items():
        if (
            not isinstance(key, str)
            or not key
            or isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise Stage4ExecutionError(
                f"{label} is malformed"
            )

        result[key] = value

    return dict(
        sorted(
            result.items()
        )
    )


def load_stage3_population(
    path: Path,
    *,
    expected_sha256: str,
    expected_total: int,
    expected_pass: int,
    expected_status_counts: Mapping[str, int],
    expected_reason_counts: Mapping[str, int],
) -> Stage3Population:
    """Verify a frozen Stage 3 table and derive only its PASS membership."""

    if (
        isinstance(expected_total, bool)
        or not isinstance(expected_total, int)
        or expected_total <= 0
    ):
        raise Stage4ExecutionError(
            "expected Stage 3 total must be positive"
        )

    if (
        isinstance(expected_pass, bool)
        or not isinstance(expected_pass, int)
        or expected_pass <= 0
        or expected_pass > expected_total
    ):
        raise Stage4ExecutionError(
            "expected Stage 3 PASS count is invalid"
        )

    decision_sha = _require_sha256(
        path,
        expected_sha256,
        label="Stage 3 decision artifact",
    )

    expected_status = _normalized_counts(
        expected_status_counts,
        label="expected Stage 3 status counts",
    )

    expected_reason = _normalized_counts(
        expected_reason_counts,
        label="expected Stage 3 reason counts",
    )

    try:
        handle = Path(path).open(
            newline="",
            encoding="utf-8",
        )
    except (
        OSError,
        UnicodeError,
    ) as exc:
        raise Stage4ExecutionError(
            "cannot read Stage 3 decision artifact"
        ) from exc

    with handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        if tuple(
            reader.fieldnames or ()
        ) != STAGE3_DECISION_FIELDS:
            raise Stage4ExecutionError(
                "unexpected Stage 3 decision schema"
            )

        rows = list(
            reader
        )

    if len(rows) != expected_total:
        raise Stage4ExecutionError(
            "Stage 3 decision row count mismatch"
        )

    seen: set[str] = set()
    pass_accessions: list[str] = []
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()

    for row in rows:
        accession = _accession(
            row[
                "canonical_genbank_assembly_accession"
            ],
            label="Stage 3 decisions",
        )

        if accession in seen:
            raise Stage4ExecutionError(
                "duplicate accession in Stage 3 decisions"
            )

        seen.add(
            accession
        )

        _lower_sha256(
            row[
                "source_evidence_sha256"
            ],
            label="Stage 3 source-evidence SHA256",
        )

        if row[
            "stage2_status"
        ] != BIOSAMPLE_CONTINUE:
            raise Stage4ExecutionError(
                "Stage 3 row does not originate from Stage 2 CONTINUE"
            )

        chromosome_count = _nonnegative_int_text(
            row[
                "chromosome_component_count"
            ],
            label="chromosome component count",
        )

        supported_count = _nonnegative_int_text(
            row[
                "closure_supported_chromosome_count"
            ],
            label="supported chromosome count",
        )

        unsupported_count = _nonnegative_int_text(
            row[
                "closure_unsupported_chromosome_count"
            ],
            label="unsupported chromosome count",
        )

        if (
            supported_count
            + unsupported_count
            != chromosome_count
        ):
            raise Stage4ExecutionError(
                "Stage 3 chromosome accounting mismatch"
            )

        _bool01(
            row[
                "chromosome_integrity_triggered"
            ],
            label="chromosome-integrity trigger",
        )

        _bool01(
            row[
                "historical_adjudication_reused"
            ],
            label="historical-adjudication reuse",
        )

        status = _nonempty_text(
            row[
                "stage3_status"
            ],
            label="Stage 3 status",
        )

        if status not in STAGE3_ALLOWED_STATUSES:
            raise Stage4ExecutionError(
                "unexpected Stage 3 status"
            )

        reason = _nonempty_text(
            row[
                "stage3_reason"
            ],
            label="Stage 3 reason",
        )

        status_counts[
            status
        ] += 1

        reason_counts[
            reason
        ] += 1

        if status == source_chromosome_integrity.PASS:
            pass_accessions.append(
                accession
            )

    observed_status = dict(
        sorted(
            status_counts.items()
        )
    )

    observed_reason = dict(
        sorted(
            reason_counts.items()
        )
    )

    if observed_status != expected_status:
        raise Stage4ExecutionError(
            "Stage 3 status accounting mismatch"
        )

    if observed_reason != expected_reason:
        raise Stage4ExecutionError(
            "Stage 3 reason accounting mismatch"
        )

    if len(pass_accessions) != expected_pass:
        raise Stage4ExecutionError(
            "Stage 4 taxonomy input count mismatch"
        )

    all_accessions = tuple(
        sorted(
            seen
        )
    )

    pass_membership = tuple(
        sorted(
            pass_accessions
        )
    )

    return Stage3Population(
        all_accessions=all_accessions,
        pass_accessions=pass_membership,
        all_membership_sha256=(
            accession_membership_sha256(
                all_accessions
            )
        ),
        pass_membership_sha256=(
            accession_membership_sha256(
                pass_membership
            )
        ),
        status_counts=observed_status,
        reason_counts=observed_reason,
        decision_artifact_sha256=decision_sha,
    )


def load_source_taxids(
    path: Path,
    *,
    expected_sha256: str,
    expected_record_count: int,
    wanted_accessions: Sequence[str],
) -> SourceTaxidBundle:
    """Bind Stage 4 candidates to organism.tax_id in a frozen source JSONL."""

    if (
        isinstance(expected_record_count, bool)
        or not isinstance(expected_record_count, int)
        or expected_record_count <= 0
    ):
        raise Stage4ExecutionError(
            "expected source record count must be positive"
        )

    if isinstance(
        wanted_accessions,
        (
            str,
            bytes,
        ),
    ):
        raise Stage4ExecutionError(
            "wanted accessions must be a sequence"
        )

    wanted_values = tuple(
        _accession(
            accession,
            label="Stage 4 membership",
        )
        for accession in wanted_accessions
    )

    if not wanted_values:
        raise Stage4ExecutionError(
            "Stage 4 membership must not be empty"
        )

    if len(
        set(
            wanted_values
        )
    ) != len(
        wanted_values
    ):
        raise Stage4ExecutionError(
            "duplicate accession in Stage 4 membership"
        )

    source_sha = _require_sha256(
        path,
        expected_sha256,
        label="raw source JSONL",
    )

    wanted = set(
        wanted_values
    )

    seen: set[str] = set()
    selected: dict[str, int] = {}
    record_count = 0

    try:
        records = iter_jsonl_records(
            path
        )

        for record in records:
            record_count += 1

            accession = _accession(
                record.get(
                    "accession"
                ),
                label="raw source JSONL",
            )

            if accession in seen:
                raise Stage4ExecutionError(
                    "duplicate accession in raw source JSONL"
                )

            seen.add(
                accession
            )

            organism = record.get(
                "organism"
            )

            if not isinstance(
                organism,
                Mapping,
            ):
                raise Stage4ExecutionError(
                    "raw source organism must be an object"
                )

            if "tax_id" not in organism:
                raise Stage4ExecutionError(
                    "raw source organism.tax_id is absent"
                )

            taxid = _positive_taxid(
                organism[
                    "tax_id"
                ],
                label="raw source organism.tax_id",
            )

            if accession in wanted:
                selected[
                    accession
                ] = taxid

    except Stage4ExecutionError:
        raise
    except (
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise Stage4ExecutionError(
            "cannot parse frozen raw source JSONL"
        ) from exc

    if record_count != expected_record_count:
        raise Stage4ExecutionError(
            "raw source record count mismatch"
        )

    if set(
        selected
    ) != wanted:
        raise Stage4ExecutionError(
            "Stage 4 accession absent from frozen source mapping"
        )

    ordered = dict(
        sorted(
            selected.items()
        )
    )

    return SourceTaxidBundle(
        taxid_by_accession=ordered,
        source_record_count=record_count,
        source_sha256=source_sha,
        unique_selected_taxid_count=len(
            set(
                ordered.values()
            )
        ),
    )


def evaluate_taxonomy_population(
    *,
    stage3: Stage3Population,
    source: SourceTaxidBundle,
    taxonomy: TaxonomyResolver,
) -> tuple[Stage4CandidateEvaluation, ...]:
    """Resolve exactly the Stage 3 PASS membership with in-run memoization."""

    if not isinstance(
        stage3,
        Stage3Population,
    ):
        raise Stage4ExecutionError(
            "unexpected Stage 3 population type"
        )

    if not isinstance(
        source,
        SourceTaxidBundle,
    ):
        raise Stage4ExecutionError(
            "unexpected source TaxID bundle type"
        )

    wanted = tuple(
        sorted(
            stage3.pass_accessions
        )
    )

    if tuple(
        sorted(
            source.taxid_by_accession
        )
    ) != wanted:
        raise Stage4ExecutionError(
            "source TaxID membership differs from Stage 4 membership"
        )

    memo: dict[int, TaxonomyDecision] = {}
    results: list[Stage4CandidateEvaluation] = []

    for accession in wanted:
        organism_taxid = _positive_taxid(
            source.taxid_by_accession[
                accession
            ],
            label="bound organism TaxID",
        )

        if organism_taxid not in memo:
            try:
                decision = resolve_taxonomy(
                    taxonomy,
                    organism_taxid,
                )
            except CompositionError as exc:
                raise Stage4ExecutionError(
                    "taxonomy resolution failed closed"
                ) from exc

            if not isinstance(
                decision,
                TaxonomyDecision,
            ):
                raise Stage4ExecutionError(
                    "taxonomy resolver returned unexpected decision type"
                )

            memo[
                organism_taxid
            ] = decision

        results.append(
            Stage4CandidateEvaluation(
                accession=accession,
                organism_taxid=organism_taxid,
                decision=memo[
                    organism_taxid
                ],
            )
        )

    return tuple(
        results
    )


def build_decision_rows(
    records: Sequence[Stage4CandidateEvaluation],
    *,
    expected_total: int,
) -> Stage4DecisionBuild:
    """Build deterministic identity-bearing rows and aggregate counts."""

    if isinstance(
        records,
        (
            str,
            bytes,
        ),
    ):
        raise Stage4ExecutionError(
            "Stage 4 records must be a sequence"
        )

    if (
        isinstance(expected_total, bool)
        or not isinstance(expected_total, int)
        or expected_total <= 0
        or len(records) != expected_total
    ):
        raise Stage4ExecutionError(
            "Stage 4 decision record count mismatch"
        )

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    organism_taxids: set[int] = set()
    species_taxids: set[int] = set()

    for record in sorted(
        records,
        key=lambda item:
            item.accession
            if isinstance(
                item,
                Stage4CandidateEvaluation,
            )
            else "",
    ):
        if not isinstance(
            record,
            Stage4CandidateEvaluation,
        ):
            raise Stage4ExecutionError(
                "unexpected Stage 4 evaluation record type"
            )

        accession = _accession(
            record.accession,
            label="Stage 4 decision",
        )

        if accession in seen:
            raise Stage4ExecutionError(
                "duplicate Stage 4 decision accession"
            )

        seen.add(
            accession
        )

        organism_taxid = _positive_taxid(
            record.organism_taxid,
            label="Stage 4 organism TaxID",
        )

        decision = record.decision

        if not isinstance(
            decision,
            TaxonomyDecision,
        ):
            raise Stage4ExecutionError(
                "unexpected taxonomy decision type"
            )

        status = _nonempty_text(
            decision.status,
            label="Stage 4 status",
        )

        reason = _nonempty_text(
            decision.reason,
            label="Stage 4 reason",
        )

        normalized = decision.normalized_taxid
        species = decision.species_taxid

        if status == TAXONOMY_PASS:
            if reason != "TAXONOMY_SPECIES_RESOLVED":
                raise Stage4ExecutionError(
                    "PASS taxonomy decision has unexpected reason"
                )

            normalized_taxid = _positive_taxid(
                normalized,
                label="normalized organism TaxID",
            )

            species_taxid = _positive_taxid(
                species,
                label="species TaxID",
            )

            normalized_text = str(
                normalized_taxid
            )

            species_text = str(
                species_taxid
            )

            species_taxids.add(
                species_taxid
            )

        elif status == TAXONOMY_UNRESOLVED:
            if species is not None:
                raise Stage4ExecutionError(
                    "unresolved taxonomy decision contains species TaxID"
                )

            if reason in NORMALIZATION_UNRESOLVED_REASONS:
                if normalized is not None:
                    raise Stage4ExecutionError(
                        "normalization-unresolved decision contains "
                        "normalized TaxID"
                    )

                normalized_text = ""

            elif reason in SPECIES_UNRESOLVED_REASONS:
                normalized_taxid = _positive_taxid(
                    normalized,
                    label="normalized organism TaxID",
                )

                normalized_text = str(
                    normalized_taxid
                )

            else:
                raise Stage4ExecutionError(
                    "unresolved taxonomy decision has unexpected reason"
                )

            species_text = ""

        else:
            raise Stage4ExecutionError(
                "unexpected Stage 4 taxonomy status"
            )

        status_counts[
            status
        ] += 1

        reason_counts[
            reason
        ] += 1

        organism_taxids.add(
            organism_taxid
        )

        rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "organism_taxid":
                    str(
                        organism_taxid
                    ),
                "normalized_organism_taxid":
                    normalized_text,
                "species_taxid":
                    species_text,
                "stage4_status":
                    status,
                "stage4_reason":
                    reason,
            }
        )

    if sum(
        status_counts.values()
    ) != expected_total:
        raise Stage4ExecutionError(
            "Stage 4 status accounting mismatch"
        )

    return Stage4DecisionBuild(
        rows=tuple(
            rows
        ),
        status_counts=dict(
            sorted(
                status_counts.items()
            )
        ),
        reason_counts=dict(
            sorted(
                reason_counts.items()
            )
        ),
        unique_organism_taxid_count=len(
            organism_taxids
        ),
        resolved_distinct_species_taxid_count=len(
            species_taxids
        ),
    )
