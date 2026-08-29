from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from bacselect.source_holdout import (
    ADEQUACY_FAIL,
    ADEQUACY_MIN_GENOMES,
    ADEQUACY_MIN_SPECIES,
    ADEQUACY_PASS,
    EXTERNAL_HOLDOUT_FIELDS,
    FROZEN_HISTORICAL_MEMBERSHIP_SUMMARY,
    HISTORICAL_ABSENT_FROM_BASELINE,
    HISTORICAL_BASELINE_ACCESSIONS,
    HISTORICAL_BASELINE_NOT_METADATA_RETAINED,
    HISTORICAL_METADATA_RETAINED,
    HISTORICAL_PRESENT_IN_BASELINE,
    RECONSTRUCTED_ABSENCE_FIELDS,
    CompleteUniverseMember,
    HoldoutError,
    HoldoutMember,
    canonical_accession_set,
    derive_external_holdout,
    evaluate_adequacy,
    external_holdout_rows,
    holdout_membership_sha256,
    reconstruct_retained_absent_from_baseline,
    reconstructed_absence_rows,
    summarize_holdout,
    validate_complete_universe,
    validate_holdout,
)
from bacselect.source_membership import MembershipSummary
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


HELPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "bacselect"
    / "source_holdout.py"
)


def accession(
    value: int,
) -> str:
    return f"GCA_{value:09d}.1"


def member(
    value: int,
    species: int,
) -> CompleteUniverseMember:
    return CompleteUniverseMember(
        accession=accession(
            value
        ),
        species_taxid=species,
    )


def holdout_member(
    value: int,
    species: int,
) -> HoldoutMember:
    return HoldoutMember(
        accession=accession(
            value
        ),
        species_taxid=species,
    )


def synthetic_expected_summary() -> MembershipSummary:
    return MembershipSummary(
        baseline_accessions=4,
        metadata_retained=6,
        retained_present_in_baseline=3,
        retained_absent_from_baseline=3,
        baseline_not_in_metadata_retained=1,
    )


def test_frozen_output_schemas():
    assert RECONSTRUCTED_ABSENCE_FIELDS == (
        "canonical_genbank_assembly_accession",
    )

    assert EXTERNAL_HOLDOUT_FIELDS == (
        "canonical_genbank_assembly_accession",
        "species_taxid",
    )


def test_frozen_historical_constants():
    assert HISTORICAL_BASELINE_ACCESSIONS == 55_306
    assert HISTORICAL_METADATA_RETAINED == 70_477
    assert HISTORICAL_PRESENT_IN_BASELINE == 55_032
    assert HISTORICAL_ABSENT_FROM_BASELINE == 15_445

    assert (
        HISTORICAL_BASELINE_NOT_METADATA_RETAINED
        == 274
    )

    assert FROZEN_HISTORICAL_MEMBERSHIP_SUMMARY == (
        MembershipSummary(
            baseline_accessions=55_306,
            metadata_retained=70_477,
            retained_present_in_baseline=55_032,
            retained_absent_from_baseline=15_445,
            baseline_not_in_metadata_retained=274,
        )
    )


def test_frozen_adequacy_constants():
    assert ADEQUACY_MIN_GENOMES == 1_000
    assert ADEQUACY_MIN_SPECIES == 200

    assert ADEQUACY_PASS == "ADEQUACY_PASS"

    assert (
        ADEQUACY_FAIL
        == "ADEQUACY_FAIL_NO_SELECTOR_DECISION"
    )


def test_canonical_accession_set_sorts_only_at_serialization():
    observed = canonical_accession_set(
        [
            accession(3),
            accession(1),
            accession(2),
        ],
        label="synthetic membership",
    )

    assert observed == frozenset(
        {
            accession(1),
            accession(2),
            accession(3),
        }
    )


def test_canonical_accession_set_rejects_duplicate():
    with pytest.raises(
        HoldoutError,
        match="duplicate accession",
    ):
        canonical_accession_set(
            [
                accession(1),
                accession(1),
            ],
            label="synthetic membership",
        )


def test_canonical_accession_set_rejects_noncanonical():
    with pytest.raises(
        HoldoutError,
        match="versioned canonical GCA",
    ):
        canonical_accession_set(
            [
                "GCF_000000001.1",
            ],
            label="synthetic membership",
        )


