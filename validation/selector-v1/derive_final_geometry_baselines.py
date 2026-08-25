#!/usr/bin/env python3
"""Prospectively derive final 300/2400 geometry baseline identities.

This is the first geometry-dependent analysis after the final selector-v1
300/2400 feature space was frozen. It intentionally does not assert or reuse
historical 150/400 OPS, SR, AG, correlation, or coverage results.

It derives:
- the final feature-correlation matrix;
- blinded OPS representative and N=500 ladder fingerprints;
- blinded SR and AG N=500 ladder fingerprints;
- species-abundance diagnostics at each frozen panel size;
- the unchanged species-balanced random ladder-set fingerprint;
- input-order invariance for OPS, SR, AG, and random ladders.

No OPS-versus-SR coverage decision is made here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

import numpy as np
import scipy

from bacselect.ag import ag_ladder
from bacselect.correlation import (
    spearman_correlation_matrix,
)
from bacselect.ops import (
    ops_ladder,
    ops_species_representatives,
)
from bacselect.random_baseline import (
    DEFAULT_MAX_N,
    DEFAULT_REPLICATES,
    DEFAULT_SEED,
    random_ladders,
)
from bacselect.sr import sr_ladder

from final_geometry_common import (
    EXPECTED_GENOMES,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_PERCENTILE_ARRAY_SHA256,
    EXPECTED_PERCENTILE_FILE_SHA256,
    EXPECTED_RAW_ARRAY_SHA256,
    EXPECTED_RAW_FILE_SHA256,
    EXPECTED_SPECIES,
    EXPECTED_SPECIES_FILE_SHA256,
    FEATURES,
    file_sha256,
    load_final_foundation,
)


PANEL_SIZES = (
    10,
    20,
    50,
    100,
    200,
    500,
)

MAX_N = max(PANEL_SIZES)
PERMUTATION_SEED = 20260824

EXPECTED_RANDOM_LADDER_SET_SHA256 = (
    "9394a26ded92fb2baafea0101b837335"
    "e9d434f4cd3d8c6484ef61bbf0741719"
)

EXPECTED_ENV_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207eae"
    "f5c2435e1b6feeddc1e4654686bc2a8c"
)

ENV_LOCK = Path(
    "envs/bacselect-dev-linux-64.lock"
)

SOURCE_FILES = (
    Path("src/bacselect/geometry.py"),
    Path("src/bacselect/ops.py"),
    Path("src/bacselect/sr.py"),
    Path("src/bacselect/ag.py"),
    Path("src/bacselect/correlation.py"),
    Path("src/bacselect/random_baseline.py"),
    Path("src/bacselect/tie.py"),
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )

    return parser.parse_args()


def git_stdout(
    repo: Path,
    *args: str,
) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return completed.stdout.strip()


def verify_repository(
    repo: Path,
) -> str:
    expected = os.environ.get(
        "BACSELECT_EXPECTED_COMMIT",
        "",
    )

    if not COMMIT_RE.fullmatch(expected):
        raise AssertionError(
            "BACSELECT_EXPECTED_COMMIT must be the "
            "full 40-character analysis commit"
        )

    head = git_stdout(
        repo,
        "rev-parse",
        "HEAD",
    )
    origin = git_stdout(
        repo,
        "rev-parse",
        "origin/main",
    )
    status = git_stdout(
        repo,
        "status",
        "--porcelain",
    )

    if head != expected:
        raise AssertionError(
            "HEAD does not match "
            "BACSELECT_EXPECTED_COMMIT"
        )

    if origin != expected:
        raise AssertionError(
            "origin/main does not match "
            "BACSELECT_EXPECTED_COMMIT"
        )

    if status:
        raise AssertionError(
            "BacSelect working tree is not clean"
        )

    return expected


def sequence_sha256(
    namespace: str,
    values: Iterable[str],
) -> str:
    payload = (
        namespace
        + "\n"
        + "\n".join(values)
        + "\n"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def ladder_accessions(
    ladder: np.ndarray,
    accessions: list[str],
) -> list[str]:
    return [
        accessions[int(index)]
        for index in ladder
    ]


def random_ladder_matrix_sha256(
    ladders: np.ndarray,
    accessions: list[str],
) -> str:
    digest = hashlib.sha256()
    digest.update(
        b"BacSelect-selector-v1|random|1000x500\n"
    )

    for ladder in ladders:
        for index in ladder:
            digest.update(
                accessions[int(index)].encode(
                    "utf-8"
                )
            )
            digest.update(b"\n")

        digest.update(
            b"--replicate--\n"
        )

    return digest.hexdigest()


def multiplicity_summary(
    selected_species: list[str],
) -> str:
    per_species = Counter(
        selected_species
    )
    multiplicities = Counter(
        per_species.values()
    )

    return ",".join(
        (
            f"{multiplicity}x:"
            f"{multiplicities[multiplicity]}"
        )
        for multiplicity
        in sorted(multiplicities)
    )


def diagnostic_row(
    selector: str,
    panel_size: int,
    ladder: np.ndarray,
    species_ids: list[str],
) -> dict[str, object]:
    prefix = ladder[:panel_size]

    if prefix.size != panel_size:
        raise AssertionError(
            f"{selector} N={panel_size}: "
            "prefix length changed"
        )

    if np.unique(prefix).size != panel_size:
        raise AssertionError(
            f"{selector} N={panel_size}: "
            "duplicate genome selected"
        )

    selected_species = [
        species_ids[int(index)]
        for index in prefix
    ]

    counts = Counter(
        selected_species
    )

    return {
        "selector": selector,
        "N": panel_size,
        "distinct_species": len(counts),
        "max_per_species": max(
            counts.values()
        ),
        "multiplicity": (
            multiplicity_summary(
                selected_species
            )
        ),
    }


def random_accession_matrix_equal(
    left: np.ndarray,
    left_accessions: list[str],
    right: np.ndarray,
    right_accessions: list[str],
) -> bool:
    if left.shape != right.shape:
        return False

    for row_index in range(
        left.shape[0]
    ):
        for column_index in range(
            left.shape[1]
        ):
            if (
                left_accessions[
                    int(
                        left[
                            row_index,
                            column_index,
                        ]
                    )
                ]
                != right_accessions[
                    int(
                        right[
                            row_index,
                            column_index,
                        ]
                    )
                ]
            ):
                return False

    return True


def format_float(
    value: float,
) -> str:
    return format(
        float(value),
        ".17g",
    )


def main() -> int:
    args = parse_args()

    repo = Path.cwd().resolve()

    print(
        "===== repository and final foundation ====="
    )

    analysis_commit = verify_repository(
        repo
    )

    if (
        file_sha256(ENV_LOCK)
        != EXPECTED_ENV_LOCK_SHA256
    ):
        raise AssertionError(
            "bacselect-dev environment lock SHA256 changed"
        )

    foundation = load_final_foundation(
        recompute_coordinates=True,
    )

    print(
        "PASS | final 300/2400 foundation | "
        f"{EXPECTED_GENOMES} genomes | "
        f"{EXPECTED_SPECIES} species | "
        f"{len(FEATURES)} features"
    )
    print(
        "PASS | recalculated species-balanced "
        "percentile matrix matches frozen matrix"
    )

    output_dir = (
        args.output_dir
        .expanduser()
        .resolve()
    )

    if output_dir.exists():
        raise AssertionError(
            "output directory already exists; "
            f"refusing to overwrite: {output_dir}"
        )

    output_dir.mkdir(
        parents=True
    )

    print(
        "===== final feature correlation ====="
    )
    correlation_start = (
        time.perf_counter()
    )

    correlation = (
        spearman_correlation_matrix(
            foundation.raw
        )
    )

    correlation_elapsed = (
        time.perf_counter()
        - correlation_start
    )

    expected_correlation_shape = (
        len(FEATURES),
        len(FEATURES),
    )

    if (
        correlation.shape
        != expected_correlation_shape
    ):
        raise AssertionError(
            "feature-correlation matrix "
            "shape changed"
        )

    if not np.all(
        np.isfinite(correlation)
    ):
        raise AssertionError(
            "feature-correlation matrix "
            "contains non-finite values"
        )

    if not np.array_equal(
        correlation,
        correlation.T,
    ):
        raise AssertionError(
            "feature-correlation matrix "
            "is not exactly symmetric"
        )

    if not np.array_equal(
        np.diag(correlation),
        np.ones(
            len(FEATURES),
            dtype=np.float64,
        ),
    ):
        raise AssertionError(
            "feature-correlation diagonal "
            "is not exactly one"
        )

    if np.any(
        np.abs(correlation) > 1.0
    ):
        raise AssertionError(
            "feature correlation outside [-1,1]"
        )

    correlation_path = (
        output_dir
        / "final300-2400-feature-correlation.tsv"
    )

    with correlation_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle,
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writerow(
            ["feature", *FEATURES]
        )

        for row_index, feature in enumerate(
            FEATURES
        ):
            writer.writerow(
                [
                    feature,
                    *(
                        format_float(value)
                        for value
                        in correlation[row_index]
                    ),
                ]
            )

    print(
        "PASS | finite symmetric unit-diagonal "
        "Spearman matrix"
    )

    print(
        "===== final selector baseline ladders ====="
    )

    ops_representative_start = (
        time.perf_counter()
    )
    ops_representatives = (
        ops_species_representatives(
            foundation.coordinates,
            foundation.species_ids,
            foundation.accessions,
        )
    )
    ops_representative_elapsed = (
        time.perf_counter()
        - ops_representative_start
    )

    if (
        ops_representatives.size
        != EXPECTED_SPECIES
    ):
        raise AssertionError(
            "OPS representative count changed"
        )

    if (
        np.unique(
            ops_representatives
        ).size
        != EXPECTED_SPECIES
    ):
        raise AssertionError(
            "OPS representatives contain duplicates"
        )

    representative_species = {
        foundation.species_ids[
            int(index)
        ]
        for index
        in ops_representatives
    }

    if (
        len(representative_species)
        != EXPECTED_SPECIES
    ):
        raise AssertionError(
            "OPS does not contain exactly "
            "one representative per species"
        )

    representative_hash = (
        sequence_sha256(
            (
                "BacSelect-selector-v1|"
                "OPS|representatives"
            ),
            ladder_accessions(
                ops_representatives,
                foundation.accessions,
            ),
        )
    )

    ops_start = time.perf_counter()
    ops = ops_ladder(
        foundation.coordinates,
        foundation.species_ids,
        foundation.accessions,
        max_n=MAX_N,
    )
    ops_elapsed = (
        time.perf_counter()
        - ops_start
    )

    sr_start = time.perf_counter()
    sr = sr_ladder(
        foundation.coordinates,
        foundation.species_ids,
        foundation.accessions,
        max_n=MAX_N,
    )
    sr_elapsed = (
        time.perf_counter()
        - sr_start
    )

    ag_start = time.perf_counter()
    ag = ag_ladder(
        foundation.coordinates,
        foundation.accessions,
        max_n=MAX_N,
    )
    ag_elapsed = (
        time.perf_counter()
        - ag_start
    )

    for name, ladder in (
        ("OPS", ops),
        ("SR", sr),
        ("AG", ag),
    ):
        if ladder.shape != (MAX_N,):
            raise AssertionError(
                f"{name} ladder shape changed: "
                f"{ladder.shape}"
            )

        if (
            np.unique(ladder).size
            != MAX_N
        ):
            raise AssertionError(
                f"{name} ladder contains duplicates"
            )

    ops_hash = sequence_sha256(
        (
            "BacSelect-selector-v1|"
            "OPS|ladder|N=500"
        ),
        ladder_accessions(
            ops,
            foundation.accessions,
        ),
    )

    sr_hash = sequence_sha256(
        (
            "BacSelect-selector-v1|"
            "SR|ladder|N=500"
        ),
        ladder_accessions(
            sr,
            foundation.accessions,
        ),
    )

    ag_hash = sequence_sha256(
        (
            "BacSelect-selector-v1|"
            "AG|ladder|N=500"
        ),
        ladder_accessions(
            ag,
            foundation.accessions,
        ),
    )

    diagnostics = []

    for selector, ladder in (
        ("OPS", ops),
        ("SR", sr),
        ("AG", ag),
    ):
        for panel_size in PANEL_SIZES:
            row = diagnostic_row(
                selector,
                panel_size,
                ladder,
                foundation.species_ids,
            )

            if (
                selector == "OPS"
                and (
                    row["distinct_species"]
                    != panel_size
                    or row["max_per_species"]
                    != 1
                )
            ):
                raise AssertionError(
                    "OPS one-per-species invariant "
                    f"failed at N={panel_size}"
                )

            diagnostics.append(row)

    diagnostics_path = (
        output_dir
        / "final300-2400-species-abundance-diagnostic.tsv"
    )

    with diagnostics_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "selector",
                "N",
                "distinct_species",
                "max_per_species",
                "multiplicity",
            ),
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(
            diagnostics
        )

    print(
        "PASS | OPS, SR, and AG "
        "N=500 ladders derived"
    )
    print(
        "PASS | species-abundance "
        "diagnostics derived at all frozen N"
    )

    print(
        "===== unchanged random ladder identity ====="
    )

    if DEFAULT_REPLICATES != 1000:
        raise AssertionError(
            "random replicate count changed"
        )
    if DEFAULT_MAX_N != 500:
        raise AssertionError(
            "random max_n changed"
        )
    if DEFAULT_SEED != 20260824:
        raise AssertionError(
            "random master seed changed"
        )

    random_start = time.perf_counter()
    random_set = random_ladders(
        foundation.species_ids,
        foundation.accessions,
        max_n=DEFAULT_MAX_N,
        replicates=DEFAULT_REPLICATES,
        seed=DEFAULT_SEED,
    )
    random_elapsed = (
        time.perf_counter()
        - random_start
    )

    if random_set.shape != (
        DEFAULT_REPLICATES,
        DEFAULT_MAX_N,
    ):
        raise AssertionError(
            "random ladder-set shape changed"
        )

    random_hash = (
        random_ladder_matrix_sha256(
            random_set,
            foundation.accessions,
        )
    )

    if (
        random_hash
        != EXPECTED_RANDOM_LADDER_SET_SHA256
    ):
        raise AssertionError(
            "random ladder-set fingerprint changed "
            "despite unchanged universe/species mapping"
        )

    print(
        "PASS | random ladder-set fingerprint "
        f"unchanged | {random_hash}"
    )

    print(
        "===== input-order invariance ====="
    )

    rng = np.random.default_rng(
        PERMUTATION_SEED
    )
    permutation = rng.permutation(
        EXPECTED_GENOMES
    )

    permuted_coordinates = (
        foundation.coordinates[
            permutation
        ]
    )

    permuted_species = [
        foundation.species_ids[
            int(index)
        ]
        for index in permutation
    ]

    permuted_accessions = [
        foundation.accessions[
            int(index)
        ]
        for index in permutation
    ]

    permuted_ops = ops_ladder(
        permuted_coordinates,
        permuted_species,
        permuted_accessions,
        max_n=MAX_N,
    )

    permuted_sr = sr_ladder(
        permuted_coordinates,
        permuted_species,
        permuted_accessions,
        max_n=MAX_N,
    )

    permuted_ag = ag_ladder(
        permuted_coordinates,
        permuted_accessions,
        max_n=MAX_N,
    )

    if (
        ladder_accessions(
            permuted_ops,
            permuted_accessions,
        )
        != ladder_accessions(
            ops,
            foundation.accessions,
        )
    ):
        raise AssertionError(
            "OPS ladder is not input-order invariant"
        )

    if (
        ladder_accessions(
            permuted_sr,
            permuted_accessions,
        )
        != ladder_accessions(
            sr,
            foundation.accessions,
        )
    ):
        raise AssertionError(
            "SR ladder is not input-order invariant"
        )

    if (
        ladder_accessions(
            permuted_ag,
            permuted_accessions,
        )
        != ladder_accessions(
            ag,
            foundation.accessions,
        )
    ):
        raise AssertionError(
            "AG ladder is not input-order invariant"
        )

    permuted_random = random_ladders(
        permuted_species,
        permuted_accessions,
        max_n=DEFAULT_MAX_N,
        replicates=DEFAULT_REPLICATES,
        seed=DEFAULT_SEED,
    )

    if not random_accession_matrix_equal(
        random_set,
        foundation.accessions,
        permuted_random,
        permuted_accessions,
    ):
        raise AssertionError(
            "random ladder set is not "
            "input-order invariant"
        )

    permuted_random_hash = (
        random_ladder_matrix_sha256(
            permuted_random,
            permuted_accessions,
        )
    )

    if permuted_random_hash != random_hash:
        raise AssertionError(
            "permuted random ladder-set "
            "fingerprint changed"
        )

    print(
        "PASS | OPS, SR, AG, and random "
        "input-order invariance"
    )

    module_hashes = {
        str(path): file_sha256(path)
        for path in SOURCE_FILES
    }

    summary = {
        "analysis": (
            "selector-v1-final-300-2400-"
            "geometry-baselines"
        ),
        "schema_version": 1,
        "analysis_commit": analysis_commit,
        "genomes": EXPECTED_GENOMES,
        "species": EXPECTED_SPECIES,
        "features": list(FEATURES),
        "panel_sizes": list(PANEL_SIZES),
        "max_n": MAX_N,
        "permutation_seed":
            PERMUTATION_SEED,
        "input_sha256": {
            "final_feature_space_manifest":
                EXPECTED_MANIFEST_SHA256,
            "final_raw_matrix":
                EXPECTED_RAW_FILE_SHA256,
            "final_percentile_matrix":
                EXPECTED_PERCENTILE_FILE_SHA256,
            "species_mapping":
                EXPECTED_SPECIES_FILE_SHA256,
            "environment_lock":
                EXPECTED_ENV_LOCK_SHA256,
        },
        "array_sha256": {
            "raw_float64_c_order":
                EXPECTED_RAW_ARRAY_SHA256,
            "percentile_float64_c_order":
                EXPECTED_PERCENTILE_ARRAY_SHA256,
        },
        "module_sha256":
            module_hashes,
        "ops": {
            "representative_count":
                int(
                    ops_representatives.size
                ),
            "representative_sha256":
                representative_hash,
            "ladder_sha256":
                ops_hash,
        },
        "sr": {
            "ladder_sha256":
                sr_hash,
        },
        "ag": {
            "ladder_sha256":
                ag_hash,
        },
        "random": {
            "replicates":
                DEFAULT_REPLICATES,
            "max_n":
                DEFAULT_MAX_N,
            "seed":
                DEFAULT_SEED,
            "ladder_set_sha256":
                random_hash,
            "matches_frozen_membership_baseline":
                True,
        },
        "runtimes_seconds": {
            "feature_correlation":
                correlation_elapsed,
            "ops_representatives":
                ops_representative_elapsed,
            "ops_ladder":
                ops_elapsed,
            "sr_ladder":
                sr_elapsed,
            "ag_ladder":
                ag_elapsed,
            "random_ladders":
                random_elapsed,
        },
        "software": {
            "python":
                platform.python_version(),
            "numpy":
                np.__version__,
            "scipy":
                scipy.__version__,
        },
        "outputs": {
            "feature_correlation_sha256":
                file_sha256(
                    correlation_path
                ),
            "species_abundance_diagnostic_sha256":
                file_sha256(
                    diagnostics_path
                ),
        },
        "coverage_decision_evaluated":
            False,
    }

    summary_path = (
        output_dir
        / "final300-2400-geometry-baselines-summary.json"
    )

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    hashes_path = (
        output_dir
        / "final300-2400-geometry-baselines-sha256.txt"
    )

    with hashes_path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        for path in (
            correlation_path,
            diagnostics_path,
            summary_path,
        ):
            handle.write(
                f"{file_sha256(path)}  "
                f"{path.name}\n"
            )

    print()
    print(
        "===== prospective baseline identities ====="
    )
    print(
        "ops_representative_sha256\t"
        f"{representative_hash}"
    )
    print(
        "ops_ladder_sha256\t"
        f"{ops_hash}"
    )
    print(
        "sr_ladder_sha256\t"
        f"{sr_hash}"
    )
    print(
        "ag_ladder_sha256\t"
        f"{ag_hash}"
    )
    print(
        "random_ladder_set_sha256\t"
        f"{random_hash}"
    )
    print(
        "feature_correlation_sha256\t"
        f"{file_sha256(correlation_path)}"
    )
    print(
        "species_abundance_diagnostic_sha256\t"
        f"{file_sha256(diagnostics_path)}"
    )
    print(
        "summary_sha256\t"
        f"{file_sha256(summary_path)}"
    )
    print(
        "output_dir\t"
        f"{output_dir}"
    )
    print()
    print(
        "PASS | final 300/2400 geometry "
        "baseline derivation complete"
    )
    print(
        "INFO | OPS-versus-SR coverage "
        "decision was not evaluated"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except Exception as exc:
        print(
            f"FAIL | {exc}",
            file=sys.stderr,
        )
        raise
