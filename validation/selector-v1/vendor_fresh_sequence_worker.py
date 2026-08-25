#!/usr/bin/env python3
"""Vendor and adapt the frozen Project Finch sequence validator for BacSelect.

The transformation is intentionally narrow and fail-closed. The input source
must have the exact frozen SHA256 recorded below.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

EXPECTED_SOURCE_SHA256 = (
    "780f8aabe2e6d9b4425498ee1f0170e3b0d55328100a4aea02efc875d4d29665"
)
FRESH_MANIFEST = (
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/"
    "final-acquisition-manifests/"
    "a8f045506ac4a3f17034cd9170867995a87eb894/"
    "fresh-download-manifest.tsv"
)
FRESH_MANIFEST_SHA256 = (
    "1c9a73231d6b8ebfed76fb60621616588a4f51b1144e5d7880f14ddf26d1863b"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"ERROR | expected exactly one {label}; observed {count}"
        )
    return text.replace(old, new, 1)


def replace_section(
    text: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
    label: str,
) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"ERROR | missing {label} start marker")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"ERROR | missing {label} end marker")
    if text.find(start_marker, start + 1) >= 0:
        raise SystemExit(f"ERROR | duplicate {label} start marker")
    return text[:start] + replacement + "\n\n" + text[end:]


def transform(source: Path, destination: Path) -> None:
    observed = sha256_file(source)
    if observed != EXPECTED_SOURCE_SHA256:
        raise SystemExit(
            "ERROR | Project Finch validator SHA256 mismatch: "
            f"{observed}"
        )

    text = source.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '"""Retrieve and validate one Experiment 0 sequence-validation batch."""',
        '"""Retrieve and validate one BacSelect fresh-acquisition batch."""',
        "module docstring",
    )
    text = replace_once(
        text,
        "EXPECTED_TARGETS = 55_426",
        "EXPECTED_TARGETS = 15_326",
        "target count",
    )
    text = replace_once(
        text,
        "EXPECTED_BATCHES = 111",
        "EXPECTED_BATCHES = 31",
        "batch count",
    )

    target_block = f'''TARGET_MANIFEST = Path(
    "{FRESH_MANIFEST}"
)
TARGET_MANIFEST_SHA256 = (
    "{FRESH_MANIFEST_SHA256}"
)'''
    text = replace_section(
        text,
        "TARGET_MANIFEST = Path(",
        "ENVIRONMENT_EXPLICIT = Path(",
        target_block,
        "target manifest block",
    )

    default_block = '''DEFAULT_OUTPUT = Path(
    "/tmp/bacselect/selector-v1/"
    "fresh-sequence-validation"
)'''
    text = replace_section(
        text,
        "DEFAULT_OUTPUT = Path(",
        "GCA_RE = re.compile(",
        default_block,
        "default output block",
    )

    fields_block = '''TARGET_FIELDS_REQUIRED = {
    "canonical_genbank_assembly_accession",
    "fresh_biosample",
    "acquisition_reason",
}'''
    text = replace_section(
        text,
        "TARGET_FIELDS_REQUIRED = {",
        "CANDIDATE_AUDIT_FIELDS = [",
        fields_block,
        "target fields block",
    )

    load_targets = '''def load_targets(repo):
    path = TARGET_MANIFEST

    if not path.is_absolute():
        path = (repo / path).resolve()

    if not path.is_file():
        die(
            f"missing BacSelect fresh target manifest: "
            f"{path}"
        )

    observed_sha = sha256_file(path)

    if observed_sha != TARGET_MANIFEST_SHA256:
        die(
            "BacSelect fresh target manifest "
            f"checksum mismatch: {observed_sha}"
        )

    fields, rows = read_tsv(path)

    missing_fields = TARGET_FIELDS_REQUIRED - fields

    if missing_fields:
        die(
            "fresh target manifest missing required fields: "
            f"{sorted(missing_fields)!r}"
        )

    if len(rows) != EXPECTED_TARGETS:
        die(
            f"expected {EXPECTED_TARGETS:,} fresh targets, "
            f"found {len(rows):,}"
        )

    accessions = [
        row["canonical_genbank_assembly_accession"]
        for row in rows
    ]

    if len(set(accessions)) != EXPECTED_TARGETS:
        die("fresh target accessions are not unique")

    if accessions != sorted(accessions):
        die("fresh target accessions are not lexicographically sorted")

    compatible_rows = []

    for row in rows:
        accession = row["canonical_genbank_assembly_accession"]

        if not GCA_RE.fullmatch(accession):
            die(f"invalid canonical accession: {accession!r}")

        biosample = row["fresh_biosample"]

        if not biosample:
            die(f"{accession}: fresh BioSample is empty")

        if row["acquisition_reason"] != "not_in_historical_cache":
            die(f"{accession}: unexpected fresh acquisition reason")

        compatible = dict(row)

        # Compatibility alias required by the frozen validation engine.
        compatible["source_biosample"] = biosample

        compatible_rows.append(compatible)

    return compatible_rows'''
    text = replace_section(
        text,
        "def load_targets(repo):",
        "def batch_slice(",
        load_targets,
        "load_targets function",
    )

    assembly_source_fragment = '''            "--assembly-source",
            "GenBank",
'''
    text = replace_once(
        text,
        assembly_source_fragment,
        "",
        "download --assembly-source fragment",
    )

    marker = 'DATASETS_VERSION = "18.35.0"\n'
    derivation = (
        marker
        + "BACSELECT_VENDOR_SOURCE_SHA256 = (\n"
        + f'    "{EXPECTED_SOURCE_SHA256}"\n'
        + ")\n"
    )
    text = replace_once(
        text,
        marker,
        derivation,
        "Datasets version marker",
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()

    if args.destination.exists():
        raise SystemExit(f"ERROR | refusing to overwrite: {args.destination}")

    transform(args.source, args.destination)
    print(
        "PASS | vendored BacSelect fresh sequence validator | "
        f"sha256={sha256_file(args.destination)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
