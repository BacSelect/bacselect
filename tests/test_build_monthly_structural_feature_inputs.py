from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from bacselect import monthly_cache_verification as cache
from bacselect import monthly_structural_features as monthly
from bacselect import source_structural_feature_execution as execution


PATH = (
    Path(__file__)
    .resolve()
    .parents[1]
    / "validation"
    / "selector-v1"
    / "build_monthly_structural_feature_inputs.py"
)

SPEC = (
    importlib.util
    .spec_from_file_location(
        "_stage10_input_adapter_test",
        PATH,
    )
)

assert SPEC is not None
assert SPEC.loader is not None

module = (
    importlib.util
    .module_from_spec(
        SPEC
    )
)

sys.modules[
    SPEC.name
] = module

SPEC.loader.exec_module(
    module
)


ACCESSION = "GCA_000000001.1"
COMPONENT = "CP000001.1"


def digest(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


@dataclass(
    frozen=True,
)
class Component:
    component_accession: str
    length: int
    topology: str
    sequence_sha256: str


def component(
    *,
    topology="circular",
):
    sequence = b"ACGT"

    return Component(
        component_accession=(
            COMPONENT
        ),
        length=len(
            sequence
        ),
        topology=topology,
        sequence_sha256=(
            digest(
                sequence
            )
        ),
    )


def feature_values(
    offset=0,
):
    return {
        "01_total_genome_length":
            100
            + offset,
        "02_whole_genome_gc_fraction":
            0.5,
        "03_replicon_count":
            1,
        "04_non_chromosomal_replicon_count":
            0,
        "05_non_chromosomal_sequence_fraction":
            0.0,
        "06_non_unique_canonical_300mer_fraction":
            0.0,
        "07_non_unique_canonical_2400mer_fraction":
            0.0,
        "08_maximum_canonical_300mer_multiplicity":
            1,
        "09_maximum_canonical_2400mer_multiplicity":
            1,
        "10_longest_exact_repeat_length":
            0,
        "11_inter_replicon_shared_canonical_300mer_fraction":
            0.0,
        "12_inter_replicon_shared_canonical_2400mer_fraction":
            0.0,
    }


def cached(
    accession,
    identity,
    *,
    offset=0,
):
    return monthly.CachedFeatureRow(
        accession=accession,
        component_identity_sha256=(
            identity
        ),
        features=(
            feature_values(
                offset
            )
        ),
    )


def test_component_identity_matches_frozen_public_primitive():
    sequence = "ACGT"

    sequence_sha = hashlib.sha256(
        sequence.encode(
            "ascii"
        )
    ).hexdigest()

    fasta = (
        b">CP000001.1\nACGT\n"
    )

    fasta_sha = digest(
        fasta
    )

    package = (
        cache
        .MonthlyCachePackageFileObservation(
            path=(
                "ncbi_dataset/data/"
                f"{ACCESSION}/"
                "genomic.fna"
            ),
            expected_size_bytes=(
                len(
                    fasta
                )
            ),
            expected_sha256=(
                fasta_sha
            ),
            observed_size_bytes=(
                len(
                    fasta
                )
            ),
            observed_sha256=(
                fasta_sha
            ),
        )
    )

    frozen_component = (
        cache.MonthlyCacheComponent(
            component_accession=(
                COMPONENT
            ),
            length=len(
                sequence
            ),
            topology="circular",
            sequence_sha256=(
                sequence_sha
            ),
            sequence=sequence,
        )
    )

    candidate = (
        cache.MonthlyCacheCandidate(
            canonical_genbank_assembly_accession=(
                ACCESSION
            ),
            biosample=(
                "SAMN00000001"
            ),
            cache_origin_release_id=(
                "2026.09"
            ),
            cache_origin_source_snapshot_id=(
                "snapshot"
            ),
            cache_origin_git_commit=(
                "a"
                * 40
            ),
            origin_batch_summary_sha256=(
                "1"
                * 64
            ),
            origin_candidate_audit_sha256=(
                "2"
                * 64
            ),
            origin_component_audit_sha256=(
                "3"
                * 64
            ),
            origin_package_files_sha256=(
                "4"
                * 64
            ),
            batch_provenance_verified=True,
            candidate_fasta_file=(
                "genomic.fna"
            ),
            candidate_fasta_sha256=(
                fasta_sha
            ),
            primary_assembly_records=1,
            components=(
                frozen_component,
            ),
            package_files=(
                package,
            ),
        )
    )

    adapter_component = Component(
        component_accession=(
            COMPONENT
        ),
        length=len(
            sequence
        ),
        topology="circular",
        sequence_sha256=(
            sequence_sha
        ),
    )

    assert (
        module
        .component_identity_sha256(
            ACCESSION,
            (
                adapter_component,
            ),
        )
        == cache
        .component_identity_sha256(
            candidate
        )
    )


def test_component_identity_is_order_independent():
    a = Component(
        component_accession=(
            "CP000001.1"
        ),
        length=4,
        topology="circular",
        sequence_sha256=(
            "1"
            * 64
        ),
    )

    b = Component(
        component_accession=(
            "CP000002.1"
        ),
        length=5,
        topology="linear",
        sequence_sha256=(
            "2"
            * 64
        ),
    )

    assert (
        module
        .component_identity_sha256(
            ACCESSION,
            (
                a,
                b,
            ),
        )
        == module
        .component_identity_sha256(
            ACCESSION,
            (
                b,
                a,
            ),
        )
    )


def test_required_compute_uses_tier1_then_tier2():
    a = "GCA_000000001.1"
    b = "GCA_000000002.1"
    c = "GCA_000000003.1"

    ia = "1" * 64
    ib = "2" * 64
    ic = "3" * 64

    observed = (
        module
        .required_compute_accessions(
            accessions=(
                a,
                b,
                c,
            ),
            current_component_identity_by_accession={
                a:
                    ia,
                b:
                    ib,
                c:
                    ic,
            },
            tier1_cache={
                a:
                    cached(
                        a,
                        ia,
                    ),
                b:
                    cached(
                        b,
                        "9" * 64,
                    ),
            },
            tier2_cache={
                b:
                    cached(
                        b,
                        ib,
                    ),
            },
        )
    )

    assert observed == (
        c,
    )


def test_topology_change_forces_compute():
    current = (
        module
        .component_identity_sha256(
            ACCESSION,
            (
                component(
                    topology="linear"
                ),
            ),
        )
    )

    cached_identity = (
        module
        .component_identity_sha256(
            ACCESSION,
            (
                component(
                    topology="circular"
                ),
            ),
        )
    )

    assert (
        module
        .required_compute_accessions(
            accessions=(
                ACCESSION,
            ),
            current_component_identity_by_accession={
                ACCESSION:
                    current,
            },
            tier1_cache={
                ACCESSION:
                    cached(
                        ACCESSION,
                        cached_identity,
                    ),
            },
            tier2_cache={},
        )
        == (
            ACCESSION,
        )
    )


def test_reauthenticate_observations_detects_mutation(
    tmp_path,
):
    path = (
        tmp_path
        / "evidence.tsv"
    )

    path.write_bytes(
        b"before\n"
    )

    observation = (
        module.FileObservation(
            path=path,
            sha256=(
                module.sha256_file(
                    path
                )
            ),
            size_bytes=(
                path.stat().st_size
            ),
        )
    )

    path.write_bytes(
        b"after\n"
    )

    with pytest.raises(
        module
        .MonthlyStructuralFeatureInputError,
        match="identity changed",
    ):
        module.reauthenticate_observations(
            (
                observation,
            )
        )


def fake_plan(
    accessions,
):
    entries = {}

    providers = {}

    species = {}

    for index, accession in enumerate(
        accessions,
        start=1,
    ):
        provenance_sha = (
            f"{index:064x}"
        )

        entries[
            accession
        ] = {
            "origin_batch_provenance_sha256":
                provenance_sha,
        }

        provider = (
            SimpleNamespace(
                batch_id=(
                    f"batch-{index:05d}"
                ),
                candidate_audit_path=(
                    Path(
                        f"/synthetic/"
                        f"batch-{index:05d}/"
                        "candidate-sequence-audit.tsv"
                    )
                ),
                batch=object(),
            )
        )

        providers[
            provenance_sha
        ] = module.ProviderState(
            provenance_sha256=(
                provenance_sha
            ),
            provenance={},
            completion_batch={},
            provider=provider,
            source_group="fresh",
            component_audit=Path(
                "/synthetic/component.tsv"
            ),
            package_manifest=Path(
                "/synthetic/package.tsv"
            ),
            observations=(),
        )

        species[
            accession
        ] = str(
            100
            + index
        )

    context = SimpleNamespace(
        stage4_context=(
            SimpleNamespace(
                entries_by_accession=(
                    entries
                ),
                cache_execution=object(),
            )
        )
    )

    stage9 = SimpleNamespace(
        species_by_accession=(
            species
        )
    )

    return module.Stage10InputPlan(
        stage9=stage9,
        context=context,
        stage6_v2=SimpleNamespace(),
        stage5_v2=SimpleNamespace(),
        stage4_v2=SimpleNamespace(),
        stage4_v1=SimpleNamespace(),
        current_component_identity_by_accession={},
        tier1_cache={},
        tier2_cache={},
        compute_accessions=tuple(
            accessions
        ),
        providers_by_provenance=(
            providers
        ),
        tier1_raw_rows={},
        tier2_raw_rows={},
    )


def test_compute_feature_records_touches_only_requested_accessions(
    monkeypatch,
):
    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )

    plan = fake_plan(
        accessions
    )

    bound = []
    computed = []

    def fake_binding(
        *,
        plan,
        accession,
    ):
        bound.append(
            accession
        )

        return SimpleNamespace(
            accession=accession,
        )

    def fake_compute(
        *,
        binding,
        species_taxid,
        finch,
        basic,
        engine,
    ):
        computed.append(
            binding.accession
        )

        return (
            execution
            .Stage6FeatureRecord(
                accession=(
                    binding.accession
                ),
                species_taxid=(
                    species_taxid
                ),
                features=(
                    feature_values()
                ),
                retained_replicon_count=1,
                total_sequence_length=100,
            )
        )

    monkeypatch.setattr(
        module,
        "build_compute_binding",
        fake_binding,
    )

    result = (
        module
        .compute_feature_records(
            plan=plan,
            finch=object(),
            basic=object(),
            engine=Path(
                "/synthetic/engine"
            ),
            compute_one=(
                fake_compute
            ),
        )
    )

    assert bound == list(
        accessions
    )

    assert computed == list(
        accessions
    )

    assert tuple(
        result
    ) == accessions


