#!/usr/bin/env python3
"""Calculate identity-blind random-baseline coverage distributions."""

from __future__ import annotations

import argparse
import hashlib
import runpy
import subprocess
import sys
import time
from dataclasses import fields
from fractions import Fraction
from pathlib import Path

import numpy as np

from bacselect.metrics import CoverageSummary, inverse_ecdf_quantile
from bacselect.random_baseline import (
    DEFAULT_MAX_N,
    DEFAULT_REPLICATES,
    DEFAULT_SEED,
    random_ladders,
)


EXPECTED_GENOMES = 55306
EXPECTED_SPECIES = 13765
EXPECTED_FEATURES = 12

EXPECTED_LADDER_SET_SHA256 = (
    "9394a26ded92fb2baafea0101b837335"
    "e9d434f4cd3d8c6484ef61bbf0741719"
)

EXPECTED_FIRST5_METRIC_SHA256 = (
    "9b6667407f676af1e6554c1ed81c902"
    "a4861acb500184e7605bb9799c10302dd"
)

EXPECTED_ENV_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207eae"
    "f5c2435e1b6feeddc1e4654686bc2a8c"
)

P025 = Fraction(1, 40)
MEDIAN = Fraction(1, 2)
P975 = Fraction(39, 40)


def sha256_text(text: str) -> str:
    """Return SHA256 for deterministic UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    """Return the streaming SHA256 of one file."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def git_stdout(repo_root: Path, *args: str) -> str:
    """Return stripped stdout from one Git command."""
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    return completed.stdout.strip()


def ladder_matrix_sha256(
    ladders: np.ndarray,
    accessions: list[str],
) -> str:
    """Return the frozen identity-blind ladder-set fingerprint."""
    digest = hashlib.sha256()
    digest.update(
        b"BacSelect-selector-v1|random|1000x500\n"
    )

    for ladder in ladders:
        for index in ladder:
            digest.update(
                accessions[int(index)].encode("utf-8")
            )
            digest.update(b"\n")

        digest.update(b"--replicate--\n")

    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--replicates",
        type=int,
        default=DEFAULT_REPLICATES,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )

    return parser.parse_args()


def output_paths(
    output_dir: Path,
    replicates: int,
) -> tuple[Path, Path, Path]:
    if replicates == DEFAULT_REPLICATES:
        suffix = ""
    else:
        suffix = f"-r{replicates}"

    return (
        output_dir / f"random-coverage-replicates{suffix}.tsv",
        output_dir / f"random-coverage-summary{suffix}.tsv",
        output_dir / f"random-coverage-provenance{suffix}.tsv",
    )


