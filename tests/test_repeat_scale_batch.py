from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from bacselect.repeat_scale import (
    K_GRID,
    REPEAT_FEATURE_FAMILIES,
)


REPO = Path(__file__).resolve().parents[1]
WORKER_PATH = (
    REPO
    / "validation"
    / "selector-v1"
    / "run_repeat_scale_batch.py"
)


def load_worker():
    spec = importlib.util.spec_from_file_location(
        "bacselect_repeat_scale_batch_test",
        WORKER_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


worker = load_worker()


def engine_text(
    k_values=worker.EXPECTED_K_GRID,
) -> str:
    rows = [
        (
            "k\tvalid_start_count\t"
            "non_unique_start_count\t"
            "non_unique_fraction\t"
            "maximum_multiplicity\t"
            "inter_replicon_shared_start_count\t"
            "inter_replicon_shared_fraction"
        )
    ]

    for k in k_values:
        rows.append(
            f"{k}\t100\t20\t0.2\t3\t10\t0.1"
        )

    return "\n".join(rows) + "\n"


def test_frozen_grid_and_feature_families_match_module() -> None:
    assert tuple(K_GRID) == (
        50,
        75,
        100,
        150,
        200,
        300,
        400,
        600,
        800,
        1200,
        1600,
        2400,
        3200,
    )

    assert tuple(REPEAT_FEATURE_FAMILIES) == (
        "non_unique_fraction",
        "maximum_multiplicity",
        "inter_replicon_shared_fraction",
    )

    worker.validate_frozen_constants()


def test_engine_command_contains_exact_grid_without_longest_repeat() -> None:
    command = worker.build_engine_command(
        Path("/engine"),
        Path("/input.tsv"),
    )

    assert command[:3] == [
        "/engine",
        "--input",
        "/input.tsv",
    ]

    observed_k = [
        int(command[index + 1])
        for index, value in enumerate(command)
        if value == "--k"
    ]

    assert observed_k == list(
        worker.EXPECTED_K_GRID
    )
    assert "--longest-repeat" not in command


def test_parse_engine_output_accepts_complete_grid() -> None:
    raw, numeric = worker.parse_engine_output(
        engine_text()
    )

    assert tuple(sorted(raw)) == (
        worker.EXPECTED_K_GRID
    )
    assert tuple(sorted(numeric)) == (
        worker.EXPECTED_K_GRID
    )
    assert numeric[150][
        "non_unique_fraction"
    ] == pytest.approx(0.2)
    assert numeric[400][
        "maximum_multiplicity"
    ] == 3


def test_parse_engine_output_rejects_missing_k() -> None:
    text = engine_text(
        worker.EXPECTED_K_GRID[:-1]
    )

    with pytest.raises(
        RuntimeError,
        match="row count mismatch",
    ):
        worker.parse_engine_output(text)


def test_parse_engine_output_rejects_duplicate_k() -> None:
    text = engine_text()
    duplicate = (
        "50\t100\t20\t0.2\t3\t10\t0.1\n"
    )
    text += duplicate

    with pytest.raises(
        RuntimeError,
        match="duplicate repeat engine row",
    ):
        worker.parse_engine_output(text)


def test_parse_engine_output_rejects_unexpected_k() -> None:
    text = engine_text(
        (
            *worker.EXPECTED_K_GRID[:-1],
            9999,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected repeat engine k",
    ):
        worker.parse_engine_output(text)


def test_engine_row_rejects_fraction_count_inconsistency() -> None:
    row = {
        "valid_start_count": "100",
        "non_unique_start_count": "20",
        "non_unique_fraction": "0.3",
        "maximum_multiplicity": "3",
        "inter_replicon_shared_start_count": "10",
        "inter_replicon_shared_fraction": "0.1",
    }

    with pytest.raises(
        RuntimeError,
        match="does not match count/denominator",
    ):
        worker.normalize_engine_feature_row(
            row,
            k=150,
            exact_keys=True,
        )


def test_engine_row_rejects_shared_count_above_non_unique() -> None:
    row = {
        "valid_start_count": "100",
        "non_unique_start_count": "10",
        "non_unique_fraction": "0.1",
        "maximum_multiplicity": "3",
        "inter_replicon_shared_start_count": "20",
        "inter_replicon_shared_fraction": "0.2",
    }

    with pytest.raises(
        RuntimeError,
        match="shared starts exceed non-unique",
    ):
        worker.normalize_engine_feature_row(
            row,
            k=150,
            exact_keys=True,
        )


def test_zero_valid_starts_requires_zero_repeat_values() -> None:
    good = {
        "valid_start_count": "0",
        "non_unique_start_count": "0",
        "non_unique_fraction": "0",
        "maximum_multiplicity": "0",
        "inter_replicon_shared_start_count": "0",
        "inter_replicon_shared_fraction": "0",
    }

    observed = (
        worker.normalize_engine_feature_row(
            good,
            k=3200,
            exact_keys=True,
        )
    )

    assert observed[
        "maximum_multiplicity"
    ] == 0

    bad = dict(good)
    bad["non_unique_fraction"] = "0.1"

    with pytest.raises(
        RuntimeError,
        match="non-zero repeat values",
    ):
        worker.normalize_engine_feature_row(
            bad,
            k=3200,
            exact_keys=True,
        )


def test_candidate_source_path_matches_frozen_snapshot_layout() -> None:
    batch = Path("/snapshot/batch-005")

    observed = worker.candidate_source_path(
        batch,
        "GCA_000000001.1",
    )

    assert observed == (
        Path("/snapshot/batch-005")
        / "package"
        / "ncbi_dataset"
        / "data"
        / "GCA_000000001.1"
    )


def test_anchor_features_are_derived_from_150_and_400_only() -> None:
    features = {
        str(k): {
            "valid_start_count": 100,
            "non_unique_start_count": 20,
            "non_unique_fraction": (
                0.15 if k == 150 else 0.4
            ),
            "maximum_multiplicity": (
                7 if k == 150 else 9
            ),
            "inter_replicon_shared_start_count": 10,
            "inter_replicon_shared_fraction": (
                0.05 if k == 150 else 0.08
            ),
        }
        for k in worker.EXPECTED_K_GRID
    }

    observed = (
        worker.anchor_features_from_numeric(
            features
        )
    )

    assert observed == {
        (
            "06_non_unique_canonical_"
            "150mer_fraction"
        ): 0.15,
        (
            "07_non_unique_canonical_"
            "400mer_fraction"
        ): 0.4,
        (
            "08_maximum_canonical_"
            "150mer_multiplicity"
        ): 7,
        (
            "09_maximum_canonical_"
            "400mer_multiplicity"
        ): 9,
        (
            "11_inter_replicon_shared_"
            "canonical_150mer_fraction"
        ): 0.05,
        (
            "12_inter_replicon_shared_"
            "canonical_400mer_fraction"
        ): 0.08,
    }
