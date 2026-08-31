"""Pure monthly source-truth composition for BacSelect production."""

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
)

from bacselect import (
    monthly_sequence_cache_catalogue as catalogue_contract,
)
from bacselect import source_truth
from bacselect.source_truth_execution import (
    SourceTruthDecision,
    accession_membership_sha256,
    decision_rows as frozen_decision_rows,
    relation_rows as frozen_relation_rows,
)


MONTHLY_SOURCE_TRUTH_RECORD_SCHEMA = (
    "bacselect-monthly-source-truth-record-v1"
)

MONTHLY_SOURCE_TRUTH_STATUS = (
    "MONTHLY_SOURCE_TRUTH_COMPLETE"
)

SEQUENCE_ELIGIBLE = (
    "eligible"
)

SEQUENCE_INELIGIBLE = (
    "ineligible"
)

TERMINAL_SOURCE_TRUTH_STATUSES = frozenset(
    {
        source_truth.SUITABLE,
        source_truth.EXCLUDE,
        source_truth.UNRESOLVED,
    }
)

DECISION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "source_evidence_sha256",
    "sequence_set_sha256",
    "duplicate_relation_count",
    "containment_relation_count",
    "source_truth_status",
    "source_truth_reason",
)

RELATION_FIELDS = (
    "canonical_genbank_assembly_accession",
    "relation_type",
    "left_component",
    "right_component",
    "inner_component",
    "outer_component",
    "inner_topology",
    "outer_topology",
    "relation",
    "outer_origin_crossing",
)

CANONICAL_GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

RELEASE_RE = re.compile(
    r"^[0-9]{4}\.(0[1-9]|1[0-2])$"
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)


class MonthlySourceTruthError(
    ValueError
):
    """Raised when monthly source-truth evidence fails closed."""


@dataclass(
    frozen=True,
)
class MonthlySourceTruthPopulation:
    release_id: str
    source_snapshot_id: str
    origin_git_commit: str
    sequence_cache_catalogue_sha256: str
    sequence_cache_entries_sha256: str
    retained_accessions: tuple[
        str,
        ...,
    ]
    sequence_eligible_accessions: tuple[
        str,
        ...,
    ]
    sequence_ineligible_accessions: tuple[
        str,
        ...,
    ]
    biosample_by_accession: Mapping[
        str,
        str,
    ]
    retained_accessions_sha256: str
    sequence_eligible_accessions_sha256: str
    sequence_ineligible_accessions_sha256: str


