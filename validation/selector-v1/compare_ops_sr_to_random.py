#!/usr/bin/env python3
"""Compare frozen blinded OPS/SR metrics with the frozen random baseline."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from bacselect.random_compare import (
    lower_is_better_empirical_rank,
)


RESULT_DIR = Path("validation/selector-v1/results")

OPS_SR_PATH = RESULT_DIR / "base12-ops-vs-sr.txt"
RANDOM_REPLICATES_PATH = (
    RESULT_DIR / "random-coverage-replicates.tsv"
)
RANDOM_SUMMARY_PATH = (
    RESULT_DIR / "random-coverage-summary.tsv"
)
RANDOM_PROVENANCE_PATH = (
    RESULT_DIR / "random-coverage-provenance.tsv"
)

EXPECTED_OPS_SR_SHA256 = (
    "94ba2725fa646a803837d999ca609513"
    "d5000766398587e4a8f13dc5eb2655a1"
)

EXPECTED_RANDOM_REPLICATES_SHA256 = (
    "86104d1ff9a3c619cdfa10e9839bf486"
    "b0ee1e77eccc758d93ea3ad9cc42a4a9"
)

EXPECTED_RANDOM_SUMMARY_SHA256 = (
    "247e7c248803226a378168f1f944b788"
    "bd056851bb475367ed08ae119a1657dc"
)

EXPECTED_RANDOM_PROVENANCE_SHA256 = (
    "450bf925999734f7a69dd4e5fda262f5"
    "65fd4dc0feb224e34bc139fa674f1021"
)

PANEL_SIZES = (10, 20, 50, 100, 200, 500)
SELECTORS = ("OPS", "SR")

METRICS = (
    "weighted_mean",
    "weighted_median",
    "weighted_p95",
    "unweighted_max",
    "median_species_mean",
    "p95_species_mean",
    "max_species_mean",
    "median_species_max",
    "p95_species_max",
    "max_species_max",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def require_sha256(
    path: Path,
    expected: str,
) -> str:
    observed = file_sha256(path)

    if observed != expected:
        raise AssertionError(
            f"SHA256 changed for {path}: {observed}"
        )

    return observed


def parse_candidate_metrics() -> dict[
    tuple[int, str, str],
    tuple[str, Decimal],
]:
    lines = OPS_SR_PATH.read_text(
        encoding="utf-8"
    ).splitlines()

    try:
        secondary_index = lines.index("SECONDARY")
    except ValueError as exc:
        raise AssertionError(
            "SECONDARY block not found"
        ) from exc

    row_index = secondary_index + 1

    while (
        row_index < len(lines)
        and not lines[row_index]
    ):
        row_index += 1

    header = lines[row_index].split("\t")

    expected_header = [
        "N",
        "selector",
        *METRICS,
    ]

    if header != expected_header:
        raise AssertionError(
            f"unexpected candidate metric header: {header!r}"
        )

    row_index += 1

    result: dict[
        tuple[int, str, str],
        tuple[str, Decimal],
    ] = {}

    while row_index < len(lines):
        line = lines[row_index]

        if not line:
            break

        fields = line.split("\t")

        if len(fields) != len(expected_header):
            raise AssertionError(
                f"unexpected candidate row: {line!r}"
            )

        panel_size = int(fields[0])
        selector = fields[1]

        if panel_size not in PANEL_SIZES:
            raise AssertionError(
                f"unexpected panel size: {panel_size}"
            )

        if selector not in SELECTORS:
            raise AssertionError(
                f"unexpected selector: {selector}"
            )

        for metric, value_text in zip(
            METRICS,
            fields[2:],
        ):
            key = (
                panel_size,
                selector,
                metric,
            )

            if key in result:
                raise AssertionError(
                    f"duplicate candidate metric: {key}"
                )

            value = Decimal(value_text)

            if not value.is_finite():
                raise AssertionError(
                    f"nonfinite candidate metric: {key}"
                )

            result[key] = (
                value_text,
                value,
            )

        row_index += 1

    expected_count = (
        len(PANEL_SIZES)
        * len(SELECTORS)
        * len(METRICS)
    )

    if len(result) != expected_count:
        raise AssertionError(
            "candidate metric count changed: "
            f"{len(result)}"
        )

    return result


def parse_random_replicates() -> dict[
    tuple[int, str],
    list[Decimal],
]:
    values: dict[
        tuple[int, str],
        list[Decimal],
    ] = defaultdict(list)

    seen: set[tuple[int, int]] = set()

    with RANDOM_REPLICATES_PATH.open(
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
            *METRICS,
        ]

        if list(reader.fieldnames or []) != expected_header:
            raise AssertionError(
                "random replicate header changed"
            )

        for row in reader:
            replicate = int(row["replicate"])
            panel_size = int(row["N"])

            if not 1 <= replicate <= 1000:
                raise AssertionError(
                    f"invalid replicate: {replicate}"
                )

            if panel_size not in PANEL_SIZES:
                raise AssertionError(
                    f"invalid panel size: {panel_size}"
                )

            row_key = (
                replicate,
                panel_size,
            )

            if row_key in seen:
                raise AssertionError(
                    f"duplicate random row: {row_key}"
                )

            seen.add(row_key)

            for metric in METRICS:
                value = Decimal(row[metric])

                if not value.is_finite():
                    raise AssertionError(
                        "nonfinite random metric: "
                        f"{row_key} {metric}"
                    )

                values[
                    (
                        panel_size,
                        metric,
                    )
                ].append(value)

    if len(seen) != 6000:
        raise AssertionError(
            f"random row count changed: {len(seen)}"
        )

    expected_rows = {
        (
            replicate,
            panel_size,
        )
        for replicate in range(1, 1001)
        for panel_size in PANEL_SIZES
    }

    if seen != expected_rows:
        raise AssertionError(
            "random replicate/N coverage changed"
        )

    for panel_size in PANEL_SIZES:
        for metric in METRICS:
            key = (
                panel_size,
                metric,
            )

            if len(values[key]) != 1000:
                raise AssertionError(
                    f"random metric count changed: {key}"
                )

    return dict(values)


def parse_random_summary() -> dict[
    tuple[int, str],
    tuple[str, str, str],
]:
    result: dict[
        tuple[int, str],
        tuple[str, str, str],
    ] = {}

    with RANDOM_SUMMARY_PATH.open(
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

        if list(reader.fieldnames or []) != expected_header:
            raise AssertionError(
                "random summary header changed"
            )

        for row in reader:
            panel_size = int(row["N"])
            metric = row["metric"]

            if panel_size not in PANEL_SIZES:
                raise AssertionError(
                    f"invalid summary N: {panel_size}"
                )

            if metric not in METRICS:
                raise AssertionError(
                    f"invalid summary metric: {metric}"
                )

            key = (
                panel_size,
                metric,
            )

            if key in result:
                raise AssertionError(
                    f"duplicate random summary: {key}"
                )

            p025 = Decimal(
                row["random_p2.5"]
            )
            median = Decimal(
                row["random_median"]
            )
            p975 = Decimal(
                row["random_p97.5"]
            )

            if not (
                p025.is_finite()
                and median.is_finite()
                and p975.is_finite()
            ):
                raise AssertionError(
                    f"nonfinite random summary: {key}"
                )

            if not p025 <= median <= p975:
                raise AssertionError(
                    f"invalid random quantile ordering: {key}"
                )

            result[key] = (
                row["random_p2.5"],
                row["random_median"],
                row["random_p97.5"],
            )

    expected_count = (
        len(PANEL_SIZES)
        * len(METRICS)
    )

    if len(result) != expected_count:
        raise AssertionError(
            "random summary count changed: "
            f"{len(result)}"
        )

    return result


def verify_inputs() -> tuple[
    dict[tuple[int, str, str], tuple[str, Decimal]],
    dict[tuple[int, str], list[Decimal]],
    dict[tuple[int, str], tuple[str, str, str]],
]:
    hashes = (
        (
            OPS_SR_PATH,
            EXPECTED_OPS_SR_SHA256,
        ),
        (
            RANDOM_REPLICATES_PATH,
            EXPECTED_RANDOM_REPLICATES_SHA256,
        ),
        (
            RANDOM_SUMMARY_PATH,
            EXPECTED_RANDOM_SUMMARY_SHA256,
        ),
        (
            RANDOM_PROVENANCE_PATH,
            EXPECTED_RANDOM_PROVENANCE_SHA256,
        ),
    )

    for path, expected in hashes:
        observed = require_sha256(
            path,
            expected,
        )

        print(
            f"PASS | frozen input | "
            f"{path.name} | {observed}"
        )

    candidates = parse_candidate_metrics()
    random_values = parse_random_replicates()
    random_summary = parse_random_summary()

    print(
        "PASS | frozen candidate metrics | "
        "6 N x 2 selectors x 10 metrics"
    )
    print(
        "PASS | frozen random metrics | "
        "1000 replicates x 6 N x 10 metrics"
    )
    print(
        "PASS | frozen random summaries | "
        "6 N x 10 metrics"
    )

    return (
        candidates,
        random_values,
        random_summary,
    )


def write_comparison(
    output: Path,
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
) -> str:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite: {output}"
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
            for metric in METRICS:
                candidate_text, candidate = candidates[
                    (
                        panel_size,
                        selector,
                        metric,
                    )
                ]

                p025, median, p975 = random_summary[
                    (
                        panel_size,
                        metric,
                    )
                ]

                rank = lower_is_better_empirical_rank(
                    candidate,
                    random_values[
                        (
                            panel_size,
                            metric,
                        )
                    ],
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

    text = "\n".join(lines) + "\n"

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        text,
        encoding="utf-8",
    )

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--verify-inputs-only",
        action="store_true",
    )

    parser.add_argument(
        "--output",
        type=Path,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    (
        candidates,
        random_values,
        random_summary,
    ) = verify_inputs()

    if args.verify_inputs_only:
        if args.output is not None:
            raise ValueError(
                "--output must not be supplied with "
                "--verify-inputs-only"
            )

        print(
            "PASS | verification only | "
            "no empirical ranks calculated"
        )
        return

    if args.output is None:
        raise ValueError(
            "--output is required unless "
            "--verify-inputs-only is used"
        )

    output_hash = write_comparison(
        args.output,
        candidates,
        random_values,
        random_summary,
    )

    print(
        f"PASS | identity-blind comparison | "
        f"{args.output}"
    )
    print(
        f"comparison_sha256 | {output_hash}"
    )


if __name__ == "__main__":
    main()
