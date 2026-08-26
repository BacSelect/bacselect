import pytest

from bacselect import source_truth
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    BIOSAMPLE_NONREPRESENTATIVE,
    BIOSAMPLE_NOT_APPLICABLE,
    BIOSAMPLE_UNRESOLVED,
    TAXONOMY_PASS,
    TAXONOMY_UNRESOLVED,
    BioSampleMember,
    CompositionError,
    TaxonomyDecision,
    reconcile_repeated_biosamples,
    resolve_taxonomy,
)


FP_A = "a" * 64
FP_B = "b" * 64


class FakeTaxonomy:
    def __init__(
        self,
        *,
        normalize_result,
        species_result,
    ):
        self.normalize_result = normalize_result
        self.species_result = species_result
        self.normalize_calls = []
        self.species_calls = []

    def normalize(
        self,
        taxid,
    ):
        self.normalize_calls.append(
            taxid
        )
        return self.normalize_result

    def species_ancestor(
        self,
        taxid,
    ):
        self.species_calls.append(
            taxid
        )
        return self.species_result


def member(
    accession,
    biosample,
    *,
    truth=source_truth.SUITABLE,
    fingerprint=FP_A,
):
    return BioSampleMember(
        accession=accession,
        biosample=biosample,
        source_truth_status=truth,
        assembly_fingerprint=fingerprint,
    )


def test_source_truth_excluded_member_does_not_require_fingerprint():
    decisions = reconcile_repeated_biosamples(
        [
            member(
                "GCA_000000001.1",
                "SAMN1",
                truth=source_truth.EXCLUDE,
                fingerprint=None,
            ),
        ]
    )

    assert decisions[
        "GCA_000000001.1"
    ].status == BIOSAMPLE_NOT_APPLICABLE

    assert decisions[
        "GCA_000000001.1"
    ].reason == "SOURCE_TRUTH_EXCLUDED"


def test_source_truth_unresolved_member_does_not_require_fingerprint():
    decisions = reconcile_repeated_biosamples(
        [
            member(
                "GCA_000000001.1",
                "SAMN1",
                truth=source_truth.UNRESOLVED,
                fingerprint=None,
            ),
        ]
    )

    assert decisions[
        "GCA_000000001.1"
    ].status == BIOSAMPLE_NOT_APPLICABLE

    assert decisions[
        "GCA_000000001.1"
    ].reason == "SOURCE_TRUTH_UNRESOLVED"


def test_source_truth_terminal_member_does_not_influence_representative():
    decisions = reconcile_repeated_biosamples(
        [
            member(
                "GCA_000000001.1",
                "SAMN1",
                truth=source_truth.EXCLUDE,
                fingerprint=None,
            ),
            member(
                "GCA_000000002.1",
                "SAMN1",
                fingerprint=FP_A,
            ),
            member(
                "GCA_000000003.1",
                "SAMN1",
                fingerprint=FP_A,
            ),
        ]
    )

    assert decisions[
        "GCA_000000001.1"
    ].status == BIOSAMPLE_NOT_APPLICABLE

    assert decisions[
        "GCA_000000002.1"
    ].status == BIOSAMPLE_CONTINUE

    assert decisions[
        "GCA_000000002.1"
    ].reason == "BIOSAMPLE_IDENTICAL_REPRESENTATIVE"

    assert decisions[
        "GCA_000000003.1"
    ].status == BIOSAMPLE_NONREPRESENTATIVE


def test_single_continuing_member_is_singleton():
    decisions = reconcile_repeated_biosamples(
        [
            member(
                "GCA_000000001.1",
                "SAMN1",
            ),
        ]
    )

    assert decisions[
        "GCA_000000001.1"
    ].status == BIOSAMPLE_CONTINUE

    assert decisions[
        "GCA_000000001.1"
    ].reason == "BIOSAMPLE_SINGLETON"


def test_identical_group_uses_lexicographically_smallest_accession():
    decisions = reconcile_repeated_biosamples(
        [
            member(
                "GCA_000000003.1",
                "SAMN1",
            ),
            member(
                "GCA_000000001.2",
                "SAMN1",
            ),
            member(
                "GCA_000000001.1",
                "SAMN1",
            ),
        ]
    )

    assert decisions[
        "GCA_000000001.1"
    ].status == BIOSAMPLE_CONTINUE

    assert decisions[
        "GCA_000000001.2"
    ].status == BIOSAMPLE_NONREPRESENTATIVE

    assert decisions[
        "GCA_000000003.1"
    ].status == BIOSAMPLE_NONREPRESENTATIVE


