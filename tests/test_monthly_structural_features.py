from __future__ import annotations

import hashlib

import pytest

from bacselect import monthly_structural_features as monthly
from bacselect import source_structural_feature_execution as execution


def identity(
    text: str,
) -> str:
    return hashlib.sha256(
        text.encode(
            "ascii"
        )
    ).hexdigest()


def features(
    offset: int = 0,
):
    return {
        "01_total_genome_length":
            5_000_000
            + offset,
        "02_whole_genome_gc_fraction":
            0.51,
        "03_replicon_count":
            2,
        "04_non_chromosomal_replicon_count":
            1,
        "05_non_chromosomal_sequence_fraction":
            0.02,
        "06_non_unique_canonical_300mer_fraction":
            0.001,
        "07_non_unique_canonical_2400mer_fraction":
            0.0001,
        "08_maximum_canonical_300mer_multiplicity":
            4,
        "09_maximum_canonical_2400mer_multiplicity":
            2,
        "10_longest_exact_repeat_length":
            3001,
        "11_inter_replicon_shared_canonical_300mer_fraction":
            0.0002,
        "12_inter_replicon_shared_canonical_2400mer_fraction":
            0.00002,
    }


def member(
    accession: str,
    taxid: str,
):
    return monthly.MonthlyUniverseMember(
        accession=accession,
        species_taxid=taxid,
    )


def cached(
    accession: str,
    identity_sha: str,
    *,
    offset: int = 0,
):
    return monthly.CachedFeatureRow(
        accession=accession,
        component_identity_sha256=(
            identity_sha
        ),
        features=features(
            offset
        ),
    )


def computed(
    accession: str,
    taxid: str,
    *,
    offset: int = 0,
):
    values = features(
        offset
    )

    return execution.Stage6FeatureRecord(
        accession=accession,
        species_taxid=taxid,
        features=values,
        retained_replicon_count=(
            values[
                "03_replicon_count"
            ]
        ),
        total_sequence_length=(
            values[
                "01_total_genome_length"
            ]
        ),
    )


def test_reuses_tier1_and_applies_current_taxonomy():
    accession = "GCA_000000001.1"
    current = identity(
        "same"
    )

    build = (
        monthly
        .build_monthly_structural_features(
            [
                member(
                    accession,
                    "999",
                )
            ],
            current_component_identity_by_accession={
                accession:
                    current,
            },
            tier1_cache={
                accession:
                    cached(
                        accession,
                        current,
                    ),
            },
            tier2_cache={},
            computed_rows={},
        )
    )

    assert (
        build.rows[0].species_taxid
        == "999"
    )

    assert (
        build.rows[0].provenance_class
        == monthly.CACHE_TIER1
    )


def test_tier1_has_precedence_over_tier2():
    accession = "GCA_000000002.1"
    current = identity(
        "same"
    )

    build = (
        monthly
        .build_monthly_structural_features(
            [
                member(
                    accession,
                    "2",
                )
            ],
            current_component_identity_by_accession={
                accession:
                    current,
            },
            tier1_cache={
                accession:
                    cached(
                        accession,
                        current,
                        offset=1,
                    ),
            },
            tier2_cache={
                accession:
                    cached(
                        accession,
                        current,
                        offset=2,
                    ),
            },
            computed_rows={},
        )
    )

    assert (
        build.rows[0].provenance_class
        == monthly.CACHE_TIER1
    )

    assert (
        build.rows[0]
        .features[
            "01_total_genome_length"
        ]
        == 5_000_001
    )


def test_falls_through_to_tier2_on_tier1_identity_change():
    accession = "GCA_000000003.1"

    current = identity(
        "current"
    )

    build = (
        monthly
        .build_monthly_structural_features(
            [
                member(
                    accession,
                    "3",
                )
            ],
            current_component_identity_by_accession={
                accession:
                    current,
            },
            tier1_cache={
                accession:
                    cached(
                        accession,
                        identity(
                            "old"
                        ),
                    ),
            },
            tier2_cache={
                accession:
                    cached(
                        accession,
                        current,
                    ),
            },
            computed_rows={},
        )
    )

    assert (
        build.rows[0].provenance_class
        == monthly.CACHE_TIER2
    )


