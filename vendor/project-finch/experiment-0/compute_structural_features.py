#!/usr/bin/env python3
"""Compute all 12 frozen Experiment 0 structural features for one genome."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASIC_MODULE = HERE / "basic_structural_features.py"


def load_basic_module():
    spec = importlib.util.spec_from_file_location(
        "finch_basic_structural_features_driver",
        BASIC_MODULE,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"cannot load basic feature module: {BASIC_MODULE}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


basic = load_basic_module()


def fail(message: str) -> None:
    raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def read_fasta(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    name: str | None = None
    chunks: list[str] = []

    with path.open(
        encoding="utf-8"
    ) as handle:
        for line_number, raw in enumerate(
            handle,
            start=1,
        ):
            line = raw.rstrip("\r\n")

            if line.startswith(">"):
                if name is not None:
                    if name in records:
                        fail(
                            f"duplicate FASTA identifier: {name}"
                        )

                    records[name] = "".join(
                        chunks
                    ).upper()

                fields = line[1:].split()

                if not fields:
                    fail(
                        f"empty FASTA header at line "
                        f"{line_number}: {path}"
                    )

                name = fields[0]
                chunks = []
            else:
                sequence = "".join(
                    line.split()
                )

                if not sequence:
                    continue

                if name is None:
                    fail(
                        f"sequence before first FASTA header "
                        f"at line {line_number}: {path}"
                    )

                chunks.append(
                    sequence
                )

    if name is not None:
        if name in records:
            fail(
                f"duplicate FASTA identifier: {name}"
            )

        records[name] = "".join(
            chunks
        ).upper()

    if not records:
        fail(
            f"no FASTA records: {path}"
        )

    return records


def read_candidate_audit_row(
    path: Path,
    accession: str,
) -> dict[str, str]:
    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = [
            row
            for row in csv.DictReader(
                handle,
                delimiter="\t",
            )
            if row[
                "canonical_genbank_assembly_accession"
            ]
            == accession
        ]

    if len(rows) != 1:
        fail(
            f"expected exactly one candidate audit row "
            f"for {accession}; observed {len(rows)}"
        )

    row = rows[0]

    if row["result"] != "PASS":
        fail(
            f"{accession}: candidate audit result is "
            f"{row['result']!r}, not PASS"
        )

    if row["sequence_eligibility"] != "eligible":
        fail(
            f"{accession}: sequence eligibility is "
            f"{row['sequence_eligibility']!r}, not eligible"
        )

    return row


def read_component_audit_rows(
    path: Path,
    accession: str,
) -> dict[str, dict[str, str]]:
    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = [
            row
            for row in csv.DictReader(
                handle,
                delimiter="\t",
            )
            if row[
                "canonical_genbank_assembly_accession"
            ]
            == accession
        ]

    if not rows:
        fail(
            f"{accession}: no component audit records"
        )

    result: dict[str, dict[str, str]] = {}

    for row in rows:
        component = row[
            "component_genbank_accession"
        ]

        if component in result:
            fail(
                f"{accession}: duplicate component audit "
                f"accession {component}"
            )

        result[component] = row

    return result


def read_sequence_report_components(
    path: Path,
    accession: str,
) -> dict[str, dict]:
    records: dict[str, dict] = {}

    with path.open(
        encoding="utf-8"
    ) as handle:
        for line_number, line in enumerate(
            handle,
            start=1,
        ):
            if not line.strip():
                fail(
                    f"{accession}: blank sequence-report "
                    f"line {line_number}"
                )

            record = json.loads(
                line
            )

            if (
                record.get("assemblyAccession")
                != accession
            ):
                fail(
                    f"{accession}: sequence-report assembly "
                    f"accession mismatch at line {line_number}"
                )

            component = record.get(
                "genbankAccession"
            )

            if not component:
                if (
                    record.get("assemblyUnit")
                    == "Primary Assembly"
                ):
                    fail(
                        f"{accession}: Primary Assembly record "
                        "without genbankAccession"
                    )

                continue

            if component in records:
                fail(
                    f"{accession}: duplicate sequence-report "
                    f"component {component}"
                )

            records[component] = record

    if not records:
        fail(
            f"{accession}: no sequence-report components"
        )

    return records


def load_replicons(
    candidate_dir: Path,
    candidate_audit_path: Path,
    component_audit_path: Path,
):
    accession = candidate_dir.name

    candidate = read_candidate_audit_row(
        candidate_audit_path,
        accession,
    )

    fasta_name = candidate[
        "fasta_file"
    ]

    fasta_path = (
        candidate_dir
        / fasta_name
    )

    if not fasta_path.is_file():
        fail(
            f"{accession}: genomic FASTA missing: "
            f"{fasta_path}"
        )

    observed_fasta_sha256 = sha256_file(
        fasta_path
    )

    if (
        observed_fasta_sha256
        != candidate["fasta_sha256"]
    ):
        fail(
            f"{accession}: genomic FASTA SHA-256 mismatch"
        )

    sequence_report_path = (
        candidate_dir
        / "sequence_report.jsonl"
    )

    if not sequence_report_path.is_file():
        fail(
            f"{accession}: sequence_report.jsonl missing"
        )

    observed_report_sha256 = sha256_file(
        sequence_report_path
    )

    if (
        observed_report_sha256
        != candidate[
            "sequence_report_sha256"
        ]
    ):
        fail(
            f"{accession}: sequence-report SHA-256 mismatch"
        )

    fasta = read_fasta(
        fasta_path
    )

    audit = read_component_audit_rows(
        component_audit_path,
        accession,
    )

    all_report = read_sequence_report_components(
        sequence_report_path,
        accession,
    )

    report = {
        component: record
        for component, record in all_report.items()
        if (
            record.get("assemblyUnit")
            == "Primary Assembly"
        )
    }

    if not report:
        fail(
            f"{accession}: no Primary Assembly "
            "sequence-report records"
        )

    fasta_set = set(fasta)
    audit_set = set(audit)
    report_set = set(report)

    if report_set != audit_set:
        fail(
            f"{accession}: sequence-report/component-audit "
            "component sets differ"
        )

    missing_from_fasta = (
        audit_set
        - fasta_set
    )

    if missing_from_fasta:
        fail(
            f"{accession}: Primary Assembly component(s) "
            "missing from FASTA: "
            + ", ".join(
                sorted(
                    missing_from_fasta
                )
            )
        )

    for component in sorted(
        fasta_set
        - audit_set
    ):
        extra_report_row = all_report.get(
            component
        )

        if extra_report_row is None:
            fail(
                f"{accession}/{component}: FASTA-only "
                "component absent from sequence report"
            )

        assembly_unit = extra_report_row.get(
            "assemblyUnit"
        )

        if (
            not assembly_unit
            or assembly_unit
            == "Primary Assembly"
        ):
            fail(
                f"{accession}/{component}: FASTA-only "
                "component is not explicitly non-Primary"
            )

    replicons = []

    topology_counts = {
        "circular": 0,
        "linear": 0,
    }

    for component in sorted(
        audit_set
    ):
        sequence = fasta[
            component
        ]

        audit_row = audit[
            component
        ]

        report_row = report[
            component
        ]

        expected_length = int(
            audit_row["length"]
        )

        if len(sequence) != expected_length:
            fail(
                f"{accession}/{component}: FASTA/audit "
                "length mismatch"
            )

        expected_sequence_sha256 = audit_row.get(
            "sequence_sha256"
        )

        if not expected_sequence_sha256:
            fail(
                f"{accession}/{component}: missing "
                "component sequence SHA-256"
            )

        observed_sequence_sha256 = sha256_text(
            sequence
        )

        if (
            observed_sequence_sha256
            != expected_sequence_sha256
        ):
            fail(
                f"{accession}/{component}: FASTA/audit "
                "sequence SHA-256 mismatch"
            )

        report_length = report_row.get(
            "length"
        )

        if (
            report_length is not None
            and int(report_length)
            != len(sequence)
        ):
            fail(
                f"{accession}/{component}: FASTA/report "
                "length mismatch"
            )

        # NCBI gcCount is descriptive metadata and can
        # disagree with the packaged sequence. GC-dependent
        # features are derived from the verified FASTA itself.

        topology = audit_row[
            "topology"
        ]

        if topology not in topology_counts:
            fail(
                f"{accession}/{component}: unsupported "
                f"topology {topology!r}"
            )

        topology_counts[
            topology
        ] += 1

        molecule_location_type = (
            report_row.get(
                "assignedMoleculeLocationType"
            )
        )

        if not molecule_location_type:
            fail(
                f"{accession}/{component}: missing "
                "assignedMoleculeLocationType"
            )

        replicons.append(
            basic.ClassifiedReplicon(
                component,
                sequence,
                topology,
                molecule_location_type,
            )
        )

    total_length = sum(
        len(replicon.sequence)
        for replicon in replicons
    )

    if (
        int(candidate["total_sequence_length"])
        != total_length
    ):
        fail(
            f"{accession}: candidate-audit total "
            "sequence length mismatch"
        )

    if (
        int(candidate["fasta_records"])
        != len(fasta)
    ):
        fail(
            f"{accession}: candidate-audit FASTA "
            "record count mismatch"
        )

    if (
        int(candidate["primary_assembly_records"])
        != len(replicons)
    ):
        fail(
            f"{accession}: candidate-audit Primary "
            "Assembly count mismatch"
        )

    if (
        int(candidate["topology_circular_records"])
        != topology_counts["circular"]
    ):
        fail(
            f"{accession}: circular topology count mismatch"
        )

    if (
        int(candidate["topology_linear_records"])
        != topology_counts["linear"]
    ):
        fail(
            f"{accession}: linear topology count mismatch"
        )

    return (
        accession,
        replicons,
        fasta_path,
        sequence_report_path,
    )


def run_repeat_engine(
    engine: Path,
    replicons,
) -> dict[int, dict[str, str]]:
    if not engine.is_file():
        fail(
            f"structural-feature engine missing: {engine}"
        )

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        suffix=".tsv",
        delete=False,
    ) as handle:
        input_path = Path(
            handle.name
        )

        writer = csv.writer(
            handle,
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writerow(
            [
                "name",
                "topology",
                "sequence",
            ]
        )

        for replicon in replicons:
            writer.writerow(
                [
                    replicon.name,
                    replicon.topology,
                    replicon.sequence,
                ]
            )

    try:
        completed = subprocess.run(
            [
                str(engine),
                "--input",
                str(input_path),
                "--k",
                "150",
                "--k",
                "400",
                "--longest-repeat",
            ],
            check=True,
            text=True,
            capture_output=True,
        )
    finally:
        input_path.unlink(
            missing_ok=True
        )

    rows = list(
        csv.DictReader(
            completed.stdout.splitlines(),
            delimiter="\t",
        )
    )

    if len(rows) != 2:
        fail(
            "structural-feature engine must return "
            f"exactly two rows; observed {len(rows)}"
        )

    by_k: dict[int, dict[str, str]] = {}

    for row in rows:
        k = int(
            row["k"]
        )

        if k in by_k:
            fail(
                f"duplicate engine row for k={k}"
            )

        by_k[k] = row

    if set(by_k) != {
        150,
        400,
    }:
        fail(
            "structural-feature engine did not return "
            "exactly k=150 and k=400"
        )

    ler_150 = int(
        by_k[150][
            "longest_exact_repeat_length"
        ]
    )

    ler_400 = int(
        by_k[400][
            "longest_exact_repeat_length"
        ]
    )

    if ler_150 != ler_400:
        fail(
            "longest-repeat result differs between "
            "engine output rows"
        )

    return by_k


def compute_feature_record(
    candidate_dir: Path,
    candidate_audit_path: Path,
    component_audit_path: Path,
    engine: Path,
) -> dict:
    (
        accession,
        replicons,
        fasta_path,
        sequence_report_path,
    ) = load_replicons(
        candidate_dir,
        candidate_audit_path,
        component_audit_path,
    )

    basic_features = (
        basic.basic_structural_features(
            replicons
        )
    )

    repeat_rows = run_repeat_engine(
        engine,
        replicons,
    )

    row150 = repeat_rows[150]
    row400 = repeat_rows[400]

    longest_repeat = int(
        row150[
            "longest_exact_repeat_length"
        ]
    )

    return {
        "schema_version": 1,
        "canonical_genbank_assembly_accession": (
            accession
        ),
        "features": {
            "01_total_genome_length": (
                basic_features[
                    "total_genome_length"
                ]
            ),
            "02_whole_genome_gc_fraction": (
                basic_features[
                    "whole_genome_gc_fraction"
                ]
            ),
            "03_replicon_count": (
                basic_features[
                    "replicon_count"
                ]
            ),
            "04_non_chromosomal_replicon_count": (
                basic_features[
                    "non_chromosomal_replicon_count"
                ]
            ),
            "05_non_chromosomal_sequence_fraction": (
                basic_features[
                    "non_chromosomal_sequence_fraction"
                ]
            ),
            "06_non_unique_canonical_150mer_fraction": float(
                row150[
                    "non_unique_fraction"
                ]
            ),
            "07_non_unique_canonical_400mer_fraction": float(
                row400[
                    "non_unique_fraction"
                ]
            ),
            "08_maximum_canonical_150mer_multiplicity": int(
                row150[
                    "maximum_multiplicity"
                ]
            ),
            "09_maximum_canonical_400mer_multiplicity": int(
                row400[
                    "maximum_multiplicity"
                ]
            ),
            "10_longest_exact_repeat_length": (
                longest_repeat
            ),
            "11_inter_replicon_shared_canonical_150mer_fraction": float(
                row150[
                    "inter_replicon_shared_fraction"
                ]
            ),
            "12_inter_replicon_shared_canonical_400mer_fraction": float(
                row400[
                    "inter_replicon_shared_fraction"
                ]
            ),
        },
        "descriptive_metadata": {
            "plasmid_count": (
                basic_features[
                    "plasmid_count"
                ]
            ),
            "plasmid_sequence_length": (
                basic_features[
                    "plasmid_sequence_length"
                ]
            ),
        },
        "components": [
            replicon.name
            for replicon in replicons
        ],
        "source": {
            "genomic_fasta_file": (
                fasta_path.name
            ),
            "genomic_fasta_sha256": (
                sha256_file(
                    fasta_path
                )
            ),
            "sequence_report_file": (
                sequence_report_path.name
            ),
            "sequence_report_sha256": (
                sha256_file(
                    sequence_report_path
                )
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--candidate-dir",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--candidate-audit",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--component-audit",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--engine",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        type=Path,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    record = compute_feature_record(
        args.candidate_dir,
        args.candidate_audit,
        args.component_audit,
        args.engine,
    )

    text = (
        json.dumps(
            record,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    if args.output is None:
        sys.stdout.write(
            text
        )
    else:
        args.output.write_text(
            text,
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except Exception as exc:
        print(
            f"ERROR | {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
