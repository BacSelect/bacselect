import pytest

from bacselect.source_chromosome_integrity import (
    ChromosomeIntegrityError,
    HistoricalReuseEvidence,
    PrimaryComponentEvidence,
    assess_trigger,
    closure_supported,
    evaluate,
)


def chromosome(
    *,
    topology="linear",
    definition="chromosome sequence",
):
    return PrimaryComponentEvidence(
        molecule_class="Chromosome",
        topology=topology,
        definition=definition,
    )


def plasmid(
    *,
    topology="linear",
    definition="plasmid sequence",
):
    return PrimaryComponentEvidence(
        molecule_class="Plasmid",
        topology=topology,
        definition=definition,
    )


def historical(
    *,
    uses_package=True,
    cache_state="pass",
    accession="GCA_000000001.1",
    outcome="RETAIN_CONFIRMED_MULTIPARTITE",
):
    return HistoricalReuseEvidence(
        uses_historical_project_finch_package=uses_package,
        cache_content_verification=cache_state,
        adjudication_accession=accession,
        adjudication_outcome=outcome,
    )


@pytest.mark.parametrize(
    (
        "topology",
        "definition",
    ),
    [
        (
            "circular",
            "chromosome sequence",
        ),
        (
            "CIRCULAR",
            "chromosome sequence",
        ),
        (
            "linear",
            "chromosome, complete sequence",
        ),
        (
            "linear",
            "complete chromosome",
        ),
        (
            "linear",
            "chromosome, COMPLETE genome",
        ),
        (
            "linear",
            "chromosome; complete.",
        ),
    ],
)
def test_closure_supported_positive(
    topology,
    definition,
):
    assert closure_supported(
        topology,
        definition,
    )


@pytest.mark.parametrize(
    "definition",
    [
        "chromosome sequence",
        "incomplete genome",
        "incompletely assembled chromosome",
        "completion of chromosome assembly",
        "completely assembled chromosome",
    ],
)
def test_complete_must_be_standalone_word(
    definition,
):
    assert not closure_supported(
        "linear",
        definition,
    )


def test_empty_topology_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="topology",
    ):
        closure_supported(
            "",
            "complete genome",
        )


def test_empty_definition_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="definition",
    ):
        closure_supported(
            "linear",
            "",
        )


def test_nonstring_topology_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="topology",
    ):
        closure_supported(
            None,
            "complete genome",
        )


def test_nonstring_definition_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="definition",
    ):
        closure_supported(
            "linear",
            None,
        )


def test_one_unsupported_chromosome_does_not_trigger():
    observed = assess_trigger(
        [
            chromosome(),
        ]
    )

    assert not observed.triggered
    assert observed.chromosome_component_count == 1
    assert observed.closure_supported_chromosome_count == 0
    assert observed.closure_unsupported_chromosome_count == 1


def test_two_supported_chromosomes_do_not_trigger():
    observed = assess_trigger(
        [
            chromosome(
                topology="circular",
            ),
            chromosome(
                definition="chromosome, complete sequence",
            ),
        ]
    )

    assert not observed.triggered
    assert observed.chromosome_component_count == 2
    assert observed.closure_supported_chromosome_count == 2
    assert observed.closure_unsupported_chromosome_count == 0


def test_two_chromosomes_one_unsupported_triggers():
    observed = assess_trigger(
        [
            chromosome(
                topology="circular",
            ),
            chromosome(),
        ]
    )

    assert observed.triggered
    assert observed.chromosome_component_count == 2
    assert observed.closure_supported_chromosome_count == 1
    assert observed.closure_unsupported_chromosome_count == 1


def test_multiple_unsupported_chromosomes_trigger():
    observed = assess_trigger(
        [
            chromosome(),
            chromosome(),
            chromosome(
                topology="circular",
            ),
        ]
    )

    assert observed.triggered
    assert observed.chromosome_component_count == 3
    assert observed.closure_supported_chromosome_count == 1
    assert observed.closure_unsupported_chromosome_count == 2