def test_differing_fingerprints_withhold_every_continuing_member():
    decisions = reconcile_repeated_biosamples(
        [
            member(
                "GCA_000000001.1",
                "SAMN1",
                fingerprint=FP_A,
            ),
            member(
                "GCA_000000002.1",
                "SAMN1",
                fingerprint=FP_B,
            ),
        ]
    )

    assert decisions[
        "GCA_000000001.1"
    ].status == BIOSAMPLE_UNRESOLVED

    assert decisions[
        "GCA_000000002.1"
    ].status == BIOSAMPLE_UNRESOLVED


def test_groups_are_reconciled_independently():
    decisions = reconcile_repeated_biosamples(
        [
            member(
                "GCA_000000001.1",
                "SAMN1",
                fingerprint=FP_A,
            ),
            member(
                "GCA_000000002.1",
                "SAMN1",
                fingerprint=FP_A,
            ),
            member(
                "GCA_000000003.1",
                "SAMN2",
                fingerprint=FP_A,
            ),
            member(
                "GCA_000000004.1",
                "SAMN2",
                fingerprint=FP_B,
            ),
        ]
    )

    assert decisions[
        "GCA_000000001.1"
    ].status == BIOSAMPLE_CONTINUE

    assert decisions[
        "GCA_000000002.1"
    ].status == BIOSAMPLE_NONREPRESENTATIVE

    assert decisions[
        "GCA_000000003.1"
    ].status == BIOSAMPLE_UNRESOLVED

    assert decisions[
        "GCA_000000004.1"
    ].status == BIOSAMPLE_UNRESOLVED


def test_duplicate_accession_fails_closed():
    with pytest.raises(
        CompositionError,
        match="duplicate candidate accession",
    ):
        reconcile_repeated_biosamples(
            [
                member(
                    "GCA_000000001.1",
                    "SAMN1",
                ),
                member(
                    "GCA_000000001.1",
                    "SAMN2",
                ),
            ]
        )


def test_invalid_continuing_fingerprint_fails_closed():
    with pytest.raises(
        CompositionError,
        match="assembly fingerprint",
    ):
        reconcile_repeated_biosamples(
            [
                member(
                    "GCA_000000001.1",
                    "SAMN1",
                    fingerprint="not-a-sha",
                ),
            ]
        )


def test_unknown_source_truth_status_fails_closed():
    with pytest.raises(
        CompositionError,
        match="unknown source-truth status",
    ):
        reconcile_repeated_biosamples(
            [
                member(
                    "GCA_000000001.1",
                    "SAMN1",
                    truth="UNKNOWN",
                ),
            ]
        )


def test_taxonomy_resolves_species():
    taxonomy = FakeTaxonomy(
        normalize_result=(
            200,
            "PASS",
            1,
        ),
        species_result=(
            150,
            "PASS",
        ),
    )

    result = resolve_taxonomy(
        taxonomy,
        100,
    )

    assert result == TaxonomyDecision(
        status=TAXONOMY_PASS,
        reason="TAXONOMY_SPECIES_RESOLVED",
        normalized_taxid=200,
        species_taxid=150,
    )

    assert taxonomy.normalize_calls == [
        100
    ]

    assert taxonomy.species_calls == [
        200
    ]


@pytest.mark.parametrize(
    "normalize_status",
    [
        "MERGED_CYCLE",
        "DELETED",
        "MISSING",
    ],
)
def test_taxonomy_normalization_failure_is_unresolved(
    normalize_status,
):
    taxonomy = FakeTaxonomy(
        normalize_result=(
            None,
            normalize_status,
            0,
        ),
        species_result=(
            999,
            "PASS",
        ),
    )

    result = resolve_taxonomy(
        taxonomy,
        100,
    )

    assert result.status == TAXONOMY_UNRESOLVED
    assert result.reason == (
        f"TAXONOMY_NORMALIZE_{normalize_status}"
    )
    assert result.normalized_taxid is None
    assert result.species_taxid is None

    assert taxonomy.species_calls == []


@pytest.mark.parametrize(
    "species_status",
    [
        "LINEAGE_CYCLE",
        "MISSING_NODE",
        "NO_SPECIES_ANCESTOR",
    ],
)
def test_species_resolution_failure_is_unresolved(
    species_status,
):
    taxonomy = FakeTaxonomy(
        normalize_result=(
            200,
            "PASS",
            0,
        ),
        species_result=(
            None,
            species_status,
        ),
    )

    result = resolve_taxonomy(
        taxonomy,
        100,
    )

    assert result.status == TAXONOMY_UNRESOLVED
    assert result.reason == (
        f"TAXONOMY_SPECIES_{species_status}"
    )
    assert result.normalized_taxid == 200
    assert result.species_taxid is None