def test_historical_reconstruction_exact_partition():
    baseline = [
        accession(1),
        accession(2),
        accession(3),
        accession(4),
    ]

    retained = [
        accession(2),
        accession(3),
        accession(4),
        accession(5),
        accession(6),
        accession(7),
    ]

    observed = reconstruct_retained_absent_from_baseline(
        baseline,
        retained,
        expected_summary=synthetic_expected_summary(),
    )

    assert (
        observed.retained_absent_from_baseline
        == (
            accession(5),
            accession(6),
            accession(7),
        )
    )

    assert observed.summary == synthetic_expected_summary()

    assert observed.membership_sha256 == (
        accession_membership_sha256(
            [
                accession(5),
                accession(6),
                accession(7),
            ]
        )
    )


def test_historical_reconstruction_fails_if_aggregate_differs():
    baseline = [
        accession(1),
        accession(2),
    ]

    retained = [
        accession(2),
        accession(3),
    ]

    with pytest.raises(
        HoldoutError,
        match="does not reproduce frozen result",
    ):
        reconstruct_retained_absent_from_baseline(
            baseline,
            retained,
            expected_summary=MembershipSummary(
                baseline_accessions=2,
                metadata_retained=2,
                retained_present_in_baseline=2,
                retained_absent_from_baseline=0,
                baseline_not_in_metadata_retained=0,
            ),
        )


def test_historical_reconstruction_rejects_duplicate_retained():
    with pytest.raises(
        HoldoutError,
        match="duplicate accession",
    ):
        reconstruct_retained_absent_from_baseline(
            [
                accession(1),
            ],
            [
                accession(2),
                accession(2),
            ],
            expected_summary=MembershipSummary(
                baseline_accessions=1,
                metadata_retained=1,
                retained_present_in_baseline=0,
                retained_absent_from_baseline=1,
                baseline_not_in_metadata_retained=1,
            ),
        )


def test_validate_complete_universe_sorts_and_checks_membership():
    values = [
        member(3, 30),
        member(1, 10),
        member(2, 20),
    ]

    expected_sha = accession_membership_sha256(
        [
            accession(1),
            accession(2),
            accession(3),
        ]
    )

    observed = validate_complete_universe(
        values,
        expected_count=3,
        expected_species_count=3,
        expected_membership_sha256=expected_sha,
    )

    assert [
        item.accession
        for item in observed
    ] == [
        accession(1),
        accession(2),
        accession(3),
    ]


def test_validate_complete_universe_rejects_duplicate():
    with pytest.raises(
        HoldoutError,
        match="duplicate complete-universe accession",
    ):
        validate_complete_universe(
            [
                member(1, 10),
                member(1, 10),
            ]
        )


def test_validate_complete_universe_rejects_invalid_species():
    with pytest.raises(
        HoldoutError,
        match="positive integer",
    ):
        validate_complete_universe(
            [
                member(1, 0),
            ]
        )


def test_validate_complete_universe_rejects_wrong_fingerprint():
    with pytest.raises(
        HoldoutError,
        match="membership SHA256 mismatch",
    ):
        validate_complete_universe(
            [
                member(1, 10),
            ],
            expected_membership_sha256="0" * 64,
        )


def test_external_holdout_is_exact_intersection():
    universe = [
        member(1, 10),
        member(2, 20),
        member(3, 30),
        member(4, 40),
    ]

    absent = [
        accession(2),
        accession(4),
        accession(99),
    ]

    observed = derive_external_holdout(
        universe,
        absent,
    )

    assert observed == (
        HoldoutMember(
            accession=accession(2),
            species_taxid=20,
        ),
        HoldoutMember(
            accession=accession(4),
            species_taxid=40,
        ),
    )


def test_external_holdout_preserves_universe_species_taxid():
    observed = derive_external_holdout(
        [
            member(1, 101),
            member(2, 202),
        ],
        [
            accession(1),
        ],
    )

    assert observed == (
        HoldoutMember(
            accession=accession(1),
            species_taxid=101,
        ),
    )


def test_external_holdout_performs_no_downsampling():
    universe = [
        member(
            value,
            1 + (
                value % 5
            ),
        )
        for value in range(
            1,
            101,
        )
    ]

    absent = [
        accession(
            value
        )
        for value in range(
            1,
            101,
        )
    ]

    observed = derive_external_holdout(
        universe,
        absent,
    )

    assert len(
        observed
    ) == 100


def test_validate_holdout_sorts_deterministically():
    observed = validate_holdout(
        [
            holdout_member(3, 30),
            holdout_member(1, 10),
            holdout_member(2, 20),
        ]
    )

    assert [
        item.accession
        for item in observed
    ] == [
        accession(1),
        accession(2),
        accession(3),
    ]


