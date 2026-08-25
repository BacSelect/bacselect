#!/usr/bin/env python3
"""Compare frozen final OPS/SR coverage with frozen final random coverage.

This comparison is deliberately bound to two independent frozen evidence
checkpoints:

- OPS/SR coverage was calculated under its own analysis commit;
- random coverage was calculated later under its own analysis commit.

The repository commit running this comparator is therefore not expected to
equal either evidence-generation commit. The comparator instead verifies the
exact committed input hashes and the embedded analysis commit for each evidence
set before calculating empirical ranks.
"""

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
    file_sha256,
    verify_repository,
    write_hash_manifest,
)


SELECTORS = (
    "OPS",
    "SR",
)

RESULT_DIR = Path(
    "validation/selector-v1/results"
)

EXPECTED_OPS_SR_ANALYSIS_COMMIT = (
    "ea547dbe7eeffbd5ce426c7ca5cb4347d8a1bc9d"
)

EXPECTED_RANDOM_ANALYSIS_COMMIT = (
    "81d7f62c3aa59b851848be9ce2afeb3b33839980"
)

EXPECTED_INPUT_SHA256 = {
    "final300-2400-ops-vs-sr-primary.tsv":
        "18349c559862cdb35a2453c1dd97c9b3"
        "f6e844ff0665e4c7b0ba79a019bf6211",
    "final300-2400-ops-vs-sr-metrics.tsv":
        "9cd2cc838cb74a044e356a1a418633ef"
        "2bdc89c4e9f71f924e4c1c0a79073388",
    "final300-2400-ops-vs-sr-summary.json":
        "4908739ac15bd2e842acb83bba6588ad"
        "7c2dc29be78a6a57b500709b33e16cf6",
    "final300-2400-ops-vs-sr-sha256.txt":
        "54a126b5bfdaa0feba583e8a8420c05c"
        "2f4a87bc53bd9355cd7ade559777a410",
    "final300-2400-random-coverage-replicates.tsv":
        "d86d572c22931c4440edceda25b17de2"
        "a02f586309611dc497b70dcdbb1a2c5f",
    "final300-2400-random-coverage-summary.tsv":
        "a1e0bf78d4be461a0de74ea8a06e103c"
        "cfeaafd394308b7ffe580f9cce96efda",
    "final300-2400-random-coverage-provenance.json":
        "7ada89bc210a561f29a9957180695395b"
        "6f8e4253d6d4e05268c3bdf9707c63a",
    "final300-2400-random-coverage-sha256.txt":
        "f009a033bc91140a7817ee3fd9f5fefe"
        "18afdab6f60244d681769150edea5a31",
}


def require_exact_input(
    directory: Path,
    name: str,
) -> Path:
    """Require one committed frozen input to match its exact SHA256."""
    path = directory / name

    if not path.is_file():
        raise AssertionError(
            f"frozen input missing: {path}"
        )

    expected = EXPECTED_INPUT_SHA256[
        name
    ]
    observed = file_sha256(
        path
    )

    if observed != expected:
        raise AssertionError(
            f"frozen input SHA256 changed for {name}: "
            f"expected {expected}, observed {observed}"
        )

    print(
        "PASS | frozen input | "
        f"{name} | {observed}"
    )

    return path


def verify_source_manifest(
    directory: Path,
    manifest_name: str,
    expected_rows: dict[str, str],
) -> None:
    """Require a frozen source manifest to contain the exact expected rows."""
    path = require_exact_input(
        directory,
        manifest_name,
    )

    observed_rows: dict[
        str,
        str,
    ] = {}

    with path.open(
        encoding="utf-8",
    ) as handle:
        for line_number, raw in enumerate(
            handle,
            start=1,
        ):
            line = raw.rstrip(
                "\n"
            )

            if not line:
                continue

            try:
                digest, name = line.split(
                    "  ",
                    1,
                )
            except ValueError as exc:
                raise AssertionError(
                    "invalid frozen source-manifest row "
                    f"{line_number}: {line!r}"
                ) from exc

            if name in observed_rows:
                raise AssertionError(
                    "duplicate frozen source-manifest "
                    f"entry: {name}"
                )

            observed_rows[
                name
            ] = digest

    if observed_rows != expected_rows:
        raise AssertionError(
            f"frozen source manifest changed: {manifest_name}"
        )


