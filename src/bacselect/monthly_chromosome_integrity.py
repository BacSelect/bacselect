"""Pure monthly chromosome-integrity contract for BacSelect.

This module does not reconstruct package evidence, parse sequence reports or
GBFF, classify package provenance, or implement historical adjudication reuse.

Those operations remain owned by the already-frozen
``source_chromosome_integrity_execution.evaluate_stage3_candidate`` helper.

This layer authenticates the monthly Stage 5 CONTINUE population, validates
the exact frozen Stage3CandidateEvaluation population, and serializes the
monthly chromosome-integrity decisions and record deterministically.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
import re

from bacselect import monthly_biosample_reconciliation
from bacselect import source_chromosome_integrity
from bacselect import source_chromosome_integrity_execution
from bacselect import source_post_sequence_eligibility
from bacselect.source_truth_execution import accession_membership_sha256


MONTHLY_CHROMOSOME_RECORD_SCHEMA = (
    "bacselect-monthly-chromosome-integrity-record-v1"
)

MONTHLY_CHROMOSOME_STATUS = (
    "MONTHLY_CHROMOSOME_INTEGRITY_COMPLETE"
)

DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "source_evidence_sha256",
    "biosample_status",
    "primary_component_count",
    "chromosome_component_count",
    "closure_supported_chromosome_count",
    "closure_unsupported_chromosome_count",
    "chromosome_integrity_triggered",
    "historical_adjudication_reused",
    "chromosome_integrity_status",
    "chromosome_integrity_reason",
)

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_RELEASE_RE = re.compile(
    r"^[0-9]{4}\.[0-9]{2}$"
)

_ALLOWED_DECISIONS = frozenset(
    {
        (
            source_chromosome_integrity.PASS,
            "NO_CHROMOSOME_INTEGRITY_TRIGGER",
            False,
            False,
        ),
        (
            source_chromosome_integrity.PASS,
            "HISTORICAL_RETAIN_CONFIRMED_MULTIPARTITE",
            True,
            True,
        ),
        (
            source_chromosome_integrity.EXCLUDE,
            "HISTORICAL_FRAGMENTED_CHROMOSOME_SET",
            True,
            True,
        ),
        (
            source_chromosome_integrity.UNRESOLVED,
            "HISTORICAL_UNRESOLVED",
            True,
            True,
        ),
        (
            source_chromosome_integrity.UNRESOLVED,
            "NO_REUSABLE_HISTORICAL_ADJUDICATION",
            True,
            False,
        ),
        (
            source_chromosome_integrity.UNRESOLVED,
            "NOT_HISTORICAL_PROJECT_FINCH_PACKAGE",
            True,
            False,
        ),
        (
            source_chromosome_integrity.UNRESOLVED,
            "HISTORICAL_CACHE_NOT_VERIFIED",
            True,
            False,
        ),
        (
            source_chromosome_integrity.UNRESOLVED,
            "HISTORICAL_ADJUDICATION_ABSENT",
            True,
            False,
        ),
        (
            source_chromosome_integrity.UNRESOLVED,
            "HISTORICAL_ACCESSION_MISMATCH",
            True,
            False,
        ),
    }
)


class MonthlyChromosomeIntegrityError(
    ValueError
):
    """Raised when monthly chromosome-integrity evidence fails closed."""


@dataclass(
    frozen=True
)
class MonthlyChromosomePopulation:
    release_id: str
    source_snapshot_id: str
    origin_git_commit: str
    biosample_decisions_sha256: str
    continue_accessions: tuple[
        str,
        ...
    ]
    continue_accessions_sha256: str
    source_evidence_sha256_by_accession: Mapping[
        str,
        str,
    ]


@dataclass(
    frozen=True
)
class MonthlyChromosomeBuild:
    population: MonthlyChromosomePopulation
    evaluations: tuple[
        source_chromosome_integrity_execution.Stage3CandidateEvaluation,
        ...
    ]
    decision_rows: tuple[
        Mapping[
            str,
            str,
        ],
        ...
    ]
    triggered_candidate_count: int
    nontriggered_candidate_count: int
    historical_adjudication_reuse_count: int
    status_counts: Mapping[
        str,
        int,
    ]
    reason_counts: Mapping[
        str,
        int,
    ]


def _canonical_accession(
    value: object,
) -> str:
    """Reuse the frozen monthly Stage 5 accession validator."""

    try:
        accession = (
            monthly_biosample_reconciliation
            ._accession(
                value
            )
        )
    except Exception as exc:
        raise MonthlyChromosomeIntegrityError(
            "canonical GenBank assembly accession is invalid"
        ) from exc

    if (
        not isinstance(
            value,
            str,
        )
        or accession != value
    ):
        raise MonthlyChromosomeIntegrityError(
            "canonical GenBank assembly accession is not canonical"
        )

    return accession


def _lower_sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyChromosomeIntegrityError(
            f"{label} must be a lowercase SHA256"
        )

    return value


def _release_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _RELEASE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyChromosomeIntegrityError(
            "release_id must use YYYY.MM"
        )

    return value


def _source_snapshot_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value.strip() != value
    ):
        raise MonthlyChromosomeIntegrityError(
            "source_snapshot_id must be non-empty text"
        )

    return value


def _origin_commit(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyChromosomeIntegrityError(
            "origin_git_commit must be a lowercase 40-character Git commit"
        )

    return value


def _positive_int(
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
        raise MonthlyChromosomeIntegrityError(
            f"{label} must be a positive integer"
        )

    return value


def _nonnegative_int(
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
        or value < 0
    ):
        raise MonthlyChromosomeIntegrityError(
            f"{label} must be a non-negative integer"
        )

    return value


def _canonical_json(
    payload: Mapping[
        str,
        object,
    ],
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def build_monthly_chromosome_population(
    biosample_decisions_payload: bytes,
    *,
    expected_biosample_decisions_sha256: str,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
) -> MonthlyChromosomePopulation:
    """Authenticate Stage 5 and derive the exact chromosome input population."""

    if not isinstance(
        biosample_decisions_payload,
        bytes,
    ):
        raise MonthlyChromosomeIntegrityError(
            "BioSample decisions payload must be bytes"
        )

    expected_sha = _lower_sha256(
        expected_biosample_decisions_sha256,
        label="authenticated Stage 5 decisions SHA256",
    )

    observed_sha = hashlib.sha256(
        biosample_decisions_payload
    ).hexdigest()

    if observed_sha != expected_sha:
        raise MonthlyChromosomeIntegrityError(
            "Stage 5 decision table does not match the "
            "authenticated Stage 5 completion"
        )

    try:
        rows = (
            monthly_biosample_reconciliation
            .audit_monthly_biosample_decisions(
                biosample_decisions_payload
            )
        )
    except Exception as exc:
        raise MonthlyChromosomeIntegrityError(
            "Stage 5 BioSample decisions failed audit"
        ) from exc

    continue_rows = tuple(
        row
        for row in rows
        if row[
            "biosample_status"
        ]
        == source_post_sequence_eligibility.BIOSAMPLE_CONTINUE
    )

    if not continue_rows:
        raise MonthlyChromosomeIntegrityError(
            "Stage 5 contains no CONTINUE candidates"
        )

    accessions = tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in continue_rows
    )

    if accessions != tuple(
        sorted(
            accessions
        )
    ):
        raise MonthlyChromosomeIntegrityError(
            "Stage 5 CONTINUE population is not sorted"
        )

    source_sha_by_accession = {
        row[
            "canonical_genbank_assembly_accession"
        ]:
            _lower_sha256(
                row[
                    "source_evidence_sha256"
                ],
                label="Stage 5 source-evidence SHA256",
            )
        for row in continue_rows
    }

    if len(
        source_sha_by_accession
    ) != len(
        accessions
    ):
        raise MonthlyChromosomeIntegrityError(
            "duplicate accession in Stage 5 CONTINUE population"
        )

    return MonthlyChromosomePopulation(
        release_id=_release_id(
            release_id
        ),
        source_snapshot_id=_source_snapshot_id(
            source_snapshot_id
        ),
        origin_git_commit=_origin_commit(
            origin_git_commit
        ),
        biosample_decisions_sha256=observed_sha,
        continue_accessions=accessions,
        continue_accessions_sha256=(
            accession_membership_sha256(
                accessions
            )
        ),
        source_evidence_sha256_by_accession=dict(
            sorted(
                source_sha_by_accession.items()
            )
        ),
    )


def _validate_evaluation(
    population: MonthlyChromosomePopulation,
    evaluation: object,
) -> None:
    if not isinstance(
        evaluation,
        source_chromosome_integrity_execution.Stage3CandidateEvaluation,
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome evaluation has unexpected type"
        )

    accession = evaluation.accession

    if accession not in (
        population.source_evidence_sha256_by_accession
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome evaluation accession is outside "
            "the Stage 5 CONTINUE population"
        )

    source_sha = _lower_sha256(
        evaluation.source_evidence_sha256,
        label="chromosome evaluation source-evidence SHA256",
    )

    if source_sha != (
        population
        .source_evidence_sha256_by_accession[
            accession
        ]
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome evaluation source evidence differs "
            "from authenticated Stage 5"
        )

    primary_count = _positive_int(
        evaluation.primary_component_count,
        label="Primary Assembly component count",
    )

    trigger = evaluation.trigger

    if not isinstance(
        trigger,
        source_chromosome_integrity.TriggerAssessment,
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome trigger has unexpected type"
        )

    chromosome_count = _nonnegative_int(
        trigger.chromosome_component_count,
        label="chromosome component count",
    )

    supported_count = _nonnegative_int(
        trigger.closure_supported_chromosome_count,
        label="closure-supported chromosome count",
    )

    unsupported_count = _nonnegative_int(
        trigger.closure_unsupported_chromosome_count,
        label="closure-unsupported chromosome count",
    )

    if (
        supported_count
        + unsupported_count
        != chromosome_count
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome trigger accounting mismatch"
        )

    if chromosome_count > primary_count:
        raise MonthlyChromosomeIntegrityError(
            "chromosome component count exceeds "
            "Primary Assembly component count"
        )

    if not isinstance(
        trigger.triggered,
        bool,
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome trigger flag must be boolean"
        )

    # The scientific trigger predicate is deliberately not recalculated here.
    # The frozen evaluate_stage3_candidate() helper owns reconstruction and
    # assess_trigger(); this pure layer checks only the resulting accounting
    # and decision consistency.
    decision = evaluation.decision

    if not isinstance(
        decision,
        source_chromosome_integrity.ChromosomeIntegrityDecision,
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision has unexpected type"
        )

    if not isinstance(
        decision.triggered,
        bool,
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision trigger flag must be boolean"
        )

    if not isinstance(
        decision.historical_adjudication_reused,
        bool,
    ):
        raise MonthlyChromosomeIntegrityError(
            "historical adjudication reuse flag must be boolean"
        )

    if decision.triggered != trigger.triggered:
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision trigger disagrees with TriggerAssessment"
        )

    observed = (
        decision.status,
        decision.reason,
        decision.triggered,
        decision.historical_adjudication_reused,
    )

    if observed not in _ALLOWED_DECISIONS:
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision status/reason/trigger/reuse "
            "combination is not frozen"
        )


def build_monthly_chromosome_integrity(
    population: MonthlyChromosomePopulation,
    evaluations: Iterable[
        source_chromosome_integrity_execution.Stage3CandidateEvaluation
    ],
) -> MonthlyChromosomeBuild:
    """Validate and package one complete monthly chromosome decision set."""

    if not isinstance(
        population,
        MonthlyChromosomePopulation,
    ):
        raise MonthlyChromosomeIntegrityError(
            "population has unexpected type"
        )

    if isinstance(
        evaluations,
        (
            str,
            bytes,
        ),
    ):
        raise MonthlyChromosomeIntegrityError(
            "evaluations must be an iterable of frozen evaluation objects"
        )

    observed = tuple(
        evaluations
    )

    if not observed:
        raise MonthlyChromosomeIntegrityError(
            "chromosome evaluation population must not be empty"
        )

    accessions = tuple(
        evaluation.accession
        if isinstance(
            evaluation,
            source_chromosome_integrity_execution.Stage3CandidateEvaluation,
        )
        else ""
        for evaluation in observed
    )

    if accessions != tuple(
        sorted(
            accessions
        )
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome evaluations must be sorted by accession"
        )

    if accessions != (
        population.continue_accessions
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome evaluation population differs from "
            "authenticated Stage 5 CONTINUE population"
        )

    rows = []
    status_counts = Counter()
    reason_counts = Counter()

    triggered_count = 0
    reused_count = 0

    for evaluation in observed:
        _validate_evaluation(
            population,
            evaluation,
        )

        trigger = evaluation.trigger
        decision = evaluation.decision

        if trigger.triggered:
            triggered_count += 1

        if decision.historical_adjudication_reused:
            reused_count += 1

        status_counts[
            decision.status
        ] += 1

        reason_counts[
            decision.reason
        ] += 1

        rows.append(
            {
                "canonical_genbank_assembly_accession":
                    evaluation.accession,
                "source_evidence_sha256":
                    evaluation.source_evidence_sha256,
                "biosample_status":
                    source_post_sequence_eligibility.BIOSAMPLE_CONTINUE,
                "primary_component_count":
                    str(
                        evaluation.primary_component_count
                    ),
                "chromosome_component_count":
                    str(
                        trigger.chromosome_component_count
                    ),
                "closure_supported_chromosome_count":
                    str(
                        trigger.closure_supported_chromosome_count
                    ),
                "closure_unsupported_chromosome_count":
                    str(
                        trigger.closure_unsupported_chromosome_count
                    ),
                "chromosome_integrity_triggered":
                    (
                        "1"
                        if trigger.triggered
                        else "0"
                    ),
                "historical_adjudication_reused":
                    (
                        "1"
                        if decision.historical_adjudication_reused
                        else "0"
                    ),
                "chromosome_integrity_status":
                    decision.status,
                "chromosome_integrity_reason":
                    decision.reason,
            }
        )

    return MonthlyChromosomeBuild(
        population=population,
        evaluations=observed,
        decision_rows=tuple(
            rows
        ),
        triggered_candidate_count=triggered_count,
        nontriggered_candidate_count=(
            len(
                observed
            )
            - triggered_count
        ),
        historical_adjudication_reuse_count=reused_count,
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
    )


def _serialize_tsv_rows(
    rows: Iterable[
        Mapping[
            str,
            str,
        ]
    ],
) -> bytes:
    lines = [
        "\t".join(
            DECISION_FIELDS
        )
    ]

    for row in rows:
        if set(
            row
        ) != set(
            DECISION_FIELDS
        ):
            raise MonthlyChromosomeIntegrityError(
                "chromosome decision row has unexpected fields"
            )

        values = []

        for field in DECISION_FIELDS:
            value = row[
                field
            ]

            if not isinstance(
                value,
                str,
            ):
                raise MonthlyChromosomeIntegrityError(
                    "chromosome decision value must be text"
                )

            if (
                "\t" in value
                or "\n" in value
                or "\r" in value
            ):
                raise MonthlyChromosomeIntegrityError(
                    "chromosome decision value contains TSV control characters"
                )

            values.append(
                value
            )

        lines.append(
            "\t".join(
                values
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def serialize_monthly_chromosome_decisions(
    build: MonthlyChromosomeBuild,
) -> bytes:
    if not isinstance(
        build,
        MonthlyChromosomeBuild,
    ):
        raise MonthlyChromosomeIntegrityError(
            "build has unexpected type"
        )

    return _serialize_tsv_rows(
        build.decision_rows
    )


def _parse_decimal(
    value: str,
    *,
    label: str,
    positive: bool,
) -> int:
    if not value.isdigit():
        raise MonthlyChromosomeIntegrityError(
            f"{label} must be canonical decimal text"
        )

    observed = int(
        value
    )

    if str(
        observed
    ) != value:
        raise MonthlyChromosomeIntegrityError(
            f"{label} must use canonical decimal text"
        )

    if (
        positive
        and observed <= 0
    ):
        raise MonthlyChromosomeIntegrityError(
            f"{label} must be positive"
        )

    return observed


def audit_monthly_chromosome_decisions(
    payload: bytes,
) -> tuple[
    Mapping[
        str,
        str,
    ],
    ...
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision payload must be bytes"
        )

    if b"\r" in payload:
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision payload must not contain CR bytes"
        )

    if not payload.endswith(
        b"\n"
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision payload must end with one newline"
        )

    if payload.endswith(
        b"\n\n"
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision payload has an extra blank line at EOF"
        )

    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision payload is not UTF-8"
        ) from exc

    lines = text.splitlines()

    if len(
        lines
    ) < 2:
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision table is empty"
        )

    if tuple(
        lines[
            0
        ].split(
            "\t"
        )
    ) != DECISION_FIELDS:
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision header differs from frozen schema"
        )

    rows = []

    for line_number, line in enumerate(
        lines[
            1:
        ],
        start=2,
    ):
        values = line.split(
            "\t"
        )

        if len(
            values
        ) != len(
            DECISION_FIELDS
        ):
            raise MonthlyChromosomeIntegrityError(
                f"chromosome decision line {line_number} "
                "has an unexpected field count"
            )

        row = dict(
            zip(
                DECISION_FIELDS,
                values,
                strict=True,
            )
        )

        _canonical_accession(
            row[
                "canonical_genbank_assembly_accession"
            ]
        )

        _lower_sha256(
            row[
                "source_evidence_sha256"
            ],
            label="chromosome decision source-evidence SHA256",
        )

        if row[
            "biosample_status"
        ] != source_post_sequence_eligibility.BIOSAMPLE_CONTINUE:
            raise MonthlyChromosomeIntegrityError(
                "chromosome decision contains a non-CONTINUE "
                "BioSample status"
            )

        primary_count = _parse_decimal(
            row[
                "primary_component_count"
            ],
            label="Primary Assembly component count",
            positive=True,
        )

        chromosome_count = _parse_decimal(
            row[
                "chromosome_component_count"
            ],
            label="chromosome component count",
            positive=False,
        )

        supported_count = _parse_decimal(
            row[
                "closure_supported_chromosome_count"
            ],
            label="closure-supported chromosome count",
            positive=False,
        )

        unsupported_count = _parse_decimal(
            row[
                "closure_unsupported_chromosome_count"
            ],
            label="closure-unsupported chromosome count",
            positive=False,
        )

        if (
            supported_count
            + unsupported_count
            != chromosome_count
        ):
            raise MonthlyChromosomeIntegrityError(
                "chromosome decision trigger accounting mismatch"
            )

        if chromosome_count > primary_count:
            raise MonthlyChromosomeIntegrityError(
                "chromosome decision chromosome count exceeds "
                "Primary Assembly count"
            )

        if row[
            "chromosome_integrity_triggered"
        ] not in {
            "0",
            "1",
        }:
            raise MonthlyChromosomeIntegrityError(
                "chromosome trigger flag must be 0 or 1"
            )

        if row[
            "historical_adjudication_reused"
        ] not in {
            "0",
            "1",
        }:
            raise MonthlyChromosomeIntegrityError(
                "historical reuse flag must be 0 or 1"
            )

        triggered = (
            row[
                "chromosome_integrity_triggered"
            ]
            == "1"
        )

        reused = (
            row[
                "historical_adjudication_reused"
            ]
            == "1"
        )

        observed = (
            row[
                "chromosome_integrity_status"
            ],
            row[
                "chromosome_integrity_reason"
            ],
            triggered,
            reused,
        )

        if observed not in _ALLOWED_DECISIONS:
            raise MonthlyChromosomeIntegrityError(
                "chromosome decision outcome combination is not frozen"
            )

        rows.append(
            row
        )

    accessions = tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in rows
    )

    if accessions != tuple(
        sorted(
            accessions
        )
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision rows are not sorted"
        )

    if len(
        set(
            accessions
        )
    ) != len(
        accessions
    ):
        raise MonthlyChromosomeIntegrityError(
            "duplicate chromosome decision accession"
        )

    return tuple(
        rows
    )


def _evaluation_from_row(
    row: Mapping[
        str,
        str,
    ],
) -> source_chromosome_integrity_execution.Stage3CandidateEvaluation:
    primary_count = int(
        row[
            "primary_component_count"
        ]
    )

    chromosome_count = int(
        row[
            "chromosome_component_count"
        ]
    )

    supported_count = int(
        row[
            "closure_supported_chromosome_count"
        ]
    )

    unsupported_count = int(
        row[
            "closure_unsupported_chromosome_count"
        ]
    )

    triggered = (
        row[
            "chromosome_integrity_triggered"
        ]
        == "1"
    )

    reused = (
        row[
            "historical_adjudication_reused"
        ]
        == "1"
    )

    return (
        source_chromosome_integrity_execution
        .Stage3CandidateEvaluation(
            accession=row[
                "canonical_genbank_assembly_accession"
            ],
            source_evidence_sha256=row[
                "source_evidence_sha256"
            ],
            primary_component_count=primary_count,
            trigger=(
                source_chromosome_integrity
                .TriggerAssessment(
                    triggered=triggered,
                    chromosome_component_count=chromosome_count,
                    closure_supported_chromosome_count=(
                        supported_count
                    ),
                    closure_unsupported_chromosome_count=(
                        unsupported_count
                    ),
                )
            ),
            decision=(
                source_chromosome_integrity
                .ChromosomeIntegrityDecision(
                    status=row[
                        "chromosome_integrity_status"
                    ],
                    reason=row[
                        "chromosome_integrity_reason"
                    ],
                    triggered=triggered,
                    historical_adjudication_reused=reused,
                )
            ),
        )
    )


def serialize_monthly_chromosome_record(
    build: MonthlyChromosomeBuild,
    *,
    biosample_record_sha256: str,
    biosample_completion_sha256: str,
) -> bytes:
    if not isinstance(
        build,
        MonthlyChromosomeBuild,
    ):
        raise MonthlyChromosomeIntegrityError(
            "build has unexpected type"
        )

    stage5_record_sha = _lower_sha256(
        biosample_record_sha256,
        label="Stage 5 record SHA256",
    )

    stage5_completion_sha = _lower_sha256(
        biosample_completion_sha256,
        label="Stage 5 completion SHA256",
    )

    decisions_payload = (
        serialize_monthly_chromosome_decisions(
            build
        )
    )

    record = {
        "schema_version":
            MONTHLY_CHROMOSOME_RECORD_SCHEMA,
        "status":
            MONTHLY_CHROMOSOME_STATUS,
        "release_id":
            build.population.release_id,
        "source_snapshot_id":
            build.population.source_snapshot_id,
        "origin_git_commit":
            build.population.origin_git_commit,
        "biosample_decisions_sha256":
            build.population.biosample_decisions_sha256,
        "biosample_record_sha256":
            stage5_record_sha,
        "biosample_completion_sha256":
            stage5_completion_sha,
        "continue_count":
            len(
                build.population.continue_accessions
            ),
        "continue_accessions_sha256":
            build.population.continue_accessions_sha256,
        "decision_count":
            len(
                build.decision_rows
            ),
        "decisions_sha256":
            hashlib.sha256(
                decisions_payload
            ).hexdigest(),
        "triggered_candidate_count":
            build.triggered_candidate_count,
        "nontriggered_candidate_count":
            build.nontriggered_candidate_count,
        "historical_adjudication_reuse_count":
            build.historical_adjudication_reuse_count,
        "status_counts":
            dict(
                sorted(
                    build.status_counts.items()
                )
            ),
        "reason_counts":
            dict(
                sorted(
                    build.reason_counts.items()
                )
            ),
    }

    return _canonical_json(
        record
    )


def audit_monthly_chromosome_record(
    payload: bytes,
    *,
    biosample_decisions_payload: bytes,
    expected_biosample_decisions_sha256: str,
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    biosample_record_sha256: str,
    biosample_completion_sha256: str,
    decisions_payload: bytes,
) -> Mapping[
    str,
    object,
]:
    population = (
        build_monthly_chromosome_population(
            biosample_decisions_payload,
            expected_biosample_decisions_sha256=(
                expected_biosample_decisions_sha256
            ),
            release_id=release_id,
            source_snapshot_id=source_snapshot_id,
            origin_git_commit=origin_git_commit,
        )
    )

    decision_rows = (
        audit_monthly_chromosome_decisions(
            decisions_payload
        )
    )

    evaluations = tuple(
        _evaluation_from_row(
            row
        )
        for row in decision_rows
    )

    build = (
        build_monthly_chromosome_integrity(
            population,
            evaluations,
        )
    )

    canonical_decisions = (
        serialize_monthly_chromosome_decisions(
            build
        )
    )

    if canonical_decisions != (
        decisions_payload
    ):
        raise MonthlyChromosomeIntegrityError(
            "chromosome decision payload is not canonical"
        )

    expected = (
        serialize_monthly_chromosome_record(
            build,
            biosample_record_sha256=(
                biosample_record_sha256
            ),
            biosample_completion_sha256=(
                biosample_completion_sha256
            ),
        )
    )

    if payload != expected:
        raise MonthlyChromosomeIntegrityError(
            "monthly chromosome-integrity record differs "
            "from authenticated inputs"
        )

    try:
        record = json.loads(
            payload
        )
    except json.JSONDecodeError as exc:
        raise MonthlyChromosomeIntegrityError(
            "monthly chromosome-integrity record is invalid JSON"
        ) from exc

    if not isinstance(
        record,
        dict,
    ):
        raise MonthlyChromosomeIntegrityError(
            "monthly chromosome-integrity record must be an object"
        )

    return record