def test_unknown_normalization_status_fails_closed():
    taxonomy = FakeTaxonomy(
        normalize_result=(
            None,
            "UNKNOWN",
            0,
        ),
        species_result=(
            None,
            "NO_SPECIES_ANCESTOR",
        ),
    )

    with pytest.raises(
        CompositionError,
        match="unknown taxonomy normalization status",
    ):
        resolve_taxonomy(
            taxonomy,
            100,
        )


def test_unknown_species_status_fails_closed():
    taxonomy = FakeTaxonomy(
        normalize_result=(
            200,
            "PASS",
            0,
        ),
        species_result=(
            None,
            "UNKNOWN",
        ),
    )

    with pytest.raises(
        CompositionError,
        match="unknown species-ancestor status",
    ):
        resolve_taxonomy(
            taxonomy,
            100,
        )


def test_unresolved_normalization_cannot_return_taxid():
    taxonomy = FakeTaxonomy(
        normalize_result=(
            200,
            "DELETED",
            0,
        ),
        species_result=(
            None,
            "NO_SPECIES_ANCESTOR",
        ),
    )

    with pytest.raises(
        CompositionError,
        match="unresolved taxonomy normalization returned a TaxID",
    ):
        resolve_taxonomy(
            taxonomy,
            100,
        )


def test_unresolved_species_cannot_return_taxid():
    taxonomy = FakeTaxonomy(
        normalize_result=(
            200,
            "PASS",
            0,
        ),
        species_result=(
            150,
            "NO_SPECIES_ANCESTOR",
        ),
    )

    with pytest.raises(
        CompositionError,
        match="unresolved species ancestry returned a TaxID",
    ):
        resolve_taxonomy(
            taxonomy,
            100,
        )


from bacselect import source_chromosome_integrity
from bacselect.source_post_sequence_eligibility import (
    CHROMOSOME_INTEGRITY_LAYER,
    ELIGIBLE,
    ELIGIBLE_LAYER,
    EXCLUDED,
    NONREPRESENTATIVE,
    REPEATED_BIOSAMPLE_LAYER,
    SOURCE_TRUTH_LAYER,
    TAXONOMY_LAYER,
    WITHHELD_UNRESOLVED,
    BioSampleDecision,
    compose_candidate,
)


def biosample_continue():
    return BioSampleDecision(
        status=BIOSAMPLE_CONTINUE,
        reason="BIOSAMPLE_SINGLETON",
    )


def chromosome_decision(
    status,
    reason,
):
    return source_chromosome_integrity.ChromosomeIntegrityDecision(
        status=status,
        reason=reason,
        triggered=False,
        historical_adjudication_reused=False,
    )


def taxonomy_pass(
    species_taxid=123,
):
    return TaxonomyDecision(
        status=TAXONOMY_PASS,
        reason="TAXONOMY_SPECIES_RESOLVED",
        normalized_taxid=456,
        species_taxid=species_taxid,
    )


def taxonomy_unresolved(
    reason="TAXONOMY_SPECIES_NO_SPECIES_ANCESTOR",
):
    return TaxonomyDecision(
        status=TAXONOMY_UNRESOLVED,
        reason=reason,
        normalized_taxid=456,
        species_taxid=None,
    )


def test_source_truth_exclusion_is_terminal_and_short_circuits():
    result = compose_candidate(
        source_truth_status=source_truth.EXCLUDE,
        source_truth_reason="EXACT_DUPLICATE_PRIMARY_COMPONENTS",
        biosample=object(),
        chromosome=object(),
        taxonomy=object(),
    )

    assert result.disposition == EXCLUDED
    assert result.terminal_layer == SOURCE_TRUTH_LAYER
    assert result.terminal_status == source_truth.EXCLUDE
    assert result.reason == "EXACT_DUPLICATE_PRIMARY_COMPONENTS"
    assert result.species_taxid is None


def test_source_truth_unresolved_is_terminal_and_short_circuits():
    result = compose_candidate(
        source_truth_status=source_truth.UNRESOLVED,
        source_truth_reason="UNRESOLVED_SOURCE_TRUTH",
        biosample=object(),
        chromosome=object(),
        taxonomy=object(),
    )

    assert result.disposition == WITHHELD_UNRESOLVED
    assert result.terminal_layer == SOURCE_TRUTH_LAYER
    assert result.terminal_status == source_truth.UNRESOLVED
    assert result.reason == "UNRESOLVED_SOURCE_TRUTH"
    assert result.species_taxid is None


