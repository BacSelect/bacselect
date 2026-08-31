"""Pure monthly repeated-BioSample reconciliation contract for BacSelect."""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import re
from typing import (
    Iterable,
    Mapping,
    Sequence,
)

from bacselect import monthly_source_truth
from bacselect import source_truth
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    BIOSAMPLE_NONREPRESENTATIVE,
    BIOSAMPLE_UNRESOLVED,
    BioSampleDecision,
)
from bacselect.source_repeated_biosample_execution import (
    VerifiedBioSampleFingerprint,
    reconcile_verified_candidates,
)
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


MONTHLY_BIOSAMPLE_RECORD_SCHEMA = (
    "bacselect-monthly-biosample-reconciliation-record-v1"
)

MONTHLY_BIOSAMPLE_STATUS = (
    "MONTHLY_BIOSAMPLE_RECONCILIATION_COMPLETE"
)

DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "biosample",
    "source_evidence_sha256",
    "assembly_fingerprint",
    "biosample_status",
    "biosample_reason",
)

ALLOWED_STATUS_REASON = frozenset(
    {
        (
            BIOSAMPLE_CONTINUE,
            "BIOSAMPLE_SINGLETON",
        ),
        (
            BIOSAMPLE_CONTINUE,
            "BIOSAMPLE_IDENTICAL_REPRESENTATIVE",
        ),
        (
            BIOSAMPLE_NONREPRESENTATIVE,
            "BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE",
        ),
        (
            BIOSAMPLE_UNRESOLVED,
            "BIOSAMPLE_FINGERPRINTS_DIFFER",
        ),
    }
)

GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class MonthlyBioSampleReconciliationError(
    RuntimeError
):
    """Raised when the monthly Stage 5 contract fails closed."""


@dataclass(
    frozen=True
)
class MonthlyBioSamplePopulation:
    """Current Stage 4 SUITABLE population entering Stage 5."""

    release_id: str
    source_snapshot_id: str
    origin_git_commit: str
    source_truth_decisions_sha256: str
    suitable_accessions: tuple[
        str,
        ...
    ]
    suitable_accessions_sha256: str
    biosample_by_accession: Mapping[
        str,
        str,
    ]
    source_evidence_sha256_by_accession: Mapping[
        str,
        str,
    ]


@dataclass(
    frozen=True
)
class MonthlyBioSampleBuild:
    """Validated monthly Stage 5 result."""

    population: MonthlyBioSamplePopulation
    fingerprints: tuple[
        VerifiedBioSampleFingerprint,
        ...
    ]
    decisions: Mapping[
        str,
        BioSampleDecision,
    ]
    decision_rows: tuple[
        Mapping[
            str,
            str,
        ],
        ...
    ]
    group_count: int
    singleton_group_count: int
    repeated_group_count: int
    identical_repeated_group_count: int
    differing_repeated_group_count: int


