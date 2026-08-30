"""Synthetic tests for Stage 7 filesystem execution semantics."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from bacselect.selector_resolution_artifacts import (
    SCIENTIFIC_ARTIFACT_NAMES,
)
from bacselect.selector_resolution_execution import (
    CONTENT_COVERED_FILES,
    Stage6MatrixExpectations,
    Stage7ExecutionError,
    Stage7FrozenBindings,
    STAGE7_FINAL_FILES,
    _numeric_array_sha256,
    execute_stage7_analysis,
    load_verified_stage6_matrix,
)
from bacselect.source_truth_execution import (
    accession_membership_sha256,
)


FEATURES = tuple(
    f"F{index:02d}"
    for index in range(
        1,
        13,
    )
)


def sequence_sha256(
    namespace: str,
    values: list[str],
) -> str:
    payload = (
        namespace
        + "\n"
        + "\n".join(
            values
        )
        + "\n"
    )

    return hashlib.sha256(
        payload.encode(
            "utf-8"
        )
    ).hexdigest()


def canonical_accession(
    index: int,
) -> str:
    return (
        "GCA_"
        + f"{index:09d}"
        + ".1"
    )


def synthetic_foundation():
    rows = 520

    index = np.arange(
        rows,
        dtype=np.float64,
    )

    raw = np.column_stack(
        [
            (
                index
                * float(
                    column + 1
                )
                + (
                    index
                    % float(
                        column + 3
                    )
                )
                / float(
                    column + 7
                )
            )
            for column in range(
                12
            )
        ]
    )

    species_ids = [
        str(
            1000
            + row // 2
        )
        for row in range(
            rows
        )
    ]

    accessions = [
        canonical_accession(
            row + 1
        )
        for row in range(
            rows
        )
    ]

    return SimpleNamespace(
        raw=raw,
        coordinates=np.zeros_like(
            raw
        ),
        species_ids=species_ids,
        accessions=accessions,
    )


def synthetic_ladders():
    return {
        "OPS":
            np.arange(
                500,
                dtype=np.int64,
            ),
        "SR":
            np.arange(
                519,
                19,
                -1,
                dtype=np.int64,
            ),
    }


def ladder_hashes(
    foundation,
    ladders,
):
    result = {}

    for selector in (
        "OPS",
        "SR",
    ):
        values = [
            foundation.accessions[
                int(index)
            ]
            for index in ladders[
                selector
            ]
        ]

        result[
            selector
        ] = sequence_sha256(
            (
                "BacSelect-selector-v1|"
                f"{selector}|ladder|N=500"
            ),
            values,
        )

    return result


def write_stage6_matrix(
    path: Path,
):
    accessions = [
        canonical_accession(
            900_000_000
            + index
        )
        for index in range(
            1,
            7,
        )
    ]

    species_ids = [
        "1001",
        "2001",
        "2001",
        "3001",
        "4001",
        "5001",
    ]

    raw = np.asarray(
        [
            [
                float(
                    row * 100
                    + column
                )
                / 17.0
                for column in range(
                    1,
                    13,
                )
            ]
            for row in range(
                1,
                7,
            )
        ],
        dtype=np.float64,
    )

    lines = [
        "\t".join(
            (
                "canonical_genbank_assembly_accession",
                "species_taxid",
                *FEATURES,
            )
        )
    ]

    for accession, species_id, values in zip(
        accessions,
        species_ids,
        raw,
        strict=True,
    ):
        lines.append(
            "\t".join(
                (
                    accession,
                    species_id,
                    *(
                        format(
                            float(value),
                            ".17g",
                        )
                        for value in values
                    ),
                )
            )
        )

    payload = (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    path.write_bytes(
        payload
    )

    expectations = Stage6MatrixExpectations(
        artifact_sha256=hashlib.sha256(
            payload
        ).hexdigest(),
        numeric_array_sha256=(
            _numeric_array_sha256(
                raw
            )
        ),
        membership_sha256=(
            accession_membership_sha256(
                accessions
            )
        ),
        row_count=len(
            accessions
        ),
        species_count=len(
            set(
                species_ids
            )
        ),
    )

    return expectations


def frozen_bindings():
    foundation = synthetic_foundation()
    ladders = synthetic_ladders()

    return Stage7FrozenBindings(
        stage7_method_sha256="1" * 64,
        selector_resolution_design_sha256="2" * 64,
        stage6_completion_evidence_sha256="3" * 64,
        environment_lock_sha256="4" * 64,
        baseline_bindings={
            "manifest_sha256":
                "5" * 64,
            "raw_file_sha256":
                "6" * 64,
            "raw_array_sha256":
                "7" * 64,
            "percentile_file_sha256":
                "8" * 64,
            "percentile_array_sha256":
                "9" * 64,
            "species_file_sha256":
                "a" * 64,
        },
        implementation_bindings={
            "scientific_core_sha256":
                "b" * 64,
            "artifact_layer_sha256":
                "c" * 64,
            "analysis_layer_sha256":
                "d" * 64,
            "execution_adapter_sha256":
                "e" * 64,
            "execution_adapter_test_sha256":
                "f" * 64,
        },
        final_ladder_sha256=(
            ladder_hashes(
                foundation,
                ladders,
            )
        ),
    )


def run_synthetic(
    tmp_path: Path,
    *,
    mode: str = "production",
    matrix_loader=None,
    bindings=None,
):
    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_root = (
        tmp_path
        / (
            "production-output"
            if mode == "production"
            else "rebuild-output"
        )
    )

    matrix_path = (
        tmp_path
        / "synthetic-stage6.tsv"
    )

    expectations = write_stage6_matrix(
        matrix_path
    )

    foundation = synthetic_foundation()
    ladders = synthetic_ladders()

    kwargs = {
        "repo":
            repo,
        "expected_commit":
            "a" * 40,
        "execution_mode":
            mode,
        "output_root":
            output_root,
        "stage6_matrix_path":
            matrix_path,
        "stage6_expectations":
            expectations,
        "frozen_bindings":
            (
                frozen_bindings()
                if bindings is None
                else bindings
            ),
        "feature_names":
            FEATURES,
        "baseline_loader":
            lambda: foundation,
        "ladder_builder":
            lambda _: ladders,
        "sequence_hasher":
            sequence_sha256,
    }

    if matrix_loader is not None:
        kwargs[
            "matrix_loader"
        ] = matrix_loader

    final_dir = execute_stage7_analysis(
        **kwargs
    )

    return final_dir


def test_stage6_matrix_round_trip(tmp_path: Path) -> None:
    path = (
        tmp_path
        / "matrix.tsv"
    )

    expectations = write_stage6_matrix(
        path
    )

    observed = load_verified_stage6_matrix(
        path,
        expectations=expectations,
        feature_names=FEATURES,
    )

    assert observed.raw.shape == (
        6,
        12,
    )

    assert len(
        observed.species_ids
    ) == 6

    assert observed.artifact_sha256 == (
        expectations.artifact_sha256
    )

    assert observed.numeric_array_sha256 == (
        expectations.numeric_array_sha256
    )

    assert observed.membership_sha256 == (
        expectations.membership_sha256
    )


def test_predecision_exists_before_matrix_loader(
    tmp_path: Path,
) -> None:
    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir()

    output_root = (
        tmp_path
        / "output"
    )

    matrix_path = (
        tmp_path
        / "matrix.tsv"
    )

    expectations = write_stage6_matrix(
        matrix_path
    )

    foundation = synthetic_foundation()
    ladders = synthetic_ladders()

    called = False

    def guarded_loader(
        path,
        *,
        expectations,
        feature_names,
    ):
        nonlocal called

        predecision = (
            output_root
            / (
                "."
                + "a" * 40
                + ".partial"
            )
            / "stage7-predecision-provenance.json"
        )

        assert predecision.is_file()

        payload = json.loads(
            predecision.read_text(
                encoding="utf-8"
            )
        )

        assert payload[
            "holdout_raw_feature_matrix_opened"
        ] is False

        assert payload[
            "holdout_percentile_coordinates_calculated"
        ] is False

        assert payload[
            "ops_sr_distances_calculated"
        ] is False

        assert payload[
            "primary_metrics_calculated"
        ] is False

        assert payload[
            "exact_selector_products_calculated"
        ] is False

        assert payload[
            "selector_outcome_generated"
        ] is False

        called = True

        return load_verified_stage6_matrix(
            path,
            expectations=expectations,
            feature_names=feature_names,
        )

    execute_stage7_analysis(
        repo=repo,
        expected_commit="a" * 40,
        execution_mode="production",
        output_root=output_root,
        stage6_matrix_path=matrix_path,
        stage6_expectations=expectations,
        frozen_bindings=frozen_bindings(),
        feature_names=FEATURES,
        baseline_loader=lambda: foundation,
        ladder_builder=lambda _: ladders,
        sequence_hasher=sequence_sha256,
        matrix_loader=guarded_loader,
    )

    assert called is True


def test_finalized_artifact_set_is_exact(tmp_path: Path) -> None:
    final_dir = run_synthetic(
        tmp_path
    )

    observed = {
        path.name
        for path in final_dir.iterdir()
        if path.is_file()
    }

    assert observed == set(
        STAGE7_FINAL_FILES
    )

    assert len(
        observed
    ) == 9


def test_six_scientific_artifacts_present(tmp_path: Path) -> None:
    final_dir = run_synthetic(
        tmp_path
    )

    for name in SCIENTIFIC_ARTIFACT_NAMES:
        assert (
            final_dir
            / name
        ).is_file()


def test_content_manifest_covers_exactly_eight_inputs(
    tmp_path: Path,
) -> None:
    final_dir = run_synthetic(
        tmp_path
    )

    lines = (
        final_dir
        / "stage7-content-manifest.tsv"
    ).read_text(
        encoding="utf-8"
    ).splitlines()

    assert lines[0] == (
        "path\tsize_bytes\tsha256"
    )

    observed = {
        line.split(
            "\t"
        )[0]
        for line in lines[1:]
    }

    assert observed == set(
        CONTENT_COVERED_FILES
    )

    assert len(
        observed
    ) == 8


def test_execution_provenance_never_contains_outcome(
    tmp_path: Path,
) -> None:
    final_dir = run_synthetic(
        tmp_path
    )

    payload = json.loads(
        (
            final_dir
            / "stage7-execution-provenance.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert payload[
        "selector_outcome_generated"
    ] is False

    assert payload[
        "baseline_geometry_verified"
    ] is True

    assert payload[
        "final_ladders_verified"
    ] is True

    assert payload[
        "holdout_raw_feature_matrix_opened"
    ] is True

    assert payload[
        "exact_selector_products_calculated"
    ] is True

    text = (
        final_dir
        / "stage7-execution-provenance.json"
    ).read_text(
        encoding="utf-8"
    ).lower()

    assert '"winner"' not in text
    assert '"decision"' not in text
    assert '"resolved_selector"' not in text


def test_exact_products_are_blinded_and_no_winner(
    tmp_path: Path,
) -> None:
    final_dir = run_synthetic(
        tmp_path
    )

    payload = json.loads(
        (
            final_dir
            / "selector-exact-products.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert set(
        payload[
            "selectors"
        ]
    ) == {
        "OPS",
        "SR",
    }

    for selector in (
        "OPS",
        "SR",
    ):
        value = payload[
            "selectors"
        ][
            selector
        ]

        assert set(
            value
        ) == {
            "denominator",
            "numerator",
        }

        Fraction(
            value[
                "numerator"
            ],
            value[
                "denominator"
            ],
        )


def test_production_and_rebuild_scientific_files_byte_identical(
    tmp_path: Path,
) -> None:
    production = run_synthetic(
        tmp_path / "p",
        mode="production",
    )

    rebuild = run_synthetic(
        tmp_path / "r",
        mode="independent_rebuild",
    )

    for name in SCIENTIFIC_ARTIFACT_NAMES:
        assert (
            production
            / name
        ).read_bytes() == (
            rebuild
            / name
        ).read_bytes()


def test_run_specific_provenance_may_differ(
    tmp_path: Path,
) -> None:
    production = run_synthetic(
        tmp_path / "p",
        mode="production",
    )

    rebuild = run_synthetic(
        tmp_path / "r",
        mode="independent_rebuild",
    )

    assert (
        production
        / "stage7-predecision-provenance.json"
    ).read_bytes() != (
        rebuild
        / "stage7-predecision-provenance.json"
    ).read_bytes()


def test_ladder_hash_mismatch_fails_before_matrix_open(
    tmp_path: Path,
) -> None:
    bindings = frozen_bindings()

    bad_hashes = dict(
        bindings.final_ladder_sha256
    )

    bad_hashes[
        "OPS"
    ] = "0" * 64

    bindings = replace(
        bindings,
        final_ladder_sha256=bad_hashes,
    )

    called = False

    def forbidden_loader(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError(
            "matrix loader must not be called"
        )

    with pytest.raises(
        Stage7ExecutionError,
        match="OPS final ladder fingerprint mismatch",
    ):
        run_synthetic(
            tmp_path,
            matrix_loader=forbidden_loader,
            bindings=bindings,
        )

    assert called is False

    partial = (
        tmp_path
        / "production-output"
        / (
            "."
            + "a" * 40
            + ".partial"
        )
    )

    assert partial.is_dir()

    assert (
        partial
        / "stage7-predecision-provenance.json"
    ).is_file()


def test_failed_matrix_verification_preserves_partial(
    tmp_path: Path,
) -> None:
    def failing_loader(*args, **kwargs):
        raise Stage7ExecutionError(
            "synthetic matrix failure"
        )

    with pytest.raises(
        Stage7ExecutionError,
        match="synthetic matrix failure",
    ):
        run_synthetic(
            tmp_path,
            matrix_loader=failing_loader,
        )

    partial = (
        tmp_path
        / "production-output"
        / (
            "."
            + "a" * 40
            + ".partial"
        )
    )

    final = (
        tmp_path
        / "production-output"
        / (
            "a" * 40
        )
    )

    assert partial.is_dir()
    assert not final.exists()

    assert (
        partial
        / "stage7-predecision-provenance.json"
    ).is_file()


def test_existing_final_directory_is_never_overwritten(
    tmp_path: Path,
) -> None:
    first = run_synthetic(
        tmp_path
    )

    marker = (
        first
        / "marker"
    )

    marker.write_text(
        "retain\n",
        encoding="utf-8",
    )

    with pytest.raises(
        Stage7ExecutionError,
        match="final Stage 7 output directory already exists",
    ):
        run_synthetic(
            tmp_path
        )

    assert marker.read_text(
        encoding="utf-8"
    ) == "retain\n"


def test_existing_partial_directory_is_never_reused(
    tmp_path: Path,
) -> None:
    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir()

    output_root = (
        tmp_path
        / "production-output"
    )

    output_root.mkdir()

    partial = (
        output_root
        / (
            "."
            + "a" * 40
            + ".partial"
        )
    )

    partial.mkdir()

    marker = (
        partial
        / "failure-evidence.txt"
    )

    marker.write_text(
        "preserve\n",
        encoding="utf-8",
    )

    matrix_path = (
        tmp_path
        / "matrix.tsv"
    )

    expectations = write_stage6_matrix(
        matrix_path
    )

    foundation = synthetic_foundation()
    ladders = synthetic_ladders()

    with pytest.raises(
        Stage7ExecutionError,
        match="partial Stage 7 output directory already exists",
    ):
        execute_stage7_analysis(
            repo=repo,
            expected_commit="a" * 40,
            execution_mode="production",
            output_root=output_root,
            stage6_matrix_path=matrix_path,
            stage6_expectations=expectations,
            frozen_bindings=frozen_bindings(),
            feature_names=FEATURES,
            baseline_loader=lambda: foundation,
            ladder_builder=lambda _: ladders,
            sequence_hasher=sequence_sha256,
        )

    assert marker.read_text(
        encoding="utf-8"
    ) == "preserve\n"


def test_output_root_inside_repository_rejected(
    tmp_path: Path,
) -> None:
    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir()

    matrix_path = (
        tmp_path
        / "matrix.tsv"
    )

    expectations = write_stage6_matrix(
        matrix_path
    )

    foundation = synthetic_foundation()
    ladders = synthetic_ladders()

    with pytest.raises(
        Stage7ExecutionError,
        match="outside repository",
    ):
        execute_stage7_analysis(
            repo=repo,
            expected_commit="a" * 40,
            execution_mode="production",
            output_root=(
                repo
                / "bad-output"
            ),
            stage6_matrix_path=matrix_path,
            stage6_expectations=expectations,
            frozen_bindings=frozen_bindings(),
            feature_names=FEATURES,
            baseline_loader=lambda: foundation,
            ladder_builder=lambda _: ladders,
            sequence_hasher=sequence_sha256,
        )


def test_stage6_matrix_hash_mismatch_rejected(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "matrix.tsv"
    )

    expectations = write_stage6_matrix(
        path
    )

    expectations = replace(
        expectations,
        artifact_sha256="0" * 64,
    )

    with pytest.raises(
        Stage7ExecutionError,
        match="artifact SHA256 mismatch",
    ):
        load_verified_stage6_matrix(
            path,
            expectations=expectations,
            feature_names=FEATURES,
        )


def test_stage6_numeric_array_hash_mismatch_rejected(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "matrix.tsv"
    )

    expectations = write_stage6_matrix(
        path
    )

    expectations = replace(
        expectations,
        numeric_array_sha256="0" * 64,
    )

    with pytest.raises(
        Stage7ExecutionError,
        match="numeric-array SHA256 mismatch",
    ):
        load_verified_stage6_matrix(
            path,
            expectations=expectations,
            feature_names=FEATURES,
        )


def test_stage6_membership_hash_mismatch_rejected(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "matrix.tsv"
    )

    expectations = write_stage6_matrix(
        path
    )

    expectations = replace(
        expectations,
        membership_sha256="0" * 64,
    )

    with pytest.raises(
        Stage7ExecutionError,
        match="membership SHA256 mismatch",
    ):
        load_verified_stage6_matrix(
            path,
            expectations=expectations,
            feature_names=FEATURES,
        )


def test_invalid_execution_mode_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        Stage7ExecutionError,
        match="invalid Stage 7 execution mode",
    ):
        run_synthetic(
            tmp_path,
            mode="wrong",
        )
