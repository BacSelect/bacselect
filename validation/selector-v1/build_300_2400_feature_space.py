#!/usr/bin/env python3
"""Build the final BacSelect selector-v1 300/2400 12-feature space.

This is a deterministic data transformation after the prospectively frozen
repeat-scale rule selected (300, 2400). Historical 150/400 evidence is not
modified.

The script writes only to its commit-scoped output directory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

from bacselect.geometry import species_balanced_percentile_matrix


REPO_COMMIT = "0f75c51edc37259f168ad10faf44d536dd9b75a5"
PRODUCTION_COMMIT = "83516de6cd3713415e78502ba58db072fa6b38f9"

EXPECTED = {
    "genomes": 55306,
    "species": 13765,
    "old_raw_sha256":
        "fd264bedda627d737a647de601c8b835f53baeca246724e9aafb73fd50c9d656",
    "species_mapping_sha256":
        "f0343238930e957f82bc28997a216ab3a8967d007b3d3471679e3f054c76af6c",
    "selection_summary_sha256":
        "beced81273c05bf039d6630ea2b173ce4485bdd4042546c781ee64aa2a785bcf",
    "production_manifest_sha256":
        "75fd427a28b712b1c76ebe93722d2c6baac1e3d1bccedf63a00de71bebea5b84",
    "full_universe_audit_summary_sha256":
        "40ce0b77936d69c039474256c904f16cb204ec4040f05c190619708547dc6dc1",
    "production_files": 55639,
}

METADATA = (
    "batch",
    "batch_index",
    "canonical_genbank_assembly_accession",
)

OLD_FEATURES = (
    "01_total_genome_length",
    "02_whole_genome_gc_fraction",
    "03_replicon_count",
    "04_non_chromosomal_replicon_count",
    "05_non_chromosomal_sequence_fraction",
    "06_non_unique_canonical_150mer_fraction",
    "07_non_unique_canonical_400mer_fraction",
    "08_maximum_canonical_150mer_multiplicity",
    "09_maximum_canonical_400mer_multiplicity",
    "10_longest_exact_repeat_length",
    "11_inter_replicon_shared_canonical_150mer_fraction",
    "12_inter_replicon_shared_canonical_400mer_fraction",
)

NEW_FEATURES = (
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

UNCHANGED_MAP = {
    "01_total_genome_length": "01_total_genome_length",
    "02_whole_genome_gc_fraction": "02_whole_genome_gc_fraction",
    "03_replicon_count": "03_replicon_count",
    "04_non_chromosomal_replicon_count":
        "04_non_chromosomal_replicon_count",
    "05_non_chromosomal_sequence_fraction":
        "05_non_chromosomal_sequence_fraction",
    "10_longest_exact_repeat_length": "10_longest_exact_repeat_length",
}

NEW_FROM_CANDIDATE = {
    "06_non_unique_canonical_300mer_fraction":
        ("300", "non_unique_fraction"),
    "07_non_unique_canonical_2400mer_fraction":
        ("2400", "non_unique_fraction"),
    "08_maximum_canonical_300mer_multiplicity":
        ("300", "maximum_multiplicity"),
    "09_maximum_canonical_2400mer_multiplicity":
        ("2400", "maximum_multiplicity"),
    "11_inter_replicon_shared_canonical_300mer_fraction":
        ("300", "inter_replicon_shared_fraction"),
    "12_inter_replicon_shared_canonical_2400mer_fraction":
        ("2400", "inter_replicon_shared_fraction"),
}

K_VALUES = (
    50, 75, 100, 150, 200, 300, 400,
    600, 800, 1200, 1600, 2400, 3200,
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def verify_file(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    observed = sha256_file(path)
    if observed != expected:
        fail(
            f"{label} SHA256 mismatch: expected {expected}, "
            f"observed {observed}"
        )


def array_sha256(array: np.ndarray) -> str:
    canonical = np.ascontiguousarray(array, dtype="<f8")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def format_float(value: float) -> str:
    return format(float(value), ".17g")


def load_production_manifest(
    root: Path,
    manifest: Path,
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    rows = 0

    with manifest.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.rstrip("\n")
            if not line:
                fail(
                    "empty production manifest row at "
                    f"line {line_number}"
                )
            try:
                expected_hash, relpath = line.split(None, 1)
            except ValueError as exc:
                raise RuntimeError(
                    f"invalid production manifest row {line_number}"
                ) from exc

            relpath = relpath.strip()
            if not relpath.startswith("./"):
                fail(
                    "non-canonical production manifest path at "
                    f"line {line_number}: {relpath!r}"
                )
            if relpath in hashes:
                fail(f"duplicate production manifest path: {relpath}")

            path = root / relpath[2:]
            if not path.is_file():
                fail(f"production file missing: {relpath}")

            observed = sha256_file(path)
            if observed != expected_hash:
                fail(
                    f"production file SHA256 mismatch: {relpath}: "
                    f"expected {expected_hash}, observed {observed}"
                )

            hashes[relpath] = expected_hash
            rows += 1

    if rows != EXPECTED["production_files"]:
        fail(
            "production file count mismatch: "
            f"expected {EXPECTED['production_files']}, observed {rows}"
        )

    return hashes


def validate_selection_summary(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if data.get("analysis") != "selector-v1-repeat-scale-selection":
        fail("selection summary analysis identity changed")
    if data.get("analysis_commit") != (
        "3c77cd33902bde25571aa4c04ab8d2e528bbec97"
    ):
        fail("selection summary analysis commit changed")
    if data.get("production_commit") != PRODUCTION_COMMIT:
        fail("selection summary production commit changed")
    if data.get("genomes") != EXPECTED["genomes"]:
        fail("selection summary genome count changed")
    if data.get("species") != EXPECTED["species"]:
        fail("selection summary species count changed")
    if tuple(data.get("k_values", ())) != K_VALUES:
        fail("selection summary k grid changed")

    pair = data.get("selected_pair")
    if not isinstance(pair, dict):
        fail("selection summary selected_pair is missing")
    if (pair.get("k_a"), pair.get("k_b")) != (300, 2400):
        fail(
            "frozen selected pair is not exactly (300, 2400)"
        )
    if data.get("selected_pair_differs_from_inherited") is not True:
        fail("selection summary does not record changed pair")

    return data


def validate_candidate(
    candidate: dict[str, Any],
    batch: str,
    batch_index: int,
    accession: str,
) -> None:
    if candidate.get("analysis") != "selector-v1-repeat-scale-grid":
        fail(f"{accession}: candidate analysis identity changed")
    if candidate.get("batch") != batch:
        fail(f"{accession}: candidate batch changed")
    if candidate.get("batch_index") != batch_index:
        fail(f"{accession}: candidate batch_index changed")
    if candidate.get(
        "canonical_genbank_assembly_accession"
    ) != accession:
        fail(f"{accession}: candidate accession changed")
    if tuple(candidate.get("k_values", ())) != K_VALUES:
        fail(f"{accession}: candidate k grid changed")

    anchor = candidate.get("reference_anchor")
    if not isinstance(anchor, dict):
        fail(f"{accession}: reference anchor missing")
    if anchor.get("passed") is not True:
        fail(f"{accession}: reference anchor no longer passes")
    if anchor.get("mismatches") != []:
        fail(f"{accession}: reference anchor contains mismatches")

    features = candidate.get("features_by_k")
    if not isinstance(features, dict):
        fail(f"{accession}: features_by_k missing")

    for k in ("300", "2400"):
        record = features.get(k)
        if not isinstance(record, dict):
            fail(f"{accession}: k={k} feature record missing")

        valid = record.get("valid_start_count")
        non_unique = record.get("non_unique_start_count")
        non_unique_fraction = record.get("non_unique_fraction")
        maximum = record.get("maximum_multiplicity")
        shared = record.get("inter_replicon_shared_start_count")
        shared_fraction = record.get(
            "inter_replicon_shared_fraction"
        )

        if not isinstance(valid, int) or isinstance(valid, bool) or valid <= 0:
            fail(f"{accession}: invalid valid_start_count at k={k}")
        for label, value in (
            ("non_unique_start_count", non_unique),
            ("inter_replicon_shared_start_count", shared),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                or value > valid
            ):
                fail(f"{accession}: invalid {label} at k={k}")

        if (
            not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or maximum < 1
        ):
            fail(
                f"{accession}: invalid maximum_multiplicity at k={k}"
            )

        for label, value in (
            ("non_unique_fraction", non_unique_fraction),
            ("inter_replicon_shared_fraction", shared_fraction),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.0 <= float(value) <= 1.0
            ):
                fail(f"{accession}: invalid {label} at k={k}")

        if not math.isclose(
            float(non_unique_fraction),
            non_unique / valid,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            fail(
                f"{accession}: non_unique_fraction/count mismatch "
                f"at k={k}"
            )
        if not math.isclose(
            float(shared_fraction),
            shared / valid,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            fail(
                f"{accession}: inter_replicon fraction/count mismatch "
                f"at k={k}"
            )


def main() -> int:
    home = Path.home()
    repo = home / "github" / "bacselect"

    old_raw = Path(
        "/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/"
        "corrected-eligible-percentile-feature-space/"
        "corrected-eligible-structural-feature-matrix.tsv"
    )
    species_mapping = Path(
        "/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/"
        "corrected-species-resolution/"
        "corrected-genome-species-taxid.tsv"
    )
    production_root = Path(
        "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/"
        "repeat-scale/alternative-k-grid/"
        f"{PRODUCTION_COMMIT}/production"
    )

    selection_summary = (
        repo
        / "validation/selector-v1/results/"
        "repeat-scale-selection-summary.json"
    )
    production_manifest = (
        repo
        / "validation/selector-v1/results/"
        "repeat-scale-full-universe-production-files.sha256"
    )
    full_audit_summary = (
        repo
        / "validation/selector-v1/results/"
        "repeat-scale-full-universe-audit-summary.json"
    )
    geometry_module = repo / "src/bacselect/geometry.py"

    output_dir = Path(
        "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/"
        "final-feature-space/"
        f"{REPO_COMMIT}"
    )

    print("===== repository and frozen inputs =====")
    if git(repo, "rev-parse", "HEAD") != REPO_COMMIT:
        fail("repository HEAD is not the expected selection-evidence commit")
    if git(repo, "rev-parse", "origin/main") != REPO_COMMIT:
        fail("origin/main is not the expected selection-evidence commit")
    if git(repo, "status", "--porcelain"):
        fail("BacSelect working tree is not clean")

    verify_file(
        old_raw,
        EXPECTED["old_raw_sha256"],
        "historical raw 150/400 matrix",
    )
    verify_file(
        species_mapping,
        EXPECTED["species_mapping_sha256"],
        "canonical species mapping",
    )
    verify_file(
        selection_summary,
        EXPECTED["selection_summary_sha256"],
        "frozen repeat-scale selection summary",
    )
    verify_file(
        production_manifest,
        EXPECTED["production_manifest_sha256"],
        "frozen production-file manifest",
    )
    verify_file(
        full_audit_summary,
        EXPECTED["full_universe_audit_summary_sha256"],
        "frozen full-universe audit summary",
    )

    selection = validate_selection_summary(selection_summary)

    audit = json.loads(full_audit_summary.read_text(encoding="utf-8"))
    if audit.get("all_pass") is not True:
        fail("full-universe repeat-scale audit is not all_pass")
    if audit.get("candidate_jsons_checked") != EXPECTED["genomes"]:
        fail("full-universe audit candidate count changed")
    if audit.get("error_count") != 0 or audit.get("warning_count") != 0:
        fail("full-universe audit is not clean")

    if output_dir.exists():
        fail(
            "output directory already exists; refusing to overwrite: "
            f"{output_dir}"
        )

    print("PASS | repository and frozen identities")

    print("===== exact production verification =====")
    production_hashes = load_production_manifest(
        production_root,
        production_manifest,
    )
    print(
        f"PASS | {len(production_hashes)} / "
        f"{EXPECTED['production_files']} production files"
    )

    print("===== load historical foundation and species mapping =====")
    with old_raw.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        old_header = tuple(reader.fieldnames or ())
        old_rows = list(reader)

    expected_old_header = (*METADATA, *OLD_FEATURES)
    if old_header != expected_old_header:
        fail("historical raw matrix schema changed")
    if len(old_rows) != EXPECTED["genomes"]:
        fail("historical raw matrix row count changed")

    with species_mapping.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        species_rows = list(csv.DictReader(handle, delimiter="\t"))

    if len(species_rows) != EXPECTED["genomes"]:
        fail("species mapping row count changed")

    for index, (raw_row, species_row) in enumerate(
        zip(old_rows, species_rows),
        start=1,
    ):
        raw_key = (
            raw_row["batch"],
            raw_row["batch_index"],
            raw_row["canonical_genbank_assembly_accession"],
        )
        species_key = (
            species_row["batch"],
            species_row["batch_index"],
            species_row["canonical_genbank_assembly_accession"],
        )
        if raw_key != species_key:
            fail(
                "historical raw/species order mismatch at data row "
                f"{index}"
            )

    species_ids = [row["species_taxid"] for row in species_rows]
    if len(set(species_ids)) != EXPECTED["species"]:
        fail("species group count changed")

    print(
        f"PASS | genomes={len(old_rows)} | "
        f"species={len(set(species_ids))}"
    )

    output_dir.mkdir(parents=True)

    raw_path = output_dir / (
        "structural-feature-matrix-300-2400.tsv"
    )
    percentile_path = output_dir / (
        "species-balanced-percentile-feature-matrix-300-2400.tsv"
    )
    row_audit_path = output_dir / (
        "feature-space-row-audit.tsv"
    )

    new_numeric = np.empty(
        (EXPECTED["genomes"], len(NEW_FEATURES)),
        dtype=np.float64,
    )

    print("===== build revised 12-feature raw matrix =====")
    with raw_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as raw_handle, row_audit_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as audit_handle:
        raw_writer = csv.DictWriter(
            raw_handle,
            fieldnames=(*METADATA, *NEW_FEATURES),
            delimiter="\t",
            lineterminator="\n",
        )
        raw_writer.writeheader()

        audit_writer = csv.DictWriter(
            audit_handle,
            fieldnames=(
                *METADATA,
                "candidate_json_sha256",
                "reference_anchor_passed",
            ),
            delimiter="\t",
            lineterminator="\n",
        )
        audit_writer.writeheader()

        for row_index, old_row in enumerate(old_rows):
            batch = old_row["batch"]
            batch_index = int(old_row["batch_index"])
            accession = old_row[
                "canonical_genbank_assembly_accession"
            ]

            relpath = (
                f"./{batch}/candidates/"
                f"{accession}.repeat-scale.json"
            )
            candidate_hash = production_hashes.get(relpath)
            if candidate_hash is None:
                fail(
                    f"{accession}: candidate JSON absent from frozen "
                    "production manifest"
                )

            candidate_path = production_root / relpath[2:]
            with candidate_path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                candidate = json.load(handle)

            validate_candidate(
                candidate,
                batch,
                batch_index,
                accession,
            )

            features = candidate["features_by_k"]

            out_row: dict[str, str] = {
                "batch": old_row["batch"],
                "batch_index": old_row["batch_index"],
                "canonical_genbank_assembly_accession":
                    accession,
            }

            for new_name in NEW_FEATURES:
                if new_name in UNCHANGED_MAP:
                    value_text = old_row[UNCHANGED_MAP[new_name]]
                    out_row[new_name] = value_text
                else:
                    k, family = NEW_FROM_CANDIDATE[new_name]
                    value = features[k][family]
                    if "multiplicity" in new_name:
                        if (
                            not isinstance(value, int)
                            or isinstance(value, bool)
                        ):
                            fail(
                                f"{accession}: {new_name} is not integer"
                            )
                        value_text = str(value)
                    else:
                        value_text = format_float(float(value))
                    out_row[new_name] = value_text

                try:
                    numeric = float(out_row[new_name])
                except ValueError as exc:
                    raise RuntimeError(
                        f"{accession}: non-numeric output {new_name}"
                    ) from exc

                if not math.isfinite(numeric):
                    fail(
                        f"{accession}: non-finite output {new_name}"
                    )

                new_numeric[row_index, NEW_FEATURES.index(new_name)] = (
                    numeric
                )

            raw_writer.writerow(out_row)
            audit_writer.writerow(
                {
                    "batch": batch,
                    "batch_index": batch_index,
                    "canonical_genbank_assembly_accession":
                        accession,
                    "candidate_json_sha256": candidate_hash,
                    "reference_anchor_passed": "true",
                }
            )

    if new_numeric.shape != (EXPECTED["genomes"], 12):
        fail("revised raw numeric matrix has unexpected shape")
    if not np.isfinite(new_numeric).all():
        fail("revised raw numeric matrix contains non-finite values")

    # Confirm the six unchanged dimensions are bit-identical as float64.
    old_numeric = np.asarray(
        [
            [float(row[name]) for name in OLD_FEATURES]
            for row in old_rows
        ],
        dtype=np.float64,
    )

    unchanged_pairs = (
        (0, 0),
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 4),
        (9, 9),
    )
    for old_col, new_col in unchanged_pairs:
        if not np.array_equal(
            old_numeric[:, old_col],
            new_numeric[:, new_col],
        ):
            fail(
                "unchanged dimension changed: "
                f"{OLD_FEATURES[old_col]}"
            )

    # Preserve existing geometry invariant: float64 must not collapse
    # distinct decimal raw values in any dimension.
    for column, feature_name in enumerate(NEW_FEATURES):
        with raw_path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            decimal_unique = sorted(
                {Decimal(row[feature_name]) for row in reader}
            )

        float_unique = np.unique(new_numeric[:, column])
        if len(decimal_unique) != float_unique.size:
            fail(
                "float64 collapsed distinct raw values for "
                f"{feature_name}"
            )
        converted = np.asarray(
            [float(value) for value in decimal_unique],
            dtype=np.float64,
        )
        if converted.size > 1 and not np.all(
            converted[:-1] < converted[1:]
        ):
            fail(
                "float64 changed raw ordering for "
                f"{feature_name}"
            )

    raw_array_hash = array_sha256(new_numeric)
    print(
        "PASS | six unchanged dimensions preserved | "
        "six 300/2400 dimensions replaced"
    )

    print("===== committed species-balanced percentile transform =====")
    coordinates = species_balanced_percentile_matrix(
        new_numeric,
        species_ids,
    )
    if coordinates.shape != new_numeric.shape:
        fail("coordinate matrix shape changed")
    if not np.isfinite(coordinates).all():
        fail("coordinate matrix contains non-finite values")
    if not np.all((coordinates >= 0.0) & (coordinates <= 1.0)):
        fail("coordinate matrix contains values outside [0,1]")

    for column, feature_name in enumerate(NEW_FEATURES):
        raw_unique = np.unique(new_numeric[:, column]).size
        coord_unique = np.unique(coordinates[:, column]).size
        if raw_unique != coord_unique:
            fail(
                "percentile transform changed unique-value count for "
                f"{feature_name}"
            )

    coordinate_hash = array_sha256(coordinates)

    # Deterministic permutation invariance using the same operation as
    # existing geometry validation, with a new fixed seed for the final schema.
    permutation_seed = 20260825
    rng = np.random.default_rng(permutation_seed)
    permutation = rng.permutation(EXPECTED["genomes"])
    permuted = species_balanced_percentile_matrix(
        new_numeric[permutation],
        [species_ids[index] for index in permutation],
    )
    restored = np.empty_like(permuted)
    restored[permutation] = permuted
    if not np.array_equal(restored, coordinates):
        fail("species-balanced percentile transform is not order invariant")
    if array_sha256(restored) != coordinate_hash:
        fail("restored percentile array hash changed")

    with percentile_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writerow((*METADATA, *NEW_FEATURES))
        for row_index, old_row in enumerate(old_rows):
            writer.writerow(
                (
                    old_row["batch"],
                    old_row["batch_index"],
                    old_row[
                        "canonical_genbank_assembly_accession"
                    ],
                    *(
                        format_float(value)
                        for value in coordinates[row_index]
                    ),
                )
            )

    # Round-trip both written matrices back to float64 and require exact arrays.
    with raw_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        raw_roundtrip = np.asarray(
            [
                [float(row[name]) for name in NEW_FEATURES]
                for row in reader
            ],
            dtype=np.float64,
        )
    if not np.array_equal(raw_roundtrip, new_numeric):
        fail("written raw matrix does not round-trip exactly")

    with percentile_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        coordinate_roundtrip = np.asarray(
            [
                [float(row[name]) for name in NEW_FEATURES]
                for row in reader
            ],
            dtype=np.float64,
        )
    if not np.array_equal(coordinate_roundtrip, coordinates):
        fail("written percentile matrix does not round-trip exactly")

    print(
        "PASS | species-balanced percentile matrix | "
        f"permutation_seed={permutation_seed}"
    )

    summary_path = output_dir / "feature-space-summary.json"
    hashes_path = output_dir / "feature-space-sha256.txt"

    summary = {
        "analysis": "selector-v1-final-feature-space-300-2400",
        "schema_version": 1,
        "repository_commit": REPO_COMMIT,
        "production_commit": PRODUCTION_COMMIT,
        "selected_repeat_scales": [300, 2400],
        "genomes": EXPECTED["genomes"],
        "species": EXPECTED["species"],
        "features": list(NEW_FEATURES),
        "unchanged_features": list(UNCHANGED_MAP),
        "replaced_features": list(NEW_FROM_CANDIDATE),
        "input_sha256": {
            "historical_raw_150_400": EXPECTED["old_raw_sha256"],
            "species_mapping": EXPECTED["species_mapping_sha256"],
            "repeat_scale_selection_summary":
                EXPECTED["selection_summary_sha256"],
            "repeat_scale_production_manifest":
                EXPECTED["production_manifest_sha256"],
            "repeat_scale_full_universe_audit_summary":
                EXPECTED["full_universe_audit_summary_sha256"],
            "geometry_module": sha256_file(geometry_module),
        },
        "array_sha256": {
            "raw_float64_c_order": raw_array_hash,
            "species_balanced_percentile_float64_c_order":
                coordinate_hash,
        },
        "permutation_seed": permutation_seed,
        "outputs": {
            "raw_matrix_sha256": sha256_file(raw_path),
            "percentile_matrix_sha256": sha256_file(percentile_path),
            "row_audit_sha256": sha256_file(row_audit_path),
        },
    }

    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with hashes_path.open("w", encoding="utf-8") as handle:
        for path in (
            raw_path,
            percentile_path,
            row_audit_path,
            summary_path,
        ):
            handle.write(
                f"{sha256_file(path)}  {path.name}\n"
            )

    print("===== final feature-space identities =====")
    print(f"raw_matrix\t{raw_path}")
    print(f"raw_matrix_sha256\t{sha256_file(raw_path)}")
    print(
        "raw_array_sha256\t"
        f"{raw_array_hash}"
    )
    print(f"percentile_matrix\t{percentile_path}")
    print(
        "percentile_matrix_sha256\t"
        f"{sha256_file(percentile_path)}"
    )
    print(
        "percentile_array_sha256\t"
        f"{coordinate_hash}"
    )
    print(f"row_audit_sha256\t{sha256_file(row_audit_path)}")
    print(f"summary_sha256\t{sha256_file(summary_path)}")
    print(f"output_dir\t{output_dir}")
    print()
    print("PASS | final 300/2400 feature-space rebuild complete")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL | {exc}", file=sys.stderr)
        raise
