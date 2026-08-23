"""Integrity checks for the frozen selector-v1 machine-readable configuration."""

from __future__ import annotations

import csv
from pathlib import Path


CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "config.tsv"
)


def _read_config() -> list[list[str]]:
    with CONFIG_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle, delimiter="\t"))


def test_selector_config_is_two_column_tsv() -> None:
    rows = _read_config()

    assert rows
    assert all(len(row) == 2 for row in rows)


def test_selector_config_keys_are_unique() -> None:
    rows = _read_config()
    keys = [row[0] for row in rows]

    assert len(keys) == len(set(keys))


def test_frozen_quantile_configuration() -> None:
    config = dict(_read_config())

    assert (
        config["quantile_method"]
        == "empirical_inverse_cdf_no_interpolation"
    )
    assert (
        config["weighted_quantile_weights"]
        == "exact_1_over_species_genome_count"
    )
    assert (
        config["quantile_thresholds"]
        == "median=1/2,p95=19/20,p2.5=1/40,p97.5=39/40"
    )


def test_frozen_random_baseline_configuration() -> None:
    config = dict(_read_config())

    assert config["random_replicates"] == "1000"
    assert config["random_master_seed"] == "20260824"
    assert config["random_rng"] == "numpy.random.Generator(PCG64)"
    assert (
        config["random_replicate_protocol"]
        == "single_generator_sequential_replicates"
    )
    assert config["random_species_order"] == "species_tie_key"
    assert config["random_genome_order"] == "genome_tie_key"
    assert config["random_max_n"] == "500"