def test_nonchromosomal_component_does_not_trigger():
    observed = assess_trigger(
        [
            chromosome(
                topology="circular",
            ),
            plasmid(),
        ]
    )

    assert not observed.triggered
    assert observed.chromosome_component_count == 1


def test_nonchromosomal_closure_fields_are_not_consulted():
    observed = assess_trigger(
        [
            chromosome(
                topology="circular",
            ),
            PrimaryComponentEvidence(
                molecule_class="Plasmid",
                topology="",
                definition="",
            ),
        ]
    )

    assert not observed.triggered


def test_empty_component_collection_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="must not be empty",
    ):
        assess_trigger(
            []
        )


@pytest.mark.parametrize(
    "components",
    [
        "not-components",
        b"not-components",
    ],
)
def test_string_like_component_collection_fails_closed(
    components,
):
    with pytest.raises(
        ChromosomeIntegrityError,
        match="sequence of component evidence",
    ):
        assess_trigger(
            components
        )


def test_wrong_component_type_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="unexpected type",
    ):
        assess_trigger(
            [
                object(),
            ]
        )


def test_empty_molecule_class_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="molecule class",
    ):
        assess_trigger(
            [
                PrimaryComponentEvidence(
                    molecule_class="",
                    topology="linear",
                    definition="sequence",
                ),
            ]
        )


def test_nontriggered_candidate_passes_without_historical_reuse():
    result = evaluate(
        accession="GCA_000000001.1",
        components=[
            chromosome(
                topology="circular",
            ),
        ],
    )

    assert result.status == "PASS"
    assert result.reason == "NO_CHROMOSOME_INTEGRITY_TRIGGER"
    assert not result.triggered
    assert not result.historical_adjudication_reused


def test_nontriggered_candidate_does_not_consult_historical_evidence():
    result = evaluate(
        accession="GCA_000000001.1",
        components=[
            chromosome(
                topology="circular",
            ),
        ],
        historical=HistoricalReuseEvidence(
            uses_historical_project_finch_package=True,
            cache_content_verification="nonsense",
            adjudication_accession="not-an-accession",
            adjudication_outcome="not-an-outcome",
        ),
    )

    assert result.status == "PASS"
    assert not result.triggered
    assert not result.historical_adjudication_reused


def test_trigger_without_historical_evidence_is_unresolved():
    result = evaluate(
        accession="GCA_000000001.1",
        components=[
            chromosome(),
            chromosome(),
        ],
    )

    assert result.status == "REVIEW_UNRESOLVED"
    assert result.reason == "NO_REUSABLE_HISTORICAL_ADJUDICATION"
    assert result.triggered
    assert not result.historical_adjudication_reused


def test_fresh_package_cannot_reuse_historical_adjudication():
    result = evaluate(
        accession="GCA_000000001.1",
        components=[
            chromosome(),
            chromosome(),
        ],
        historical=historical(
            uses_package=False,
        ),
    )

    assert result.status == "REVIEW_UNRESOLVED"
    assert result.reason == "NOT_HISTORICAL_PROJECT_FINCH_PACKAGE"
    assert not result.historical_adjudication_reused


def test_fallback_to_fresh_cannot_reuse_historical_adjudication():
    result = evaluate(
        accession="GCA_000000001.1",
        components=[
            chromosome(),
            chromosome(),
        ],
        historical=historical(
            cache_state="fallback_to_fresh",
        ),
    )

    assert result.status == "REVIEW_UNRESOLVED"
    assert result.reason == "HISTORICAL_CACHE_NOT_VERIFIED"
    assert not result.historical_adjudication_reused


def test_unknown_cache_state_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="unknown cache content verification state",
    ):
        evaluate(
            accession="GCA_000000001.1",
            components=[
                chromosome(),
                chromosome(),
            ],
            historical=historical(
                cache_state="unknown",
            ),
        )