@dataclass(
    frozen=True,
)
class MonthlySourceTruthBuild:
    population: MonthlySourceTruthPopulation
    decisions: tuple[
        SourceTruthDecision,
        ...,
    ]
    decision_rows: tuple[
        Mapping[
            str,
            str,
        ],
        ...,
    ]
    relation_rows: tuple[
        Mapping[
            str,
            str,
        ],
        ...,
    ]


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
        raise MonthlySourceTruthError(
            f"{label} is not a lowercase SHA256"
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
        or RELEASE_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlySourceTruthError(
            "monthly source-truth release ID is invalid"
        )

    return value


def _git_commit(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlySourceTruthError(
            "monthly source-truth Git commit is invalid"
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
        or value != value.strip()
        or any(
            character.isspace()
            for character in value
        )
    ):
        raise MonthlySourceTruthError(
            "monthly source-truth snapshot ID is invalid"
        )

    return value


def _accession(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or CANONICAL_GCA_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlySourceTruthError(
            "monthly source-truth accession is invalid"
        )

    return value


def _biosample(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value != value.strip()
        or any(
            character.isspace()
            for character in value
        )
    ):
        raise MonthlySourceTruthError(
            "monthly source-truth BioSample is invalid"
        )

    return value


def _nonnegative_int(
    value: object,
    *,
    label: str,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 0
    ):
        raise MonthlySourceTruthError(
            f"{label} must be a non-negative integer"
        )

    return value


def _canonical_json_bytes(
    value: object,
) -> bytes:
    try:
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
    except (
        TypeError,
        ValueError,
        UnicodeEncodeError,
    ) as exc:
        raise MonthlySourceTruthError(
            "monthly source-truth record is not canonical-JSON serializable"
        ) from exc


def _serialize_tsv(
    rows: Iterable[
        Mapping[
            str,
            str,
        ]
    ],
    fields: tuple[
        str,
        ...,
    ],
) -> bytes:
    values = tuple(
        rows
    )

    for row in values:
        if (
            not isinstance(
                row,
                Mapping,
            )
            or set(
                row
            )
            != set(
                fields
            )
        ):
            raise MonthlySourceTruthError(
                "monthly source-truth TSV row schema changed"
            )

        if any(
            not isinstance(
                row[
                    field
                ],
                str,
            )
            for field in fields
        ):
            raise MonthlySourceTruthError(
                "monthly source-truth TSV values must be strings"
            )

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

    writer.writerows(
        values
    )

    try:
        return handle.getvalue().encode(
            "ascii"
        )
    except UnicodeEncodeError as exc:
        raise MonthlySourceTruthError(
            "monthly source-truth TSV is not ASCII"
        ) from exc


def _parse_tsv(
    payload: bytes,
    *,
    fields: tuple[
        str,
        ...,
    ],
    label: str,
) -> tuple[
    dict[
        str,
        str,
    ],
    ...,
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
        raise MonthlySourceTruthError(
            f"{label} is not ASCII"
        ) from exc

    if not text.endswith(
        "\n"
    ):
        raise MonthlySourceTruthError(
            f"{label} is not newline terminated"
        )

    reader = csv.DictReader(
        io.StringIO(
            text,
            newline="",
        ),
        delimiter="\t",
    )

    if tuple(
        reader.fieldnames
        or ()
    ) != fields:
        raise MonthlySourceTruthError(
            f"{label} schema changed"
        )

    rows: list[
        dict[
            str,
            str,
        ]
    ] = []

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
            raise MonthlySourceTruthError(
                f"{label} row schema changed"
            )

        values = {
            field:
                str(
                    row[
                        field
                    ]
                )
            for field in fields
        }

        rows.append(
            values
        )

    if _serialize_tsv(
        rows,
        fields,
    ) != payload:
        raise MonthlySourceTruthError(
            f"{label} is not canonical TSV"
        )

    return tuple(
        rows
    )


def _population_from_audited_catalogue(
    catalogue_record: Mapping[
        str,
        object,
    ],
    *,
    catalogue_sha256: str,
    current_metadata: Mapping[
        str,
        str,
    ],
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
) -> MonthlySourceTruthPopulation:
    release = _release_id(
        release_id
    )

    snapshot = _source_snapshot_id(
        source_snapshot_id
    )

    commit = _git_commit(
        origin_git_commit
    )

    catalogue_sha = _sha256(
        catalogue_sha256,
        label="sequence-cache catalogue SHA256",
    )

    if not isinstance(
        catalogue_record,
        Mapping,
    ):
        raise MonthlySourceTruthError(
            "audited sequence-cache catalogue has wrong type"
        )

    if catalogue_record.get(
        "release_id"
    ) != release:
        raise MonthlySourceTruthError(
            "sequence-cache catalogue release differs from current release"
        )

    if catalogue_record.get(
        "source_snapshot_id"
    ) != snapshot:
        raise MonthlySourceTruthError(
            "sequence-cache catalogue snapshot differs from current release"
        )

    if catalogue_record.get(
        "origin_git_commit"
    ) != commit:
        raise MonthlySourceTruthError(
            "sequence-cache catalogue commit differs from current execution"
        )

    entries_sha = _sha256(
        catalogue_record.get(
            "entries_sha256"
        ),
        label="sequence-cache catalogue entry-set SHA256",
    )

    entries_value = catalogue_record.get(
        "entries"
    )

    if not isinstance(
        entries_value,
        list,
    ):
        raise MonthlySourceTruthError(
            "sequence-cache catalogue entries are malformed"
        )

    if not isinstance(
        current_metadata,
        Mapping,
    ):
        raise TypeError(
            "current metadata must be a mapping"
        )

    metadata: dict[
        str,
        str,
    ] = {}

    for accession_value, biosample_value in (
        current_metadata.items()
    ):
        accession = _accession(
            accession_value
        )

        biosample = _biosample(
            biosample_value
        )

        if accession in metadata:
            raise MonthlySourceTruthError(
                "current metadata contains duplicate accession"
            )

        metadata[
            accession
        ] = biosample

    entry_by_accession: dict[
        str,
        Mapping[
            str,
            object,
        ]
    ] = {}

    seen_catalogue_accessions: set[
        str
    ] = set()

    eligible: list[
        str
    ] = []

    ineligible: list[
        str
    ] = []

    for value in entries_value:
        if not isinstance(
            value,
            Mapping,
        ):
            raise MonthlySourceTruthError(
                "sequence-cache catalogue entry is malformed"
            )

        accession = _accession(
            value.get(
                "canonical_genbank_assembly_accession"
            )
        )

        if accession in seen_catalogue_accessions:
            raise MonthlySourceTruthError(
                "sequence-cache catalogue contains duplicate accession"
            )

        seen_catalogue_accessions.add(
            accession
        )

        biosample = _biosample(
            value.get(
                "biosample"
            )
        )

        expected_biosample = (
            metadata.get(
                accession
            )
        )

        if expected_biosample is None:
            # The sequence-cache catalogue is cumulative. Historical
            # cache entries that are outside the current retained
            # metadata universe remain valid cache history but do not
            # enter the current Stage 4 population.
            continue

        if expected_biosample != biosample:
            raise MonthlySourceTruthError(
                "sequence-cache catalogue BioSample differs from "
                "current retained metadata"
            )

        state = value.get(
            "origin_sequence_eligibility"
        )

        if state == SEQUENCE_ELIGIBLE:
            eligible.append(
                accession
            )
        elif state == SEQUENCE_INELIGIBLE:
            ineligible.append(
                accession
            )
        else:
            raise MonthlySourceTruthError(
                "sequence-cache catalogue eligibility state changed"
            )

        entry_by_accession[
            accession
        ] = value

    missing = (
        set(
            metadata
        )
        - set(
            entry_by_accession
        )
    )

    if missing:
        raise MonthlySourceTruthError(
            "current retained metadata lacks complete "
            "sequence-cache catalogue coverage"
        )

    retained = tuple(
        sorted(
            metadata
        )
    )

    eligible_accessions = tuple(
        sorted(
            eligible
        )
    )

    ineligible_accessions = tuple(
        sorted(
            ineligible
        )
    )

    if (
        set(
            eligible_accessions
        )
        & set(
            ineligible_accessions
        )
    ):
        raise MonthlySourceTruthError(
            "sequence eligibility partition overlaps"
        )

    if set(
        retained
    ) != (
        set(
            eligible_accessions
        )
        | set(
            ineligible_accessions
        )
    ):
        raise MonthlySourceTruthError(
            "sequence eligibility partition is incomplete"
        )

    return MonthlySourceTruthPopulation(
        release_id=release,
        source_snapshot_id=snapshot,
        origin_git_commit=commit,
        sequence_cache_catalogue_sha256=(
            catalogue_sha
        ),
        sequence_cache_entries_sha256=(
            entries_sha
        ),
        retained_accessions=(
            retained
        ),
        sequence_eligible_accessions=(
            eligible_accessions
        ),
        sequence_ineligible_accessions=(
            ineligible_accessions
        ),
        biosample_by_accession={
            accession:
                metadata[
                    accession
                ]
            for accession in retained
        },
        retained_accessions_sha256=(
            accession_membership_sha256(
                retained
            )
        ),
        sequence_eligible_accessions_sha256=(
            accession_membership_sha256(
                eligible_accessions
            )
        ),
        sequence_ineligible_accessions_sha256=(
            accession_membership_sha256(
                ineligible_accessions
            )
        ),
    )


def build_monthly_source_truth_population(
    catalogue_payload: bytes,
    *,
    current_metadata: Mapping[
        str,
        str,
    ],
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
) -> MonthlySourceTruthPopulation:
    """Audit the current cumulative catalogue and freeze Stage 4 membership."""

    if not isinstance(
        catalogue_payload,
        bytes,
    ):
        raise TypeError(
            "sequence-cache catalogue payload must be bytes"
        )

    try:
        catalogue_record = (
            catalogue_contract.audit_sequence_cache_catalogue(
                catalogue_payload
            )
        )
    except Exception as exc:
        raise MonthlySourceTruthError(
            "current sequence-cache catalogue audit failed"
        ) from exc

    catalogue_sha = hashlib.sha256(
        catalogue_payload
    ).hexdigest()

    return _population_from_audited_catalogue(
        catalogue_record,
        catalogue_sha256=(
            catalogue_sha
        ),
        current_metadata=(
            current_metadata
        ),
        release_id=(
            release_id
        ),
        source_snapshot_id=(
            source_snapshot_id
        ),
        origin_git_commit=(
            origin_git_commit
        ),
    )


def build_monthly_source_truth(
    population: MonthlySourceTruthPopulation,
    decisions: Iterable[
        SourceTruthDecision
    ],
) -> MonthlySourceTruthBuild:
    """Bind frozen source-truth decisions to the monthly eligible population."""

    if not isinstance(
        population,
        MonthlySourceTruthPopulation,
    ):
        raise TypeError(
            "monthly source-truth population has wrong type"
        )

    values = tuple(
        decisions
    )

    if any(
        not isinstance(
            item,
            SourceTruthDecision,
        )
        for item in values
    ):
        raise TypeError(
            "monthly source-truth decision has wrong type"
        )

    ordered = tuple(
        sorted(
            values,
            key=lambda item:
                item.accession,
        )
    )

    accessions = tuple(
        item.accession
        for item in ordered
    )

    if len(
        accessions
    ) != len(
        set(
            accessions
        )
    ):
        raise MonthlySourceTruthError(
            "duplicate monthly source-truth decision accession"
        )

    if accessions != (
        population
        .sequence_eligible_accessions
    ):
        raise MonthlySourceTruthError(
            "monthly source-truth decisions do not exactly cover "
            "the sequence-eligible population"
        )

    ineligible_set = set(
        population
        .sequence_ineligible_accessions
    )

    if (
        set(
            accessions
        )
        & ineligible_set
    ):
        raise MonthlySourceTruthError(
            "sequence-ineligible candidate received a source-truth decision"
        )

    for item in ordered:
        _accession(
            item.accession
        )

        if item.source_evidence_sha256 is None:
            raise MonthlySourceTruthError(
                "monthly source-truth decision lacks source-evidence SHA256"
            )

        _sha256(
            item.source_evidence_sha256,
            label="source-truth source-evidence SHA256",
        )

        _sha256(
            item.sequence_set_sha256,
            label="source-truth sequence-set SHA256",
        )

        if item.status not in (
            TERMINAL_SOURCE_TRUTH_STATUSES
        ):
            raise MonthlySourceTruthError(
                "monthly source-truth decision is non-terminal"
            )

        if (
            not isinstance(
                item.reason,
                str,
            )
            or not item.reason
            or item.reason
            != item.reason.strip()
        ):
            raise MonthlySourceTruthError(
                "monthly source-truth decision reason is invalid"
            )

    try:
        decision_values = tuple(
            frozen_decision_rows(
                ordered
            )
        )

        relation_values = tuple(
            frozen_relation_rows(
                ordered
            )
        )
    except Exception as exc:
        raise MonthlySourceTruthError(
            "frozen source-truth output serialization failed"
        ) from exc

    return MonthlySourceTruthBuild(
        population=population,
        decisions=ordered,
        decision_rows=(
            decision_values
        ),
        relation_rows=(
            relation_values
        ),
    )


def serialize_monthly_source_truth_decisions(
    build: MonthlySourceTruthBuild,
) -> bytes:
    if not isinstance(
        build,
        MonthlySourceTruthBuild,
    ):
        raise TypeError(
            "monthly source-truth build has wrong type"
        )

    return _serialize_tsv(
        build.decision_rows,
        DECISION_FIELDS,
    )


def serialize_monthly_source_truth_relations(
    build: MonthlySourceTruthBuild,
) -> bytes:
    if not isinstance(
        build,
        MonthlySourceTruthBuild,
    ):
        raise TypeError(
            "monthly source-truth build has wrong type"
        )

    return _serialize_tsv(
        build.relation_rows,
        RELATION_FIELDS,
    )


def audit_monthly_source_truth_decisions(
    payload: bytes,
) -> tuple[
    Mapping[
        str,
        str,
    ],
    ...,
]:
    rows = _parse_tsv(
        payload,
        fields=(
            DECISION_FIELDS
        ),
        label="monthly source-truth decisions",
    )

    accessions: list[
        str
    ] = []

    for row in rows:
        accession = _accession(
            row[
                "canonical_genbank_assembly_accession"
            ]
        )

        accessions.append(
            accession
        )

        _sha256(
            row[
                "source_evidence_sha256"
            ],
            label="decision source-evidence SHA256",
        )

        _sha256(
            row[
                "sequence_set_sha256"
            ],
            label="decision sequence-set SHA256",
        )

        for field in (
            "duplicate_relation_count",
            "containment_relation_count",
        ):
            try:
                count = int(
                    row[
                        field
                    ]
                )
            except ValueError as exc:
                raise MonthlySourceTruthError(
                    f"decision {field} is invalid"
                ) from exc

            if count < 0:
                raise MonthlySourceTruthError(
                    f"decision {field} is negative"
                )

        if row[
            "source_truth_status"
        ] not in TERMINAL_SOURCE_TRUTH_STATUSES:
            raise MonthlySourceTruthError(
                "decision contains non-terminal source-truth status"
            )

        reason = row[
            "source_truth_reason"
        ]

        if (
            not reason
            or reason != reason.strip()
        ):
            raise MonthlySourceTruthError(
                "decision source-truth reason is invalid"
            )

    observed = tuple(
        accessions
    )

    if observed != tuple(
        sorted(
            observed
        )
    ):
        raise MonthlySourceTruthError(
            "monthly source-truth decisions are not sorted"
        )

    if len(
        observed
    ) != len(
        set(
            observed
        )
    ):
        raise MonthlySourceTruthError(
            "monthly source-truth decisions contain duplicate accession"
        )

    return tuple(
        rows
    )


def audit_monthly_source_truth_relations(
    payload: bytes,
) -> tuple[
    Mapping[
        str,
        str,
    ],
    ...,
]:
    rows = _parse_tsv(
        payload,
        fields=(
            RELATION_FIELDS
        ),
        label="monthly source-truth relations",
    )

    previous_accession: str | None = None

    seen: set[
        tuple[
            str,
            ...,
        ]
    ] = set()

    relation_phase_by_accession: dict[
        str,
        int,
    ] = {}

    previous_order_key: tuple[
        str,
        int,
        str,
        str,
        str,
        str,
    ] | None = None

    for row in rows:
        accession = _accession(
            row[
                "canonical_genbank_assembly_accession"
            ]
        )

        if (
            previous_accession is not None
            and accession
            < previous_accession
        ):
            raise MonthlySourceTruthError(
                "monthly source-truth relations are not sorted by accession"
            )

        previous_accession = accession

        relation_type = row[
            "relation_type"
        ]

        if relation_type == "duplicate":
            if any(
                (
                    row[
                        field
                    ]
                )
                for field in (
                    "inner_component",
                    "outer_component",
                    "inner_topology",
                    "outer_topology",
                    "outer_origin_crossing",
                )
            ):
                raise MonthlySourceTruthError(
                    "duplicate relation contains containment-only fields"
                )

            if (
                not row[
                    "left_component"
                ]
                or not row[
                    "right_component"
                ]
                or not row[
                    "relation"
                ]
            ):
                raise MonthlySourceTruthError(
                    "duplicate relation is incomplete"
                )

            phase = 0

            order_key = (
                accession,
                phase,
                row[
                    "left_component"
                ],
                row[
                    "right_component"
                ],
                row[
                    "relation"
                ],
                "",
            )

        elif relation_type == "containment":
            if (
                row[
                    "left_component"
                ]
                or row[
                    "right_component"
                ]
            ):
                raise MonthlySourceTruthError(
                    "containment relation contains duplicate-only fields"
                )

            if (
                not row[
                    "inner_component"
                ]
                or not row[
                    "outer_component"
                ]
                or not row[
                    "inner_topology"
                ]
                or not row[
                    "outer_topology"
                ]
                or not row[
                    "relation"
                ]
                or row[
                    "outer_origin_crossing"
                ]
                not in {
                    "0",
                    "1",
                }
            ):
                raise MonthlySourceTruthError(
                    "containment relation is incomplete"
                )

            phase = 1

            order_key = (
                accession,
                phase,
                row[
                    "inner_component"
                ],
                row[
                    "outer_component"
                ],
                row[
                    "relation"
                ],
                row[
                    "outer_origin_crossing"
                ],
            )

        else:
            raise MonthlySourceTruthError(
                "unknown monthly source-truth relation type"
            )

        if (
            previous_order_key is not None
            and order_key < previous_order_key
        ):
            raise MonthlySourceTruthError(
                "monthly source-truth relations are not "
                "deterministically ordered"
            )

        previous_order_key = (
            order_key
        )

        previous_phase = (
            relation_phase_by_accession.get(
                accession,
                0,
            )
        )

        if phase < previous_phase:
            raise MonthlySourceTruthError(
                "duplicate relation follows containment relation"
            )

        relation_phase_by_accession[
            accession
        ] = phase

        identity = tuple(
            row[
                field
            ]
            for field in RELATION_FIELDS
        )

        if identity in seen:
            raise MonthlySourceTruthError(
                "duplicate monthly source-truth relation row"
            )

        seen.add(
            identity
        )

    return tuple(
        rows
    )


def _record_from_rows(
    population: MonthlySourceTruthPopulation,
    *,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
    decisions_payload: bytes,
    decision_values: tuple[
        Mapping[
            str,
            str,
        ],
        ...,
    ],
    relations_payload: bytes,
    relation_values: tuple[
        Mapping[
            str,
            str,
        ],
        ...,
    ],
) -> dict[
    str,
    object,
]:
    decision_accessions = tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in decision_values
    )

    if decision_accessions != (
        population
        .sequence_eligible_accessions
    ):
        raise MonthlySourceTruthError(
            "source-truth decision manifest does not exactly cover "
            "the sequence-eligible population"
        )

    decision_set = set(
        decision_accessions
    )

    duplicate_counts = Counter()
    containment_counts = Counter()

    for row in relation_values:
        accession = row[
            "canonical_genbank_assembly_accession"
        ]

        if accession not in decision_set:
            raise MonthlySourceTruthError(
                "relation evidence references accession without "
                "a source-truth decision"
            )

        if row[
            "relation_type"
        ] == "duplicate":
            duplicate_counts[
                accession
            ] += 1
        else:
            containment_counts[
                accession
            ] += 1

    for row in decision_values:
        accession = row[
            "canonical_genbank_assembly_accession"
        ]

        if int(
            row[
                "duplicate_relation_count"
            ]
        ) != duplicate_counts[
            accession
        ]:
            raise MonthlySourceTruthError(
                "duplicate relation count differs from relation evidence"
            )

        if int(
            row[
                "containment_relation_count"
            ]
        ) != containment_counts[
            accession
        ]:
            raise MonthlySourceTruthError(
                "containment relation count differs from relation evidence"
            )

    status_counts = Counter(
        row[
            "source_truth_status"
        ]
        for row in decision_values
    )

    reason_counts = Counter(
        row[
            "source_truth_reason"
        ]
        for row in decision_values
    )

    return {
        "decision_count":
            len(
                decision_values
            ),
        "decision_manifest_sha256":
            hashlib.sha256(
                decisions_payload
            ).hexdigest(),
        "metadata_completion_sha256":
            _sha256(
                metadata_completion_sha256,
                label="metadata completion SHA256",
            ),
        "metadata_record_sha256":
            _sha256(
                metadata_record_sha256,
                label="metadata record SHA256",
            ),
        "origin_git_commit":
            population.origin_git_commit,
        "reason_counts":
            dict(
                sorted(
                    reason_counts.items()
                )
            ),
        "relation_count":
            len(
                relation_values
            ),
        "relation_manifest_sha256":
            hashlib.sha256(
                relations_payload
            ).hexdigest(),
        "release_id":
            population.release_id,
        "retained_accessions_sha256":
            population.retained_accessions_sha256,
        "retained_count":
            len(
                population.retained_accessions
            ),
        "schema_version":
            MONTHLY_SOURCE_TRUTH_RECORD_SCHEMA,
        "sequence_cache_catalogue_sha256":
            population.sequence_cache_catalogue_sha256,
        "sequence_cache_entries_sha256":
            population.sequence_cache_entries_sha256,
        "sequence_eligible_accessions_sha256":
            population.sequence_eligible_accessions_sha256,
        "sequence_eligible_count":
            len(
                population.sequence_eligible_accessions
            ),
        "sequence_ineligible_accessions_sha256":
            population.sequence_ineligible_accessions_sha256,
        "sequence_ineligible_count":
            len(
                population.sequence_ineligible_accessions
            ),
        "source_snapshot_id":
            population.source_snapshot_id,
        "status":
            MONTHLY_SOURCE_TRUTH_STATUS,
        "status_counts":
            dict(
                sorted(
                    status_counts.items()
                )
            ),
    }


def serialize_monthly_source_truth_record(
    build: MonthlySourceTruthBuild,
    *,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
) -> bytes:
    if not isinstance(
        build,
        MonthlySourceTruthBuild,
    ):
        raise TypeError(
            "monthly source-truth build has wrong type"
        )

    decisions_payload = (
        serialize_monthly_source_truth_decisions(
            build
        )
    )

    relations_payload = (
        serialize_monthly_source_truth_relations(
            build
        )
    )

    decision_values = (
        audit_monthly_source_truth_decisions(
            decisions_payload
        )
    )

    relation_values = (
        audit_monthly_source_truth_relations(
            relations_payload
        )
    )

    return _canonical_json_bytes(
        _record_from_rows(
            build.population,
            metadata_record_sha256=(
                metadata_record_sha256
            ),
            metadata_completion_sha256=(
                metadata_completion_sha256
            ),
            decisions_payload=(
                decisions_payload
            ),
            decision_values=(
                decision_values
            ),
            relations_payload=(
                relations_payload
            ),
            relation_values=(
                relation_values
            ),
        )
    )


def audit_monthly_source_truth_record(
    payload: bytes,
    *,
    catalogue_payload: bytes,
    current_metadata: Mapping[
        str,
        str,
    ],
    release_id: str,
    source_snapshot_id: str,
    origin_git_commit: str,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
    decisions_payload: bytes,
    relations_payload: bytes,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "monthly source-truth record must be bytes"
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
        raise MonthlySourceTruthError(
            "invalid monthly source-truth record JSON"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise MonthlySourceTruthError(
            "monthly source-truth record must be a JSON object"
        )

    if _canonical_json_bytes(
        value
    ) != payload:
        raise MonthlySourceTruthError(
            "monthly source-truth record is not canonical JSON"
        )

    population = (
        build_monthly_source_truth_population(
            catalogue_payload,
            current_metadata=(
                current_metadata
            ),
            release_id=(
                release_id
            ),
            source_snapshot_id=(
                source_snapshot_id
            ),
            origin_git_commit=(
                origin_git_commit
            ),
        )
    )

    decision_values = (
        audit_monthly_source_truth_decisions(
            decisions_payload
        )
    )

    relation_values = (
        audit_monthly_source_truth_relations(
            relations_payload
        )
    )

    expected = _record_from_rows(
        population,
        metadata_record_sha256=(
            metadata_record_sha256
        ),
        metadata_completion_sha256=(
            metadata_completion_sha256
        ),
        decisions_payload=(
            decisions_payload
        ),
        decision_values=(
            decision_values
        ),
        relations_payload=(
            relations_payload
        ),
        relation_values=(
            relation_values
        ),
    )

    if value != expected:
        raise MonthlySourceTruthError(
            "monthly source-truth record changed"
        )

    if value[
        "schema_version"
    ] != MONTHLY_SOURCE_TRUTH_RECORD_SCHEMA:
        raise MonthlySourceTruthError(
            "monthly source-truth record schema changed"
        )

    if value[
        "status"
    ] != MONTHLY_SOURCE_TRUTH_STATUS:
        raise MonthlySourceTruthError(
            "monthly source-truth record status changed"
        )

    retained = _nonnegative_int(
        value[
            "retained_count"
        ],
        label="retained count",
    )

    eligible = _nonnegative_int(
        value[
            "sequence_eligible_count"
        ],
        label="sequence-eligible count",
    )

    ineligible = _nonnegative_int(
        value[
            "sequence_ineligible_count"
        ],
        label="sequence-ineligible count",
    )

    if retained != (
        eligible
        + ineligible
    ):
        raise MonthlySourceTruthError(
            "monthly sequence-eligibility accounting changed"
        )

    if value[
        "decision_count"
    ] != eligible:
        raise MonthlySourceTruthError(
            "source-truth decision count differs from eligible count"
        )

    return value