def load_candidate_metrics(
    directory: Path,
) -> dict[
    tuple[int, str, str],
    tuple[str, Decimal],
]:
    """Load exact frozen OPS/SR coverage evidence."""
    verify_source_manifest(
        directory,
        "final300-2400-ops-vs-sr-sha256.txt",
        {
            "final300-2400-ops-vs-sr-primary.tsv":
                EXPECTED_INPUT_SHA256[
                    "final300-2400-ops-vs-sr-primary.tsv"
                ],
            "final300-2400-ops-vs-sr-metrics.tsv":
                EXPECTED_INPUT_SHA256[
                    "final300-2400-ops-vs-sr-metrics.tsv"
                ],
            "final300-2400-ops-vs-sr-summary.json":
                EXPECTED_INPUT_SHA256[
                    "final300-2400-ops-vs-sr-summary.json"
                ],
        },
    )

    primary_path = require_exact_input(
        directory,
        "final300-2400-ops-vs-sr-primary.tsv",
    )
    metrics_path = require_exact_input(
        directory,
        "final300-2400-ops-vs-sr-metrics.tsv",
    )
    summary_path = require_exact_input(
        directory,
        "final300-2400-ops-vs-sr-summary.json",
    )

    summary = json.loads(
        summary_path.read_text(
            encoding="utf-8"
        )
    )

    if summary.get("analysis") != (
        "selector-v1-final-300-2400-ops-vs-sr"
    ):
        raise AssertionError(
            "OPS/SR analysis identity changed"
        )

    if (
        summary.get("analysis_commit")
        != EXPECTED_OPS_SR_ANALYSIS_COMMIT
    ):
        raise AssertionError(
            "OPS/SR evidence-generation commit changed"
        )

    if summary.get(
        "primary_status"
    ) != (
        "PRIMARY_CURVES_NOT_UNIFORMLY_ORDERED"
    ):
        raise AssertionError(
            "OPS/SR frozen primary status changed"
        )

    if summary.get(
        "automatic_primary_winner"
    ) is not None:
        raise AssertionError(
            "OPS/SR frozen automatic-winner status changed"
        )

    if summary.get(
        "secondary_interpretation_evaluated"
    ) is not False:
        raise AssertionError(
            "OPS/SR evidence unexpectedly contains "
            "secondary interpretation"
        )

    if summary.get(
        "new_decision_criterion_introduced"
    ) is not False:
        raise AssertionError(
            "OPS/SR evidence unexpectedly contains "
            "a new decision criterion"
        )

    if summary.get(
        "panel_sizes"
    ) != list(
        PANEL_SIZES
    ):
        raise AssertionError(
            "OPS/SR panel-size set changed"
        )

    if summary.get(
        "primary_metric"
    ) != "weighted_p95":
        raise AssertionError(
            "OPS/SR primary metric changed"
        )

    # The primary table is not used to construct the empirical-rank table,
    # but it is verified as a frozen evidence dependency.
    with primary_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        rows = list(
            csv.DictReader(
                handle,
                delimiter="\t",
            )
        )

    if len(rows) != len(
        PANEL_SIZES
    ):
        raise AssertionError(
            "OPS/SR primary row count changed"
        )

    result: dict[
        tuple[int, str, str],
        tuple[str, Decimal],
    ] = {}

    with metrics_path.open(
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
                        "duplicate candidate metric"
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

                result[
                    key
                ] = (
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

    print(
        "PASS | frozen OPS/SR evidence | "
        "6 N x 2 selectors x 10 metrics | "
        f"analysis_commit={EXPECTED_OPS_SR_ANALYSIS_COMMIT}"
    )

    return result


def load_random(
    directory: Path,
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
    """Load exact frozen final random-coverage evidence."""
    verify_source_manifest(
        directory,
        "final300-2400-random-coverage-sha256.txt",
        {
            "final300-2400-random-coverage-replicates.tsv":
                EXPECTED_INPUT_SHA256[
                    "final300-2400-random-coverage-replicates.tsv"
                ],
            "final300-2400-random-coverage-summary.tsv":
                EXPECTED_INPUT_SHA256[
                    "final300-2400-random-coverage-summary.tsv"
                ],
            "final300-2400-random-coverage-provenance.json":
                EXPECTED_INPUT_SHA256[
                    "final300-2400-random-coverage-provenance.json"
                ],
        },
    )

    replicate_path = require_exact_input(
        directory,
        "final300-2400-random-coverage-replicates.tsv",
    )
    summary_path = require_exact_input(
        directory,
        "final300-2400-random-coverage-summary.tsv",
    )
    provenance_path = require_exact_input(
        directory,
        "final300-2400-random-coverage-provenance.json",
    )

    provenance = json.loads(
        provenance_path.read_text(
            encoding="utf-8"
        )
    )

    if provenance.get("analysis") != (
        "selector-v1-final-300-2400-random-coverage"
    ):
        raise AssertionError(
            "random analysis identity changed"
        )

    if (
        provenance.get("analysis_commit")
        != EXPECTED_RANDOM_ANALYSIS_COMMIT
    ):
        raise AssertionError(
            "random evidence-generation commit changed"
        )

    if provenance.get(
        "replicates"
    ) != 1000:
        raise AssertionError(
            "random replicate count changed"
        )

    if provenance.get(
        "panel_sizes"
    ) != list(
        PANEL_SIZES
    ):
        raise AssertionError(
            "random panel-size set changed"
        )

    if provenance.get(
        "random_master_seed"
    ) != 20260824:
        raise AssertionError(
            "random master seed changed"
        )

    if provenance.get(
        "random_ladder_sha256"
    ) != (
        "9394a26ded92fb2baafea0101b837335"
        "e9d434f4cd3d8c6484ef61bbf0741719"
    ):
        raise AssertionError(
            "random ladder-set identity changed"
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
                    row[
                        metric
                    ]
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
                row[
                    "random_p2.5"
                ],
                row[
                    "random_median"
                ],
                row[
                    "random_p97.5"
                ],
            )

            decimals = tuple(
                Decimal(
                    value
                )
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

            summary[
                key
            ] = values

    if len(summary) != (
        len(PANEL_SIZES)
        * len(METRIC_NAMES)
    ):
        raise AssertionError(
            "random summary row count changed"
        )

    print(
        "PASS | frozen random evidence | "
        "1000 replicates x 6 N x 10 metrics | "
        f"analysis_commit={EXPECTED_RANDOM_ANALYSIS_COMMIT}"
    )

    return (
        replicate_values,
        summary,
    )


def verify_inputs(
    directory: Path,
) -> tuple[
    dict[
        tuple[int, str, str],
        tuple[str, Decimal],
    ],
    dict[
        tuple[int, str],
        list[Decimal],
    ],
    dict[
        tuple[int, str],
        tuple[str, str, str],
    ],
]:
    """Verify both independently frozen evidence checkpoints."""
    candidates = load_candidate_metrics(
        directory
    )
    random_values, random_summary = (
        load_random(
            directory
        )
    )

    print(
        "PASS | independent evidence commits "
        "verified separately"
    )

    return (
        candidates,
        random_values,
        random_summary,
    )


def write_comparison(
    output_dir: Path,
    analysis_commit: str,
    candidates: dict[
        tuple[int, str, str],
        tuple[str, Decimal],
    ],
    random_values: dict[
        tuple[int, str],
        list[Decimal],
    ],
    random_summary: dict[
        tuple[int, str],
        tuple[str, str, str],
    ],
) -> tuple[
    Path,
    Path,
    Path,
]:
    """Write empirical ranks without creating a selector decision rule."""
    if output_dir.exists():
        raise FileExistsError(
            f"refusing to overwrite output directory: {output_dir}"
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
        "\n".join(
            lines
        )
        + "\n"
    )

    comparison_path.write_text(
        comparison_text,
        encoding="utf-8",
    )

    summary = {
        "analysis":
            "selector-v1-final-300-2400-ops-sr-vs-random",
        "schema_version":
            1,
        "analysis_commit":
            analysis_commit,
        "ops_sr_evidence_generation_commit":
            EXPECTED_OPS_SR_ANALYSIS_COMMIT,
        "random_evidence_generation_commit":
            EXPECTED_RANDOM_ANALYSIS_COMMIT,
        "input_sha256":
            EXPECTED_INPUT_SHA256,
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
        "output_sha256": {
            "comparison":
                hashlib.sha256(
                    comparison_text.encode(
                        "utf-8"
                    )
                ).hexdigest(),
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
            comparison_path,
            summary_path,
        ],
        manifest_path,
    )

    return (
        comparison_path,
        summary_path,
        manifest_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--verify-inputs-only",
        action="store_true",
        help=(
            "verify both frozen evidence checkpoints "
            "without calculating empirical ranks"
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "new output directory; required unless "
            "--verify-inputs-only is used"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo = Path.cwd().resolve()
    analysis_commit = verify_repository(
        repo
    )

    (
        candidates,
        random_values,
        random_summary,
    ) = verify_inputs(
        RESULT_DIR
    )

    if args.verify_inputs_only:
        if args.output_dir is not None:
            raise ValueError(
                "--output-dir must not be supplied "
                "with --verify-inputs-only"
            )

        print(
            "PASS | verification only | "
            "no empirical ranks calculated"
        )

        return 0

    if args.output_dir is None:
        raise ValueError(
            "--output-dir is required unless "
            "--verify-inputs-only is used"
        )

    output_dir = (
        args.output_dir
        .expanduser()
        .resolve()
    )

    (
        comparison_path,
        summary_path,
        manifest_path,
    ) = write_comparison(
        output_dir,
        analysis_commit,
        candidates,
        random_values,
        random_summary,
    )

    print(
        "PASS | final OPS/SR versus random "
        "empirical ranks calculated"
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
        "comparison_sha256\t"
        f"{file_sha256(comparison_path)}"
    )
    print(
        "summary_sha256\t"
        f"{file_sha256(summary_path)}"
    )
    print(
        "manifest_sha256\t"
        f"{file_sha256(manifest_path)}"
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
