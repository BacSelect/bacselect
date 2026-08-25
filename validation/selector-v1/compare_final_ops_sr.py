#!/usr/bin/env python3
"""Prospective final-schema OPS-versus-SR coverage comparison."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from final_coverage_common import (
    EXPECTED_OPS_LADDER_SHA256,
    EXPECTED_SR_LADDER_SHA256,
    METRIC_NAMES,
    PANEL_SIZES,
    PRIMARY_METRIC,
    candidate_ladders,
    evaluate_ladder,
    file_sha256,
    format_metric,
    load_verified_final_foundation,
    primary_status,
    verify_repository,
    write_hash_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

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
        "===== final OPS/SR foundation ====="
    )

    foundation_start = time.perf_counter()
    foundation = (
        load_verified_final_foundation()
    )
    ops, sr = candidate_ladders(
        foundation
    )
    foundation_elapsed = (
        time.perf_counter()
        - foundation_start
    )

    print(
        "PASS | frozen final OPS ladder | "
        f"{EXPECTED_OPS_LADDER_SHA256}"
    )
    print(
        "PASS | frozen final SR ladder | "
        f"{EXPECTED_SR_LADDER_SHA256}"
    )

    print(
        "===== final OPS/SR coverage ====="
    )

    evaluation_start = time.perf_counter()

    ops_metrics = evaluate_ladder(
        foundation.coordinates,
        foundation.species_ids,
        ops,
    )
    sr_metrics = evaluate_ladder(
        foundation.coordinates,
        foundation.species_ids,
        sr,
    )

    evaluation_elapsed = (
        time.perf_counter()
        - evaluation_start
    )

    primary_path = (
        output_dir
        / "final300-2400-ops-vs-sr-primary.tsv"
    )
    metrics_path = (
        output_dir
        / "final300-2400-ops-vs-sr-metrics.tsv"
    )
    summary_path = (
        output_dir
        / "final300-2400-ops-vs-sr-summary.json"
    )
    manifest_path = (
        output_dir
        / "final300-2400-ops-vs-sr-sha256.txt"
    )

    primary_rows: list[
        dict[str, str]
    ] = []
    winners: list[str] = []

    for panel_size in PANEL_SIZES:
        ops_value = (
            ops_metrics[
                panel_size
            ].weighted_p95
        )
        sr_value = (
            sr_metrics[
                panel_size
            ].weighted_p95
        )

        if ops_value < sr_value:
            lower = "OPS"
        elif sr_value < ops_value:
            lower = "SR"
        else:
            lower = "TIE"

        winners.append(lower)

        primary_rows.append(
            {
                "N": str(panel_size),
                "OPS_weighted_p95":
                    format_metric(
                        ops_value
                    ),
                "SR_weighted_p95":
                    format_metric(
                        sr_value
                    ),
                "lower": lower,
                "SR_minus_OPS":
                    format_metric(
                        sr_value
                        - ops_value
                    ),
            }
        )

    status, automatic_winner = (
        primary_status(
            winners
        )
    )

    with primary_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "N",
                "OPS_weighted_p95",
                "SR_weighted_p95",
                "lower",
                "SR_minus_OPS",
            ),
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(
            primary_rows
        )

    with metrics_path.open(
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
                "selector",
                *METRIC_NAMES,
            ]
        )

        for panel_size in PANEL_SIZES:
            for selector, summaries in (
                ("OPS", ops_metrics),
                ("SR", sr_metrics),
            ):
                summary = summaries[
                    panel_size
                ]

                writer.writerow(
                    [
                        panel_size,
                        selector,
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

    summary = {
        "analysis":
            "selector-v1-final-300-2400-ops-vs-sr",
        "schema_version": 1,
        "analysis_commit":
            analysis_commit,
        "panel_sizes":
            list(PANEL_SIZES),
        "primary_metric":
            PRIMARY_METRIC,
        "primary_rule": (
            "automatic winner only if the same "
            "candidate has lower weighted_p95 at "
            "all six frozen panel sizes"
        ),
        "primary_status":
            status,
        "automatic_primary_winner":
            automatic_winner,
        "secondary_metrics":
            list(METRIC_NAMES),
        "secondary_interpretation_evaluated":
            False,
        "new_decision_criterion_introduced":
            False,
        "frozen_ladder_sha256": {
            "OPS":
                EXPECTED_OPS_LADDER_SHA256,
            "SR":
                EXPECTED_SR_LADDER_SHA256,
        },
        "outputs": {
            "primary_sha256":
                file_sha256(
                    primary_path
                ),
            "metrics_sha256":
                file_sha256(
                    metrics_path
                ),
        },
        "runtimes_seconds": {
            "foundation_and_ladders":
                foundation_elapsed,
            "coverage_evaluation":
                evaluation_elapsed,
        },
    }

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    write_hash_manifest(
        [
            primary_path,
            metrics_path,
            summary_path,
        ],
        manifest_path,
    )

    print()
    print(
        "===== primary comparison ====="
    )

    for row in primary_rows:
        print(
            f"N={row['N']} | "
            f"OPS={row['OPS_weighted_p95']} | "
            f"SR={row['SR_weighted_p95']} | "
            f"lower={row['lower']}"
        )

    print()
    print(
        f"primary_status\t{status}"
    )
    print(
        "automatic_primary_winner\t"
        f"{automatic_winner or 'NONE'}"
    )
    print(
        "secondary_interpretation_evaluated\tfalse"
    )
    print(
        "new_decision_criterion_introduced\tfalse"
    )
    print()
    print(
        "PASS | final OPS/SR coverage "
        "comparison complete"
    )
    print(
        "INFO | no post-hoc secondary "
        "decision was made"
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
