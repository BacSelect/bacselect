#!/usr/bin/env python3
"""Retrieve and validate one BacSelect fresh-acquisition batch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from collections import Counter
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from datetime import datetime, timezone
from pathlib import Path


DATASETS_VERSION = "18.35.0"
BACSELECT_VENDOR_SOURCE_SHA256 = (
    "780f8aabe2e6d9b4425498ee1f0170e3b0d55328100a4aea02efc875d4d29665"
)
SCHEMA_VERSION = 2

EXPECTED_TARGETS = 15_326
BATCH_SIZE = 500
EXPECTED_BATCHES = 31
WORKERS = 10
TARGETED_RETRY_ROUNDS = 2

EFETCH_ENDPOINT = (
    "https://eutils.ncbi.nlm.nih.gov/"
    "entrez/eutils/efetch.fcgi"
)
EFETCH_CHUNK_SIZE = 100
EFETCH_RETRY_ROUNDS = 3
EFETCH_RETRY_DELAY_SECONDS = 3
EFETCH_REQUEST_INTERVAL_SECONDS = 0.4
EFETCH_TIMEOUT_SECONDS = 120

TARGET_MANIFEST = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/final-acquisition-manifests/a8f045506ac4a3f17034cd9170867995a87eb894/fresh-download-manifest.tsv"
)
TARGET_MANIFEST_SHA256 = (
    "1c9a73231d6b8ebfed76fb60621616588a4f51b1144e5d7880f14ddf26d1863b"
)

ENVIRONMENT_EXPLICIT = Path(
    "environments/ncbi-datasets-linux-64.explicit.txt"
)
ENVIRONMENT_EXPLICIT_SHA256 = (
    "6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd"
)

DEFAULT_OUTPUT = Path(
    "/tmp/bacselect/selector-v1/"
    "fresh-sequence-validation"
)

GCA_RE = re.compile(r"^GCA_\d+\.\d+$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

IUPAC_DNA = frozenset(
    "ACGTRYSWKMBDHVN"
)
PRIMARY_DNA = frozenset(
    "ACGT"
)

TARGET_FIELDS_REQUIRED = {
    "canonical_genbank_assembly_accession",
    "fresh_biosample",
    "acquisition_reason",
}

CANDIDATE_AUDIT_FIELDS = [
    "canonical_genbank_assembly_accession",
    "expected_biosample",
    "observed_biosample",
    "assembly_status",
    "current_accession",
    "assembly_level",
    "sequence_report_records",
    "sequence_report_length_present_records",
    "sequence_report_length_missing_records",
    "sequence_report_length_missing_components",
    "primary_assembly_records",
    "auxiliary_assembly_records",
    "auxiliary_assembly_units",
    "auxiliary_component_accessions",
    "fasta_records",
    "gbff_records",
    "total_sequence_length",
    "package_total_sequence_length",
    "auxiliary_total_sequence_length",
    "topology_circular_records",
    "topology_linear_records",
    "topology_unspecified_records",
    "ambiguous_base_count",
    "ambiguous_symbols",
    "sequence_eligibility",
    "exclusion_reasons",
    "fasta_file",
    "fasta_sha256",
    "gbff_file",
    "gbff_sha256",
    "gbff_source",
    "gbff_provenance_file",
    "gbff_provenance_sha256",
    "sequence_report_sha256",
    "result",
]

COMPONENT_AUDIT_FIELDS = [
    "canonical_genbank_assembly_accession",
    "component_genbank_accession",
    "length",
    "topology",
    "ambiguous_base_count",
    "ambiguous_symbols",
    "sequence_sha256",
]

PACKAGE_FILE_FIELDS = [
    "path",
    "size_bytes",
    "sha256",
]


def die(message):
    raise SystemExit(
        f"ERROR | {message}"
    )


def utc_now():
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256_file(path):
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def sha256_text(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def git_output(repo, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        die(
            f"git {' '.join(args)} failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    return result.stdout.strip()


def production_git_head(repo):
    status = git_output(
        repo,
        "status",
        "--porcelain",
    )

    if status:
        die(
            "Git working tree is not clean; commit or discard "
            "tracked and untracked repository changes before a "
            "production snapshot"
        )

    head = git_output(
        repo,
        "rev-parse",
        "HEAD",
    )

    origin = git_output(
        repo,
        "rev-parse",
        "origin/main",
    )

    if not GIT_SHA_RE.fullmatch(head):
        die(
            f"invalid local Git HEAD: {head!r}"
        )

    if not GIT_SHA_RE.fullmatch(origin):
        die(
            f"invalid origin/main commit: {origin!r}"
        )

    if head != origin:
        die(
            "local HEAD does not match origin/main; push the "
            "snapshot code and inputs before network retrieval"
        )

    return head


def datasets_prefix(repo):
    env_path = (
        repo
        / ENVIRONMENT_EXPLICIT
    )

    if not env_path.is_file():
        die(
            f"missing environment file: "
            f"{ENVIRONMENT_EXPLICIT}"
        )

    observed = sha256_file(
        env_path
    )

    if observed != ENVIRONMENT_EXPLICIT_SHA256:
        die(
            "NCBI Datasets explicit environment "
            "checksum mismatch"
        )

    conda = shutil.which(
        "conda"
    )

    if conda is None:
        die(
            "conda not found on PATH"
        )

    prefix = [
        conda,
        "run",
        "--no-capture-output",
        "-n",
        "finch-ncbi-datasets",
        "datasets",
    ]

    result = subprocess.run(
        prefix + ["--version"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        die(
            "unable to query NCBI Datasets version: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    version_text = (
        result.stdout
        + "\n"
        + result.stderr
    ).strip()

    if DATASETS_VERSION not in version_text:
        die(
            f"expected NCBI Datasets {DATASETS_VERSION}, "
            f"got {version_text!r}"
        )

    return prefix


def read_tsv(path):
    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        fields = set(
            reader.fieldnames
            or []
        )

        return (
            fields,
            list(reader),
        )


def write_tsv(
    path,
    fields,
    rows,
):
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(rows)


def write_json(
    path,
    payload,
):
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def load_targets(repo):
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

    return compatible_rows

def batch_slice(
    rows,
    batch_index,
):
    batch_count = (
        len(rows)
        + BATCH_SIZE
        - 1
    ) // BATCH_SIZE

    if batch_count != EXPECTED_BATCHES:
        die(
            f"expected {EXPECTED_BATCHES} batches, "
            f"calculated {batch_count}"
        )

    if not (
        1
        <= batch_index
        <= batch_count
    ):
        die(
            f"--batch must be 1..{batch_count}"
        )

    start = (
        batch_index - 1
    ) * BATCH_SIZE

    selected = rows[
        start:start + BATCH_SIZE
    ]

    expected_count = (
        BATCH_SIZE
        if batch_index
        < batch_count
        else (
            EXPECTED_TARGETS
            - BATCH_SIZE
            * (batch_count - 1)
        )
    )

    if len(selected) != expected_count:
        die(
            f"batch {batch_index}: expected "
            f"{expected_count} targets, "
            f"found {len(selected)}"
        )

    return (
        batch_count,
        selected,
    )


def safe_extract(
    zip_path,
    destination,
):
    with zipfile.ZipFile(
        zip_path
    ) as archive:
        root = destination.resolve()

        bad_member = archive.testzip()

        if bad_member is not None:
            die(
                "ZIP CRC validation failed: "
                f"{bad_member}"
            )

        for member in archive.infolist():
            target = (
                destination
                / member.filename
            ).resolve()

            if (
                target != root
                and root not in target.parents
            ):
                die(
                    "unsafe path in ZIP archive: "
                    f"{member.filename!r}"
                )

        archive.extractall(
            destination
        )


def jsonl_records(path):
    records = []

    with path.open(
        encoding="utf-8",
    ) as handle:
        for line_number, line in enumerate(
            handle,
            1,
        ):
            if not line.strip():
                die(
                    f"{path}: blank JSONL line "
                    f"{line_number}"
                )

            try:
                obj = json.loads(
                    line
                )
            except json.JSONDecodeError as exc:
                die(
                    f"{path}: invalid JSONL line "
                    f"{line_number}: {exc}"
                )

            if not isinstance(
                obj,
                dict,
            ):
                die(
                    f"{path}: JSONL line "
                    f"{line_number} is not an object"
                )

            records.append(
                obj
            )

    if not records:
        die(
            f"{path}: no JSON records"
        )

    return records


def value(
    obj,
    *names,
):
    for name in names:
        if name in obj:
            return obj[
                name
            ]

    return None


def validate_metadata(
    package,
    target_rows,
):
    data_root = (
        package
        / "ncbi_dataset"
        / "data"
    )

    if not data_root.is_dir():
        die(
            "dehydrated package lacks "
            "ncbi_dataset/data"
        )

    report = (
        data_root
        / "assembly_data_report.jsonl"
    )

    if not report.is_file():
        die(
            "dehydrated package lacks "
            "assembly_data_report.jsonl"
        )

    expected = {
        row[
            "canonical_genbank_assembly_accession"
        ]: row[
            "source_biosample"
        ]
        for row in target_rows
    }

    records = jsonl_records(
        report
    )

    observed = {}

    for obj in records:
        accession = value(
            obj,
            "accession",
        )

        if not GCA_RE.fullmatch(
            accession or ""
        ):
            die(
                "invalid accession in assembly "
                f"report: {accession!r}"
            )

        if accession in observed:
            die(
                f"duplicate assembly-report "
                f"accession: {accession}"
            )

        info = (
            obj.get(
                "assemblyInfo"
            )
            or obj.get(
                "assembly_info"
            )
            or {}
        )

        status = value(
            info,
            "assemblyStatus",
            "assembly_status",
        )

        current = value(
            obj,
            "currentAccession",
            "current_accession",
        )

        level = value(
            info,
            "assemblyLevel",
            "assembly_level",
        )

        biosample_obj = (
            info.get(
                "biosample"
            )
            or {}
        )

        biosample = value(
            biosample_obj,
            "accession",
        )

        if accession not in expected:
            die(
                "assembly report contains "
                f"unexpected accession {accession}"
            )

        if (
            biosample
            != expected[accession]
        ):
            die(
                f"{accession}: BioSample mismatch; "
                f"expected {expected[accession]!r}, "
                f"got {biosample!r}"
            )

        if status != "current":
            die(
                f"{accession}: assembly status "
                f"is not current: {status!r}"
            )

        if current != accession:
            die(
                f"{accession}: currentAccession "
                f"mismatch: {current!r}"
            )

        if level != "Complete Genome":
            die(
                f"{accession}: assembly level "
                f"is not Complete Genome: {level!r}"
            )

        observed[
            accession
        ] = biosample

    if set(observed) != set(
        expected
    ):
        missing = sorted(
            set(expected)
            - set(observed)
        )

        extra = sorted(
            set(observed)
            - set(expected)
        )

        die(
            "assembly data report does not "
            "exactly match target set; "
            f"missing={missing!r}; extra={extra!r}"
        )

    return (
        data_root,
        observed,
        report,
    )


def parse_fetch_txt(
    package,
    expected_accessions,
):
    fetch_path = (
        package
        / "ncbi_dataset"
        / "fetch.txt"
    )

    if not fetch_path.is_file():
        die(
            "dehydrated package lacks "
            "ncbi_dataset/fetch.txt"
        )

    entries = []
    seen_paths = set()

    with fetch_path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.reader(
            handle,
            delimiter="\t",
        )

        for line_number, row in enumerate(
            reader,
            1,
        ):
            if len(row) != 3:
                die(
                    f"{fetch_path}: expected 3 fields "
                    f"on line {line_number}, got {len(row)}"
                )

            url, raw_size, relative = row

            try:
                expected_size = int(
                    raw_size
                )
            except ValueError:
                die(
                    f"{fetch_path}: invalid size "
                    f"on line {line_number}"
                )

            if expected_size < 0:
                die(
                    f"{fetch_path}: negative size "
                    f"on line {line_number}"
                )

            rel = Path(
                relative
            )

            if (
                rel.is_absolute()
                or ".." in rel.parts
            ):
                die(
                    f"{fetch_path}: unsafe destination "
                    f"{relative!r}"
                )

            if relative in seen_paths:
                die(
                    f"{fetch_path}: duplicate destination "
                    f"{relative!r}"
                )

            seen_paths.add(
                relative
            )

            parts = rel.parts

            if (
                len(parts) < 3
                or parts[0] != "data"
            ):
                die(
                    f"{fetch_path}: unexpected destination "
                    f"{relative!r}"
                )

            accession = parts[1]

            if accession not in expected_accessions:
                die(
                    f"{fetch_path}: destination belongs "
                    f"to unexpected accession {accession!r}"
                )

            entries.append(
                {
                    "url": url,
                    "expected_size":
                        expected_size,
                    "relative_path":
                        relative,
                    "accession":
                        accession,
                }
            )

    by_accession = {
        accession: []
        for accession in expected_accessions
    }

    for entry in entries:
        by_accession[
            entry["accession"]
        ].append(
            entry
        )

    missing = [
        accession
        for accession, values
        in by_accession.items()
        if not values
    ]

    if missing:
        die(
            "fetch.txt has no hydrated payload "
            f"entries for {missing!r}"
        )

    return (
        fetch_path,
        entries,
        by_accession,
    )


def fetch_entry_problem(
    package,
    entry,
):
    path = (
        package
        / "ncbi_dataset"
        / entry[
            "relative_path"
        ]
    )

    if not path.is_file():
        return "missing"

    size = path.stat().st_size

    if size <= 0:
        return "empty"

    expected_size = entry[
        "expected_size"
    ]

    if (
        expected_size > 0
        and size != expected_size
    ):
        return (
            f"size_mismatch:"
            f"{size}!={expected_size}"
        )

    return None


def unresolved_fetches(
    package,
    by_accession,
):
    unresolved = {}

    for accession, entries in (
        by_accession.items()
    ):
        problems = []

        for entry in entries:
            problem = fetch_entry_problem(
                package,
                entry,
            )

            if problem is not None:
                problems.append(
                    (
                        entry[
                            "relative_path"
                        ],
                        problem,
                    )
                )

        if problems:
            unresolved[
                accession
            ] = problems

    return unresolved


def remove_fetch_destinations(
    package,
    entries,
):
    for entry in entries:
        path = (
            package
            / "ncbi_dataset"
            / entry[
                "relative_path"
            ]
        )

        if path.is_file():
            path.unlink()


def read_fasta(path):
    sequences = {}

    identifier = None
    chunks = []

    def store():
        nonlocal identifier
        nonlocal chunks

        if identifier is None:
            return

        if identifier in sequences:
            die(
                f"{path}: duplicate FASTA identifier "
                f"{identifier!r}"
            )

        sequence = "".join(
            chunks
        ).upper()

        if not sequence:
            die(
                f"{path}: empty FASTA sequence "
                f"{identifier!r}"
            )

        invalid = (
            set(sequence)
            - IUPAC_DNA
        )

        if invalid:
            die(
                f"{path}: unsupported nucleotide symbols "
                f"in {identifier}: {sorted(invalid)!r}"
            )

        sequences[
            identifier
        ] = sequence

    with path.open(
        encoding="utf-8",
    ) as handle:
        for line_number, line in enumerate(
            handle,
            1,
        ):
            if line.startswith(">"):
                store()

                header = (
                    line[1:]
                    .strip()
                )

                if not header:
                    die(
                        f"{path}: empty FASTA header "
                        f"at line {line_number}"
                    )

                identifier = (
                    header.split()[0]
                )

                chunks = []

            else:
                sequence = "".join(
                    line.split()
                )

                if not sequence:
                    continue

                if identifier is None:
                    die(
                        f"{path}: sequence before "
                        "first FASTA header"
                    )

                chunks.append(
                    sequence
                )

    store()

    if not sequences:
        die(
            f"{path}: no FASTA records"
        )

    return sequences


def read_gbff_records(path):
    records = {}

    length = None
    topology = None
    version = None
    in_record = False
    in_origin = False
    saw_origin = False
    origin_parts = []

    with path.open(
        encoding="utf-8",
        errors="strict",
    ) as handle:
        for line_number, line in enumerate(
            handle,
            1,
        ):
            if line.startswith("LOCUS"):
                if in_record:
                    die(
                        f"{path}: LOCUS before "
                        "previous record ended"
                    )

                tokens = (
                    line.split()
                )

                if len(tokens) < 3:
                    die(
                        f"{path}: malformed LOCUS "
                        f"line {line_number}"
                    )

                try:
                    length = int(
                        tokens[2]
                    )
                except ValueError:
                    die(
                        f"{path}: invalid LOCUS length "
                        f"at line {line_number}"
                    )

                topologies = [
                    token.lower()
                    for token in tokens
                    if token.lower()
                    in {
                        "linear",
                        "circular",
                    }
                ]

                if len(topologies) > 1:
                    die(
                        f"{path}: multiple topology tokens "
                        f"on LOCUS line {line_number}"
                    )

                topology = (
                    topologies[0]
                    if topologies
                    else "unspecified"
                )

                version = None
                in_record = True
                in_origin = False
                saw_origin = False
                origin_parts = []

            elif line.startswith(
                "VERSION"
            ):
                if not in_record:
                    die(
                        f"{path}: VERSION outside "
                        "a LOCUS record"
                    )

                tokens = (
                    line.split()
                )

                if len(tokens) < 2:
                    die(
                        f"{path}: malformed VERSION "
                        f"line {line_number}"
                    )

                version = (
                    tokens[1]
                )

            elif line.startswith(
                "ORIGIN"
            ):
                if not in_record:
                    die(
                        f"{path}: ORIGIN outside "
                        "a LOCUS record"
                    )

                if in_origin:
                    die(
                        f"{path}: duplicate ORIGIN "
                        f"at line {line_number}"
                    )

                in_origin = True
                saw_origin = True
                origin_parts = []

            elif line.startswith(
                "//"
            ):
                if not in_record:
                    die(
                        f"{path}: record terminator "
                        "without LOCUS"
                    )

                if not version:
                    die(
                        f"{path}: GBFF record lacks "
                        "VERSION"
                    )

                if not saw_origin:
                    die(
                        f"{path}: GBFF record "
                        f"{version!r} lacks ORIGIN"
                    )

                if version in records:
                    die(
                        f"{path}: duplicate GBFF VERSION "
                        f"{version}"
                    )

                sequence = (
                    "".join(
                        origin_parts
                    )
                    .upper()
                )

                if len(sequence) != length:
                    die(
                        f"{path}: GBFF ORIGIN length "
                        f"for {version!r} is "
                        f"{len(sequence)}, but LOCUS "
                        f"reports {length}"
                    )

                records[
                    version
                ] = {
                    "length": length,
                    "topology": topology,
                    "sequence": sequence,
                }

                length = None
                topology = None
                version = None
                in_record = False
                in_origin = False
                saw_origin = False
                origin_parts = []

            elif in_origin:
                origin_parts.append(
                    "".join(
                        character
                        for character in line
                        if character.isalpha()
                    )
                )

    if in_record:
        die(
            f"{path}: unterminated GBFF record"
        )

    if not records:
        die(
            f"{path}: no GBFF records"
        )

    return records


def retrieve_efetch_gbff(
    acc_dir,
    accession,
    component_accessions,
):
    ordered_components = sorted(
        component_accessions
    )

    if not ordered_components:
        die(
            f"{accession}: cannot use EFetch fallback "
            "without component accessions"
        )

    gbff = (
        acc_dir
        / f"{accession}_efetch_components.gbff"
    )

    provenance = (
        acc_dir
        / f"{accession}_efetch_components.json"
    )

    if gbff.exists() or provenance.exists():
        if not (
            gbff.is_file()
            and provenance.is_file()
        ):
            die(
                f"{accession}: incomplete existing "
                "EFetch fallback payload"
            )

        try:
            existing = json.loads(
                provenance.read_text(
                    encoding="utf-8"
                )
            )
        except (
            json.JSONDecodeError,
            OSError,
        ) as exc:
            die(
                f"{accession}: invalid existing "
                f"EFetch provenance: {exc}"
            )

        if (
            existing.get(
                "requested_component_accessions"
            )
            != ordered_components
        ):
            die(
                f"{accession}: existing EFetch "
                "component request differs from "
                "sequence report"
            )

        if (
            existing.get(
                "combined_gbff_sha256"
            )
            != sha256_file(
                gbff
            )
        ):
            die(
                f"{accession}: existing EFetch GBFF "
                "hash does not match provenance"
            )

        return (
            gbff,
            provenance,
        )

    chunks = [
        ordered_components[
            start:
            start + EFETCH_CHUNK_SIZE
        ]
        for start in range(
            0,
            len(ordered_components),
            EFETCH_CHUNK_SIZE,
        )
    ]

    combined_parts = []
    chunk_events = []

    for chunk_index, chunk in enumerate(
        chunks,
        1,
    ):
        encoded = urllib_parse.urlencode(
            {
                "db": "nuccore",
                "id": ",".join(
                    chunk
                ),
                "rettype": "gbwithparts",
                "retmode": "text",
                "tool": "project_finch",
            }
        ).encode(
            "ascii"
        )

        request = urllib_request.Request(
            EFETCH_ENDPOINT,
            data=encoded,
            headers={
                "User-Agent":
                    "Project-FINCH Experiment-0",
            },
            method="POST",
        )

        response_body = None
        last_error = None

        for attempt in range(
            1,
            EFETCH_RETRY_ROUNDS + 1,
        ):
            try:
                with urllib_request.urlopen(
                    request,
                    timeout=EFETCH_TIMEOUT_SECONDS,
                ) as response:
                    response_body = (
                        response.read()
                    )

                if not response_body:
                    raise OSError(
                        "empty EFetch response"
                    )

                last_error = None
                break

            except (
                urllib_error.URLError,
                TimeoutError,
                OSError,
            ) as exc:
                last_error = exc

                if (
                    attempt
                    < EFETCH_RETRY_ROUNDS
                ):
                    time.sleep(
                        EFETCH_RETRY_DELAY_SECONDS
                        * attempt
                    )

        if response_body is None:
            die(
                f"{accession}: EFetch fallback "
                f"chunk {chunk_index} failed after "
                f"{EFETCH_RETRY_ROUNDS} attempts: "
                f"{last_error}"
            )

        normalized = (
            response_body.rstrip()
            + b"\n"
        )

        combined_parts.append(
            normalized
        )

        chunk_events.append(
            {
                "chunk_index":
                    chunk_index,
                "requested_component_accessions":
                    chunk,
                "response_size_bytes":
                    len(
                        response_body
                    ),
                "response_sha256":
                    hashlib.sha256(
                        response_body
                    ).hexdigest(),
            }
        )

        if chunk_index < len(chunks):
            time.sleep(
                EFETCH_REQUEST_INTERVAL_SECONDS
            )

    combined = b"".join(
        combined_parts
    )

    if not combined:
        die(
            f"{accession}: EFetch fallback "
            "produced an empty GBFF"
        )

    gbff_partial = (
        gbff.with_name(
            gbff.name + ".partial"
        )
    )

    gbff_partial.write_bytes(
        combined
    )

    retrieved_records = read_gbff_records(
        gbff_partial
    )

    if (
        set(
            retrieved_records
        )
        != set(
            ordered_components
        )
    ):
        missing = sorted(
            set(
                ordered_components
            )
            - set(
                retrieved_records
            )
        )

        extra = sorted(
            set(
                retrieved_records
            )
            - set(
                ordered_components
            )
        )

        gbff_partial.unlink(
            missing_ok=True
        )

        die(
            f"{accession}: EFetch fallback "
            "component set mismatch; "
            f"missing={missing!r}; "
            f"extra={extra!r}"
        )

    gbff_partial.replace(
        gbff
    )

    provenance_payload = {
        "schema_version":
            1,
        "retrieval_method":
            "ncbi_efetch_nuccore",
        "endpoint":
            EFETCH_ENDPOINT,
        "db":
            "nuccore",
        "rettype":
            "gbwithparts",
        "retmode":
            "text",
        "assembly_accession":
            accession,
        "requested_component_accessions":
            ordered_components,
        "requested_component_count":
            len(
                ordered_components
            ),
        "chunk_size":
            EFETCH_CHUNK_SIZE,
        "chunk_count":
            len(
                chunks
            ),
        "chunks":
            chunk_events,
        "combined_gbff_size_bytes":
            gbff.stat().st_size,
        "combined_gbff_sha256":
            sha256_file(
                gbff
            ),
        "retrieved_at_utc":
            utc_now(),
    }

    provenance_partial = (
        provenance.with_name(
            provenance.name + ".partial"
        )
    )

    provenance_partial.write_text(
        json.dumps(
            provenance_payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    provenance_partial.replace(
        provenance
    )

    return (
        gbff,
        provenance,
    )


def validate_candidate_payload(
    data_root,
    target,
    observed_biosample,
):
    accession = target[
        "canonical_genbank_assembly_accession"
    ]

    acc_dir = (
        data_root
        / accession
    )

    if not acc_dir.is_dir():
        die(
            f"{accession}: missing hydrated "
            "accession directory"
        )

    sequence_report = (
        acc_dir
        / "sequence_report.jsonl"
    )

    if not sequence_report.is_file():
        die(
            f"{accession}: missing "
            "sequence_report.jsonl"
        )

    seq_rows = jsonl_records(
        sequence_report
    )

    sequence_report_lengths = {}
    primary_components = set()
    auxiliary_components = {}

    for row in seq_rows:
        returned = value(
            row,
            "assemblyAccession",
            "assembly_accession",
        )

        if returned != accession:
            die(
                f"{accession}: sequence report "
                f"returned accession {returned!r}"
            )

        unit = value(
            row,
            "assemblyUnit",
            "assembly_unit",
        )

        if not unit:
            die(
                f"{accession}: sequence report "
                "record lacks assembly unit"
            )

        component = value(
            row,
            "genbankAccession",
            "genbank_accession",
        )

        if not component:
            die(
                f"{accession}: sequence report "
                "record lacks GenBank accession"
            )

        if component in sequence_report_lengths:
            die(
                f"{accession}: duplicate component "
                f"accession {component!r}"
            )

        raw_length = value(
            row,
            "length",
        )

        if raw_length is None:
            component_length = None
        else:
            try:
                component_length = int(
                    raw_length
                )
            except (
                TypeError,
                ValueError,
            ):
                die(
                    f"{accession}: invalid component "
                    f"length {raw_length!r}"
                )

        sequence_report_lengths[
            component
        ] = component_length

        if unit == "Primary Assembly":
            primary_components.add(
                component
            )
        else:
            auxiliary_components[
                component
            ] = str(unit)

    if not primary_components:
        die(
            f"{accession}: sequence report contains "
            "no Primary Assembly records"
        )

    missing_length_components = sorted(
        component
        for component, component_length
        in sequence_report_lengths.items()
        if component_length is None
    )

    present_length_records = (
        len(sequence_report_lengths)
        - len(missing_length_components)
    )

    all_fasta_files = sorted(
        acc_dir.glob(
            "*.fna"
        )
    )

    derived_fasta_files = {
        path
        for path in all_fasta_files
        if path.name.endswith(
            (
                "_cds_from_genomic.fna",
                "_rna_from_genomic.fna",
            )
        )
    }

    fasta_files = [
        path
        for path in all_fasta_files
        if path not in derived_fasta_files
    ]

    efetch_gbff = (
        acc_dir
        / f"{accession}_efetch_components.gbff"
    )

    efetch_provenance = (
        acc_dir
        / f"{accession}_efetch_components.json"
    )

    gbff_files = sorted(
        path
        for path in acc_dir.glob(
            "*.gbff"
        )
        if path != efetch_gbff
    )

    if len(fasta_files) != 1:
        die(
            f"{accession}: expected exactly one "
            "genomic FASTA after excluding NCBI "
            "CDS/RNA derived FASTAs, found "
            f"{len(fasta_files)}"
        )

    if len(gbff_files) > 1:
        die(
            f"{accession}: expected at most one "
            f"GBFF, found {len(gbff_files)}"
        )

    fasta = fasta_files[0]

    gbff_source = (
        "ncbi_datasets"
    )
    gbff_provenance = None

    if len(gbff_files) == 1:
        if (
            efetch_gbff.exists()
            or efetch_provenance.exists()
        ):
            die(
                f"{accession}: both NCBI Datasets "
                "GBFF and EFetch fallback payload "
                "are present"
            )

        gbff = gbff_files[0]
    else:
        (
            gbff,
            gbff_provenance,
        ) = retrieve_efetch_gbff(
            acc_dir,
            accession,
            sequence_report_lengths,
        )

        gbff_source = (
            "ncbi_efetch_nuccore"
        )

    if fasta.stat().st_size <= 0:
        die(
            f"{accession}: genomic FASTA is empty"
        )

    if gbff.stat().st_size <= 0:
        die(
            f"{accession}: GBFF is empty"
        )

    sequences = read_fasta(
        fasta
    )

    fasta_lengths = {
        component: len(sequence)
        for component, sequence
        in sequences.items()
    }

    if set(fasta_lengths) != set(sequence_report_lengths):
        die(
            f"{accession}: FASTA components do not "
            "match sequence report"
        )

    gbff_records = read_gbff_records(
        gbff
    )

    gbff_lengths = {
        component: row["length"]
        for component, row
        in gbff_records.items()
    }

    if set(gbff_lengths) != set(sequence_report_lengths):
        die(
            f"{accession}: GBFF components do not "
            "match sequence report"
        )

    if fasta_lengths != gbff_lengths:
        die(
            f"{accession}: FASTA and GBFF component "
            "lengths do not agree"
        )

    for component in sorted(
        fasta_lengths
    ):
        if (
            sequences[
                component
            ]
            != gbff_records[
                component
            ][
                "sequence"
            ]
        ):
            die(
                f"{accession}: FASTA and GBFF ORIGIN "
                f"sequences differ for "
                f"{component!r}"
            )

    for component, reported_length in (
        sequence_report_lengths.items()
    ):
        if reported_length is None:
            continue

        observed_length = fasta_lengths[
            component
        ]

        if observed_length != reported_length:
            die(
                f"{accession}: sequence report length "
                f"for {component!r} is "
                f"{reported_length}, but FASTA and "
                f"GBFF agree on {observed_length}"
            )

    package_total_length = sum(
        len(sequence)
        for sequence in sequences.values()
    )

    auxiliary_total_length = sum(
        fasta_lengths[component]
        for component in auxiliary_components
    )

    component_rows = []

    ambiguous_total = 0
    ambiguous_symbols_all = set()

    circular = 0
    linear = 0
    unspecified = 0

    total_length = 0

    for component in sorted(
        primary_components
    ):
        sequence = sequences[
            component
        ]

        topology = (
            gbff_records[
                component
            ][
                "topology"
            ]
        )

        if topology == "circular":
            circular += 1
        elif topology == "linear":
            linear += 1
        elif topology == "unspecified":
            unspecified += 1
        else:
            die(
                f"{accession}: impossible topology "
                f"{topology!r}"
            )

        ambiguous_symbols = (
            set(sequence)
            - PRIMARY_DNA
        )

        ambiguous_count = sum(
            1
            for base in sequence
            if base not in PRIMARY_DNA
        )

        ambiguous_total += (
            ambiguous_count
        )

        ambiguous_symbols_all.update(
            ambiguous_symbols
        )

        total_length += len(
            sequence
        )

        component_rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "component_genbank_accession":
                    component,
                "length":
                    str(len(sequence)),
                "topology":
                    topology,
                "ambiguous_base_count":
                    str(ambiguous_count),
                "ambiguous_symbols":
                    (
                        ",".join(
                            sorted(
                                ambiguous_symbols
                            )
                        )
                        if ambiguous_symbols
                        else "none"
                    ),
                "sequence_sha256":
                    sha256_text(sequence),
            }
        )

    exclusion_reasons = []

    if ambiguous_total:
        exclusion_reasons.append(
            "ambiguous_nucleotide"
        )

    if unspecified:
        exclusion_reasons.append(
            "unresolved_topology"
        )

    eligible = (
        not exclusion_reasons
    )

    candidate_row = {
        "canonical_genbank_assembly_accession":
            accession,
        "expected_biosample":
            target[
                "source_biosample"
            ],
        "observed_biosample":
            observed_biosample,
        "assembly_status":
            "current",
        "current_accession":
            accession,
        "assembly_level":
            "Complete Genome",
        "sequence_report_records":
            str(len(seq_rows)),
        "sequence_report_length_present_records":
            str(present_length_records),
        "sequence_report_length_missing_records":
            str(len(missing_length_components)),
        "sequence_report_length_missing_components":
            (
                "|".join(
                    missing_length_components
                )
                if missing_length_components
                else "none"
            ),
        "primary_assembly_records":
            str(len(primary_components)),
        "auxiliary_assembly_records":
            str(len(auxiliary_components)),
        "auxiliary_assembly_units":
            (
                "|".join(
                    sorted(
                        set(
                            auxiliary_components.values()
                        )
                    )
                )
                if auxiliary_components
                else "none"
            ),
        "auxiliary_component_accessions":
            (
                "|".join(
                    sorted(
                        auxiliary_components
                    )
                )
                if auxiliary_components
                else "none"
            ),
        "fasta_records":
            str(len(sequences)),
        "gbff_records":
            str(len(gbff_records)),
        "total_sequence_length":
            str(total_length),
        "package_total_sequence_length":
            str(package_total_length),
        "auxiliary_total_sequence_length":
            str(auxiliary_total_length),
        "topology_circular_records":
            str(circular),
        "topology_linear_records":
            str(linear),
        "topology_unspecified_records":
            str(unspecified),
        "ambiguous_base_count":
            str(ambiguous_total),
        "ambiguous_symbols":
            (
                ",".join(
                    sorted(
                        ambiguous_symbols_all
                    )
                )
                if ambiguous_symbols_all
                else "none"
            ),
        "sequence_eligibility":
            (
                "eligible"
                if eligible
                else "ineligible"
            ),
        "exclusion_reasons":
            (
                "|".join(
                    exclusion_reasons
                )
                if exclusion_reasons
                else "none"
            ),
        "fasta_file":
            fasta.name,
        "fasta_sha256":
            sha256_file(
                fasta
            ),
        "gbff_file":
            gbff.name,
        "gbff_sha256":
            sha256_file(
                gbff
            ),
        "gbff_source":
            gbff_source,
        "gbff_provenance_file":
            (
                gbff_provenance.name
                if gbff_provenance
                is not None
                else "none"
            ),
        "gbff_provenance_sha256":
            (
                sha256_file(
                    gbff_provenance
                )
                if gbff_provenance
                is not None
                else "none"
            ),
        "sequence_report_sha256":
            sha256_file(
                sequence_report
            ),
        "result":
            "PASS",
    }

    return (
        candidate_row,
        component_rows,
    )


def package_file_manifest(
    package,
):
    rows = []

    for path in sorted(
        item
        for item in package.rglob(
            "*"
        )
        if item.is_file()
    ):
        relative = (
            path.relative_to(
                package
            )
            .as_posix()
        )

        rows.append(
            {
                "path":
                    relative,
                "size_bytes":
                    str(
                        path.stat().st_size
                    ),
                "sha256":
                    sha256_file(
                        path
                    ),
            }
        )

    return rows


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--batch",
        type=int,
        required=True,
        help=(
            "1-based deterministic batch index"
        ),
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "default: "
            f"{DEFAULT_OUTPUT}"
        ),
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "resume hydration/validation from an "
            "existing batch-NNN.partial directory"
        ),
    )

    parser.add_argument(
        "--plan",
        action="store_true",
        help=(
            "validate inputs and print the deterministic "
            "batch slice without network retrieval"
        ),
    )

    args = parser.parse_args()

    script_path = Path(
        __file__
    ).resolve()

    repo = (
        script_path.parents[2]
    )

    targets = load_targets(
        repo
    )

    (
        batch_count,
        target_rows,
    ) = batch_slice(
        targets,
        args.batch,
    )

    accessions = [
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in target_rows
    ]

    batch_id = (
        f"batch-{args.batch:03d}"
    )

    if args.plan:
        print(
            "PASS | sequence-validation "
            "batch plan"
        )
        print(
            f"batch={args.batch}"
        )
        print(
            f"batch_id={batch_id}"
        )
        print(
            f"batch_count={batch_count}"
        )
        print(
            f"requested_accessions="
            f"{len(accessions)}"
        )
        print(
            f"first_accession="
            f"{accessions[0]}"
        )
        print(
            f"last_accession="
            f"{accessions[-1]}"
        )
        print(
            "target_manifest_sha256="
            f"{TARGET_MANIFEST_SHA256}"
        )
        return

    git_head = production_git_head(
        repo
    )

    datasets = datasets_prefix(
        repo
    )

    output_root = (
        args.output_root
    )

    if not output_root.is_absolute():
        output_root = (
            repo
            / output_root
        ).resolve()
    else:
        output_root = (
            output_root.resolve()
        )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_dir = (
        output_root
        / batch_id
    )

    partial_dir = (
        output_root
        / f"{batch_id}.partial"
    )

    accessions_txt = (
        partial_dir
        / "accessions.txt"
    )

    dehydrated_zip = (
        partial_dir
        / "dehydrated.zip"
    )

    partial_zip = (
        partial_dir
        / "dehydrated.zip.partial"
    )

    package = (
        partial_dir
        / "package"
    )

    attempt_path = (
        partial_dir
        / "attempt-origin.json"
    )

    if final_dir.exists():
        die(
            f"completed output already exists: "
            f"{final_dir}"
        )

    script_relative = (
        script_path
        .relative_to(
            repo
        )
    )

    script_sha = sha256_file(
        script_path
    )

    expected_accessions_text = (
        "".join(
            f"{accession}\n"
            for accession in accessions
        )
    )

    if args.resume:
        if not partial_dir.is_dir():
            die(
                "cannot resume because partial "
                f"output does not exist: {partial_dir}"
            )

        if partial_zip.exists():
            die(
                "dehydrated download was interrupted "
                "before completion; inspect and remove "
                f"{partial_dir} before a fresh attempt"
            )

        for required in (
            accessions_txt,
            dehydrated_zip,
            package,
            attempt_path,
        ):
            if not required.exists():
                die(
                    "partial batch lacks required "
                    f"resume path: {required}"
                )

        if (
            accessions_txt.read_text(
                encoding="utf-8"
            )
            != expected_accessions_text
        ):
            die(
                "partial batch accession list does "
                "not match deterministic target slice"
            )

        try:
            attempt = json.loads(
                attempt_path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as exc:
            die(
                f"invalid attempt-origin.json: {exc}"
            )

        expected_origin = {
            "schema_version":
                SCHEMA_VERSION,
            "batch_index":
                args.batch,
            "batch_id":
                batch_id,
            "target_manifest_sha256":
                TARGET_MANIFEST_SHA256,
            "accessions_sha256":
                sha256_file(
                    accessions_txt
                ),
            "origin_git_head":
                git_head,
            "snapshot_script_sha256":
                script_sha,
            "environment_explicit_sha256":
                ENVIRONMENT_EXPLICIT_SHA256,
            "datasets_version":
                DATASETS_VERSION,
        }

        for key, expected in (
            expected_origin.items()
        ):
            observed = attempt.get(
                key
            )

            if observed != expected:
                die(
                    f"attempt-origin mismatch for "
                    f"{key}: expected {expected!r}, "
                    f"got {observed!r}"
                )

        recorded_zip_sha = (
            attempt.get(
                "dehydrated_zip_sha256"
            )
        )

        if (
            not recorded_zip_sha
            or recorded_zip_sha
            != sha256_file(
                dehydrated_zip
            )
        ):
            die(
                "dehydrated ZIP checksum does "
                "not match attempt origin"
            )

    else:
        if partial_dir.exists():
            die(
                "partial output already exists: "
                f"{partial_dir}; use --resume "
                "after inspection or remove it "
                "before a fresh attempt"
            )

        partial_dir.mkdir(
            parents=True
        )

        accessions_txt.write_text(
            expected_accessions_text,
            encoding="utf-8",
        )

        attempt = {
            "schema_version":
                SCHEMA_VERSION,
            "recorded_at_utc":
                utc_now(),
            "created_before_network_retrieval":
                True,
            "origin_git_head":
                git_head,
            "datasets_version":
                DATASETS_VERSION,
            "snapshot_script":
                script_relative.as_posix(),
            "snapshot_script_sha256":
                script_sha,
            "environment_explicit":
                ENVIRONMENT_EXPLICIT.as_posix(),
            "environment_explicit_sha256":
                ENVIRONMENT_EXPLICIT_SHA256,
            "target_manifest":
                TARGET_MANIFEST.as_posix(),
            "target_manifest_sha256":
                TARGET_MANIFEST_SHA256,
            "target_count":
                EXPECTED_TARGETS,
            "batch_index":
                args.batch,
            "batch_id":
                batch_id,
            "batch_count":
                batch_count,
            "batch_size":
                BATCH_SIZE,
            "requested_accessions":
                len(accessions),
            "first_accession":
                accessions[0],
            "last_accession":
                accessions[-1],
            "accessions_sha256":
                sha256_file(
                    accessions_txt
                ),
            "include": [
                "genome",
                "gbff",
                "seq-report",
            ],
            "assembly_source":
                "GenBank",
            "dehydrated_zip_sha256":
                None,
        }

        write_json(
            attempt_path,
            attempt,
        )

        download_cmd = datasets + [
            "download",
            "genome",
            "accession",
            "--inputfile",
            str(
                accessions_txt
            ),
            "--include",
            "genome,gbff,seq-report",
            "--dehydrated",
            "--filename",
            str(
                partial_zip
            ),
            "--no-progressbar",
        ]

        write_json(
            partial_dir
            / "download-command.json",
            download_cmd,
        )

        print(
            f"download | {batch_id} | "
            f"targets={len(accessions)}"
        )

        sys.stdout.flush()

        result = subprocess.run(
            download_cmd,
            cwd=repo,
            text=True,
            capture_output=True,
        )

        (
            partial_dir
            / "download.stdout.txt"
        ).write_text(
            result.stdout,
            encoding="utf-8",
        )

        (
            partial_dir
            / "download.stderr.txt"
        ).write_text(
            result.stderr,
            encoding="utf-8",
        )

        (
            partial_dir
            / "download-exit-code.txt"
        ).write_text(
            f"{result.returncode}\n",
            encoding="utf-8",
        )

        if result.returncode != 0:
            die(
                "datasets dehydrated download "
                f"failed with exit code "
                f"{result.returncode}; partial "
                "attempt retained for inspection"
            )

        if not partial_zip.is_file():
            die(
                "datasets reported success but "
                "dehydrated ZIP is absent"
            )

        try:
            with zipfile.ZipFile(
                partial_zip
            ) as archive:
                bad_member = (
                    archive.testzip()
                )

                if bad_member is not None:
                    die(
                        "dehydrated ZIP CRC failure: "
                        f"{bad_member}"
                    )

        except zipfile.BadZipFile as exc:
            die(
                "invalid dehydrated ZIP: "
                f"{exc}"
            )

        partial_zip.replace(
            dehydrated_zip
        )

        package.mkdir(
            parents=True
        )

        safe_extract(
            dehydrated_zip,
            package,
        )

        attempt[
            "dehydrated_zip_sha256"
        ] = sha256_file(
            dehydrated_zip
        )

        write_json(
            attempt_path,
            attempt,
        )

    (
        data_root,
        observed_biosamples,
        assembly_report,
    ) = validate_metadata(
        package,
        target_rows,
    )

    expected_set = set(
        accessions
    )

    (
        fetch_path,
        fetch_entries,
        fetch_by_accession,
    ) = parse_fetch_txt(
        package,
        expected_set,
    )

    unresolved_before = (
        unresolved_fetches(
            package,
            fetch_by_accession,
        )
    )

    rehydrate_cmd = datasets + [
        "rehydrate",
        "--directory",
        str(
            package
        ),
        "--max-workers",
        str(
            WORKERS
        ),
        "--no-progressbar",
    ]

    broad_exit_code = None

    if (
        not args.resume
        or unresolved_before
    ):
        print(
            f"rehydrate | {batch_id} | "
            f"unresolved_before="
            f"{len(unresolved_before)}"
        )

        sys.stdout.flush()

        result = subprocess.run(
            rehydrate_cmd,
            cwd=repo,
            text=True,
            capture_output=True,
        )

        broad_exit_code = (
            result.returncode
        )

        (
            partial_dir
            / "rehydrate.stdout.txt"
        ).write_text(
            result.stdout,
            encoding="utf-8",
        )

        (
            partial_dir
            / "rehydrate.stderr.txt"
        ).write_text(
            result.stderr,
            encoding="utf-8",
        )

        (
            partial_dir
            / "rehydrate-exit-code.txt"
        ).write_text(
            f"{result.returncode}\n",
            encoding="utf-8",
        )

    unresolved_after_broad = (
        unresolved_fetches(
            package,
            fetch_by_accession,
        )
    )

    retry_events = []

    for accession in sorted(
        unresolved_after_broad
    ):
        problem = (
            unresolved_after_broad[
                accession
            ]
        )

        for attempt_number in range(
            1,
            TARGETED_RETRY_ROUNDS + 1,
        ):
            remove_fetch_destinations(
                package,
                fetch_by_accession[
                    accession
                ],
            )

            target_cmd = datasets + [
                "rehydrate",
                "--directory",
                str(
                    package
                ),
                "--match",
                accession,
                "--max-workers",
                "1",
                "--no-progressbar",
            ]

            result = subprocess.run(
                target_cmd,
                cwd=repo,
                text=True,
                capture_output=True,
            )

            remaining = (
                unresolved_fetches(
                    package,
                    {
                        accession:
                            fetch_by_accession[
                                accession
                            ]
                    },
                )
            )

            retry_events.append(
                {
                    "assembly_accession":
                        accession,
                    "attempt":
                        attempt_number,
                    "exit_code":
                        result.returncode,
                    "result":
                        (
                            "valid"
                            if not remaining
                            else repr(
                                remaining[
                                    accession
                                ]
                            )
                        ),
                }
            )

            if not remaining:
                problem = None
                break

            problem = remaining[
                accession
            ]

        if problem is not None:
            die(
                f"{accession}: hydrated payload "
                "remains incomplete after targeted "
                f"recovery: {problem!r}"
            )

    unresolved_final = (
        unresolved_fetches(
            package,
            fetch_by_accession,
        )
    )

    if unresolved_final:
        die(
            "hydrated package remains incomplete: "
            f"{unresolved_final!r}"
        )

    candidate_rows = []
    component_rows = []

    for target in target_rows:
        accession = target[
            "canonical_genbank_assembly_accession"
        ]

        (
            candidate,
            components,
        ) = validate_candidate_payload(
            data_root,
            target,
            observed_biosamples[
                accession
            ],
        )

        candidate_rows.append(
            candidate
        )

        component_rows.extend(
            components
        )

    if [
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in candidate_rows
    ] != accessions:
        die(
            "candidate audit does not preserve "
            "target accession order"
        )

    candidate_audit_path = (
        partial_dir
        / "candidate-sequence-audit.tsv"
    )

    component_audit_path = (
        partial_dir
        / "component-sequence-audit.tsv"
    )

    write_tsv(
        candidate_audit_path,
        CANDIDATE_AUDIT_FIELDS,
        candidate_rows,
    )

    write_tsv(
        component_audit_path,
        COMPONENT_AUDIT_FIELDS,
        component_rows,
    )

    package_files = (
        package_file_manifest(
            package
        )
    )

    package_files_path = (
        partial_dir
        / "package-files.tsv"
    )

    write_tsv(
        package_files_path,
        PACKAGE_FILE_FIELDS,
        package_files,
    )

    eligibility_counts = Counter(
        row[
            "sequence_eligibility"
        ]
        for row in candidate_rows
    )

    exclusion_counts = Counter()

    for row in candidate_rows:
        if row[
            "exclusion_reasons"
        ] == "none":
            continue

        for reason in row[
            "exclusion_reasons"
        ].split("|"):
            exclusion_counts[
                reason
            ] += 1

    topology_counts = Counter()

    for row in component_rows:
        topology_counts[
            row[
                "topology"
            ]
        ] += 1

    total_bases = sum(
        int(
            row[
                "total_sequence_length"
            ]
        )
        for row in candidate_rows
    )

    total_ambiguous = sum(
        int(
            row[
                "ambiguous_base_count"
            ]
        )
        for row in candidate_rows
    )

    gbff_source_counts = Counter(
        row[
            "gbff_source"
        ]
        for row in candidate_rows
    )

    gbff_fallback_accessions = [
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in candidate_rows
        if row[
            "gbff_source"
        ] == "ncbi_efetch_nuccore"
    ]

    summary = {
        "schema_version":
            SCHEMA_VERSION,
        "datasets_version":
            DATASETS_VERSION,
        "environment_explicit":
            ENVIRONMENT_EXPLICIT.as_posix(),
        "environment_explicit_sha256":
            ENVIRONMENT_EXPLICIT_SHA256,
        "git_head":
            git_head,
        "snapshot_script":
            script_relative.as_posix(),
        "snapshot_script_sha256":
            script_sha,
        "target_manifest":
            TARGET_MANIFEST.as_posix(),
        "target_manifest_sha256":
            TARGET_MANIFEST_SHA256,
        "target_count":
            EXPECTED_TARGETS,
        "batch_index":
            args.batch,
        "batch_id":
            batch_id,
        "batch_count":
            batch_count,
        "batch_size":
            BATCH_SIZE,
        "requested_accessions":
            len(accessions),
        "first_accession":
            accessions[0],
        "last_accession":
            accessions[-1],
        "accessions_sha256":
            sha256_file(
                accessions_txt
            ),
        "assembly_data_report_sha256":
            sha256_file(
                assembly_report
            ),
        "fetch_txt_sha256":
            sha256_file(
                fetch_path
            ),
        "fetch_entries":
            len(
                fetch_entries
            ),
        "dehydrated_zip_size_bytes":
            dehydrated_zip.stat().st_size,
        "dehydrated_zip_sha256":
            sha256_file(
                dehydrated_zip
            ),
        "rehydrate_workers":
            WORKERS,
        "initial_unresolved_accessions":
            len(
                unresolved_before
            ),
        "broad_rehydrate_exit_code":
            broad_exit_code,
        "targeted_retry_rounds":
            TARGETED_RETRY_ROUNDS,
        "targeted_retry_events":
            retry_events,
        "gbff_source_counts":
            dict(
                sorted(
                    gbff_source_counts.items()
                )
            ),
        "gbff_fallback_accessions":
            gbff_fallback_accessions,
        "candidate_records":
            len(
                candidate_rows
            ),
        "component_records":
            len(
                component_rows
            ),
        "total_sequence_bases":
            total_bases,
        "ambiguous_base_count":
            total_ambiguous,
        "sequence_eligibility_counts":
            dict(
                sorted(
                    eligibility_counts.items()
                )
            ),
        "sequence_exclusion_reason_counts":
            dict(
                sorted(
                    exclusion_counts.items()
                )
            ),
        "topology_counts":
            dict(
                sorted(
                    topology_counts.items()
                )
            ),
        "candidate_sequence_audit_sha256":
            sha256_file(
                candidate_audit_path
            ),
        "component_sequence_audit_sha256":
            sha256_file(
                component_audit_path
            ),
        "package_files":
            len(
                package_files
            ),
        "package_files_sha256":
            sha256_file(
                package_files_path
            ),
        "attempt_origin_sha256":
            sha256_file(
                attempt_path
            ),
        "execution_completed_at_utc":
            utc_now(),
    }

    summary_path = (
        partial_dir
        / "batch-summary.json"
    )

    write_json(
        summary_path,
        summary,
    )

    partial_dir.replace(
        final_dir
    )

    print(
        f"PASS | {batch_id}: "
        f"{len(accessions)} requested assemblies"
    )

    print(
        f"PASS | sequence payloads complete; "
        f"components={len(component_rows)}"
    )

    print(
        "sequence eligibility | "
        f"eligible="
        f"{eligibility_counts['eligible']} | "
        f"ineligible="
        f"{eligibility_counts['ineligible']}"
    )

    print(
        "topology | "
        + " | ".join(
            f"{key}={value}"
            for key, value
            in sorted(
                topology_counts.items()
            )
        )
    )

    print(
        f"bases | total={total_bases:,} | "
        f"ambiguous={total_ambiguous:,}"
    )

    print(
        f"summary | "
        f"{final_dir / 'batch-summary.json'}"
    )


if __name__ == "__main__":
    main()
