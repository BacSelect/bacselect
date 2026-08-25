#!/usr/bin/env python3
"""Run the frozen BacSelect selector-v1 repeat-scale pair selection.

This is a thin analysis driver. It does not implement the percentile,
distance, pair-scoring, or selection mathematics. Those calculations are
delegated directly to the committed functions in bacselect.repeat_scale.
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from bacselect.repeat_scale import (
    repeat_scale_percentile_tensor,
    species_balanced_scale_distance_matrix,
    score_scale_pairs,
    select_scale_pair,
)


ANALYSIS_COMMIT = "3c77cd33902bde25571aa4c04ab8d2e528bbec97"
PRODUCTION_COMMIT = "83516de6cd3713415e78502ba58db072fa6b38f9"

EXPECTED = {
    "production_files_manifest_sha256":
        "75fd427a28b712b1c76ebe93722d2c6baac1e3d1bccedf63a00de71bebea5b84",
    "full_universe_audit_summary_sha256":
        "40ce0b77936d69c039474256c904f16cb204ec4040f05c190619708547dc6dc1",
    "species_mapping_sha256":
        "f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c",
    "repeat_scale_module_sha256":
        "7dcd0cab3da9698ca4a697315326bc303e30c96d3b3ed12e48b627287a3b6f6c",
    "repeat_scale_method_sha256":
        "2897282450221e662bb1d6c1142da7c999e07e23c21d66f265cbf2fe13313d01",
    "genomes": 55306,
    "species": 13765,
    "batches": 111,
    "production_files": 55639,
}

K_VALUES = (
    50, 75, 100, 150, 200, 300, 400,
    600, 800, 1200, 1600, 2400, 3200,
)

FAMILIES = (
    "non_unique_fraction",
    "maximum_multiplicity",
    "inter_replicon_shared_fraction",
)

SPECIES_MAPPING_HEADER_REQUIRED = {
    "batch",
    "batch_index",
    "canonical_genbank_assembly_accession",
    "species_taxid",
}


def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def verify_repository(repo: Path) -> None:
    head = git(repo, "rev-parse", "HEAD")
    origin = git(repo, "rev-parse", "origin/main")
    status = git(repo, "status", "--porcelain")

    if head != ANALYSIS_COMMIT:
        fail(f"HEAD mismatch: expected {ANALYSIS_COMMIT}, observed {head}")
    if origin != ANALYSIS_COMMIT:
        fail(
            "origin/main mismatch: "
            f"expected {ANALYSIS_COMMIT}, observed {origin}"
        )
    if status:
        fail("BacSelect scientific repository is not clean")


def verify_file(path: Path, expected_sha256: str, label: str) -> None:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    observed = sha256_file(path)
    if observed != expected_sha256:
        fail(
            f"{label} SHA256 mismatch: expected {expected_sha256}, "
            f"observed {observed}"
        )


def verify_production_manifest(
    production_root: Path,
    manifest_path: Path,
) -> None:
    rows = 0
    seen: set[str] = set()

    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            raw = raw.rstrip("\n")
            if not raw:
                fail(
                    "production-file manifest contains an empty row at "
                    f"line {line_number}"
                )

            try:
                expected_sha, relpath = raw.split(None, 1)
            except ValueError as exc:
                raise RuntimeError(
                    f"invalid production manifest row {line_number}"
                ) from exc

            relpath = relpath.strip()
            if not relpath.startswith("./"):
                fail(
                    f"production manifest path is not canonical at "
                    f"line {line_number}: {relpath!r}"
                )
            if relpath in seen:
                fail(f"duplicate production manifest path: {relpath}")
            seen.add(relpath)

            path = production_root / relpath[2:]
            if not path.is_file():
                fail(f"production file missing: {relpath}")

            observed_sha = sha256_file(path)
            if observed_sha != expected_sha:
                fail(
                    f"production file SHA256 mismatch: {relpath}: "
                    f"expected {expected_sha}, observed {observed_sha}"
                )

            rows += 1

    if rows != EXPECTED["production_files"]:
        fail(
            "production manifest row count mismatch: "
            f"expected {EXPECTED['production_files']}, observed {rows}"
        )


def load_species_mapping(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or [])
        missing = SPECIES_MAPPING_HEADER_REQUIRED - fields
        if missing:
            fail(
                "species mapping is missing required columns: "
                + ", ".join(sorted(missing))
            )
        rows = list(reader)

    if len(rows) != EXPECTED["genomes"]:
        fail(
            "species mapping row count mismatch: "
            f"expected {EXPECTED['genomes']}, observed {len(rows)}"
        )

    keys: set[tuple[str, int, str]] = set()
    accessions: set[str] = set()
    species_ids: list[str] = []

    for row_number, row in enumerate(rows, start=2):
        batch = row["batch"]
        accession = row["canonical_genbank_assembly_accession"]
        species_id = row["species_taxid"]

        try:
            batch_index = int(row["batch_index"])
        except ValueError as exc:
            raise RuntimeError(
                f"invalid batch_index at species mapping row {row_number}"
            ) from exc

        if not batch.startswith("batch-"):
            fail(f"invalid batch value at mapping row {row_number}: {batch!r}")
        if not accession:
            fail(f"missing accession at species mapping row {row_number}")
        if not species_id:
            fail(f"missing species_taxid at species mapping row {row_number}")

        key = (batch, batch_index, accession)
        if key in keys:
            fail(f"duplicate species-mapping key: {key!r}")
        keys.add(key)

        if accession in accessions:
            fail(f"duplicate accession in species mapping: {accession}")
        accessions.add(accession)
        species_ids.append(species_id)

    observed_species = len(set(species_ids))
    if observed_species != EXPECTED["species"]:
        fail(
            "species count mismatch: "
            f"expected {EXPECTED['species']}, observed {observed_species}"
        )

    return rows


def load_raw_tensor(
    production_root: Path,
    mapping_rows: list[dict[str, str]],
) -> tuple[np.ndarray, list[str]]:
    raw = np.empty(
        (EXPECTED["genomes"], len(K_VALUES), len(FAMILIES)),
        dtype=np.float64,
    )
    species_ids: list[str] = []

    for row_index, row in enumerate(mapping_rows):
        batch = row["batch"]
        accession = row["canonical_genbank_assembly_accession"]
        batch_index = int(row["batch_index"])
        species_id = row["species_taxid"]

        candidate_path = (
            production_root
            / batch
            / "candidates"
            / f"{accession}.repeat-scale.json"
        )
        if not candidate_path.is_file():
            fail(f"candidate JSON missing: {candidate_path}")

        with candidate_path.open("r", encoding="utf-8") as handle:
            candidate = json.load(handle)

        if candidate.get("analysis") != "selector-v1-repeat-scale-grid":
            fail(f"{accession}: unexpected analysis identity")
        if candidate.get("batch") != batch:
            fail(f"{accession}: batch mismatch")
        if candidate.get("batch_index") != batch_index:
            fail(f"{accession}: batch_index mismatch")
        if (
            candidate.get("canonical_genbank_assembly_accession")
            != accession
        ):
            fail(f"{accession}: accession mismatch")
        if tuple(candidate.get("k_values", ())) != K_VALUES:
            fail(f"{accession}: k grid mismatch")
        if tuple(candidate.get("repeat_feature_families", ())) != FAMILIES:
            fail(f"{accession}: repeat feature-family order mismatch")

        anchor = candidate.get("reference_anchor", {})
        if anchor.get("passed") is not True or anchor.get("mismatches") != []:
            fail(f"{accession}: frozen 150/400 reference anchor did not pass")

        features = candidate.get("features_by_k")
        if not isinstance(features, dict):
            fail(f"{accession}: features_by_k is not an object")

        for k_index, k in enumerate(K_VALUES):
            record = features.get(str(k))
            if not isinstance(record, dict):
                fail(f"{accession}: missing feature record for k={k}")

            for family_index, family in enumerate(FAMILIES):
                value = record.get(family)
                if isinstance(value, bool) or not isinstance(
                    value, (int, float)
                ):
                    fail(
                        f"{accession}: non-numeric {family} at k={k}"
                    )
                value = float(value)
                if not math.isfinite(value):
                    fail(
                        f"{accession}: non-finite {family} at k={k}"
                    )
                raw[row_index, k_index, family_index] = value

        species_ids.append(species_id)

    return raw, species_ids


def extract_pair(score: Any) -> tuple[int, int]:
    if not dataclasses.is_dataclass(score):
        fail("score_scale_pairs returned a non-dataclass score")

    record = dataclasses.asdict(score)
    numeric_objectives = {
        "maximum_nearest_distance",
        "mean_nearest_distance",
    }

    if not numeric_objectives.issubset(record):
        fail(
            "ScalePairScore is missing expected objective fields: "
            f"{sorted(record)}"
        )

    remainder = [
        value
        for key, value in record.items()
        if key not in numeric_objectives
    ]

    ints = [
        int(value)
        for value in remainder
        if isinstance(value, int) and not isinstance(value, bool)
    ]

    pair: tuple[int, int] | None = None

    if len(ints) == 2:
        pair = tuple(sorted(ints))
    elif len(remainder) == 1:
        value = remainder[0]
        if (
            isinstance(value, (tuple, list))
            and len(value) == 2
            and all(
                isinstance(item, int) and not isinstance(item, bool)
                for item in value
            )
        ):
            pair = tuple(sorted((int(value[0]), int(value[1]))))

    if pair is None:
        fail(
            "could not identify scale pair from ScalePairScore fields: "
            f"{record!r}"
        )

    if pair[0] == pair[1] or not set(pair).issubset(K_VALUES):
        fail(f"invalid scale pair returned by score object: {pair!r}")

    return pair


def score_record(score: Any) -> dict[str, Any]:
    record = dataclasses.asdict(score)
    pair = extract_pair(score)
    maximum = record["maximum_nearest_distance"]
    mean = record["mean_nearest_distance"]

    if not isinstance(maximum, (int, float)) or not math.isfinite(
        float(maximum)
    ):
        fail(f"invalid maximum nearest distance for pair {pair}")
    if not isinstance(mean, (int, float)) or not math.isfinite(float(mean)):
        fail(f"invalid mean nearest distance for pair {pair}")

    return {
        "k_a": pair[0],
        "k_b": pair[1],
        "maximum_nearest_distance": float(maximum),
        "mean_nearest_distance": float(mean),
    }


def hash_array(array: np.ndarray) -> str:
    canonical = np.ascontiguousarray(array, dtype="<f8")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def write_distance_matrix(path: Path, distances: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(
            handle,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writerow(["k", *K_VALUES])
        for row_index, k in enumerate(K_VALUES):
            writer.writerow(
                [
                    k,
                    *(
                        format(
                            float(distances[row_index, col_index]),
                            ".17g",
                        )
                        for col_index in range(len(K_VALUES))
                    ),
                ]
            )


def write_pair_scores(
    path: Path,
    ranked: list[dict[str, Any]],
    selected_pair: tuple[int, int],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "rank",
            "k_a",
            "k_b",
            "maximum_nearest_distance",
            "mean_nearest_distance",
            "selected",
            "inherited_150_400",
        ]
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()

        for rank, row in enumerate(ranked, start=1):
            pair = (row["k_a"], row["k_b"])
            writer.writerow(
                {
                    "rank": rank,
                    "k_a": pair[0],
                    "k_b": pair[1],
                    "maximum_nearest_distance": format(
                        row["maximum_nearest_distance"], ".17g"
                    ),
                    "mean_nearest_distance": format(
                        row["mean_nearest_distance"], ".17g"
                    ),
                    "selected": str(pair == selected_pair).lower(),
                    "inherited_150_400": str(
                        pair == (150, 400)
                    ).lower(),
                }
            )


def main() -> int:
    home = Path.home()
    repo = home / "github" / "bacselect"
    production_root = Path(
        "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/"
        "repeat-scale/alternative-k-grid/"
        f"{PRODUCTION_COMMIT}/production"
    )
    species_mapping = Path(
        "/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/"
        "corrected-species-resolution/"
        "corrected-genome-species-taxid.tsv"
    )

    evidence_dir = repo / "validation" / "selector-v1" / "results"
    production_manifest = (
        evidence_dir
        / "repeat-scale-full-universe-production-files.sha256"
    )
    audit_summary = (
        evidence_dir
        / "repeat-scale-full-universe-audit-summary.json"
    )
    repeat_scale_module = repo / "src" / "bacselect" / "repeat_scale.py"
    repeat_scale_method = (
        repo / "validation" / "selector-v1" / "repeat-scale-method.md"
    )

    output_dir = (
        home
        / "bacselect-repeat-scale-selection"
        / ANALYSIS_COMMIT
    )

    print("===== frozen input identities =====")
    verify_repository(repo)

    verify_file(
        production_manifest,
        EXPECTED["production_files_manifest_sha256"],
        "frozen production-file manifest",
    )
    verify_file(
        audit_summary,
        EXPECTED["full_universe_audit_summary_sha256"],
        "full-universe audit summary",
    )
    verify_file(
        species_mapping,
        EXPECTED["species_mapping_sha256"],
        "corrected species mapping",
    )
    verify_file(
        repeat_scale_module,
        EXPECTED["repeat_scale_module_sha256"],
        "repeat-scale implementation",
    )
    verify_file(
        repeat_scale_method,
        EXPECTED["repeat_scale_method_sha256"],
        "frozen repeat-scale method",
    )

    if not production_root.is_dir():
        fail(f"production root missing: {production_root}")

    if output_dir.exists():
        fail(
            "analysis output directory already exists; refusing to overwrite: "
            f"{output_dir}"
        )
    output_dir.mkdir(parents=True)

    print("PASS | repository and frozen input identities")

    print("===== exact production-file verification =====")
    verify_production_manifest(production_root, production_manifest)
    print(
        f"PASS | {EXPECTED['production_files']} / "
        f"{EXPECTED['production_files']} production files"
    )

    print("===== load canonical species mapping =====")
    mapping_rows = load_species_mapping(species_mapping)
    print(
        f"PASS | genomes={len(mapping_rows)} | "
        f"species={len({row['species_taxid'] for row in mapping_rows})}"
    )

    print("===== assemble validated 13-k x 3-family tensor =====")
    raw_values, species_ids = load_raw_tensor(
        production_root,
        mapping_rows,
    )
    if raw_values.shape != (EXPECTED["genomes"], 13, 3):
        fail(f"unexpected raw tensor shape: {raw_values.shape!r}")
    print(f"PASS | raw tensor shape={raw_values.shape}")

    raw_sha = hash_array(raw_values)

    print("===== committed percentile transform =====")
    percentile_values = repeat_scale_percentile_tensor(
        raw_values,
        species_ids,
    )
    if percentile_values.shape != raw_values.shape:
        fail(
            "percentile tensor shape changed: "
            f"{percentile_values.shape!r}"
        )
    if not np.isfinite(percentile_values).all():
        fail("percentile tensor contains non-finite values")
    percentile_sha = hash_array(percentile_values)
    print("PASS | repeat_scale_percentile_tensor")

    print("===== committed species-balanced scale distances =====")
    distances = species_balanced_scale_distance_matrix(
        percentile_values,
        species_ids,
    )
    if distances.shape != (13, 13):
        fail(f"unexpected distance matrix shape: {distances.shape!r}")
    if not np.isfinite(distances).all():
        fail("distance matrix contains non-finite values")
    distance_sha = hash_array(distances)
    print("PASS | species_balanced_scale_distance_matrix")

    print("===== committed pair scoring and selection =====")
    scores = score_scale_pairs(distances, K_VALUES)
    if len(scores) != 78:
        fail(f"expected 78 candidate pairs, observed {len(scores)}")

    records = [score_record(score) for score in scores]
    observed_pairs = {
        (record["k_a"], record["k_b"])
        for record in records
    }
    expected_pairs = {
        (K_VALUES[left], K_VALUES[right])
        for left in range(len(K_VALUES))
        for right in range(left + 1, len(K_VALUES))
    }
    if observed_pairs != expected_pairs:
        fail("score_scale_pairs did not return the exact 78-pair grid")

    ranked = sorted(
        records,
        key=lambda row: (
            row["maximum_nearest_distance"],
            row["mean_nearest_distance"],
            row["k_a"],
            row["k_b"],
        ),
    )

    selected = select_scale_pair(distances, K_VALUES)
    selected_pair = extract_pair(selected)
    selected_record = score_record(selected)

    ranked_winner = (ranked[0]["k_a"], ranked[0]["k_b"])
    if selected_pair != ranked_winner:
        fail(
            "select_scale_pair disagrees with the ranking of "
            "score_scale_pairs"
        )

    inherited = next(
        row
        for row in ranked
        if (row["k_a"], row["k_b"]) == (150, 400)
    )
    inherited_rank = next(
        rank
        for rank, row in enumerate(ranked, start=1)
        if (row["k_a"], row["k_b"]) == (150, 400)
    )

    distance_path = output_dir / "repeat-scale-distance-matrix.tsv"
    scores_path = output_dir / "repeat-scale-pair-scores.tsv"
    write_distance_matrix(distance_path, distances)
    write_pair_scores(scores_path, ranked, selected_pair)

    summary = {
        "analysis": "selector-v1-repeat-scale-selection",
        "schema_version": 1,
        "analysis_commit": ANALYSIS_COMMIT,
        "production_commit": PRODUCTION_COMMIT,
        "genomes": EXPECTED["genomes"],
        "species": EXPECTED["species"],
        "k_values": list(K_VALUES),
        "repeat_feature_families": list(FAMILIES),
        "input_sha256": {
            "production_files_manifest":
                EXPECTED["production_files_manifest_sha256"],
            "full_universe_audit_summary":
                EXPECTED["full_universe_audit_summary_sha256"],
            "species_mapping":
                EXPECTED["species_mapping_sha256"],
            "repeat_scale_module":
                EXPECTED["repeat_scale_module_sha256"],
            "repeat_scale_method":
                EXPECTED["repeat_scale_method_sha256"],
        },
        "array_sha256": {
            "raw_values_float64_c_order": raw_sha,
            "percentile_values_float64_c_order": percentile_sha,
            "distance_matrix_float64_c_order": distance_sha,
        },
        "selected_pair": {
            "k_a": selected_pair[0],
            "k_b": selected_pair[1],
            "maximum_nearest_distance":
                selected_record["maximum_nearest_distance"],
            "mean_nearest_distance":
                selected_record["mean_nearest_distance"],
        },
        "inherited_pair_150_400": {
            "rank": inherited_rank,
            "maximum_nearest_distance":
                inherited["maximum_nearest_distance"],
            "mean_nearest_distance":
                inherited["mean_nearest_distance"],
        },
        "selected_pair_differs_from_inherited":
            selected_pair != (150, 400),
        "outputs": {
            "distance_matrix_sha256": sha256_file(distance_path),
            "pair_scores_sha256": sha256_file(scores_path),
        },
    }

    summary_path = output_dir / "repeat-scale-selection-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    hashes_path = output_dir / "repeat-scale-selection-sha256.txt"
    with hashes_path.open("w", encoding="utf-8") as handle:
        for path in (distance_path, scores_path, summary_path):
            handle.write(f"{sha256_file(path)}  {path.name}\n")

    print("PASS | score_scale_pairs and select_scale_pair")
    print()
    print("===== deterministic result =====")
    print(
        "selected_pair\t"
        f"({selected_pair[0]},{selected_pair[1]})"
    )
    print(
        "selected_Rmax\t"
        f"{selected_record['maximum_nearest_distance']:.17g}"
    )
    print(
        "selected_Rmean\t"
        f"{selected_record['mean_nearest_distance']:.17g}"
    )
    print(f"inherited_150_400_rank\t{inherited_rank} / 78")
    print(
        "inherited_Rmax\t"
        f"{inherited['maximum_nearest_distance']:.17g}"
    )
    print(
        "inherited_Rmean\t"
        f"{inherited['mean_nearest_distance']:.17g}"
    )
    print(
        "selected_pair_differs_from_inherited\t"
        f"{str(selected_pair != (150, 400)).lower()}"
    )
    print(f"output_dir\t{output_dir}")
    print()
    print("PASS | frozen repeat-scale selection analysis complete")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL | {exc}", file=sys.stderr)
        raise