def test_absent_historical_adjudication_is_unresolved():
    result = evaluate(
        accession="GCA_000000001.1",
        components=[
            chromosome(),
            chromosome(),
        ],
        historical=HistoricalReuseEvidence(
            uses_historical_project_finch_package=True,
            cache_content_verification="pass",
            adjudication_accession=None,
            adjudication_outcome=None,
        ),
    )

    assert result.status == "REVIEW_UNRESOLVED"
    assert result.reason == "HISTORICAL_ADJUDICATION_ABSENT"
    assert not result.historical_adjudication_reused


def test_partially_missing_historical_adjudication_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="historical adjudication evidence is incomplete",
    ):
        evaluate(
            accession="GCA_000000001.1",
            components=[
                chromosome(),
                chromosome(),
            ],
            historical=HistoricalReuseEvidence(
                uses_historical_project_finch_package=True,
                cache_content_verification="pass",
                adjudication_accession="GCA_000000001.1",
                adjudication_outcome=None,
            ),
        )


def test_historical_accession_must_match_exact_version():
    result = evaluate(
        accession="GCA_000000001.2",
        components=[
            chromosome(),
            chromosome(),
        ],
        historical=historical(
            accession="GCA_000000001.1",
        ),
    )

    assert result.status == "REVIEW_UNRESOLVED"
    assert result.reason == "HISTORICAL_ACCESSION_MISMATCH"
    assert not result.historical_adjudication_reused


def test_malformed_current_accession_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="current accession",
    ):
        evaluate(
            accession="GCF_000000001.1",
            components=[
                chromosome(),
                chromosome(),
            ],
        )


def test_malformed_historical_accession_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="historical adjudication accession",
    ):
        evaluate(
            accession="GCA_000000001.1",
            components=[
                chromosome(),
                chromosome(),
            ],
            historical=historical(
                accession="GCF_000000001.1",
            ),
        )


def test_nonboolean_historical_package_flag_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="historical package flag must be boolean",
    ):
        evaluate(
            accession="GCA_000000001.1",
            components=[
                chromosome(),
                chromosome(),
            ],
            historical=HistoricalReuseEvidence(
                uses_historical_project_finch_package="yes",
                cache_content_verification="pass",
                adjudication_accession="GCA_000000001.1",
                adjudication_outcome="RETAIN_CONFIRMED_MULTIPARTITE",
            ),
        )


def test_historical_retain_passes():
    result = evaluate(
        accession="GCA_000000001.1",
        components=[
            chromosome(),
            chromosome(),
        ],
        historical=historical(
            outcome="RETAIN_CONFIRMED_MULTIPARTITE",
        ),
    )

    assert result.status == "PASS"
    assert result.reason == "HISTORICAL_RETAIN_CONFIRMED_MULTIPARTITE"
    assert result.triggered
    assert result.historical_adjudication_reused


def test_historical_fragmented_excludes():
    result = evaluate(
        accession="GCA_000000001.1",
        components=[
            chromosome(),
            chromosome(),
        ],
        historical=historical(
            outcome="EXCLUDE_FRAGMENTED_CHROMOSOME_SET",
        ),
    )

    assert result.status == "EXCLUDE_SOURCE_REPLICON_INTEGRITY"
    assert result.reason == "HISTORICAL_FRAGMENTED_CHROMOSOME_SET"
    assert result.triggered
    assert result.historical_adjudication_reused


def test_historical_unresolved_remains_unresolved():
    result = evaluate(
        accession="GCA_000000001.1",
        components=[
            chromosome(),
            chromosome(),
        ],
        historical=historical(
            outcome="UNRESOLVED",
        ),
    )

    assert result.status == "REVIEW_UNRESOLVED"
    assert result.reason == "HISTORICAL_UNRESOLVED"
    assert result.triggered
    assert result.historical_adjudication_reused


def test_unknown_historical_outcome_fails_closed():
    with pytest.raises(
        ChromosomeIntegrityError,
        match="unknown historical adjudication outcome",
    ):
        evaluate(
            accession="GCA_000000001.1",
            components=[
                chromosome(),
                chromosome(),
            ],
            historical=historical(
                outcome="MANUAL_RETAIN",
            ),
        )