def test_changed_component_identity_requires_compute():
    accession = "GCA_024207115.1"

    current = identity(
        "topology-linear"
    )

    build = (
        monthly
        .build_monthly_structural_features(
            [
                member(
                    accession,
                    "123",
                )
            ],
            current_component_identity_by_accession={
                accession:
                    current,
            },
            tier1_cache={
                accession:
                    cached(
                        accession,
                        identity(
                            "topology-circular"
                        ),
                    ),
            },
            tier2_cache={},
            computed_rows={
                accession:
                    computed(
                        accession,
                        "123",
                    ),
            },
        )
    )

    assert (
        build.computed_accessions
        == (
            accession,
        )
    )

    assert (
        build.rows[0].provenance_class
        == monthly.COMPUTED
    )


def test_missing_required_computation_fails_closed():
    accession = "GCA_000000004.1"

    with pytest.raises(
        monthly.MonthlyStructuralFeatureError,
        match=(
            "requires fresh "
            "structural-feature computation"
        ),
    ):
        (
            monthly
            .build_monthly_structural_features(
                [
                    member(
                        accession,
                        "4",
                    )
                ],
                current_component_identity_by_accession={
                    accession:
                        identity(
                            "current"
                        ),
                },
                tier1_cache={},
                tier2_cache={},
                computed_rows={},
            )
        )


def test_unused_computation_fails_closed():
    accession = "GCA_000000005.1"
    current = identity(
        "same"
    )

    with pytest.raises(
        monthly.MonthlyStructuralFeatureError,
        match="contain rows that were reusable",
    ):
        (
            monthly
            .build_monthly_structural_features(
                [
                    member(
                        accession,
                        "5",
                    )
                ],
                current_component_identity_by_accession={
                    accession:
                        current,
                },
                tier1_cache={
                    accession:
                        cached(
                            accession,
                            current,
                        ),
                },
                tier2_cache={},
                computed_rows={
                    accession:
                        computed(
                            accession,
                            "5",
                        ),
                },
            )
        )


def test_current_species_taxid_is_required_for_fresh_row():
    accession = "GCA_000000006.1"

    with pytest.raises(
        monthly.MonthlyStructuralFeatureError,
        match="species TaxID differs",
    ):
        (
            monthly
            .build_monthly_structural_features(
                [
                    member(
                        accession,
                        "6",
                    )
                ],
                current_component_identity_by_accession={
                    accession:
                        identity(
                            "current"
                        ),
                },
                tier1_cache={},
                tier2_cache={},
                computed_rows={
                    accession:
                        computed(
                            accession,
                            "7",
                        ),
                },
            )
        )


def test_serialized_matrix_contains_only_raw_features():
    accession = "GCA_000000007.1"
    current = identity(
        "same"
    )

    build = (
        monthly
        .build_monthly_structural_features(
            [
                member(
                    accession,
                    "7",
                )
            ],
            current_component_identity_by_accession={
                accession:
                    current,
            },
            tier1_cache={
                accession:
                    cached(
                        accession,
                        current,
                    ),
            },
            tier2_cache={},
            computed_rows={},
        )
    )

    payload = (
        monthly
        .serialize_monthly_structural_feature_matrix(
            build
        )
    )

    header = (
        payload.splitlines()[0]
        .decode(
            "ascii"
        )
        .split(
            "\t"
        )
    )

    assert tuple(
        header
    ) == monthly.MATRIX_FIELDS

    assert not any(
        "percentile" in field
        for field in header
    )

    assert not any(
        field.startswith(
            "ops"
        )
        for field in header
    )


def test_provenance_serialization_distinguishes_cache_and_compute():
    a = "GCA_000000008.1"
    b = "GCA_000000009.1"

    ia = identity(
        "a"
    )
    ib = identity(
        "b"
    )

    build = (
        monthly
        .build_monthly_structural_features(
            [
                member(
                    a,
                    "8",
                ),
                member(
                    b,
                    "9",
                ),
            ],
            current_component_identity_by_accession={
                a:
                    ia,
                b:
                    ib,
            },
            tier1_cache={
                a:
                    cached(
                        a,
                        ia,
                    ),
            },
            tier2_cache={},
            computed_rows={
                b:
                    computed(
                        b,
                        "9",
                    ),
            },
        )
    )

    payload = (
        monthly
        .serialize_monthly_structural_feature_provenance(
            build
        )
    )

    text = payload.decode(
        "ascii"
    )

    assert (
        monthly.CACHE_TIER1
        in text
    )

    assert (
        monthly.COMPUTED
        in text
    )
