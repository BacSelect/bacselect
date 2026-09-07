from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest

from bacselect import monthly_structural_features as monthly
from bacselect import source_structural_feature_execution as structural


PATH = (
    Path(__file__)
    .resolve()
    .parents[1]
    / "validation"
    / "selector-v1"
    / "run_monthly_structural_features.py"
)

SPEC = (
    importlib.util
    .spec_from_file_location(
        "_monthly_stage10_wrapper_test",
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


def sha(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode(
            "ascii"
        )
    ).hexdigest()


def feature_values():
    return {
        "01_total_genome_length":
            10,
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


def fake_build():
    rows = []

    for accession, provenance in (
        (
            "GCA_000000001.1",
            monthly.CACHE_TIER1,
        ),
        (
            "GCA_000000002.1",
            monthly.CACHE_TIER2,
        ),
        (
            module.FORCED_COMPUTE_ACCESSION,
            monthly.COMPUTED,
        ),
    ):
        rows.append(
            monthly.MonthlyStructuralFeatureRow(
                accession=accession,
                species_taxid="1",
                component_identity_sha256=(
                    sha(
                        accession
                    )
                ),
                provenance_class=(
                    provenance
                ),
                features=(
                    feature_values()
                ),
            )
        )

    return (
        monthly.MonthlyStructuralFeatureBuild(
            rows=tuple(
                rows
            ),
            tier1_accessions=(
                "GCA_000000001.1",
            ),
            tier2_accessions=(
                "GCA_000000002.1",
            ),
            computed_accessions=(
                module
                .FORCED_COMPUTE_ACCESSION,
            ),
            membership_sha256=(
                "0"
                * 64
            ),
            tier1_membership_sha256=(
                "1"
                * 64
            ),
            tier2_membership_sha256=(
                "2"
                * 64
            ),
            computed_membership_sha256=(
                "3"
                * 64
            ),
            partition_mapping_sha256=(
                "4"
                * 64
            ),
            numeric_array_sha256=(
                "5"
                * 64
            ),
        )
    )


def test_frozen_identity_constants():
    assert (
        module.EXPECTED_CORE_SHA256
        == (
            "f520deabe78312bfe3316bdc49daf63870772002cc65941c68901bab85244428"
        )
    )

    assert (
        module.EXPECTED_TIER1_ROW_AUDIT_SHA256
        == (
            "2155a672c676f99e546909ab4bedf1245c953ccadf82276be75303bcf121fcc7"
        )
    )

    assert (
        module.EXPECTED_COMPUTE_COUNT
        == 333
    )


def test_stage_inventory_contains_raw_features_only():
    assert module.STAGE_FILES == {
        module.MATRIX_NAME,
        module.PROVENANCE_NAME,
        module.RECORD_NAME,
    }

    assert not any(
        "percentile" in name
        or "selector" in name
        or "panel" in name
        for name in module.STAGE_FILES
    )


def test_partition_gate_fails_if_counts_differ(
    monkeypatch,
):
    build = fake_build()

    monkeypatch.setattr(
        module,
        "EXPECTED_TOTAL_COUNT",
        3,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_TIER1_COUNT",
        1,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_TIER2_COUNT",
        1,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_REUSE_COUNT",
        2,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_COMPUTE_COUNT",
        2,
    )

    with pytest.raises(
        module
        .MonthlyStructuralFeatureExecutionError,
        match="partition counts changed",
    ):
        module.audit_frozen_partition(
            build
        )


def test_partition_gate_accepts_exact_synthetic_contract(
    monkeypatch,
):
    build = fake_build()

    monkeypatch.setattr(
        module,
        "EXPECTED_TOTAL_COUNT",
        3,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_TIER1_COUNT",
        1,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_TIER2_COUNT",
        1,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_REUSE_COUNT",
        2,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_COMPUTE_COUNT",
        1,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_MEMBERSHIP_SHA256",
        build.membership_sha256,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_TIER1_MEMBERSHIP_SHA256",
        build.tier1_membership_sha256,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_TIER2_MEMBERSHIP_SHA256",
        build.tier2_membership_sha256,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_COMPUTE_MEMBERSHIP_SHA256",
        build.computed_membership_sha256,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_PARTITION_MAPPING_SHA256",
        build.partition_mapping_sha256,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_REUSE_MEMBERSHIP_SHA256",
        monthly
        .accession_membership_sha256(
            (
                "GCA_000000001.1",
                "GCA_000000002.1",
            )
        ),
    )

    module.audit_frozen_partition(
        build
    )


def test_stage_publication_is_exact_and_no_clobber(
    tmp_path,
):
    matrix = b"matrix\n"
    provenance = b"provenance\n"
    record = b"record\n"

    calls = []

    final = module.publish_stage(
        stage1_root=tmp_path,
        matrix_payload=matrix,
        provenance_payload=provenance,
        record_payload=record,
        stability_check=lambda:
            calls.append(
                "checked"
            ),
    )

    assert calls == [
        "checked",
        "checked",
    ]

    assert final == (
        tmp_path
        / module.STAGE_NAME
    )

    assert {
        item.name
        for item in final.iterdir()
    } == module.STAGE_FILES

    assert (
        final
        / module.MATRIX_NAME
    ).read_bytes() == matrix

    assert not (
        tmp_path
        / module.PARTIAL_NAME
    ).exists()

    with pytest.raises(
        module
        .MonthlyStructuralFeatureExecutionError,
        match="already exists",
    ):
        module.publish_stage(
            stage1_root=tmp_path,
            matrix_payload=matrix,
            provenance_payload=(
                provenance
            ),
            record_payload=record,
            stability_check=lambda:
                None,
        )


def test_stage_stability_failure_cleans_publication(
    tmp_path,
):
    calls = []

    def stability():
        calls.append(
            "checked"
        )

        if len(
            calls
        ) == 2:
            raise RuntimeError(
                "synthetic failure"
            )

    with pytest.raises(
        RuntimeError,
        match="synthetic failure",
    ):
        module.publish_stage(
            stage1_root=tmp_path,
            matrix_payload=b"m\n",
            provenance_payload=b"p\n",
            record_payload=b"r\n",
            stability_check=stability,
        )

    assert not (
        tmp_path
        / module.STAGE_NAME
    ).exists()

    assert not (
        tmp_path
        / module.PARTIAL_NAME
    ).exists()


def test_completion_publication_no_clobber(
    tmp_path,
):
    payload = b"{}\n"

    calls = []

    path = (
        module.publish_completion(
            stage1_root=tmp_path,
            payload=payload,
            stability_check=lambda:
                calls.append(
                    "checked"
                ),
        )
    )

    assert calls == [
        "checked",
        "checked",
    ]

    assert path.read_bytes() == payload

    assert not (
        tmp_path
        / module.COMPLETION_TEMP_NAME
    ).exists()

    with pytest.raises(
        module
        .MonthlyStructuralFeatureExecutionError,
        match="already exists",
    ):
        module.publish_completion(
            stage1_root=tmp_path,
            payload=payload,
            stability_check=lambda:
                None,
        )


def test_record_explicitly_excludes_downstream_science(
    monkeypatch,
):
    build = fake_build()

    monkeypatch.setattr(
        module,
        "audit_frozen_partition",
        lambda value:
            None,
    )

    stage9 = module.Stage9Authority(
        universe=(),
        species_by_accession={},
        universe_sha256=(
            module
            .EXPECTED_STAGE9_UNIVERSE_SHA256
        ),
        record_sha256=(
            module
            .EXPECTED_STAGE9_RECORD_SHA256
        ),
        completion_sha256=(
            module
            .EXPECTED_STAGE9_COMPLETION_SHA256
        ),
    )

    payload = (
        module.build_execution_record(
            release_id="2026.09",
            source_snapshot_id="snapshot",
            execution_commit=(
                "a"
                * 40
            ),
            build=build,
            stage9=stage9,
            current_component_identity_sha256=(
                module
                .EXPECTED_COMPONENT_IDENTITY_MAPPING_SHA256
            ),
            matrix_sha256=(
                "b"
                * 64
            ),
            provenance_sha256=(
                "c"
                * 64
            ),
        )
    )

    record = json_loads(
        payload
    )

    assert (
        record[
            "percentile_coordinates_calculated"
        ]
        is False
    )

    assert (
        record[
            "selector_outcomes_calculated"
        ]
        is False
    )

    assert (
        record[
            "nested_panels_calculated"
        ]
        is False
    )


def json_loads(
    payload: bytes,
):
    import json

    return json.loads(
        payload.decode(
            "ascii"
        )
    )