def test_suitable_source_truth_requires_biosample_decision():
    with pytest.raises(
        CompositionError,
        match="requires a BioSample decision",
    ):
        compose_candidate(
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="NO_SOURCE_REDUNDANCY",
        )


def test_biosample_nonrepresentative_is_terminal_and_short_circuits():
    result = compose_candidate(
        source_truth_status=source_truth.SUITABLE,
        source_truth_reason="NO_SOURCE_REDUNDANCY",
        biosample=BioSampleDecision(
            status=BIOSAMPLE_NONREPRESENTATIVE,
            reason="BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE",
        ),
        chromosome=object(),
        taxonomy=object(),
    )

    assert result.disposition == NONREPRESENTATIVE
    assert result.terminal_layer == REPEATED_BIOSAMPLE_LAYER
    assert result.terminal_status == BIOSAMPLE_NONREPRESENTATIVE
    assert result.reason == "BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE"
    assert result.species_taxid is None


def test_biosample_unresolved_is_terminal_and_short_circuits():
    result = compose_candidate(
        source_truth_status=source_truth.SUITABLE,
        source_truth_reason="NO_SOURCE_REDUNDANCY",
        biosample=BioSampleDecision(
            status=BIOSAMPLE_UNRESOLVED,
            reason="BIOSAMPLE_FINGERPRINTS_DIFFER",
        ),
        chromosome=object(),
        taxonomy=object(),
    )

    assert result.disposition == WITHHELD_UNRESOLVED
    assert result.terminal_layer == REPEATED_BIOSAMPLE_LAYER
    assert result.terminal_status == BIOSAMPLE_UNRESOLVED
    assert result.reason == "BIOSAMPLE_FINGERPRINTS_DIFFER"
    assert result.species_taxid is None


def test_suitable_candidate_cannot_have_biosample_not_applicable():
    with pytest.raises(
        CompositionError,
        match="cannot have NOT_APPLICABLE",
    ):
        compose_candidate(
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="NO_SOURCE_REDUNDANCY",
            biosample=BioSampleDecision(
                status=BIOSAMPLE_NOT_APPLICABLE,
                reason="SOURCE_TRUTH_EXCLUDED",
            ),
        )


def test_biosample_continue_requires_chromosome_decision():
    with pytest.raises(
        CompositionError,
        match="requires a chromosome-integrity decision",
    ):
        compose_candidate(
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="NO_SOURCE_REDUNDANCY",
            biosample=biosample_continue(),
        )


def test_chromosome_exclusion_is_terminal_and_short_circuits_taxonomy():
    result = compose_candidate(
        source_truth_status=source_truth.SUITABLE,
        source_truth_reason="NO_SOURCE_REDUNDANCY",
        biosample=biosample_continue(),
        chromosome=chromosome_decision(
            source_chromosome_integrity.EXCLUDE,
            "HISTORICAL_FRAGMENTED_CHROMOSOME_SET",
        ),
        taxonomy=object(),
    )

    assert result.disposition == EXCLUDED
    assert result.terminal_layer == CHROMOSOME_INTEGRITY_LAYER
    assert result.terminal_status == source_chromosome_integrity.EXCLUDE
    assert result.reason == "HISTORICAL_FRAGMENTED_CHROMOSOME_SET"
    assert result.species_taxid is None


def test_chromosome_unresolved_is_terminal_and_short_circuits_taxonomy():
    result = compose_candidate(
        source_truth_status=source_truth.SUITABLE,
        source_truth_reason="NO_SOURCE_REDUNDANCY",
        biosample=biosample_continue(),
        chromosome=chromosome_decision(
            source_chromosome_integrity.UNRESOLVED,
            "HISTORICAL_UNRESOLVED",
        ),
        taxonomy=object(),
    )

    assert result.disposition == WITHHELD_UNRESOLVED
    assert result.terminal_layer == CHROMOSOME_INTEGRITY_LAYER
    assert result.terminal_status == source_chromosome_integrity.UNRESOLVED
    assert result.reason == "HISTORICAL_UNRESOLVED"
    assert result.species_taxid is None


def test_chromosome_pass_requires_taxonomy_decision():
    with pytest.raises(
        CompositionError,
        match="requires a taxonomy decision",
    ):
        compose_candidate(
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="NO_SOURCE_REDUNDANCY",
            biosample=biosample_continue(),
            chromosome=chromosome_decision(
                source_chromosome_integrity.PASS,
                "NO_CHROMOSOME_INTEGRITY_TRIGGER",
            ),
        )