def test_holdout_membership_fingerprint_matches_frozen_semantics():
    values = [
        holdout_member(3, 30),
        holdout_member(1, 10),
        holdout_member(2, 20),
    ]

    observed = holdout_membership_sha256(
        values
    )

    manual = hashlib.sha256(
        (
            accession(1)
            + "\n"
            + accession(2)
            + "\n"
            + accession(3)
            + "\n"
        ).encode(
            "ascii"
        )
    ).hexdigest()

    assert observed == manual


def test_holdout_summary_is_aggregate_only():
    summary = summarize_holdout(
        [
            holdout_member(1, 10),
            holdout_member(2, 10),
            holdout_member(3, 20),
        ]
    )

    assert summary.genome_count == 3
    assert summary.distinct_species_count == 2

    payload = summary.as_dict()

    assert set(
        payload
    ) == {
        "genome_count",
        "distinct_species_count",
        "membership_sha256",
    }

    assert "GCA_" not in repr(
        payload
    )


def test_reconstructed_absence_rows_are_sorted():
    baseline = [
        accession(1),
        accession(2),
        accession(3),
        accession(4),
    ]

    retained = [
        accession(2),
        accession(3),
        accession(4),
        accession(5),
        accession(6),
        accession(7),
    ]

    reconstruction = (
        reconstruct_retained_absent_from_baseline(
            baseline,
            retained,
            expected_summary=synthetic_expected_summary(),
        )
    )

    rows = reconstructed_absence_rows(
        reconstruction
    )

    assert rows == (
        {
            "canonical_genbank_assembly_accession":
                accession(5),
        },
        {
            "canonical_genbank_assembly_accession":
                accession(6),
        },
        {
            "canonical_genbank_assembly_accession":
                accession(7),
        },
    )


def test_external_holdout_rows_are_sorted_and_keep_species():
    rows = external_holdout_rows(
        [
            holdout_member(3, 30),
            holdout_member(1, 10),
            holdout_member(2, 20),
        ]
    )

    assert rows == (
        {
            "canonical_genbank_assembly_accession":
                accession(1),
            "species_taxid":
                "10",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(2),
            "species_taxid":
                "20",
        },
        {
            "canonical_genbank_assembly_accession":
                accession(3),
            "species_taxid":
                "30",
        },
    )


def test_adequacy_passes_at_exact_frozen_thresholds():
    values = [
        HoldoutMember(
            accession=accession(
                value
            ),
            species_taxid=(
                (
                    value - 1
                )
                % 200
            )
            + 1,
        )
        for value in range(
            1,
            1_001,
        )
    ]

    observed = evaluate_adequacy(
        values
    )

    assert observed.status == ADEQUACY_PASS
    assert observed.passed is True
    assert observed.genome_count == 1_000
    assert observed.distinct_species_count == 200


def test_adequacy_fails_one_genome_below_threshold():
    values = [
        HoldoutMember(
            accession=accession(
                value
            ),
            species_taxid=(
                (
                    value - 1
                )
                % 200
            )
            + 1,
        )
        for value in range(
            1,
            1_000,
        )
    ]

    observed = evaluate_adequacy(
        values
    )

    assert observed.status == ADEQUACY_FAIL
    assert observed.passed is False
    assert observed.genome_count == 999
    assert observed.distinct_species_count == 200


def test_adequacy_fails_one_species_below_threshold():
    values = [
        HoldoutMember(
            accession=accession(
                value
            ),
            species_taxid=(
                (
                    value - 1
                )
                % 199
            )
            + 1,
        )
        for value in range(
            1,
            1_001,
        )
    ]

    observed = evaluate_adequacy(
        values
    )

    assert observed.status == ADEQUACY_FAIL
    assert observed.passed is False
    assert observed.genome_count == 1_000
    assert observed.distinct_species_count == 199


def test_helper_has_no_file_io_or_downstream_imports():
    tree = ast.parse(
        HELPER_PATH.read_text(
            encoding="utf-8"
        )
    )

    imports = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imports.update(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module is not None:
                imports.add(
                    node.module
                )

    prohibited_import_fragments = (
        "pathlib",
        "csv",
        "json",
        "os",
        "subprocess",
        "structural_feature",
        "coverage",
        "selector",
        "distance",
    )

    for imported in imports:
        assert not any(
            fragment in imported
            for fragment in prohibited_import_fragments
        ), imported


def test_helper_contains_no_production_path_or_selector_identity():
    text = HELPER_PATH.read_text(
        encoding="utf-8"
    )

    assert "/NGS/" not in text
    assert "external-decision-holdout.tsv" not in text
    assert "reconstructed-retained-absent-from-baseline.tsv" not in text

    prohibited = (
        "OPS",
        "SR distance",
        "panel membership",
    )

    for token in prohibited:
        assert token not in text
