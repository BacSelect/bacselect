"""Pure monthly structural-feature cache/recompute composition.

This module does not perform package discovery, filesystem publication,
percentile geometry, representative selection, OPS ranking, or panel
construction.

It combines:

* the current monthly complete universe;
* exact component-identity fingerprints;
* authenticated historical raw-feature caches; and
* freshly computed raw-feature records.

Cached raw feature values are reusable only when the exact component
identity matches. Current monthly species TaxIDs are always authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
import struct
from typing import Mapping, Sequence

from bacselect import source_structural_feature_execution as structural
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

POSITIVE_INTEGER_RE = re.compile(
    r"^[1-9][0-9]*$"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

FEATURE_FIELDS = tuple(
    structural.FEATURE_FIELDS
)

MATRIX_FIELDS = (
    "canonical_genbank_assembly_accession",
    "species_taxid",
    *FEATURE_FIELDS,
)

INTEGER_FEATURE_FIELDS = frozenset(
    {
        "01_total_genome_length",
        "03_replicon_count",
        "04_non_chromosomal_replicon_count",
        "08_maximum_canonical_300mer_multiplicity",
        "09_maximum_canonical_2400mer_multiplicity",
        "10_longest_exact_repeat_length",
    }
)

CACHE_TIER1 = "FULL_UNIVERSE_CACHE"
CACHE_TIER2 = "STAGE6_CACHE"
COMPUTED = "COMPUTE"


class MonthlyStructuralFeatureError(
    ValueError
):
    """Monthly raw structural-feature composition failed closed."""


@dataclass(
    frozen=True,
)
class MonthlyUniverseMember:
    accession: str
    species_taxid: str


@dataclass(
    frozen=True,
)
class CachedFeatureRow:
    accession: str
    component_identity_sha256: str
    features: Mapping[
        str,
        int | float,
    ]


@dataclass(
    frozen=True,
)
class MonthlyStructuralFeatureRow:
    accession: str
    species_taxid: str
    component_identity_sha256: str
    provenance_class: str
    features: Mapping[
        str,
        int | float,
    ]


@dataclass(
    frozen=True,
)
class MonthlyStructuralFeatureBuild:
    rows: tuple[
        MonthlyStructuralFeatureRow,
        ...
    ]
    tier1_accessions: tuple[
        str,
        ...
    ]
    tier2_accessions: tuple[
        str,
        ...
    ]
    computed_accessions: tuple[
        str,
        ...
    ]
    membership_sha256: str
    tier1_membership_sha256: str
    tier2_membership_sha256: str
    computed_membership_sha256: str
    partition_mapping_sha256: str
    numeric_array_sha256: str


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
        raise MonthlyStructuralFeatureError(
            "assembly accession is invalid"
        )

    return value


def _species_taxid(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or POSITIVE_INTEGER_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyStructuralFeatureError(
            "species TaxID is invalid"
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
        raise MonthlyStructuralFeatureError(
            f"{label} is not a lowercase SHA256"
        )

    return value




def validate_features(
    features: Mapping[
        str,
        int | float,
    ],
) -> dict[
    str,
    int | float,
]:
    if not isinstance(
        features,
        Mapping,
    ):
        raise MonthlyStructuralFeatureError(
            "feature vector is not a mapping"
        )

    if tuple(
        features
    ) != FEATURE_FIELDS:
        raise MonthlyStructuralFeatureError(
            "feature vector schema/order changed"
        )

    result: dict[
        str,
        int | float,
    ] = {}

    for field in FEATURE_FIELDS:
        value = features[
            field
        ]

        if field in INTEGER_FEATURE_FIELDS:
            if (
                isinstance(
                    value,
                    bool,
                )
                or not isinstance(
                    value,
                    int,
                )
            ):
                raise MonthlyStructuralFeatureError(
                    f"{field} must be integer"
                )

            result[
                field
            ] = value

            continue

        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                (
                    int,
                    float,
                ),
            )
        ):
            raise MonthlyStructuralFeatureError(
                f"{field} must be numeric"
            )

        numeric = float(
            value
        )

        if not math.isfinite(
            numeric
        ):
            raise MonthlyStructuralFeatureError(
                f"{field} is non-finite"
            )

        result[
            field
        ] = numeric

    return result


def _validate_cache(
    cache: Mapping[
        str,
        CachedFeatureRow,
    ],
    *,
    label: str,
) -> dict[
    str,
    CachedFeatureRow,
]:
    if not isinstance(
        cache,
        Mapping,
    ):
        raise MonthlyStructuralFeatureError(
            f"{label} is not a mapping"
        )

    result = {}

    for accession_value, row in (
        cache.items()
    ):
        accession = _accession(
            accession_value
        )

        if not isinstance(
            row,
            CachedFeatureRow,
        ):
            raise MonthlyStructuralFeatureError(
                f"{label} contains wrong row type"
            )

        if (
            _accession(
                row.accession
            )
            != accession
        ):
            raise MonthlyStructuralFeatureError(
                f"{label} accession binding changed"
            )

        result[
            accession
        ] = CachedFeatureRow(
            accession=accession,
            component_identity_sha256=(
                _sha256(
                    row.component_identity_sha256,
                    label=(
                        f"{label} component identity"
                    ),
                )
            ),
            features=validate_features(
                row.features
            ),
        )

    return result


def build_monthly_structural_features(
    universe: Sequence[
        MonthlyUniverseMember,
    ],
    *,
    current_component_identity_by_accession: Mapping[
        str,
        str,
    ],
    tier1_cache: Mapping[
        str,
        CachedFeatureRow,
    ],
    tier2_cache: Mapping[
        str,
        CachedFeatureRow,
    ],
    computed_rows: Mapping[
        str,
        structural.Stage6FeatureRecord,
    ],
) -> MonthlyStructuralFeatureBuild:
    """Compose one raw-feature row for every current monthly universe member."""

    members: dict[
        str,
        MonthlyUniverseMember,
    ] = {}

    ordered_accessions = []

    for value in universe:
        if not isinstance(
            value,
            MonthlyUniverseMember,
        ):
            raise MonthlyStructuralFeatureError(
                "monthly universe contains wrong row type"
            )

        accession = _accession(
            value.accession
        )

        species_taxid = (
            _species_taxid(
                value.species_taxid
            )
        )

        if accession in members:
            raise MonthlyStructuralFeatureError(
                "monthly universe contains duplicate accession"
            )

        members[
            accession
        ] = MonthlyUniverseMember(
            accession=accession,
            species_taxid=species_taxid,
        )

        ordered_accessions.append(
            accession
        )

    current_identity = {}

    for accession_value, sha_value in (
        current_component_identity_by_accession
        .items()
    ):
        accession = _accession(
            accession_value
        )

        current_identity[
            accession
        ] = _sha256(
            sha_value,
            label=(
                "current component identity"
            ),
        )

    if set(
        current_identity
    ) != set(
        members
    ):
        raise MonthlyStructuralFeatureError(
            "current component identity membership differs from monthly universe"
        )

    tier1 = _validate_cache(
        tier1_cache,
        label="Tier 1 cache",
    )

    tier2 = _validate_cache(
        tier2_cache,
        label="Tier 2 cache",
    )

    if not isinstance(
        computed_rows,
        Mapping,
    ):
        raise MonthlyStructuralFeatureError(
            "computed rows are not a mapping"
        )

    result_rows = []

    tier1_accessions = []
    tier2_accessions = []
    compute_accessions = []

    used_computed = set()

    for accession in ordered_accessions:
        member = members[
            accession
        ]

        identity = current_identity[
            accession
        ]

        first = tier1.get(
            accession
        )

        if (
            first is not None
            and first.component_identity_sha256
            == identity
        ):
            result_rows.append(
                MonthlyStructuralFeatureRow(
                    accession=accession,
                    species_taxid=(
                        member.species_taxid
                    ),
                    component_identity_sha256=(
                        identity
                    ),
                    provenance_class=(
                        CACHE_TIER1
                    ),
                    features=dict(
                        first.features
                    ),
                )
            )

            tier1_accessions.append(
                accession
            )

            continue

        second = tier2.get(
            accession
        )

        if (
            second is not None
            and second.component_identity_sha256
            == identity
        ):
            result_rows.append(
                MonthlyStructuralFeatureRow(
                    accession=accession,
                    species_taxid=(
                        member.species_taxid
                    ),
                    component_identity_sha256=(
                        identity
                    ),
                    provenance_class=(
                        CACHE_TIER2
                    ),
                    features=dict(
                        second.features
                    ),
                )
            )

            tier2_accessions.append(
                accession
            )

            continue

        record = computed_rows.get(
            accession
        )

        if record is None:
            raise MonthlyStructuralFeatureError(
                f"{accession} requires fresh structural-feature computation"
            )

        if not isinstance(
            record,
            structural.Stage6FeatureRecord,
        ):
            raise MonthlyStructuralFeatureError(
                "fresh feature row has wrong type"
            )

        if (
            _accession(
                record.accession
            )
            != accession
        ):
            raise MonthlyStructuralFeatureError(
                "fresh feature-record accession changed"
            )

        if (
            _species_taxid(
                record.species_taxid
            )
            != member.species_taxid
        ):
            raise MonthlyStructuralFeatureError(
                "fresh feature-record species TaxID differs from current universe"
            )

        result_rows.append(
            MonthlyStructuralFeatureRow(
                accession=accession,
                species_taxid=(
                    member.species_taxid
                ),
                component_identity_sha256=(
                    identity
                ),
                provenance_class=(
                    COMPUTED
                ),
                features=validate_features(
                    record.features
                ),
            )
        )

        used_computed.add(
            accession
        )

        compute_accessions.append(
            accession
        )

    extra_computed = (
        set(
            computed_rows
        )
        - used_computed
    )

    if extra_computed:
        raise MonthlyStructuralFeatureError(
            "fresh structural-feature results contain rows that were reusable"
        )

    partition_payload = "".join(
        row.accession
        + "\t"
        + row.provenance_class
        + "\t"
        + row.component_identity_sha256
        + "\n"
        for row in sorted(
            result_rows,
            key=lambda item:
                item.accession,
        )
    ).encode(
        "ascii"
    )

    numeric = hashlib.sha256()

    for row in result_rows:
        for field in FEATURE_FIELDS:
            value = float(
                row.features[
                    field
                ]
            )

            if not math.isfinite(
                value
            ):
                raise MonthlyStructuralFeatureError(
                    "non-finite value in numeric feature array"
                )

            numeric.update(
                struct.pack(
                    "<d",
                    value,
                )
            )

    return MonthlyStructuralFeatureBuild(
        rows=tuple(
            result_rows
        ),
        tier1_accessions=tuple(
            tier1_accessions
        ),
        tier2_accessions=tuple(
            tier2_accessions
        ),
        computed_accessions=tuple(
            compute_accessions
        ),
        membership_sha256=(
            accession_membership_sha256(
                ordered_accessions
            )
        ),
        tier1_membership_sha256=(
            accession_membership_sha256(
                tier1_accessions
            )
        ),
        tier2_membership_sha256=(
            accession_membership_sha256(
                tier2_accessions
            )
        ),
        computed_membership_sha256=(
            accession_membership_sha256(
                compute_accessions
            )
        ),
        partition_mapping_sha256=(
            hashlib.sha256(
                partition_payload
            ).hexdigest()
        ),
        numeric_array_sha256=(
            numeric.hexdigest()
        ),
    )


def _format_feature(
    field: str,
    value: int | float,
) -> str:
    if field in INTEGER_FEATURE_FIELDS:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
        ):
            raise MonthlyStructuralFeatureError(
                "integer feature has non-integer value"
            )

        return str(
            value
        )

    numeric = float(
        value
    )

    if not math.isfinite(
        numeric
    ):
        raise MonthlyStructuralFeatureError(
            "floating feature is non-finite"
        )

    return format(
        numeric,
        ".17g",
    )


def serialize_monthly_structural_feature_matrix(
    build: MonthlyStructuralFeatureBuild,
) -> bytes:
    if not isinstance(
        build,
        MonthlyStructuralFeatureBuild,
    ):
        raise TypeError(
            "monthly structural-feature build has wrong type"
        )

    output = [
        "\t".join(
            MATRIX_FIELDS
        )
        + "\n"
    ]

    for row in build.rows:
        values = [
            row.accession,
            row.species_taxid,
        ]

        values.extend(
            _format_feature(
                field,
                row.features[
                    field
                ],
            )
            for field in FEATURE_FIELDS
        )

        output.append(
            "\t".join(
                values
            )
            + "\n"
        )

    return "".join(
        output
    ).encode(
        "ascii"
    )


def serialize_monthly_structural_feature_provenance(
    build: MonthlyStructuralFeatureBuild,
) -> bytes:
    if not isinstance(
        build,
        MonthlyStructuralFeatureBuild,
    ):
        raise TypeError(
            "monthly structural-feature build has wrong type"
        )

    fields = (
        "canonical_genbank_assembly_accession",
        "component_identity_sha256",
        "feature_provenance",
    )

    output = [
        "\t".join(
            fields
        )
        + "\n"
    ]

    for row in build.rows:
        output.append(
            "\t".join(
                (
                    row.accession,
                    row.component_identity_sha256,
                    row.provenance_class,
                )
            )
            + "\n"
        )

    return "".join(
        output
    ).encode(
        "ascii"
    )