def test_taxonomy_unresolved_is_terminal():
    result = compose_candidate(
        source_truth_status=source_truth.SUITABLE,
        source_truth_reason="NO_SOURCE_REDUNDANCY",
        biosample=biosample_continue(),
        chromosome=chromosome_decision(
            source_chromosome_integrity.PASS,
            "NO_CHROMOSOME_INTEGRITY_TRIGGER",
        ),
        taxonomy=taxonomy_unresolved(),
    )

    assert result.disposition == WITHHELD_UNRESOLVED
    assert result.terminal_layer == TAXONOMY_LAYER
    assert result.terminal_status == TAXONOMY_UNRESOLVED
    assert result.reason == "TAXONOMY_SPECIES_NO_SPECIES_ANCESTOR"
    assert result.species_taxid is None


def test_candidate_passing_every_stage_is_eligible():
    result = compose_candidate(
        source_truth_status=source_truth.SUITABLE,
        source_truth_reason="NO_SOURCE_REDUNDANCY",
        biosample=biosample_continue(),
        chromosome=chromosome_decision(
            source_chromosome_integrity.PASS,
            "NO_CHROMOSOME_INTEGRITY_TRIGGER",
        ),
        taxonomy=taxonomy_pass(
            species_taxid=123,
        ),
    )

    assert result.disposition == ELIGIBLE
    assert result.terminal_layer == ELIGIBLE_LAYER
    assert result.terminal_status == "PASS"
    assert result.reason == "POST_SEQUENCE_ELIGIBLE"
    assert result.species_taxid == 123


def test_unknown_source_truth_status_fails_closed_in_composition():
    with pytest.raises(
        CompositionError,
        match="unknown source-truth status",
    ):
        compose_candidate(
            source_truth_status="UNKNOWN",
            source_truth_reason="UNKNOWN",
        )


def test_unknown_biosample_status_fails_closed():
    with pytest.raises(
        CompositionError,
        match="unknown BioSample status",
    ):
        compose_candidate(
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="NO_SOURCE_REDUNDANCY",
            biosample=BioSampleDecision(
                status="UNKNOWN",
                reason="UNKNOWN",
            ),
        )


def test_unknown_chromosome_status_fails_closed():
    with pytest.raises(
        CompositionError,
        match="unknown chromosome-integrity status",
    ):
        compose_candidate(
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="NO_SOURCE_REDUNDANCY",
            biosample=biosample_continue(),
            chromosome=chromosome_decision(
                "UNKNOWN",
                "UNKNOWN",
            ),
        )


def test_unknown_taxonomy_status_fails_closed():
    with pytest.raises(
        CompositionError,
        match="unknown taxonomy status",
    ):
        compose_candidate(
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="NO_SOURCE_REDUNDANCY",
            biosample=biosample_continue(),
            chromosome=chromosome_decision(
                source_chromosome_integrity.PASS,
                "NO_CHROMOSOME_INTEGRITY_TRIGGER",
            ),
            taxonomy=TaxonomyDecision(
                status="UNKNOWN",
                reason="UNKNOWN",
                normalized_taxid=456,
                species_taxid=None,
            ),
        )


def test_unresolved_taxonomy_cannot_contain_species_taxid():
    with pytest.raises(
        CompositionError,
        match="unresolved taxonomy decision contains a species TaxID",
    ):
        compose_candidate(
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="NO_SOURCE_REDUNDANCY",
            biosample=biosample_continue(),
            chromosome=chromosome_decision(
                source_chromosome_integrity.PASS,
                "NO_CHROMOSOME_INTEGRITY_TRIGGER",
            ),
            taxonomy=TaxonomyDecision(
                status=TAXONOMY_UNRESOLVED,
                reason="TAXONOMY_SPECIES_MISSING_NODE",
                normalized_taxid=456,
                species_taxid=123,
            ),
        )


@pytest.mark.parametrize(
    "species_taxid",
    [
        None,
        0,
        -1,
        True,
        "123",
    ],
)
def test_taxonomy_pass_requires_positive_integer_species_taxid(
    species_taxid,
):
    with pytest.raises(
        CompositionError,
        match="species TaxID must be a positive integer",
    ):
        compose_candidate(
            source_truth_status=source_truth.SUITABLE,
            source_truth_reason="NO_SOURCE_REDUNDANCY",
            biosample=biosample_continue(),
            chromosome=chromosome_decision(
                source_chromosome_integrity.PASS,
                "NO_CHROMOSOME_INTEGRITY_TRIGGER",
            ),
            taxonomy=taxonomy_pass(
                species_taxid=species_taxid,
            ),
        )
