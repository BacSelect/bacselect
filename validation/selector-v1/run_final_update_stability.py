#!/usr/bin/env python3
"""Run blinded final selector-v1 update-stability validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import platform
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from bacselect.geometry import species_balanced_percentile_matrix
from bacselect.ops import (
    _exact_centroid as ops_exact_centroid,
    _squared_distances as ops_squared_distances,
    ops_ladder,
    ops_species_representatives,
)
from bacselect.provenance import verify_input_manifest
from bacselect.sr import (
    _choose_genome_maximum,
    _choose_genome_minimum,
    _choose_species_maximum,
    _choose_species_minimum,
    _exact_centroid as sr_exact_centroid,
    _species_groups,
    _squared_distances as sr_squared_distances,
    sr_ladder,
)
from bacselect.tie import species_tie_key, tie_key


EXPECTED_GENOMES = 55306
EXPECTED_SPECIES = 13765

FEATURES = (
    "01_total_genome_length",
    "02_whole_genome_gc_fraction",
    "03_replicon_count",
    "04_non_chromosomal_replicon_count",
    "05_non_chromosomal_sequence_fraction",
    "06_non_unique_canonical_300mer_fraction",
    "07_non_unique_canonical_2400mer_fraction",
    "08_maximum_canonical_300mer_multiplicity",
    "09_maximum_canonical_2400mer_multiplicity",
    "10_longest_exact_repeat_length",
    "11_inter_replicon_shared_canonical_300mer_fraction",
    "12_inter_replicon_shared_canonical_2400mer_fraction",
)
METADATA_COLUMNS = (
    "batch",
    "batch_index",
    "canonical_genbank_assembly_accession",
)
ACCESSION_COLUMN = "canonical_genbank_assembly_accession"
SPECIES_COLUMN = "species_taxid"

PANEL_SIZES = (10, 20, 50, 100, 200, 500)
MAX_N = 500
UPDATE_NAMESPACE = "BacSelect-selector-v1|update-stability-v1|"

INPUT_MANIFEST = Path(
    "validation/selector-v1/final-feature-space-inputs.tsv"
)
ENV_LOCK = Path("envs/bacselect-dev-linux-64.lock")

EXPECTED_INPUT_MANIFEST_SHA256 = (
    "512d466ff6b8af3e51eb91db715d5fc5"
    "c76995892a4c1b18489d922a0414f0f2"
)
EXPECTED_RAW_FILE_SHA256 = (
    "86c0c3d49317dfc3cc452114e3863666"
    "fe2112b6a3ae8dae2090b60a2a598948"
)
EXPECTED_SPECIES_MAPPING_SHA256 = (
    "f0343238930e957f82bc28997a216ab3"
    "a8967d007b3d3471679e3f054c76af6c"
)
EXPECTED_RAW_ARRAY_SHA256 = (
    "2a0dbd5809fa4d5d77ab6e2d5255ddec"
    "9bb933a94be6c270260ec81758d8cbd6"
)
EXPECTED_PERCENTILE_ARRAY_SHA256 = (
    "9a4a120562ff1151fd8c83e831eb81362"
    "b2372844f7dd7407746554af49cda67"
)
EXPECTED_OPS_LADDER_SHA256 = (
    "c81d9fd30cda2d49f0f6c81d4bf99da"
    "ce9fff811c7612036d9265ef90707fa13"
)
EXPECTED_SR_LADDER_SHA256 = (
    "3c703f5f898e0a13c6eb8568c0b83f5"
    "b0d19d4e374155d2d3a8a4e20378bd51f"
)
EXPECTED_ENV_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207ea"
    "ef5c2435e1b6feeddc1e4654686bc2a8c"
)


@dataclass
class Universe:
    raw: np.ndarray
    species: list[str]
    accessions: list[str]
    synthetic: list[bool]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha256(path: Path, expected: str) -> None:
    observed = file_sha256(path)
    if observed != expected:
        raise AssertionError(
            f"SHA256 changed for {path}: expected={expected} observed={observed}"
        )


def array_sha256(values: np.ndarray) -> str:
    canonical = np.ascontiguousarray(values, dtype="<f8")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def stable_hash(*parts: str) -> str:
    payload = UPDATE_NAMESPACE + "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def shadow_accession(scenario: str, template: str, ordinal: int) -> str:
    return "BSUPD_" + stable_hash(scenario, template, str(ordinal))[:32]


def synthetic_species(scenario: str, key: str) -> str:
    return "BSUPDSP_" + stable_hash(scenario, key)[:32]


def format_float(value: float | None) -> str:
    if value is None:
        return ""
    return format(float(value), ".17g")


def write_text_exact(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def sequence_sha256(namespace: str, values: list[str]) -> str:
    payload = namespace + "\n" + "\n".join(values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_baseline() -> Universe:
    require_sha256(INPUT_MANIFEST, EXPECTED_INPUT_MANIFEST_SHA256)
    require_sha256(ENV_LOCK, EXPECTED_ENV_LOCK_SHA256)

    artifacts = verify_input_manifest(INPUT_MANIFEST)
    artifact_map = {artifact.artifact: artifact.path for artifact in artifacts}
    raw_path = artifact_map["final_raw_structural_feature_matrix"]
    species_path = artifact_map["corrected_species_mapping"]

    require_sha256(raw_path, EXPECTED_RAW_FILE_SHA256)
    require_sha256(species_path, EXPECTED_SPECIES_MAPPING_SHA256)

    with raw_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != (*METADATA_COLUMNS, *FEATURES):
            raise AssertionError("final raw schema changed")
        raw_rows = list(reader)

    with species_path.open(newline="", encoding="utf-8") as handle:
        species_rows = list(csv.DictReader(handle, delimiter="\t"))

    accessions = [row[ACCESSION_COLUMN] for row in raw_rows]
    mapping = [row[ACCESSION_COLUMN] for row in species_rows]
    if accessions != mapping:
        raise AssertionError("raw/species accession order changed")

    species = [row[SPECIES_COLUMN] for row in species_rows]
    raw = np.asarray(
        [[float(row[feature]) for feature in FEATURES] for row in raw_rows],
        dtype=np.float64,
    )

    if raw.shape != (EXPECTED_GENOMES, 12):
        raise AssertionError("baseline raw matrix shape changed")
    if len(set(species)) != EXPECTED_SPECIES:
        raise AssertionError("baseline species count changed")
    if array_sha256(raw) != EXPECTED_RAW_ARRAY_SHA256:
        raise AssertionError("baseline raw array identity changed")

    return Universe(
        raw=raw,
        species=species,
        accessions=accessions,
        synthetic=[False] * len(accessions),
    )


def ranked_indices(
    accessions: list[str],
    scenario: str,
    count: int,
) -> list[int]:
    return sorted(
        range(len(accessions)),
        key=lambda i: (stable_hash(scenario, accessions[i]), accessions[i]),
    )[:count]


def species_members(universe: Universe) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for index, species_id in enumerate(universe.species):
        groups.setdefault(species_id, []).append(index)
    return groups


def species_key(universe: Universe, indices: list[int]) -> str:
    return species_tie_key([universe.accessions[i] for i in indices])


def scenario_fingerprint(universe: Universe) -> str:
    rows = sorted(
        (
            tie_key(universe.accessions[index]),
            stable_hash(
                "species-membership",
                str(universe.species[index]),
            ),
            "1" if universe.synthetic[index] else "0",
            *[
                format(float(value), ".17g")
                for value in universe.raw[index]
            ],
        )
        for index in range(len(universe.accessions))
    )
    payload = "\n".join("\t".join(row) for row in rows) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def add_shadows(
    universe: Universe,
    source: Universe,
    scenario: str,
    additions: list[tuple[int, str, int]],
) -> Universe:
    if not additions:
        return universe

    added_raw = np.asarray(
        [source.raw[index] for index, _, _ in additions],
        dtype=np.float64,
    )

    return Universe(
        raw=np.vstack([universe.raw, added_raw]),
        species=[
            *universe.species,
            *[species_id for _, species_id, _ in additions],
        ],
        accessions=[
            *universe.accessions,
            *[
                shadow_accession(
                    scenario,
                    source.accessions[index],
                    ordinal,
                )
                for index, _, ordinal in additions
            ],
        ],
        synthetic=[
            *universe.synthetic,
            *([True] * len(additions)),
        ],
    )


def make_scenario(baseline: Universe, scenario: str) -> Universe:
    u = Universe(
        raw=baseline.raw.copy(),
        species=list(baseline.species),
        accessions=list(baseline.accessions),
        synthetic=list(baseline.synthetic),
    )

    if scenario == "add_general_500":
        templates = ranked_indices(
            baseline.accessions, scenario + "|templates", 500
        )
        additions = [
            (index, baseline.species[index], ordinal)
            for ordinal, index in enumerate(templates, start=1)
        ]
        u = add_shadows(u, baseline, scenario, additions)

    elif scenario == "remove_500":
        remove = set(
            ranked_indices(baseline.accessions, scenario + "|remove", 500)
        )
        keep = [i for i in range(len(baseline.accessions)) if i not in remove]
        u = Universe(
            raw=baseline.raw[keep].copy(),
            species=[baseline.species[i] for i in keep],
            accessions=[baseline.accessions[i] for i in keep],
            synthetic=[False] * len(keep),
        )

    elif scenario == "replace_500":
        replace = ranked_indices(
            baseline.accessions, scenario + "|replace", 500
        )
        replace_set = set(replace)
        keep = [i for i in range(len(baseline.accessions)) if i not in replace_set]
        u = Universe(
            raw=baseline.raw[keep].copy(),
            species=[baseline.species[i] for i in keep],
            accessions=[baseline.accessions[i] for i in keep],
            synthetic=[False] * len(keep),
        )
        additions = [
            (index, baseline.species[index], ordinal)
            for ordinal, index in enumerate(replace, start=1)
        ]
        u = add_shadows(u, baseline, scenario, additions)

    elif scenario == "add_heavy_species_500":
        groups = species_members(baseline)
        ordered_species = sorted(
            groups,
            key=lambda sp: (-len(groups[sp]), species_key(baseline, groups[sp])),
        )
        heavy = ordered_species[:10]
        if any(len(groups[sp]) < 500 for sp in heavy):
            raise AssertionError("heavy-species precondition changed")
        additions: list[tuple[int, str, int]] = []
        ordinal = 0
        for sp in heavy:
            members = sorted(
                groups[sp],
                key=lambda i: (
                    stable_hash(scenario, baseline.accessions[i]),
                    baseline.accessions[i],
                ),
            )[:50]
            for index in members:
                ordinal += 1
                additions.append((index, sp, ordinal))
        u = add_shadows(u, baseline, scenario, additions)

    elif scenario == "add_new_species_100":
        templates = ranked_indices(
            baseline.accessions, scenario + "|templates", 100
        )
        additions = [
            (
                index,
                synthetic_species(scenario, str(ordinal)),
                ordinal,
            )
            for ordinal, index in enumerate(templates, start=1)
        ]
        u = add_shadows(u, baseline, scenario, additions)

    elif scenario == "taxonomy_split_500":
        groups = species_members(baseline)
        ordered_species = sorted(
            groups,
            key=lambda sp: (-len(groups[sp]), species_key(baseline, groups[sp])),
        )
        target = ordered_species[0]
        if len(groups[target]) != 4388:
            raise AssertionError("maximum baseline species size changed")
        members = sorted(
            groups[target],
            key=lambda i: (
                stable_hash(scenario, baseline.accessions[i]),
                baseline.accessions[i],
            ),
        )[:500]
        new_species = synthetic_species(scenario, "split")
        for index in members:
            u.species[index] = new_species

    elif scenario == "taxonomy_merge_100_singletons":
        groups = species_members(baseline)
        singletons = [sp for sp, members in groups.items() if len(members) == 1]
        ordered = sorted(
            singletons,
            key=lambda sp: (
                stable_hash(scenario, species_key(baseline, groups[sp])),
                species_key(baseline, groups[sp]),
            ),
        )[:100]
        if len(ordered) != 100:
            raise AssertionError("not enough singleton species")
        merged = synthetic_species(scenario, "merge")
        for sp in ordered:
            u.species[groups[sp][0]] = merged

    else:
        raise ValueError(f"unknown scenario: {scenario}")

    if len(set(u.accessions)) != len(u.accessions):
        raise AssertionError(f"scenario has duplicate accessions: {scenario}")

    return u


SCENARIOS = (
    "add_general_500",
    "remove_500",
    "replace_500",
    "add_heavy_species_500",
    "add_new_species_100",
    "taxonomy_split_500",
    "taxonomy_merge_100_singletons",
)


def ladder_fingerprint(
    selector: str,
    ladder: np.ndarray,
    accessions: list[str],
) -> str:
    values = [accessions[int(i)] for i in ladder]
    return sequence_sha256(
        f"BacSelect-selector-v1|final300-2400|{selector}|ladder|N=500",
        values,
    )


def ops_trace(
    coordinates: np.ndarray,
    species: list[str],
    accessions: list[str],
    baseline_choices: list[str],
) -> tuple[np.ndarray, list[dict[str, object]]]:
    reps = ops_species_representatives(coordinates, species, accessions)
    rep_coords = coordinates[reps]
    rep_accessions = [accessions[int(i)] for i in reps]
    rep_by_accession = {acc: local for local, acc in enumerate(rep_accessions)}
    available_accessions = set(accessions)

    centroid = ops_exact_centroid(rep_coords)
    first_scores = ops_squared_distances(rep_coords, centroid)
    first_local = min(
        range(len(rep_accessions)),
        key=lambda i: (first_scores[i], tie_key(rep_accessions[i])),
    )

    selected = [first_local]
    mask = np.zeros(len(reps), dtype=bool)
    mask[first_local] = True
    nearest = ops_squared_distances(rep_coords, rep_coords[first_local])
    nearest[first_local] = 0.0

    traces: list[dict[str, object]] = []

    for rank in range(1, MAX_N + 1):
        baseline_acc = baseline_choices[rank - 1]
        if rank == 1:
            chosen = first_local
            primary = float(first_scores[chosen])
            baseline_local = rep_by_accession.get(baseline_acc)
            baseline_primary = (
                None if baseline_local is None
                else float(first_scores[baseline_local])
            )
            traces.append(
                {
                    "rank": rank,
                    "chosen_index": int(reps[chosen]),
                    "stage": "initial_centroid_min",
                    "primary": primary,
                    "secondary": None,
                    "baseline_present": baseline_acc in available_accessions,
                    "baseline_candidate": baseline_local is not None,
                    "baseline_primary": baseline_primary,
                    "baseline_secondary": None,
                }
            )
            continue

        remaining = np.flatnonzero(~mask)
        best_value = np.max(nearest[remaining])
        tied = remaining[nearest[remaining] == best_value]
        chosen = min(
            (int(i) for i in tied),
            key=lambda i: tie_key(rep_accessions[i]),
        )

        baseline_local = rep_by_accession.get(baseline_acc)
        baseline_candidate = (
            baseline_local is not None and not mask[baseline_local]
        )
        baseline_primary = (
            float(nearest[baseline_local])
            if baseline_candidate else None
        )

        selected.append(chosen)
        traces.append(
            {
                "rank": rank,
                "chosen_index": int(reps[chosen]),
                "stage": "maximin",
                "primary": float(nearest[chosen]),
                "secondary": None,
                "baseline_present": baseline_acc in available_accessions,
                "baseline_candidate": baseline_candidate,
                "baseline_primary": baseline_primary,
                "baseline_secondary": None,
            }
        )
        mask[chosen] = True
        distances = ops_squared_distances(rep_coords, rep_coords[chosen])
        nearest = np.minimum(nearest, distances)
        nearest[mask] = 0.0

    ladder = reps[np.asarray(selected, dtype=np.int64)]
    expected = ops_ladder(coordinates, species, accessions, max_n=MAX_N)
    if not np.array_equal(ladder, expected):
        raise AssertionError("OPS traced ladder differs from committed selector")
    return ladder, traces


def sr_trace(
    coordinates: np.ndarray,
    species: list[str],
    accessions: list[str],
    baseline_choices: list[str],
) -> tuple[np.ndarray, list[dict[str, object]]]:
    groups = _species_groups(species, accessions)
    group_count = len(groups)
    centroids = np.vstack(
        [sr_exact_centroid(coordinates[members]) for _, members, _ in groups]
    )
    global_centroid = sr_exact_centroid(centroids)
    centroid_distances = sr_squared_distances(centroids, global_centroid)
    species_keys = [item[2] for item in groups]
    all_groups = np.arange(group_count, dtype=np.int64)

    first_group = _choose_species_minimum(
        centroid_distances, all_groups, species_keys
    )
    first_members = groups[first_group][1]
    genome_distances = sr_squared_distances(coordinates, global_centroid)
    first_genome = _choose_genome_minimum(
        genome_distances, first_members, accessions
    )

    selected = [first_genome]
    selected_mask = np.zeros(len(accessions), dtype=bool)
    selected_mask[first_genome] = True
    nearest = sr_squared_distances(coordinates, coordinates[first_genome])
    nearest[first_genome] = 0.0

    accession_to_index = {acc: i for i, acc in enumerate(accessions)}
    index_to_group: dict[int, int] = {}
    for group_index, (_, members, _) in enumerate(groups):
        for index in members:
            index_to_group[int(index)] = group_index

    traces: list[dict[str, object]] = []

    for rank in range(1, MAX_N + 1):
        baseline_acc = baseline_choices[rank - 1]

        if rank == 1:
            baseline_index = accession_to_index.get(baseline_acc)
            baseline_group = (
                None if baseline_index is None
                else index_to_group[baseline_index]
            )
            traces.append(
                {
                    "rank": rank,
                    "chosen_index": int(first_genome),
                    "stage": "initial_species_centroid_then_genome_min",
                    "primary": float(centroid_distances[first_group]),
                    "secondary": float(genome_distances[first_genome]),
                    "baseline_present": baseline_index is not None,
                    "baseline_candidate": baseline_index is not None,
                    "baseline_primary": (
                        None if baseline_group is None
                        else float(centroid_distances[baseline_group])
                    ),
                    "baseline_secondary": (
                        None if baseline_index is None
                        else float(genome_distances[baseline_index])
                    ),
                    "selected_group": int(first_group),
                    "baseline_group": (
                        None if baseline_group is None
                        else int(baseline_group)
                    ),
                }
            )
            continue

        residual = np.full(group_count, -np.inf, dtype=np.float64)
        eligible_groups: list[int] = []
        for group_index, (_, members, _) in enumerate(groups):
            if np.all(selected_mask[members]):
                continue
            eligible_groups.append(group_index)
            residual[group_index] = (
                math.fsum(float(nearest[int(i)]) for i in members)
                / members.size
            )

        chosen_group = _choose_species_maximum(
            residual,
            np.asarray(eligible_groups, dtype=np.int64),
            species_keys,
        )
        members = groups[chosen_group][1]
        unselected = members[~selected_mask[members]]
        next_genome = _choose_genome_maximum(
            nearest, unselected, accessions
        )

        baseline_index = accession_to_index.get(baseline_acc)
        baseline_group = (
            None if baseline_index is None else index_to_group[baseline_index]
        )
        baseline_candidate = (
            baseline_index is not None
            and not selected_mask[baseline_index]
            and baseline_group in eligible_groups
        )

        traces.append(
            {
                "rank": rank,
                "chosen_index": int(next_genome),
                "stage": "species_residual_then_genome_maximin",
                "primary": float(residual[chosen_group]),
                "secondary": float(nearest[next_genome]),
                "baseline_present": baseline_index is not None,
                "baseline_candidate": baseline_candidate,
                "baseline_primary": (
                    float(residual[baseline_group])
                    if baseline_candidate else None
                ),
                "baseline_secondary": (
                    float(nearest[baseline_index])
                    if baseline_candidate else None
                ),
                "selected_group": int(chosen_group),
                "baseline_group": (
                    None if baseline_group is None
                    else int(baseline_group)
                ),
            }
        )

        selected.append(next_genome)
        selected_mask[next_genome] = True
        distances = sr_squared_distances(coordinates, coordinates[next_genome])
        nearest = np.minimum(nearest, distances)
        nearest[selected_mask] = 0.0

    ladder = np.asarray(selected, dtype=np.int64)
    expected = sr_ladder(coordinates, species, accessions, max_n=MAX_N)
    if not np.array_equal(ladder, expected):
        raise AssertionError("SR traced ladder differs from committed selector")
    return ladder, traces


def first_divergence(
    baseline_accessions: list[str],
    perturbed_ladder: np.ndarray,
    perturbed_accessions: list[str],
    traces: list[dict[str, object]],
    selector: str,
) -> dict[str, object]:
    chosen_accessions = [
        perturbed_accessions[int(i)] for i in perturbed_ladder
    ]
    rank = next(
        (
            i + 1
            for i, (a, b) in enumerate(zip(baseline_accessions, chosen_accessions))
            if a != b
        ),
        0,
    )
    if rank == 0:
        return {
            "first_divergence_rank": 0,
            "stage": "none",
            "baseline_present": True,
            "baseline_candidate": True,
            "selected_primary_score": None,
            "baseline_primary_score": None,
            "selected_secondary_score": None,
            "baseline_secondary_score": None,
            "score_relation": "identical_through_N500",
            "reason": "none",
        }

    trace = traces[rank - 1]
    present = bool(trace["baseline_present"])
    candidate = bool(trace["baseline_candidate"])
    primary = trace["primary"]
    baseline_primary = trace["baseline_primary"]
    secondary = trace["secondary"]
    baseline_secondary = trace["baseline_secondary"]

    if not present:
        reason = "baseline_choice_unavailable"
        relation = "not_comparable"
    elif not candidate:
        reason = (
            "baseline_choice_not_species_representative"
            if selector == "OPS"
            else "baseline_choice_not_eligible_under_current_species_state"
        )
        relation = "not_comparable"
    else:
        if selector == "OPS":
            if rank == 1:
                if primary < baseline_primary:
                    reason = "lower_initial_centroid_distance"
                    relation = "selected_lower"
                elif primary == baseline_primary:
                    reason = "tie_break"
                    relation = "equal"
                else:
                    reason = "unexpected_score_order"
                    relation = "selected_higher"
            else:
                if primary > baseline_primary:
                    reason = "higher_maximin_score"
                    relation = "selected_higher"
                elif primary == baseline_primary:
                    reason = "tie_break"
                    relation = "equal"
                else:
                    reason = "unexpected_score_order"
                    relation = "selected_lower"
        else:
            selected_group = trace["selected_group"]
            baseline_group = trace["baseline_group"]

            if rank == 1:
                if primary < baseline_primary:
                    reason = "lower_initial_species_centroid_distance"
                    relation = "selected_primary_lower"
                elif primary > baseline_primary:
                    reason = "unexpected_primary_score_order"
                    relation = "selected_primary_higher"
                elif selected_group != baseline_group:
                    reason = "species_tie_break"
                    relation = "primary_equal_species_tie_break"
                elif secondary < baseline_secondary:
                    reason = "lower_initial_genome_centroid_distance"
                    relation = "primary_equal_secondary_lower"
                elif secondary == baseline_secondary:
                    reason = "genome_tie_break"
                    relation = "scores_equal_genome_tie_break"
                else:
                    reason = "unexpected_secondary_score_order"
                    relation = "primary_equal_secondary_higher"
            else:
                if primary > baseline_primary:
                    reason = "higher_species_residual_score"
                    relation = "selected_primary_higher"
                elif primary < baseline_primary:
                    reason = "unexpected_primary_score_order"
                    relation = "selected_primary_lower"
                elif selected_group != baseline_group:
                    reason = "species_tie_break"
                    relation = "primary_equal_species_tie_break"
                elif secondary > baseline_secondary:
                    reason = "higher_genome_maximin_score"
                    relation = "primary_equal_secondary_higher"
                elif secondary == baseline_secondary:
                    reason = "genome_tie_break"
                    relation = "scores_equal_genome_tie_break"
                else:
                    reason = "unexpected_secondary_score_order"
                    relation = "primary_equal_secondary_lower"

    return {
        "first_divergence_rank": rank,
        "stage": trace["stage"],
        "baseline_present": present,
        "baseline_candidate": candidate,
        "selected_primary_score": primary,
        "baseline_primary_score": baseline_primary,
        "selected_secondary_score": secondary,
        "baseline_secondary_score": baseline_secondary,
        "score_relation": relation,
        "reason": reason,
    }


def shared_geometry_shift(
    baseline: Universe,
    baseline_coords: np.ndarray,
    perturbed: Universe,
    perturbed_coords: np.ndarray,
) -> tuple[int, float, float]:
    base_index = {acc: i for i, acc in enumerate(baseline.accessions)}
    pert_index = {acc: i for i, acc in enumerate(perturbed.accessions)}
    shared = sorted(set(base_index) & set(pert_index))
    if not shared:
        raise AssertionError("no shared baseline accessions in scenario")
    diffs = np.asarray(
        [
            np.abs(
                baseline_coords[base_index[acc]]
                - perturbed_coords[pert_index[acc]]
            )
            for acc in shared
        ],
        dtype=np.float64,
    )
    return (
        len(shared),
        float(np.mean(diffs)),
        float(np.max(diffs)),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-inputs-only", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    baseline = load_baseline()

    counts = Counter(baseline.species)
    if max(counts.values()) != 4388:
        raise AssertionError("baseline maximum species size changed")
    if sum(value >= 500 for value in counts.values()) != 10:
        raise AssertionError("baseline >=500-genome species count changed")

    scenario_objects = {
        scenario: make_scenario(baseline, scenario)
        for scenario in SCENARIOS
    }

    print("PASS | frozen update-stability scenario definitions")
    for scenario in SCENARIOS:
        u = scenario_objects[scenario]
        print(
            f"scenario | {scenario} | genomes={len(u.accessions)} | "
            f"species={len(set(u.species))} | "
            f"fingerprint={scenario_fingerprint(u)}"
        )

    if args.verify_inputs_only:
        if args.output_dir is not None:
            raise ValueError("--output-dir must not be used with --verify-inputs-only")
        print(
            "PASS | verification only | "
            "no perturbed percentile geometry or selector calculated"
        )
        return

    if args.output_dir is None:
        raise ValueError("--output-dir is required")
    output_dir = args.output_dir
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite: {output_dir}")
    output_dir.mkdir(parents=True)

    baseline_coords = species_balanced_percentile_matrix(
        baseline.raw, baseline.species
    )
    if array_sha256(baseline_coords) != EXPECTED_PERCENTILE_ARRAY_SHA256:
        raise AssertionError("baseline percentile array changed")

    baseline_ops = ops_ladder(
        baseline_coords, baseline.species, baseline.accessions, max_n=MAX_N
    )
    baseline_sr = sr_ladder(
        baseline_coords, baseline.species, baseline.accessions, max_n=MAX_N
    )
    if ladder_fingerprint(
        "OPS", baseline_ops, baseline.accessions
    ) != EXPECTED_OPS_LADDER_SHA256:
        raise AssertionError("baseline OPS fingerprint changed")
    if ladder_fingerprint(
        "SR", baseline_sr, baseline.accessions
    ) != EXPECTED_SR_LADDER_SHA256:
        raise AssertionError("baseline SR fingerprint changed")

    baseline_ladders = {"OPS": baseline_ops, "SR": baseline_sr}
    baseline_accessions = {
        selector: [baseline.accessions[int(i)] for i in ladder]
        for selector, ladder in baseline_ladders.items()
    }

    scenario_rows: list[list[object]] = []
    prefix_rows: list[list[object]] = []
    trace_rows: list[list[object]] = []

    for scenario in SCENARIOS:
        u = scenario_objects[scenario]
        coords = species_balanced_percentile_matrix(u.raw, u.species)

        shared_n, mean_shift, max_shift = shared_geometry_shift(
            baseline, baseline_coords, u, coords
        )

        added = len(set(u.accessions) - set(baseline.accessions))
        removed = len(set(baseline.accessions) - set(u.accessions))
        perturbed_species_by_accession = {
            acc: species_id
            for acc, species_id in zip(u.accessions, u.species)
        }
        reassigned = sum(
            1
            for acc, base_sp in zip(baseline.accessions, baseline.species)
            if acc in perturbed_species_by_accession
            and perturbed_species_by_accession[acc] != base_sp
        )

        scenario_rows.append(
            [
                scenario,
                scenario_fingerprint(u),
                len(u.accessions),
                len(set(u.species)),
                added,
                removed,
                reassigned,
                shared_n,
                format_float(mean_shift),
                format_float(max_shift),
                array_sha256(coords),
            ]
        )

        for selector in ("OPS", "SR"):
            choices = baseline_accessions[selector]
            if selector == "OPS":
                ladder, traces = ops_trace(
                    coords, u.species, u.accessions, choices
                )
            else:
                ladder, traces = sr_trace(
                    coords, u.species, u.accessions, choices
                )

            divergence = first_divergence(
                choices, ladder, u.accessions, traces, selector
            )

            perturbed_set_by_n = {
                n: {u.accessions[int(i)] for i in ladder[:n]}
                for n in PANEL_SIZES
            }
            synthetic_set = {
                acc
                for acc, flag in zip(u.accessions, u.synthetic)
                if flag
            }
            available = set(u.accessions)

            for n in PANEL_SIZES:
                base_set = set(choices[:n])
                pert_set = perturbed_set_by_n[n]
                overlap = len(base_set & pert_set)
                prefix_rows.append(
                    [
                        scenario,
                        selector,
                        n,
                        overlap,
                        n - overlap,
                        f"{overlap}/{n}",
                        len(pert_set & synthetic_set),
                        len(base_set - available),
                        divergence["first_divergence_rank"],
                    ]
                )

            trace_rows.append(
                [
                    scenario,
                    selector,
                    divergence["first_divergence_rank"],
                    divergence["stage"],
                    "YES" if divergence["baseline_present"] else "NO",
                    "YES" if divergence["baseline_candidate"] else "NO",
                    format_float(divergence["selected_primary_score"]),
                    format_float(divergence["baseline_primary_score"]),
                    format_float(divergence["selected_secondary_score"]),
                    format_float(divergence["baseline_secondary_score"]),
                    divergence["score_relation"],
                    divergence["reason"],
                ]
            )

        print(
            f"PASS | update scenario completed | {scenario} | "
            f"genomes={len(u.accessions)} | species={len(set(u.species))}"
        )

    scenario_path = output_dir / "final-update-stability-scenarios.tsv"
    prefix_path = output_dir / "final-update-stability-prefixes.tsv"
    trace_path = output_dir / "final-update-stability-first-divergence.tsv"
    summary_path = output_dir / "final-update-stability-summary.json"

    def write_tsv(path: Path, header: list[str], rows: list[list[object]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)

    write_tsv(
        scenario_path,
        [
            "scenario",
            "scenario_fingerprint",
            "genomes",
            "species",
            "added_genomes",
            "removed_genomes",
            "reassigned_existing_genomes",
            "shared_baseline_accessions",
            "mean_abs_percentile_shift",
            "max_abs_percentile_shift",
            "perturbed_percentile_array_sha256",
        ],
        scenario_rows,
    )
    write_tsv(
        prefix_path,
        [
            "scenario",
            "selector",
            "N",
            "overlap_count",
            "changed_count",
            "overlap_fraction",
            "synthetic_selected_count",
            "baseline_unavailable_count",
            "first_divergence_rank",
        ],
        prefix_rows,
    )
    write_tsv(
        trace_path,
        [
            "scenario",
            "selector",
            "first_divergence_rank",
            "stage",
            "baseline_choice_present",
            "baseline_choice_candidate",
            "selected_primary_score",
            "baseline_primary_score",
            "selected_secondary_score",
            "baseline_secondary_score",
            "score_relation",
            "reason",
        ],
        trace_rows,
    )

    summary = {
        "analysis": "selector-v1-final-update-stability",
        "schema_version": 1,
        "scenarios": list(SCENARIOS),
        "panel_sizes": list(PANEL_SIZES),
        "selectors": ["OPS", "SR"],
        "baseline_genomes": EXPECTED_GENOMES,
        "baseline_species": EXPECTED_SPECIES,
        "synthetic_feature_policy":
            "shadow copies of observed raw structural profiles only",
        "selection_policy":
            "scenario-specific SHA256 ranking; no PRNG",
        "scientific_output_sha256": {
            "scenarios": file_sha256(scenario_path),
            "prefixes": file_sha256(prefix_path),
            "first_divergence": file_sha256(trace_path),
        },
        "identity_blinding": "REQUIRED",
        "selector_decision_rule_introduced": False,
        "stability_acceptance_threshold_defined": False,
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    write_text_exact(
        summary_path,
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
    )

    for path in (scenario_path, prefix_path, trace_path, summary_path):
        text = path.read_text(encoding="utf-8")
        if "GCA_" in text or "GCF_" in text:
            raise AssertionError(f"identity-like accession leaked into {path}")

    print("===== scientific output SHA256 =====")
    for path in (scenario_path, prefix_path, trace_path, summary_path):
        print(f"{file_sha256(path)}  {path}")
    print("PASS | final update-stability validation completed")


if __name__ == "__main__":
    main()