def test_compute_binding_rejects_reusable_accession():
    plan = fake_plan(
        (
            "GCA_000000001.1",
        )
    )

    plan = (
        module.Stage10InputPlan(
            stage9=plan.stage9,
            context=plan.context,
            stage6_v2=plan.stage6_v2,
            stage5_v2=plan.stage5_v2,
            stage4_v2=plan.stage4_v2,
            stage4_v1=plan.stage4_v1,
            current_component_identity_by_accession={},
            tier1_cache={},
            tier2_cache={},
            compute_accessions=(),
            providers_by_provenance=(
                plan
                .providers_by_provenance
            ),
            tier1_raw_rows={},
            tier2_raw_rows={},
        )
    )

    with pytest.raises(
        module
        .MonthlyStructuralFeatureInputError,
        match="reusable accession",
    ):
        module.build_compute_binding(
            plan=plan,
            accession=(
                "GCA_000000001.1"
            ),
        )


def test_adapter_contains_no_environment_specific_or_network_runtime():
    text = PATH.read_text(
        encoding="utf-8"
    )

    for token in (
        "/NGS/",
        "Rhys_wkdir",
        "requests.",
        "urllib.",
        "socket.",
        "sbatch",
        "srun",
        "SLURM_",
    ):
        assert token not in text


def test_adapter_does_not_publish_stage10():
    text = PATH.read_text(
        encoding="utf-8"
    )

    assert (
        ".execute_monthly_structural_features("
        not in text
    )

    assert (
        "publish_stage("
        not in text
    )

    assert (
        "publish_completion("
        not in text
    )
