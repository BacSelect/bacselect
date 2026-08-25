#!/usr/bin/env python3
"""Calculate prospective final-schema random-baseline coverage distributions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from dataclasses import fields
from fractions import Fraction
from pathlib import Path

import numpy as np

from bacselect.metrics import (
    CoverageSummary,
    inverse_ecdf_quantile,
)
from bacselect.random_baseline import (
    DEFAULT_MAX_N,
    DEFAULT_REPLICATES,
    DEFAULT_SEED,
    random_ladders,
)

from final_coverage_common import (
    EXPECTED_RANDOM_LADDER_SET_SHA256,
    METRIC_NAMES,
    PANEL_SIZES,
    evaluate_ladder,
    file_sha256,
    format_metric,
    load_verified_final_foundation,
    verify_repository,
    write_hash_manifest,
)


P025 = Fraction(1, 40)
MEDIAN = Fraction(1, 2)
P975 = Fraction(39, 40)


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


def random_ladder_matrix_sha256(
    ladders: np.ndarray,
    accessions: list[str],
) -> str:
    """Return frozen random ladder-set fingerprint."""
    digest = hashlib.sha256()
    digest.update(
        b"BacSelect-selector-v1|random|1000x500\n"
    )

    for ladder in ladders:
        for index in ladder:
            digest.update(
                accessions[
                    int(index)
                ].encode("utf-8")
            )
            digest.update(b"\n")

        digest.update(
            b"--replicate--\n"
        )

    return digest.hexdigest()


def metric_digest(
    summaries_by_replicate: list[
        dict[int, CoverageSummary]
    ],
    *,
    limit: int,
) -> str:
    """Fingerprint the first `limit` random coverage replicates."""
    digest = hashlib.sha256()
    digest.update(
        b"BacSelect-selector-v1|"
        b"final300-2400-random-coverage|"
        b"first-replicates\n"
    )

    for replicate_index, summaries in enumerate(
        summaries_by_replicate[:limit],
        start=1,
    ):
        for panel_size in PANEL_SIZES:
            summary = summaries[
                panel_size
            ]

            for metric_name in METRIC_NAMES:
                digest.update(
                    (
                        f"{replicate_index}\t"
                        f"{panel_size}\t"
                        f"{metric_name}\t"
                        f"{format_metric(getattr(summary, metric_name))}\n"
                    ).encode("utf-8")
                )

    return digest.hexdigest()


def main() -> int:
    args = parse_args()

    if args.replicates < 1:
        raise ValueError(
            "--replicates must be at least 1"
        )

    if args.replicates > DEFAULT_REPLICATES:
        raise ValueError(
            "--replicates must not exceed "
            f"{DEFAULT_REPLICATES}"
        )

    if tuple(PANEL_SIZES) != (
        10,
        20,
        50,
        100,
        200,
        500,
    ):
        raise AssertionError(
            "frozen panel sizes changed"
        )

    if DEFAULT_MAX_N != 500:
        raise AssertionError(
            "random maximum N changed"
        )

    if DEFAULT_REPLICATES != 1000:
        raise AssertionError(
            "random replicate count changed"
        )

    if DEFAULT_SEED != 20260824:
        raise AssertionError(
            "random master seed changed"
        )

    repo = Path.cwd().resolve()
    analysis_commit = verify_repository(
        repo
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
        "===== final random coverage foundation ====="
    )

    foundation_start = time.perf_counter()
    foundation = (
        load_verified_final_foundation()
    )
    foundation_elapsed = (
        time.perf_counter()
        - foundation_start
    )

    ladders = random_ladders(
        foundation.species_ids,
        foundation.accessions,
        max_n=DEFAULT_MAX_N,
        replicates=args.replicates,
        seed=DEFAULT_SEED,
    )

    if ladders.shape != (
        args.replicates,
        DEFAULT_MAX_N,
    ):
        raise AssertionError(
            "random ladder-set shape changed"
        )

    if args.replicates == DEFAULT_REPLICATES:
        ladder_hash = (
            random_ladder_matrix_sha256(
                ladders,
                foundation.accessions,
            )
        )

        if (
            ladder_hash
            != EXPECTED_RANDOM_LADDER_SET_SHA256
        ):
            raise AssertionError(
                "random ladder-set fingerprint changed: "
                f"{ladder_hash}"
            )

        print(
            "PASS | frozen random ladder-set "
            f"fingerprint | {ladder_hash}"
        )
    else:
        ladder_hash = (
            "not_applicable_partial_prefix"
        )

    print(
        "===== random coverage evaluation ====="
    )

    summaries_by_replicate: list[
        dict[int, CoverageSummary]
    ] = []

    evaluation_start = time.perf_counter()

    for replicate_index, ladder in enumerate(
        ladders,
        start=1,
    ):
        summaries = evaluate_ladder(
            foundation.coordinates,
            foundation.species_ids,
            ladder,
        )

        if tuple(summaries) != PANEL_SIZES:
            raise AssertionError(
                "random coverage panel-size set changed"
            )

        summaries_by_replicate.append(
            summaries
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
                "progress | "
                f"{replicate_index}/{args.replicates} | "
                f"elapsed_seconds={elapsed:.3f}"
            )

    evaluation_elapsed = (
        time.perf_counter()
        - evaluation_start
    )

    first_count = min(
        5,
        args.replicates,
    )

    first_hash = metric_digest(
        summaries_by_replicate,
        limit=first_count,
    )

    verification_summaries = [
        evaluate_ladder(
            foundation.coordinates,
            foundation.species_ids,
            ladders[index],
        )
        for index in range(
            first_count
        )
    ]

    verification_hash = metric_digest(
        verification_summaries,
        limit=first_count,
    )

    if first_hash != verification_hash:
        raise AssertionError(
            "repeat evaluation of initial random "
            "coverage replicates changed"
        )

    print(
        "PASS | repeated initial random "
        f"coverage fingerprint | {first_hash}"
    )

    replicate_path = (
        output_dir
        / "final300-2400-random-coverage-replicates.tsv"
    )
    summary_path = (
        output_dir
        / "final300-2400-random-coverage-summary.tsv"
    )
    provenance_path = (
        output_dir
        / "final300-2400-random-coverage-provenance.json"
    )
    manifest_path = (
        output_dir
        / "final300-2400-random-coverage-sha256.txt"
    )

    with replicate_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.writer(
            handle,
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writerow(
            [
                "replicate",
                "N",
                *METRIC_NAMES,
            ]
        )

        for replicate_index, summaries in enumerate(
            summaries_by_replicate,
            start=1,
        ):
            for panel_size in PANEL_SIZES:
                summary = summaries[
                    panel_size
                ]

                writer.writerow(
                    [
                        replicate_index,
                        panel_size,
                        *(
                            format_metric(
                                getattr(
                                    summary,
                                    metric,
                                )
                            )
                            for metric
                            in METRIC_NAMES
                        ),
                    ]
                )

    with summary_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.writer(
            handle,
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writerow(
            [
                "N",
                "metric",
                "random_p2.5",
                "random_median",
                "random_p97.5",
            ]
        )

        for panel_size in PANEL_SIZES:
            for metric_name in METRIC_NAMES:
                values = [
                    getattr(
                        summaries[
                            panel_size
                        ],
                        metric_name,
                    )
                    for summaries
                    in summaries_by_replicate
                ]

                writer.writerow(
                    [
                        panel_size,
                        metric_name,
                        format_metric(
                            inverse_ecdf_quantile(
                                values,
                                P025,
                            )
                        ),
                        format_metric(
                            inverse_ecdf_quantile(
                                values,
                                MEDIAN,
                            )
                        ),
                        format_metric(
                            inverse_ecdf_quantile(
                                values,
                                P975,
                            )
                        ),
                    ]
                )

    provenance = {
        "analysis":
            "selector-v1-final-300-2400-random-coverage",
        "schema_version": 1,
        "analysis_commit":
            analysis_commit,
        "replicates":
            args.replicates,
        "random_master_seed":
            DEFAULT_SEED,
        "random_rng":
            "numpy.random.Generator(PCG64)",
        "random_replicate_protocol":
            "single_generator_sequential_replicates",
        "random_max_n":
            DEFAULT_MAX_N,
        "panel_sizes":
            list(PANEL_SIZES),
        "quantile_method":
            "empirical_inverse_cdf_no_interpolation",
        "quantile_thresholds": {
            "p2.5": "1/40",
            "median": "1/2",
            "p97.5": "39/40",
        },
        "random_ladder_sha256":
            ladder_hash,
        "initial_metric_replicates":
            first_count,
        "initial_metric_sha256":
            first_hash,
        "initial_metric_repeat_sha256":
            verification_hash,
        "software": {
            "python":
                platform.python_version(),
            "numpy":
                np.__version__,
        },
        "runtimes_seconds": {
            "foundation":
                foundation_elapsed,
            "coverage_evaluation":
                evaluation_elapsed,
            "per_replicate":
                (
                    evaluation_elapsed
                    / args.replicates
                ),
        },
        "outputs": {
            "replicate_metrics_sha256":
                file_sha256(
                    replicate_path
                ),
            "random_summary_sha256":
                file_sha256(
                    summary_path
                ),
        },
    }

    provenance_path.write_text(
        json.dumps(
            provenance,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    write_hash_manifest(
        [
            replicate_path,
            summary_path,
            provenance_path,
        ],
        manifest_path,
    )

    print()
    print(
        "coverage_evaluation_seconds\t"
        f"{evaluation_elapsed:.3f}"
    )
    print(
        "seconds_per_replicate\t"
        f"{evaluation_elapsed / args.replicates:.3f}"
    )
    print(
        "replicate_metrics_sha256\t"
        f"{file_sha256(replicate_path)}"
    )
    print(
        "random_summary_sha256\t"
        f"{file_sha256(summary_path)}"
    )
    print(
        "provenance_sha256\t"
        f"{file_sha256(provenance_path)}"
    )
    print(
        "PASS | final identity-blind "
        "random coverage complete"
    )
    print(
        f"output_dir\t{output_dir}"
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
