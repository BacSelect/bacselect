#!/usr/bin/env python3
"""Compare frozen final OPS/SR metrics with frozen final random coverage."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

from bacselect.random_compare import (
    lower_is_better_empirical_rank,
)

from final_coverage_common import (
    METRIC_NAMES,
    PANEL_SIZES,
    verify_hash_manifest,
    verify_repository,
)


SELECTORS = (
    "OPS",
    "SR",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--ops-sr-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--random-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )

    return parser.parse_args()


def load_candidate_metrics(
    directory: Path,
    expected_commit: str,
) -> dict[
    tuple[int, str, str],
    tuple[str, Decimal],
]:
    manifest = (
        directory
        / "final300-2400-ops-vs-sr-sha256.txt"
    )
    verified = verify_hash_manifest(
        manifest
    )

    required = {
        "final300-2400-ops-vs-sr-primary.tsv",
        "final300-2400-ops-vs-sr-metrics.tsv",
        "final300-2400-ops-vs-sr-summary.json",
    }

    if set(verified) != required:
        raise AssertionError(
            "candidate coverage manifest artifact set changed"
        )

    summary = json.loads(
        (
            directory
            / "final300-2400-ops-vs-sr-summary.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    if summary["analysis_commit"] != expected_commit:
        raise AssertionError(
            "candidate coverage analysis commit changed"
        )

    if (
        summary[
            "secondary_interpretation_evaluated"
        ]
        is not False
    ):
        raise AssertionError(
            "candidate summary unexpectedly "
            "contains secondary interpretation"
        )

    result: dict[
        tuple[int, str, str],
        tuple[str, Decimal],
    ] = {}

    path = (
        directory
        / "final300-2400-ops-vs-sr-metrics.tsv"
    )

    with path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        expected_header = [
            "N",
            "selector",
            *METRIC_NAMES,
        ]

        if reader.fieldnames != expected_header:
            raise AssertionError(
                "candidate metric header changed"
            )

        for row in reader:
            panel_size = int(
                row["N"]
            )
            selector = row[
                "selector"
            ]

            if panel_size not in PANEL_SIZES:
                raise AssertionError(
                    "unexpected candidate panel size"
                )

            if selector not in SELECTORS:
                raise AssertionError(
                    "unexpected candidate selector"
                )

            for metric in METRIC_NAMES:
                key = (
                    panel_size,
                    selector,
                    metric,
                )

                if key in result:
                    raise AssertionError(
                        "duplicate candidate metric row"
                    )

                text = row[
                    metric
                ]

                value = Decimal(
                    text
                )

                if not value.is_finite():
                    raise AssertionError(
                        "non-finite candidate metric"
                    )

                result[key] = (
                    text,
                    value,
                )

    expected_count = (
        len(PANEL_SIZES)
        * len(SELECTORS)
        * len(METRIC_NAMES)
    )

    if len(result) != expected_count:
        raise AssertionError(
            "candidate metric count changed"
        )

    return result


def load_random(
    directory: Path,
    expected_commit: str,
) -> tuple[
    dict[
        tuple[int, str],
        list[Decimal],
    ],
    dict[
        tuple[int, str],
        tuple[str, str, str],
    ],
]:
    manifest = (
        directory
        / "final300-2400-random-coverage-sha256.txt"
    )
    verified = verify_hash_manifest(
        manifest
    )

    required = {
        "final300-2400-random-coverage-replicates.tsv",
        "final300-2400-random-coverage-summary.tsv",
        "final300-2400-random-coverage-provenance.json",
    }

    if set(verified) != required:
        raise AssertionError(
            "random coverage manifest artifact set changed"
        )

    provenance = json.loads(
        (
            directory
            / "final300-2400-random-coverage-provenance.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    if provenance["analysis_commit"] != expected_commit:
        raise AssertionError(
            "random coverage analysis commit changed"
        )

    if provenance["replicates"] != 1000:
        raise AssertionError(
            "random replicate count changed"
        )

    replicate_values: dict[
        tuple[int, str],
        list[Decimal],
    ] = {
        (
            panel_size,
            metric,
        ): []
        for panel_size in PANEL_SIZES
        for metric in METRIC_NAMES
    }

    replicate_path = (
        directory
        / "final300-2400-random-coverage-replicates.tsv"
    )

    with replicate_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        expected_header = [
            "replicate",
            "N",
            *METRIC_NAMES,
        ]

        if reader.fieldnames != expected_header:
            raise AssertionError(
                "random replicate header changed"
            )

        seen_rows: set[
            tuple[int, int]
        ] = set()

        for row in reader:
            replicate = int(
                row["replicate"]
            )
            panel_size = int(
                row["N"]
            )

            row_key = (
                replicate,
                panel_size,
            )

            if row_key in seen_rows:
                raise AssertionError(
                    "duplicate random replicate row"
                )

            seen_rows.add(
                row_key
            )

            if not (
                1 <= replicate <= 1000
            ):
                raise AssertionError(
                    "random replicate index changed"
                )

            if panel_size not in PANEL_SIZES:
                raise AssertionError(
                    "random panel size changed"
                )

            for metric in METRIC_NAMES:
                value = Decimal(
                    row[metric]
                )

                if not value.is_finite():
                    raise AssertionError(
                        "non-finite random metric"
                    )

                replicate_values[
                    (
                        panel_size,
                        metric,
                    )
                ].append(
                    value
                )

    if len(seen_rows) != (
        1000
        * len(PANEL_SIZES)
    ):
        raise AssertionError(
            "random replicate row count changed"
        )

    for values in replicate_values.values():
        if len(values) != 1000:
            raise AssertionError(
                "random metric replicate count changed"
            )

    summary: dict[
        tuple[int, str],
        tuple[str, str, str],
    ] = {}

    summary_path = (
        directory
        / "final300-2400-random-coverage-summary.tsv"
    )

    with summary_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        expected_header = [
            "N",
            "metric",
            "random_p2.5",
            "random_median",
            "random_p97.5",
        ]

        if reader.fieldnames != expected_header:
            raise AssertionError(
                "random summary header changed"
            )

        for row in reader:
            panel_size = int(
                row["N"]
            )
            metric = row[
                "metric"
            ]

            key = (
                panel_size,
                metric,
            )

            if panel_size not in PANEL_SIZES:
                raise AssertionError(
                    "random summary panel size changed"
                )

            if metric not in METRIC_NAMES:
                raise AssertionError(
                    "random summary metric changed"
                )

            if key in summary:
                raise AssertionError(
                    "duplicate random summary row"
                )

            values = (
                row["random_p2.5"],
                row["random_median"],
                row["random_p97.5"],
            )

            decimals = tuple(
                Decimal(value)
                for value in values
            )

            if not all(
                value.is_finite()
                for value in decimals
            ):
                raise AssertionError(
                    "non-finite random summary"
                )

            if not (
                decimals[0]
                <= decimals[1]
                <= decimals[2]
            ):
                raise AssertionError(
                    "random quantile ordering changed"
                )

            summary[key] = values

    if len(summary) != (
        len(PANEL_SIZES)
        * len(METRIC_NAMES)
    ):
        raise AssertionError(
            "random summary row count changed"
        )

    return (
        replicate_values,
        summary,
    )


def main() -> int:
    args = parse_args()

    repo = Path.cwd().resolve()
    analysis_commit = verify_repository(
        repo
    )

    ops_sr_dir = (
        args.ops_sr_dir
        .expanduser()
        .resolve()
    )
    random_dir = (
        args.random_dir
        .expanduser()
        .resolve()
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

    candidates = load_candidate_metrics(
        ops_sr_dir,
        analysis_commit,
    )
    random_values, random_summary = (
        load_random(
            random_dir,
            analysis_commit,
        )
    )

    output_dir.mkdir(
        parents=True
    )

    comparison_path = (
        output_dir
        / "final300-2400-ops-sr-vs-random.tsv"
    )
    summary_path = (
        output_dir
        / "final300-2400-ops-sr-vs-random-summary.json"
    )
    manifest_path = (
        output_dir
        / "final300-2400-ops-sr-vs-random-sha256.txt"
    )

    lines = [
        (
            "N\tselector\tmetric\tcandidate_value\t"
            "random_p2.5\trandom_median\t"
            "random_p97.5\tempirical_rank"
        )
    ]

    for panel_size in PANEL_SIZES:
        for selector in SELECTORS:
            for metric in METRIC_NAMES:
                candidate_text, candidate = (
                    candidates[
                        (
                            panel_size,
                            selector,
                            metric,
                        )
                    ]
                )

                p025, median, p975 = (
                    random_summary[
                        (
                            panel_size,
                            metric,
                        )
                    ]
                )

                rank = (
                    lower_is_better_empirical_rank(
                        candidate,
                        random_values[
                            (
                                panel_size,
                                metric,
                            )
                        ],
                    )
                )

                lines.append(
                    f"{panel_size}\t"
                    f"{selector}\t"
                    f"{metric}\t"
                    f"{candidate_text}\t"
                    f"{p025}\t"
                    f"{median}\t"
                    f"{p975}\t"
                    f"{rank}"
                )

    comparison_text = (
        "\n".join(lines)
        + "\n"
    )

    comparison_path.write_text(
        comparison_text,
        encoding="utf-8",
    )

    summary = {
        "analysis":
            "selector-v1-final-300-2400-ops-sr-vs-random",
        "schema_version": 1,
        "analysis_commit":
            analysis_commit,
        "panel_sizes":
            list(PANEL_SIZES),
        "selectors":
            list(SELECTORS),
        "metrics":
            list(METRIC_NAMES),
        "empirical_rank_method":
            "lower_is_better_empirical_rank",
        "random_replicates":
            1000,
        "new_selector_decision_criterion_introduced":
            False,
        "selector_decision_evaluated":
            False,
        "input_manifests": {
            "ops_sr":
                str(
                    ops_sr_dir
                    / "final300-2400-ops-vs-sr-sha256.txt"
                ),
            "random":
                str(
                    random_dir
                    / "final300-2400-random-coverage-sha256.txt"
                ),
        },
        "output_sha256": (
            hashlib.sha256(
                comparison_text.encode(
                    "utf-8"
                )
            ).hexdigest()
        ),
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

    from final_coverage_common import (
        write_hash_manifest,
    )

    write_hash_manifest(
        [
            comparison_path,
            summary_path,
        ],
        manifest_path,
    )

    print(
        "PASS | final OPS/SR versus "
        "random empirical ranks calculated"
    )
    print(
        "INFO | no new selector decision "
        "criterion introduced"
    )
    print(
        "INFO | selector decision was "
        "not interpreted by this script"
    )
    print(
        f"comparison_sha256\t"
        f"{summary['output_sha256']}"
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