def main() -> None:
    args = parse_args()

    if args.replicates < 1:
        raise ValueError("--replicates must be at least 1")

    if args.replicates > DEFAULT_REPLICATES:
        raise ValueError(
            f"--replicates must not exceed {DEFAULT_REPLICATES}"
        )

    replicate_path, summary_path, provenance_path = output_paths(
        args.output_dir,
        args.replicates,
    )

    for path in (
        replicate_path,
        summary_path,
        provenance_path,
    ):
        if path.exists():
            raise FileExistsError(
                f"refusing to overwrite existing output: {path}"
            )

    validation_dir = Path(__file__).resolve().parent

    comparison = runpy.run_path(
        validation_dir / "compare_ops_sr.py"
    )

    load_foundation = comparison["load_foundation"]
    evaluate_ladder = comparison["evaluate_ladder"]
    format_metric = comparison["format_metric"]
    panel_sizes = tuple(comparison["PANEL_SIZES"])

    assert panel_sizes == (10, 20, 50, 100, 200, 500)
    assert DEFAULT_MAX_N == 500
    assert DEFAULT_REPLICATES == 1000
    assert DEFAULT_SEED == 20260824

    metric_names = [
        field.name
        for field in fields(CoverageSummary)
    ]

    repo_root = Path(__file__).resolve().parents[2]

    git_commit = git_stdout(
        repo_root,
        "rev-parse",
        "HEAD",
    )

    git_worktree_clean = not bool(
        git_stdout(
            repo_root,
            "status",
            "--porcelain",
        )
    )

    env_lock_path = (
        repo_root
        / "envs"
        / "bacselect-dev-linux-64.lock"
    )

    env_lock_hash = file_sha256(env_lock_path)

    assert env_lock_hash == EXPECTED_ENV_LOCK_SHA256, (
        "bacselect-dev environment lock fingerprint changed: "
        f"{env_lock_hash}"
    )

    print(
        "PASS | frozen environment lock | "
        f"{env_lock_hash}"
    )

    print(
        f"repository | "
        f"commit={git_commit} | "
        f"worktree_clean={str(git_worktree_clean).lower()}"
    )

    print(
        f"environment | "
        f"python={sys.version.split()[0]} | "
        f"numpy={np.__version__}"
    )

    foundation_start = time.perf_counter()

    coordinates, species_ids, accessions = load_foundation()

    foundation_elapsed = (
        time.perf_counter() - foundation_start
    )

    assert coordinates.shape == (
        EXPECTED_GENOMES,
        EXPECTED_FEATURES,
    )
    assert len(species_ids) == EXPECTED_GENOMES
    assert len(accessions) == EXPECTED_GENOMES
    assert len(set(species_ids)) == EXPECTED_SPECIES

    print(
        f"PASS | authoritative validation foundation | "
        f"{EXPECTED_GENOMES} genomes | "
        f"{EXPECTED_SPECIES} species | "
        f"{EXPECTED_FEATURES} features"
    )

    ladders = random_ladders(
        species_ids,
        accessions,
        max_n=DEFAULT_MAX_N,
        replicates=args.replicates,
        seed=DEFAULT_SEED,
    )

    assert ladders.shape == (
        args.replicates,
        DEFAULT_MAX_N,
    )

    if args.replicates == DEFAULT_REPLICATES:
        ladder_hash = ladder_matrix_sha256(
            ladders,
            accessions,
        )

        assert ladder_hash == EXPECTED_LADDER_SET_SHA256, (
            "random ladder-set fingerprint changed: "
            f"{ladder_hash}"
        )

        print(
            "PASS | frozen random ladder-set fingerprint | "
            f"{ladder_hash}"
        )
    else:
        ladder_hash = "not_applicable_partial_prefix"

    summaries_by_replicate: list[
        dict[int, CoverageSummary]
    ] = []

    first5_digest = hashlib.sha256()
    first5_digest.update(
        b"BacSelect-selector-v1|random-coverage-benchmark|"
        b"first-5-replicates\n"
    )

    evaluation_start = time.perf_counter()

    for replicate_index, ladder in enumerate(
        ladders,
        start=1,
    ):
        summaries = evaluate_ladder(
            coordinates,
            species_ids,
            ladder,
        )

        assert tuple(summaries) == panel_sizes

        summaries_by_replicate.append(summaries)

        if replicate_index <= 5:
            for panel_size in panel_sizes:
                summary = summaries[panel_size]

                for metric_name in metric_names:
                    value = getattr(
                        summary,
                        metric_name,
                    )

                    first5_digest.update(
                        (
                            f"{replicate_index}\t"
                            f"{panel_size}\t"
                            f"{metric_name}\t"
                            f"{format_metric(value)}\n"
                        ).encode("utf-8")
                    )

        if (
            args.replicates <= 10
            or replicate_index == 1
            or replicate_index % 25 == 0
            or replicate_index == args.replicates
        ):
            elapsed = (
                time.perf_counter()
                - evaluation_start
            )

            print(
                f"progress | "
                f"{replicate_index}/{args.replicates} | "
                f"elapsed_seconds={elapsed:.3f}"
            )

    evaluation_elapsed = (
        time.perf_counter() - evaluation_start
    )

    if args.replicates >= 5:
        first5_hash = first5_digest.hexdigest()

        assert (
            first5_hash
            == EXPECTED_FIRST5_METRIC_SHA256
        ), (
            "first-five metric fingerprint changed: "
            f"{first5_hash}"
        )

        print(
            "PASS | frozen first-five metric fingerprint | "
            f"{first5_hash}"
        )
    else:
        first5_hash = "not_applicable_fewer_than_5_replicates"

    replicate_lines = [
        "replicate\tN\t"
        + "\t".join(metric_names)
    ]

    for replicate_index, summaries in enumerate(
        summaries_by_replicate,
        start=1,
    ):
        for panel_size in panel_sizes:
            summary = summaries[panel_size]

            values = [
                format_metric(
                    getattr(summary, metric_name)
                )
                for metric_name in metric_names
            ]

            replicate_lines.append(
                f"{replicate_index}\t"
                f"{panel_size}\t"
                + "\t".join(values)
            )

    replicate_text = (
        "\n".join(replicate_lines) + "\n"
    )

    summary_lines = [
        "N\tmetric\trandom_p2.5\t"
        "random_median\trandom_p97.5"
    ]

    for panel_size in panel_sizes:
        for metric_name in metric_names:
            values = [
                getattr(
                    summaries[panel_size],
                    metric_name,
                )
                for summaries in summaries_by_replicate
            ]

            p025 = inverse_ecdf_quantile(
                values,
                P025,
            )
            median = inverse_ecdf_quantile(
                values,
                MEDIAN,
            )
            p975 = inverse_ecdf_quantile(
                values,
                P975,
            )

            summary_lines.append(
                f"{panel_size}\t"
                f"{metric_name}\t"
                f"{format_metric(p025)}\t"
                f"{format_metric(median)}\t"
                f"{format_metric(p975)}"
            )

    summary_text = (
        "\n".join(summary_lines) + "\n"
    )

    replicate_hash = sha256_text(
        replicate_text
    )
    summary_hash = sha256_text(
        summary_text
    )

    provenance_lines = [
        "key\tvalue",
        "selector_version\t1",
        f"random_replicates\t{args.replicates}",
        f"random_master_seed\t{DEFAULT_SEED}",
        "random_rng\tnumpy.random.Generator(PCG64)",
        (
            "random_replicate_protocol\t"
            "single_generator_sequential_replicates"
        ),
        "random_max_n\t500",
        "panel_sizes\t10,20,50,100,200,500",
        (
            "quantile_method\t"
            "empirical_inverse_cdf_no_interpolation"
        ),
        "quantile_thresholds\t"
        "p2.5=1/40,median=1/2,p97.5=39/40",
        f"python_version\t{sys.version.split()[0]}",
        f"numpy_version\t{np.__version__}",
        f"git_commit\t{git_commit}",
        (
            "git_worktree_clean\t"
            f"{str(git_worktree_clean).lower()}"
        ),
        (
            "environment_lock\t"
            "envs/bacselect-dev-linux-64.lock"
        ),
        (
            "environment_lock_sha256\t"
            f"{env_lock_hash}"
        ),
        f"random_ladder_sha256\t{ladder_hash}",
        (
            "first5_metric_sha256\t"
            f"{first5_hash}"
        ),
        (
            "replicate_metrics_sha256\t"
            f"{replicate_hash}"
        ),
        (
            "random_summary_sha256\t"
            f"{summary_hash}"
        ),
    ]

    provenance_text = (
        "\n".join(provenance_lines) + "\n"
    )

    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    replicate_path.write_text(
        replicate_text,
        encoding="utf-8",
    )
    summary_path.write_text(
        summary_text,
        encoding="utf-8",
    )
    provenance_path.write_text(
        provenance_text,
        encoding="utf-8",
    )

    print()
    print(
        f"foundation_load_seconds "
        f"{foundation_elapsed:.3f}"
    )
    print(
        f"coverage_evaluation_seconds "
        f"{evaluation_elapsed:.3f}"
    )
    print(
        f"seconds_per_replicate "
        f"{evaluation_elapsed / args.replicates:.3f}"
    )
    print(
        f"replicate_metrics_sha256 "
        f"{replicate_hash}"
    )
    print(
        f"random_summary_sha256 "
        f"{summary_hash}"
    )
    print(
        f"PASS | identity-blind replicate metrics | "
        f"{replicate_path}"
    )
    print(
        f"PASS | identity-blind random summary | "
        f"{summary_path}"
    )
    print(
        f"PASS | provenance | "
        f"{provenance_path}"
    )


if __name__ == "__main__":
    main()
