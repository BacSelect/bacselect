from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

from bacselect.monthly_release_package import (
    ARCHITECTURE_SCHEMA_VERSION,
    PANEL_SIZES,
    SELECTOR,
    SELECTOR_VERSION,
    PublicMetadataRow,
    first_public_panel_n,
    panel_identity,
    serialize_panel_accessions,
)


REPO = (
    Path(
        __file__
    ).resolve().parents[
        1
    ]
)

WRAPPER = (
    REPO
    / "validation"
    / "selector-v1"
    / "run_monthly_release_package.py"
)


def load_module():
    name = (
        "_bacselect_test_stage15_wrapper"
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            name,
            WRAPPER,
        )
    )

    assert spec is not None
    assert spec.loader is not None

    module = (
        importlib.util.module_from_spec(
            spec
        )
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


@pytest.fixture
def module():
    return load_module()


def metadata_rows(
    module,
):
    values = []

    for rank in range(
        1,
        501,
    ):
        accession = (
            f"GCA_{rank:09d}.1"
        )

        values.append(
            PublicMetadataRow(
                selection_rank=str(
                    rank
                ),
                first_public_panel_n=str(
                    first_public_panel_n(
                        rank
                    )
                ),
                genbank_assembly_accession=accession,
                biosample_accession=(
                    f"SAMN{rank:08d}"
                ),
                ncbi_organism_name=(
                    f"Organism {rank}"
                ),
                ncbi_organism_taxid=str(
                    100000
                    + rank
                ),
                bacselect_species_name=(
                    f"Species {rank}"
                ),
                bacselect_species_taxid=str(
                    200000
                    + rank
                ),
                assembly_name=(
                    f"ASM{rank}v1"
                ),
                submitter=(
                    f"Submitter {rank}"
                ),
                assembly_release_date=(
                    "2026-08-01"
                ),
                panel_identity=(
                    panel_identity(
                        module.RELEASE_ID
                    )
                ),
                selector=SELECTOR,
                selector_version=(
                    SELECTOR_VERSION
                ),
                architecture_schema_version=(
                    ARCHITECTURE_SCHEMA_VERSION
                ),
                source_snapshot_sha256=(
                    module.EXPECTED_SOURCE_RAW_SHA256
                ),
                taxonomy_snapshot_sha256=(
                    module.EXPECTED_TAXONOMY_ARCHIVE_SHA256
                ),
                execution_git_commit=(
                    module.EXPECTED_STAGE13_EXECUTION_COMMIT
                ),
                ncbi_assembly_url=(
                    "https://www.ncbi.nlm.nih.gov/assembly/"
                    + accession
                    + "/"
                ),
            )
        )

    return tuple(
        values
    )


def source_authority(
    module,
):
    return module.SourceAuthority(
        source_snapshot_record_sha256=(
            module.EXPECTED_SOURCE_SNAPSHOT_RECORD_SHA256
        ),
        source_raw_sha256=(
            module.EXPECTED_SOURCE_RAW_SHA256
        ),
        taxonomy_archive_sha256=(
            module.EXPECTED_TAXONOMY_ARCHIVE_SHA256
        ),
        source_universe_count=(
            module.EXPECTED_COMPLETE_UNIVERSE_COUNT
        ),
        species_count=(
            module.EXPECTED_SPECIES_COUNT
        ),
    )


def stage14_authority(
    module,
    rows,
):
    panels = {
        panel_size:
            serialize_panel_accessions(
                rows,
                release_id=(
                    module.RELEASE_ID
                ),
                panel_size=(
                    panel_size
                ),
            )
        for panel_size
        in PANEL_SIZES
    }

    metrics = {
        str(
            panel_size
        ): {
            "median_nearest_panel_distance":
                f"{panel_size}.1",
            "p95_nearest_panel_distance":
                f"{panel_size}.2",
            "maximum_nearest_panel_distance":
                f"{panel_size}.3",
        }
        for panel_size
        in PANEL_SIZES
    }

    return module.Stage14Authority(
        panel_payloads=panels,
        membership_manifest_payload=(
            b"membership\n"
        ),
        coverage_summary_payload=(
            b"coverage\n"
        ),
        coverage_distances_payload=(
            b"distances\n"
        ),
        record={
            "required_coverage_metrics":
                metrics,
        },
        completion={},
    )


def copied():
    return {
        "panel-membership-manifest.tsv":
            b"membership\n",
        "complete-ops-ladder.tsv":
            b"ladder\n",
        "monthly-ops-ladder-record.json":
            b'{"selector":"OPS"}\n',
        "structural-coverage-summary.tsv":
            b"coverage\n",
    }


def build(
    module,
):
    rows = metadata_rows(
        module
    )

    return module.build_stage15_artifacts(
        execution_commit=(
            "a" * 40
        ),
        metadata_rows=rows,
        source=source_authority(
            module
        ),
        stage14=stage14_authority(
            module,
            rows,
        ),
        evidence_manifest_payload=(
            b"role\trelative_path\tsha256\tbytes\n"
            b"source_snapshot_metadata\tx\t"
            + (
                b"1"
                * 64
            )
            + b"\t1\n"
        ),
        copied_artifacts=copied(),
    )


def test_stage15_identity_constants(module):
    assert (
        module.RELEASE_ID
        == "2026.09"
    )

    assert (
        module.SOURCE_SNAPSHOT_ID
        == (
            "bacselect-source-2026.09-"
            "20260901T021652Z"
        )
    )

    assert (
        module.STATUS
        == "MONTHLY_RELEASE_PACKAGE_COMPLETE"
    )

    assert (
        module.STAGE_NAME
        == "release-package"
    )


def test_frozen_dependency_identities_are_exact(module):
    assert (
        module.EXPECTED_STAGE14_WRAPPER_SHA256
        == "2260728793419a5ed2f45f933c48239c21b246226942059dc33c9c3cb345a554"
    )

    assert (
        module.EXPECTED_PACKAGE_MODULE_SHA256
        == "481f4b867c22fd6725570b0a99076d6355864db72a63e2302571724b09ace4ff"
    )

    assert (
        module.EXPECTED_PACKAGE_SCHEMA_SHA256
        == "c7ca02ab09ba73ba6b8c08f9d678335efa15073c1252601a497f84dd2539df20"
    )


def test_package_inventory_is_complete(module):
    assert len(
        module.PUBLIC_DOWNLOAD_NAMES
    ) == 19

    assert (
        module.COPIED_RELEASE_ARTIFACT_NAMES
        == {
            "panel-membership-manifest.tsv",
            "complete-ops-ladder.tsv",
            "monthly-ops-ladder-record.json",
            "structural-coverage-summary.tsv",
        }
    )

    assert len(
        module.PACKAGE_ARTIFACT_NAMES
    ) == 27

    assert len(
        module.STAGE_FILES
    ) == 28


def test_evidence_contract_binds_large_scientific_inputs(module):
    values = set(
        module.EVIDENCE_FILE_SPECS
    )

    assert (
        "source_snapshot_metadata",
        "assembly_data_report.raw.jsonl",
    ) in values

    assert (
        "metadata_eligibility",
        "complete-universe/complete-universe.tsv",
    ) in values

    assert (
        "taxonomy_snapshot_identity",
        "taxonomy-snapshot/new_taxdump.tar.gz",
    ) in values

    assert (
        "raw_structural_features",
        (
            "structural-features/"
            "structural-feature-matrix-300-2400.tsv"
        ),
    ) in values

    assert (
        "percentile_geometry",
        (
            "percentile-geometry/"
            "species-balanced-percentile-feature-matrix-300-2400.tsv"
        ),
    ) in values

    assert (
        "public_panel_coverage",
        (
            "public-panels-and-coverage/"
            "structural-coverage-distances.tsv"
        ),
    ) in values


def test_stage15_build_has_exact_inventory(module):
    result = build(
        module
    )

    assert set(
        result.artifacts
    ) == set(
        module.PACKAGE_ARTIFACT_NAMES
    )

    assert len(
        result.artifacts
    ) == 27


def test_stage15_txt_files_are_exact_stage14_prefixes(module):
    rows = metadata_rows(
        module
    )

    authority = stage14_authority(
        module,
        rows,
    )

    result = module.build_stage15_artifacts(
        execution_commit=(
            "a" * 40
        ),
        metadata_rows=rows,
        source=source_authority(
            module
        ),
        stage14=authority,
        evidence_manifest_payload=(
            b"evidence\n"
        ),
        copied_artifacts=copied(),
    )

    for panel_size in PANEL_SIZES:
        name = (
            f"bacselect-2026.09-n{panel_size}.txt"
        )

        assert (
            result.artifacts[
                name
            ]
            == authority.panel_payloads[
                panel_size
            ]
        )


def test_stage15_refuses_stage14_txt_drift(module):
    rows = metadata_rows(
        module
    )

    authority = stage14_authority(
        module,
        rows,
    )

    wrong = dict(
        authority.panel_payloads
    )

    wrong[
        10
    ] = b"GCA_999999999.1\n"

    authority = replace(
        authority,
        panel_payloads=wrong,
    )

    with pytest.raises(
        module.MonthlyReleaseExecutionError,
        match="differ from Stage 14",
    ):
        module.build_stage15_artifacts(
            execution_commit=(
                "a" * 40
            ),
            metadata_rows=rows,
            source=source_authority(
                module
            ),
            stage14=authority,
            evidence_manifest_payload=(
                b"evidence\n"
            ),
            copied_artifacts=copied(),
        )


def test_real_xlsx_style_is_preserved_in_build(module):
    result = build(
        module
    )

    payload = result.artifacts[
        "bacselect-2026.09-n10.xlsx"
    ]

    with zipfile.ZipFile(
        io.BytesIO(
            payload
        )
    ) as archive:
        styles = archive.read(
            "xl/styles.xml"
        ).decode(
            "utf-8"
        )

        sheet = archive.read(
            "xl/worksheets/sheet1.xml"
        ).decode(
            "utf-8"
        )

    assert (
        '<fgColor rgb="FF6846C7"/>'
        in styles
    )

    assert (
        '<pane ySplit="1"'
        in sheet
    )

    assert (
        '<autoFilter ref="A1:S11"/>'
        in sheet
    )


def test_release_summary_has_public_scientific_identity(module):
    rows = metadata_rows(
        module
    )

    payload = module.build_release_summary(
        source=source_authority(
            module
        ),
        stage14=stage14_authority(
            module,
            rows,
        ),
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    assert record[
        "release_id"
    ] == "2026.09"

    assert record[
        "panel_identity"
    ] == "bacselect-2026.09"

    assert record[
        "selector"
    ] == "OPS"

    assert record[
        "selector_version"
    ] == "1.0.0"

    assert record[
        "architecture_schema_version"
    ] == "1"

    assert record[
        "source_universe_count"
    ] == 68164

    assert record[
        "species_group_count"
    ] == 16223

    assert record[
        "complete_ladder_count"
    ] == 16223

    assert record[
        "panel_definition"
    ] == "complete_OPS_ladder[0:N]"

    assert (
        "publication_state"
        not in record
    )

    assert (
        "doi"
        not in record
    )


def test_release_provenance_binds_frozen_execution_chain(module):
    rows = metadata_rows(
        module
    )

    result = build(
        module
    )

    provenance = json.loads(
        result.artifacts[
            module.RELEASE_PROVENANCE_NAME
        ].decode(
            "ascii"
        )
    )

    assert provenance[
        "stage13_selector_execution_commit"
    ] == (
        module.EXPECTED_STAGE13_EXECUTION_COMMIT
    )

    assert provenance[
        "stage14_execution_commit"
    ] == (
        module.EXPECTED_STAGE14_EXECUTION_COMMIT
    )

    assert provenance[
        "stage15_execution_commit"
    ] == (
        "a"
        * 40
    )

    assert provenance[
        "stage15_serializer_sha256"
    ] == (
        module.EXPECTED_PACKAGE_MODULE_SHA256
    )

    assert provenance[
        "source_raw_response_sha256"
    ] == (
        module.EXPECTED_SOURCE_RAW_SHA256
    )

    assert provenance[
        "taxonomy_archive_sha256"
    ] == (
        module.EXPECTED_TAXONOMY_ARCHIVE_SHA256
    )

    assert provenance[
        "metadata_ladder_sha256"
    ] == result.metadata_ladder_sha256


def test_sha256sums_covers_every_other_package_artifact(module):
    result = build(
        module
    )

    lines = result.artifacts[
        module.CHECKSUMS_NAME
    ].decode(
        "ascii"
    ).splitlines()

    observed = {}

    for line in lines:
        digest, name = line.split(
            "  ",
            1,
        )

        observed[
            name
        ] = digest

    expected_names = (
        set(
            result.artifacts
        )
        - {
            module.CHECKSUMS_NAME,
        }
    )

    assert set(
        observed
    ) == expected_names

    for name in expected_names:
        assert observed[
            name
        ] == hashlib.sha256(
            result.artifacts[
                name
            ]
        ).hexdigest()


def test_execution_record_explicitly_blocks_publication_claims(module):
    result = build(
        module
    )

    payload = module.build_execution_record(
        execution_commit=(
            "a"
            * 40
        ),
        build=result,
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    assert record[
        "ops_rerun"
    ] is False

    assert record[
        "coverage_rerun"
    ] is False

    assert record[
        "production_rebuild_audit_passed"
    ] is False

    assert record[
        "publication_gate_passed"
    ] is False

    assert record[
        "release_published"
    ] is False

    assert record[
        "zenodo_published"
    ] is False


def test_completion_does_not_claim_rebuild_or_publication(module):
    result = build(
        module
    )

    record_payload = (
        module.build_execution_record(
            execution_commit=(
                "a"
                * 40
            ),
            build=result,
        )
    )

    record_sha = hashlib.sha256(
        record_payload
    ).hexdigest()

    payload = (
        module.build_completion_receipt(
            execution_commit=(
                "a"
                * 40
            ),
            build=result,
            record_sha256=(
                record_sha
            ),
        )
    )

    receipt = json.loads(
        payload.decode(
            "ascii"
        )
    )

    assert receipt[
        "production_rebuild_audit_passed"
    ] is False

    assert receipt[
        "publication_gate_passed"
    ] is False

    assert receipt[
        "release_published"
    ] is False

    assert receipt[
        "record_sha256"
    ] == record_sha


def test_package_bytes_are_deterministic(module):
    first = build(
        module
    )

    second = build(
        module
    )

    assert first.artifacts == second.artifacts

    assert (
        first.metadata_ladder_sha256
        == second.metadata_ladder_sha256
    )

    assert (
        first.evidence_manifest_sha256
        == second.evidence_manifest_sha256
    )


def test_atomic_stage_publication(module, tmp_path):
    result = build(
        module
    )

    stage = module.publish_stage(
        output_root=tmp_path,
        artifacts=result.artifacts,
        record_payload=b"record\n",
        stability_check=lambda: None,
    )

    assert stage == (
        tmp_path
        / module.STAGE_NAME
    )

    assert stage.is_dir()

    assert not (
        tmp_path
        / module.PARTIAL_NAME
    ).exists()

    assert {
        path.name
        for path in stage.iterdir()
    } == module.STAGE_FILES


def test_atomic_completion_publication(module, tmp_path):
    path = module.publish_completion(
        output_root=tmp_path,
        payload=b"completion\n",
        stability_check=lambda: None,
    )

    assert path.read_bytes() == (
        b"completion\n"
    )

    assert not (
        tmp_path
        / module.COMPLETION_TEMP_NAME
    ).exists()


def test_existing_stage_is_refused(module, tmp_path):
    (
        tmp_path
        / module.STAGE_NAME
    ).mkdir()

    with pytest.raises(
        module.MonthlyReleaseExecutionError,
        match="already exists",
    ):
        module.publish_stage(
            output_root=tmp_path,
            artifacts={
                name:
                    b"x"
                for name in module.PACKAGE_ARTIFACT_NAMES
            },
            record_payload=b"record\n",
            stability_check=lambda: None,
        )


def test_separate_output_root_does_not_modify_authority_root(
    module,
    tmp_path,
):
    authority = (
        tmp_path
        / "authority"
    )

    output = (
        tmp_path
        / "rebuild"
    )

    authority.mkdir()
    output.mkdir()

    marker = (
        authority
        / "marker.txt"
    )

    marker.write_bytes(
        b"authority\n"
    )

    result = build(
        module
    )

    module.publish_stage(
        output_root=output,
        artifacts=result.artifacts,
        record_payload=b"record\n",
        stability_check=lambda: None,
    )

    assert marker.read_bytes() == (
        b"authority\n"
    )

    assert not (
        authority
        / module.STAGE_NAME
    ).exists()

    assert (
        output
        / module.STAGE_NAME
    ).is_dir()


def test_wrapper_does_not_rerun_selector_or_coverage(module):
    text = WRAPPER.read_text(
        encoding="utf-8"
    )

    forbidden_calls = (
        "build_complete_ops_ladder(",
        "evaluate_structural_coverage(",
        "nearest_panel_distances(",
        "build_stage14_artifacts(",
        "build_reference_panel_artifacts(",
        "serialize_generation_summary(",
    )

    for token in forbidden_calls:
        assert token not in text


def test_wrapper_has_no_network_or_zenodo_execution():
    text = WRAPPER.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "requests",
        "urllib",
        "urlopen",
        "ZENODO_ACCESS_TOKEN",
        "api.zenodo.org",
        "sandbox.zenodo.org",
        "Bearer ",
    )

    for token in forbidden:
        assert token not in text


def test_stage15_output_names_contain_no_historical_reference_identity(module):
    for name in (
        module.PACKAGE_ARTIFACT_NAMES
        | module.STAGE_FILES
    ):
        assert (
            "reference"
            not in name
        )


def test_public_download_metadata_is_release_specific(module):
    result = build(
        module
    )

    text = result.artifacts[
        "bacselect-2026.09-n10.tsv"
    ].decode(
        "utf-8"
    )

    assert (
        "bacselect-2026.09"
        in text
    )

    assert (
        "selector-v1-reference"
        not in text
    )


def test_release_summary_contains_all_six_coverage_metric_sets(module):
    rows = metadata_rows(
        module
    )

    summary = json.loads(
        module.build_release_summary(
            source=source_authority(
                module
            ),
            stage14=stage14_authority(
                module,
                rows,
            ),
        ).decode(
            "ascii"
        )
    )

    assert set(
        summary[
            "required_structural_coverage_metrics"
        ]
    ) == {
        str(
            panel_size
        )
        for panel_size
        in PANEL_SIZES
    }


def test_package_record_binds_every_package_artifact(module):
    result = build(
        module
    )

    record = json.loads(
        module.build_execution_record(
            execution_commit=(
                "a"
                * 40
            ),
            build=result,
        ).decode(
            "ascii"
        )
    )

    assert set(
        record[
            "package_artifact_sha256"
        ]
    ) == set(
        module.PACKAGE_ARTIFACT_NAMES
    )

    assert record[
        "package_artifact_count"
    ] == 27


def test_evidence_manifest_role_inventory_is_frozen(module):
    roles = {
        role
        for role, _
        in module.EVIDENCE_FILE_SPECS
    }

    assert roles == {
        "source_snapshot_metadata",
        "metadata_eligibility",
        "source_truth_eligibility",
        "biosample_reconciliation",
        "chromosome_integrity_review",
        "taxonomy_snapshot_identity",
        "species_resolution",
        "raw_structural_features",
        "percentile_geometry",
        "species_representatives",
        "complete_diversity_ladder",
        "selector_trace",
        "public_panel_coverage",
    }


def test_no_stage15_production_path_is_hardcoded():
    text = WRAPPER.read_text(
        encoding="utf-8"
    )

    assert (
        "/NGS/scratch/"
        not in text
    )

    assert (
        "Rhys_wkdir"
        not in text
    )