def _accession(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or GCA_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyBioSampleReconciliationError(
            "invalid canonical GenBank assembly accession"
        )

    return value


def _text(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value != value.strip()
    ):
        raise MonthlyBioSampleReconciliationError(
            f"{label} is invalid"
        )

    return value


def _sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyBioSampleReconciliationError(
            f"{label} is not a lowercase SHA256"
        )

    return value


def _canonical_json_bytes(
    value: object,
) -> bytes:
    return (
        json.dumps(
            value,
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


def _serialize_tsv(
    rows: Sequence[
        Mapping[
            str,
            str,
        ]
    ],
    fields: Sequence[
        str
    ],
) -> bytes:
    handle = io.StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        handle,
        fieldnames=list(
            fields
        ),
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )

    writer.writeheader()

    for row in rows:
        if set(
            row
        ) != set(
            fields
        ):
            raise MonthlyBioSampleReconciliationError(
                "monthly BioSample row schema changed"
            )

        writer.writerow(
            row
        )

    return handle.getvalue().encode(
        "ascii"
    )


def _parse_tsv(
    payload: bytes,
    *,
    fields: Sequence[
        str
    ],
    label: str,
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
        raise TypeError(
            f"{label} must be bytes"
        )

    try:
        text = payload.decode(
            "ascii"
        )
    except UnicodeDecodeError as exc:
        raise MonthlyBioSampleReconciliationError(
            f"{label} is not ASCII"
        ) from exc

    handle = io.StringIO(
        text,
        newline=""
    )

    reader = csv.DictReader(
        handle,
        delimiter="\t",
    )

    if tuple(
        reader.fieldnames
        or ()
    ) != tuple(
        fields
    ):
        raise MonthlyBioSampleReconciliationError(
            f"{label} header changed"
        )

    rows = []

    for row in reader:
        if (
            None in row
            or set(
                row
            )
            != set(
                fields
            )
        ):
            raise MonthlyBioSampleReconciliationError(
                f"{label} row schema changed"
            )

        rows.append(
            dict(
                row
            )
        )

    return tuple(
        rows
    )


def build_monthly_biosample_population(
    source_truth_decisions_payload: bytes,
    *,
    expected_source_truth_decisions_sha256: str,
    current_metadata: Mapping[
        str,
        str,
    ],
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
) -> MonthlyBioSamplePopulation:
    """Derive exactly the current Stage 4 SUITABLE population."""

    release = _text(
        release_id,
        label="release ID",
    )

    snapshot = _text(
        source_snapshot_id,
        label="source-snapshot ID",
    )

    commit = _text(
        origin_git_commit,
        label="origin Git commit",
    )

    if not isinstance(
        current_metadata,
        Mapping,
    ):
        raise MonthlyBioSampleReconciliationError(
            "current metadata must be a mapping"
        )

    try:
        rows = (
            monthly_source_truth
            .audit_monthly_source_truth_decisions(
                source_truth_decisions_payload
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleReconciliationError(
            "monthly source-truth decisions failed audit"
        ) from exc

    decisions_sha = hashlib.sha256(
        source_truth_decisions_payload
    ).hexdigest()

    expected_decisions_sha = _sha256(
        expected_source_truth_decisions_sha256,
        label=(
            "authenticated Stage 4 decisions SHA256"
        ),
    )

    if decisions_sha != expected_decisions_sha:
        raise MonthlyBioSampleReconciliationError(
            "monthly source-truth decisions SHA256 differs from "
            "authenticated Stage 4 completion"
        )

    suitable: list[
        str
    ] = []

    biosample_by_accession: dict[
        str,
        str,
    ] = {}

    source_evidence_by_accession: dict[
        str,
        str,
    ] = {}

    for row in rows:
        if (
            row[
                "source_truth_status"
            ]
            != source_truth.SUITABLE
        ):
            continue

        accession = _accession(
            row[
                "canonical_genbank_assembly_accession"
            ]
        )

        if accession in biosample_by_accession:
            raise MonthlyBioSampleReconciliationError(
                "duplicate Stage 5 accession"
            )

        biosample = current_metadata.get(
            accession
        )

        if biosample is None:
            raise MonthlyBioSampleReconciliationError(
                "Stage 4 SUITABLE accession lacks current BioSample"
            )

        biosample = _text(
            biosample,
            label=f"{accession} BioSample",
        )

        source_evidence = _sha256(
            row[
                "source_evidence_sha256"
            ],
            label=(
                f"{accession} source-evidence SHA256"
            ),
        )

        suitable.append(
            accession
        )

        biosample_by_accession[
            accession
        ] = biosample

        source_evidence_by_accession[
            accession
        ] = source_evidence

    observed = tuple(
        suitable
    )

    if observed != tuple(
        sorted(
            observed
        )
    ):
        raise MonthlyBioSampleReconciliationError(
            "Stage 5 suitable population is not sorted"
        )

    if not observed:
        raise MonthlyBioSampleReconciliationError(
            "Stage 5 suitable population is empty"
        )

    membership_sha = accession_membership_sha256(
        observed
    )

    _sha256(
        membership_sha,
        label="Stage 5 membership SHA256",
    )

    return MonthlyBioSamplePopulation(
        release_id=release,
        source_snapshot_id=snapshot,
        origin_git_commit=commit,
        source_truth_decisions_sha256=(
            decisions_sha
        ),
        suitable_accessions=observed,
        suitable_accessions_sha256=(
            membership_sha
        ),
        biosample_by_accession=(
            biosample_by_accession
        ),
        source_evidence_sha256_by_accession=(
            source_evidence_by_accession
        ),
    )


def _validate_fingerprints(
    population: MonthlyBioSamplePopulation,
    fingerprints: Iterable[
        VerifiedBioSampleFingerprint
    ],
) -> tuple[
    VerifiedBioSampleFingerprint,
    ...
]:
    if isinstance(
        fingerprints,
        (
            str,
            bytes,
        ),
    ):
        raise MonthlyBioSampleReconciliationError(
            "fingerprints must be an iterable of verified records"
        )

    values = tuple(
        fingerprints
    )

    if any(
        not isinstance(
            value,
            VerifiedBioSampleFingerprint,
        )
        for value in values
    ):
        raise MonthlyBioSampleReconciliationError(
            "unexpected verified fingerprint type"
        )

    ordered = tuple(
        sorted(
            values,
            key=lambda item:
                item.accession,
        )
    )

    accessions: list[
        str
    ] = []

    for value in ordered:
        accession = _accession(
            value.accession
        )

        accessions.append(
            accession
        )

        expected_biosample = (
            population
            .biosample_by_accession
            .get(
                accession
            )
        )

        if expected_biosample is None:
            raise MonthlyBioSampleReconciliationError(
                "verified fingerprint contains accession outside "
                "Stage 4 SUITABLE population"
            )

        if value.biosample != expected_biosample:
            raise MonthlyBioSampleReconciliationError(
                "verified fingerprint BioSample differs from "
                "current metadata"
            )

        expected_source_evidence = (
            population
            .source_evidence_sha256_by_accession[
                accession
            ]
        )

        if (
            value.source_evidence_sha256
            != expected_source_evidence
        ):
            raise MonthlyBioSampleReconciliationError(
                "verified fingerprint source evidence differs "
                "from Stage 4 decision"
            )

        _sha256(
            value.assembly_fingerprint,
            label=(
                f"{accession} assembly fingerprint"
            ),
        )

    observed = tuple(
        accessions
    )

    if len(
        observed
    ) != len(
        set(
            observed
        )
    ):
        raise MonthlyBioSampleReconciliationError(
            "verified fingerprints contain duplicate accession"
        )

    if observed != (
        population
        .suitable_accessions
    ):
        raise MonthlyBioSampleReconciliationError(
            "verified fingerprint population differs from "
            "Stage 4 SUITABLE population"
        )

    return ordered


def _group_counts(
    fingerprints: Sequence[
        VerifiedBioSampleFingerprint
    ],
) -> tuple[
    int,
    int,
    int,
    int,
    int,
]:
    groups: dict[
        str,
        list[
            VerifiedBioSampleFingerprint
        ],
    ] = {}

    for value in fingerprints:
        groups.setdefault(
            value.biosample,
            [],
        ).append(
            value
        )

    singleton = 0
    repeated = 0
    identical = 0
    differing = 0

    for members in groups.values():
        if len(
            members
        ) == 1:
            singleton += 1
            continue

        repeated += 1

        fingerprints_seen = {
            member.assembly_fingerprint
            for member in members
        }

        if len(
            fingerprints_seen
        ) == 1:
            identical += 1
        else:
            differing += 1

    if (
        singleton
        + repeated
        != len(
            groups
        )
    ):
        raise AssertionError(
            "BioSample group accounting failed"
        )

    if (
        identical
        + differing
        != repeated
    ):
        raise AssertionError(
            "repeated BioSample group accounting failed"
        )

    return (
        len(
            groups
        ),
        singleton,
        repeated,
        identical,
        differing,
    )


def build_monthly_biosample_reconciliation(
    population: MonthlyBioSamplePopulation,
    fingerprints: Iterable[
        VerifiedBioSampleFingerprint
    ],
) -> MonthlyBioSampleBuild:
    """Delegate monthly Stage 5 decisions to the frozen reconciler."""

    if not isinstance(
        population,
        MonthlyBioSamplePopulation,
    ):
        raise TypeError(
            "population has wrong type"
        )

    verified = _validate_fingerprints(
        population,
        fingerprints,
    )

    try:
        decisions = (
            reconcile_verified_candidates(
                verified
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleReconciliationError(
            "frozen repeated-BioSample reconciliation failed"
        ) from exc

    if set(
        decisions
    ) != set(
        population.suitable_accessions
    ):
        raise MonthlyBioSampleReconciliationError(
            "repeated-BioSample decisions do not exactly cover "
            "Stage 4 SUITABLE population"
        )

    by_accession = {
        value.accession:
            value
        for value in verified
    }

    rows = []

    for accession in (
        population.suitable_accessions
    ):
        fingerprint = by_accession[
            accession
        ]

        decision = decisions[
            accession
        ]

        pair = (
            decision.status,
            decision.reason,
        )

        if pair not in ALLOWED_STATUS_REASON:
            raise MonthlyBioSampleReconciliationError(
                "frozen BioSample status/reason vocabulary changed"
            )

        rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "biosample":
                    fingerprint.biosample,
                "source_evidence_sha256":
                    fingerprint.source_evidence_sha256,
                "assembly_fingerprint":
                    fingerprint.assembly_fingerprint,
                "biosample_status":
                    decision.status,
                "biosample_reason":
                    decision.reason,
            }
        )

    (
        group_count,
        singleton_group_count,
        repeated_group_count,
        identical_repeated_group_count,
        differing_repeated_group_count,
    ) = _group_counts(
        verified
    )

    return MonthlyBioSampleBuild(
        population=population,
        fingerprints=verified,
        decisions=dict(
            decisions
        ),
        decision_rows=tuple(
            rows
        ),
        group_count=group_count,
        singleton_group_count=(
            singleton_group_count
        ),
        repeated_group_count=(
            repeated_group_count
        ),
        identical_repeated_group_count=(
            identical_repeated_group_count
        ),
        differing_repeated_group_count=(
            differing_repeated_group_count
        ),
    )


def serialize_monthly_biosample_decisions(
    build: MonthlyBioSampleBuild,
) -> bytes:
    if not isinstance(
        build,
        MonthlyBioSampleBuild,
    ):
        raise TypeError(
            "monthly BioSample build has wrong type"
        )

    return _serialize_tsv(
        build.decision_rows,
        DECISION_FIELDS,
    )


def audit_monthly_biosample_decisions(
    payload: bytes,
) -> tuple[
    Mapping[
        str,
        str,
    ],
    ...
]:
    rows = _parse_tsv(
        payload,
        fields=DECISION_FIELDS,
        label="monthly BioSample decisions",
    )

    accessions = []

    for row in rows:
        accession = _accession(
            row[
                "canonical_genbank_assembly_accession"
            ]
        )

        accessions.append(
            accession
        )

        _text(
            row[
                "biosample"
            ],
            label=f"{accession} BioSample",
        )

        _sha256(
            row[
                "source_evidence_sha256"
            ],
            label=(
                f"{accession} source-evidence SHA256"
            ),
        )

        _sha256(
            row[
                "assembly_fingerprint"
            ],
            label=(
                f"{accession} assembly fingerprint"
            ),
        )

        if (
            row[
                "biosample_status"
            ],
            row[
                "biosample_reason"
            ],
        ) not in ALLOWED_STATUS_REASON:
            raise MonthlyBioSampleReconciliationError(
                "monthly BioSample decision status/reason is invalid"
            )

    observed = tuple(
        accessions
    )

    if observed != tuple(
        sorted(
            observed
        )
    ):
        raise MonthlyBioSampleReconciliationError(
            "monthly BioSample decisions are not sorted"
        )

    if len(
        observed
    ) != len(
        set(
            observed
        )
    ):
        raise MonthlyBioSampleReconciliationError(
            "monthly BioSample decisions contain duplicate accession"
        )

    return rows


def _record_payload(
    build: MonthlyBioSampleBuild,
    *,
    source_truth_record_sha256: str,
    source_truth_completion_sha256: str,
) -> Mapping[
    str,
    object,
]:
    source_truth_record_sha = _sha256(
        source_truth_record_sha256,
        label="source-truth record SHA256",
    )

    source_truth_completion_sha = _sha256(
        source_truth_completion_sha256,
        label="source-truth completion SHA256",
    )

    decisions_payload = (
        serialize_monthly_biosample_decisions(
            build
        )
    )

    decisions_sha = hashlib.sha256(
        decisions_payload
    ).hexdigest()

    status_counts = Counter(
        row[
            "biosample_status"
        ]
        for row in build.decision_rows
    )

    reason_counts = Counter(
        row[
            "biosample_reason"
        ]
        for row in build.decision_rows
    )

    if sum(
        status_counts.values()
    ) != len(
        build.decision_rows
    ):
        raise AssertionError(
            "BioSample decision status accounting failed"
        )

    return {
        "decision_count":
            len(
                build.decision_rows
            ),
        "decision_reason_counts":
            dict(
                sorted(
                    reason_counts.items()
                )
            ),
        "decision_status_counts":
            dict(
                sorted(
                    status_counts.items()
                )
            ),
        "decisions_sha256":
            decisions_sha,
        "differing_repeated_group_count":
            build.differing_repeated_group_count,
        "group_count":
            build.group_count,
        "identical_repeated_group_count":
            build.identical_repeated_group_count,
        "origin_git_commit":
            build.population.origin_git_commit,
        "release_id":
            build.population.release_id,
        "repeated_group_count":
            build.repeated_group_count,
        "schema_version":
            MONTHLY_BIOSAMPLE_RECORD_SCHEMA,
        "singleton_group_count":
            build.singleton_group_count,
        "source_snapshot_id":
            build.population.source_snapshot_id,
        "source_truth_completion_sha256":
            source_truth_completion_sha,
        "source_truth_decisions_sha256":
            build.population.source_truth_decisions_sha256,
        "source_truth_record_sha256":
            source_truth_record_sha,
        "status":
            MONTHLY_BIOSAMPLE_STATUS,
        "suitable_accessions_sha256":
            build.population.suitable_accessions_sha256,
        "suitable_count":
            len(
                build.population.suitable_accessions
            ),
    }


def serialize_monthly_biosample_record(
    build: MonthlyBioSampleBuild,
    *,
    source_truth_record_sha256: str,
    source_truth_completion_sha256: str,
) -> bytes:
    if not isinstance(
        build,
        MonthlyBioSampleBuild,
    ):
        raise TypeError(
            "monthly BioSample build has wrong type"
        )

    return _canonical_json_bytes(
        _record_payload(
            build,
            source_truth_record_sha256=(
                source_truth_record_sha256
            ),
            source_truth_completion_sha256=(
                source_truth_completion_sha256
            ),
        )
    )


def _build_from_decision_rows(
    population: MonthlyBioSamplePopulation,
    rows: Sequence[
        Mapping[
            str,
            str,
        ]
    ],
) -> MonthlyBioSampleBuild:
    if tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in rows
    ) != population.suitable_accessions:
        raise MonthlyBioSampleReconciliationError(
            "monthly BioSample decision membership differs from "
            "Stage 4 SUITABLE population"
        )

    fingerprints = []

    decisions: dict[
        str,
        BioSampleDecision,
    ] = {}

    for row in rows:
        accession = row[
            "canonical_genbank_assembly_accession"
        ]

        if (
            row[
                "biosample"
            ]
            != population.biosample_by_accession[
                accession
            ]
        ):
            raise MonthlyBioSampleReconciliationError(
                "monthly BioSample decision BioSample differs from "
                "current metadata"
            )

        if (
            row[
                "source_evidence_sha256"
            ]
            != population
            .source_evidence_sha256_by_accession[
                accession
            ]
        ):
            raise MonthlyBioSampleReconciliationError(
                "monthly BioSample decision source evidence differs "
                "from Stage 4"
            )

        fingerprints.append(
            VerifiedBioSampleFingerprint(
                accession=accession,
                biosample=row[
                    "biosample"
                ],
                source_evidence_sha256=row[
                    "source_evidence_sha256"
                ],
                assembly_fingerprint=row[
                    "assembly_fingerprint"
                ],
            )
        )

        decisions[
            accession
        ] = BioSampleDecision(
            status=row[
                "biosample_status"
            ],
            reason=row[
                "biosample_reason"
            ],
        )

    verified = _validate_fingerprints(
        population,
        fingerprints,
    )

    try:
        expected_decisions = (
            reconcile_verified_candidates(
                verified
            )
        )
    except Exception as exc:
        raise MonthlyBioSampleReconciliationError(
            "frozen repeated-BioSample reconciliation failed during audit"
        ) from exc

    if decisions != expected_decisions:
        raise MonthlyBioSampleReconciliationError(
            "monthly BioSample decisions differ from frozen reconciler"
        )

    (
        group_count,
        singleton_group_count,
        repeated_group_count,
        identical_repeated_group_count,
        differing_repeated_group_count,
    ) = _group_counts(
        verified
    )

    return MonthlyBioSampleBuild(
        population=population,
        fingerprints=verified,
        decisions=decisions,
        decision_rows=tuple(
            rows
        ),
        group_count=group_count,
        singleton_group_count=(
            singleton_group_count
        ),
        repeated_group_count=(
            repeated_group_count
        ),
        identical_repeated_group_count=(
            identical_repeated_group_count
        ),
        differing_repeated_group_count=(
            differing_repeated_group_count
        ),
    )


def audit_monthly_biosample_record(
    payload: bytes,
    *,
    source_truth_decisions_payload: bytes,
    expected_source_truth_decisions_sha256: str,
    current_metadata: Mapping[
        str,
        str,
    ],
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    source_truth_record_sha256: str,
    source_truth_completion_sha256: str,
    decisions_payload: bytes,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "monthly BioSample record must be bytes"
        )

    population = (
        build_monthly_biosample_population(
            source_truth_decisions_payload,
            expected_source_truth_decisions_sha256=(
                expected_source_truth_decisions_sha256
            ),
            current_metadata=current_metadata,
            release_id=release_id,
            source_snapshot_id=source_snapshot_id,
            origin_git_commit=origin_git_commit,
        )
    )

    rows = (
        audit_monthly_biosample_decisions(
            decisions_payload
        )
    )

    build = _build_from_decision_rows(
        population,
        rows,
    )

    expected = (
        serialize_monthly_biosample_record(
            build,
            source_truth_record_sha256=(
                source_truth_record_sha256
            ),
            source_truth_completion_sha256=(
                source_truth_completion_sha256
            ),
        )
    )

    if payload != expected:
        raise MonthlyBioSampleReconciliationError(
            "monthly BioSample record changed"
        )

    try:
        value = json.loads(
            payload.decode(
                "ascii"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlyBioSampleReconciliationError(
            "monthly BioSample record is invalid JSON"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise MonthlyBioSampleReconciliationError(
            "monthly BioSample record is not an object"
        )

    if (
        value.get(
            "schema_version"
        )
        != MONTHLY_BIOSAMPLE_RECORD_SCHEMA
        or value.get(
            "status"
        )
        != MONTHLY_BIOSAMPLE_STATUS
    ):
        raise MonthlyBioSampleReconciliationError(
            "monthly BioSample record schema/status changed"
        )

    return value
