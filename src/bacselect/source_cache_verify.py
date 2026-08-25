"""Historical Project Finch cache content verification for BacSelect.

The verifier re-hashes existing immutable cache evidence. It performs no
network access, downloads no sequence data, computes no structural features,
and consumes no selector identity or distance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
from typing import Iterable, Mapping, Sequence


CANONICAL_GCA_RE = re.compile(r"^GCA_[0-9]+\.[0-9]+$")
GCA_ANYWHERE_RE = re.compile(r"GCA_[0-9]+\.[0-9]+")

HISTORICAL_DATASETS_VERSION = "18.35.0"
HISTORICAL_ENV_LOCK_SHA256 = (
    "6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd"
)

EXPECTED_HISTORICAL_BATCHES = 111
EXPECTED_HISTORICAL_ACCESSIONS = 55_426
EXPECTED_PACKAGE_MANIFEST_ROWS = 166_844

ALLOWED_SNAPSHOT_SCRIPT_SHA256 = frozenset(
    {
        "1e2298d0ed0749d2ba58edd53d6bfc08626f1a494d8197469adbe787287070ff",
        "6981522b47c5a5c75d8a000b2fffca2176a9395e79996d8a9203aca0a4a58bb0",
        "780f8aabe2e6d9b4425498ee1f0170e3b0d55328100a4aea02efc875d4d29665",
        "8b5ff91a8dc0796d573520dedc82736ff162bd99bba19ae30ef91d6be45c9936",
    }
)

SMALL_PROVENANCE_HASHES = {
    "accessions_sha256": "accessions.txt",
    "candidate_sequence_audit_sha256": "candidate-sequence-audit.tsv",
    "component_sequence_audit_sha256": "component-sequence-audit.tsv",
    "package_files_sha256": "package-files.tsv",
    "dehydrated_zip_sha256": "dehydrated.zip",
    "attempt_origin_sha256": "attempt-origin.json",
}

FILE_FIELDS = (
    "path",
    "scope",
    "canonical_genbank_assembly_accession",
    "expected_size_bytes",
    "observed_size_bytes",
    "expected_sha256",
    "observed_sha256",
    "status",
)

ACCESSION_FIELDS = (
    "batch",
    "canonical_genbank_assembly_accession",
    "package_file_count",
    "accession_package_files_pass",
    "batch_common_provenance_pass",
    "cache_content_verification",
)


@dataclass(frozen=True)
class VerifiedFile:
    path: str
    scope: str
    accession: str
    expected_size_bytes: int
    observed_size_bytes: int | None
    expected_sha256: str
    observed_sha256: str
    status: str

    def as_row(self) -> dict[str, str]:
        return {
            "path": self.path,
            "scope": self.scope,
            "canonical_genbank_assembly_accession": self.accession,
            "expected_size_bytes": str(self.expected_size_bytes),
            "observed_size_bytes": (
                ""
                if self.observed_size_bytes is None
                else str(self.observed_size_bytes)
            ),
            "expected_sha256": self.expected_sha256,
            "observed_sha256": self.observed_sha256,
            "status": self.status,
        }


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    """Stream a SHA256 without reading the whole file into memory."""

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)

    return digest.hexdigest()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_manifest_path(batch_dir: Path, relative_path: str) -> Path:
    """Resolve one historical package-manifest path fail-closed.

    Historical manifests are accepted only when exactly one of the two observed
    snapshot layouts exists:
      batch/<manifest path>
      batch/package/<manifest path>
    """

    rel = Path(relative_path)

    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("unsafe package-manifest path")

    batch_root = batch_dir.resolve()

    candidates = (
        (batch_dir / rel).resolve(),
        (batch_dir / "package" / rel).resolve(),
    )

    for candidate in candidates:
        if not _inside(candidate, batch_root):
            raise ValueError("package-manifest path escapes batch root")

    existing = [
        candidate
        for candidate in candidates
        if candidate.is_file()
    ]

    if len(existing) != 1:
        raise ValueError(
            "package-manifest path must resolve to exactly one regular file"
        )

    return existing[0]


def path_scope(relative_path: str) -> tuple[str, str]:
    """Return ('accession', GCA) or ('batch_common', '').

    Multiple occurrences of the same GCA are allowed because the accession may
    occur in both directory and file names. More than one distinct GCA fails
    closed.
    """

    matches = set(GCA_ANYWHERE_RE.findall(relative_path))

    if not matches:
        return ("batch_common", "")

    if len(matches) != 1:
        raise ValueError(
            "package-manifest path contains multiple distinct GCA accessions"
        )

    accession = next(iter(matches))

    if not CANONICAL_GCA_RE.fullmatch(accession):
        raise ValueError("invalid canonical GCA accession in package path")

    return ("accession", accession)


def verify_manifest_row(
    batch_dir: Path,
    row: Mapping[str, str],
) -> VerifiedFile:
    """Verify one package-files.tsv row."""

    relative_path = row.get("path", "")
    expected_size_text = row.get("size_bytes", "")
    expected_sha = row.get("sha256", "")

    if not relative_path:
        raise ValueError("package manifest row has empty path")

    try:
        expected_size = int(expected_size_text)
    except (TypeError, ValueError):
        raise ValueError("package manifest row has invalid size_bytes") from None

    if expected_size < 0:
        raise ValueError("package manifest row has negative size_bytes")

    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ValueError("package manifest row has invalid sha256")

    scope, accession = path_scope(relative_path)

    try:
        path = resolve_manifest_path(batch_dir, relative_path)
    except ValueError:
        return VerifiedFile(
            path=relative_path,
            scope=scope,
            accession=accession,
            expected_size_bytes=expected_size,
            observed_size_bytes=None,
            expected_sha256=expected_sha,
            observed_sha256="",
            status="missing_or_ambiguous_path",
        )

    observed_size = path.stat().st_size

    if observed_size != expected_size:
        return VerifiedFile(
            path=relative_path,
            scope=scope,
            accession=accession,
            expected_size_bytes=expected_size,
            observed_size_bytes=observed_size,
            expected_sha256=expected_sha,
            observed_sha256="",
            status="size_mismatch",
        )

    observed_sha = sha256_file(path)

    return VerifiedFile(
        path=relative_path,
        scope=scope,
        accession=accession,
        expected_size_bytes=expected_size,
        observed_size_bytes=observed_size,
        expected_sha256=expected_sha,
        observed_sha256=observed_sha,
        status=(
            "pass"
            if observed_sha == expected_sha
            else "sha256_mismatch"
        ),
    )


def _read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")

        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing TSV header")

        fields = list(reader.fieldnames)
        rows = [dict(row) for row in reader]

    return fields, rows


def _read_accessions(path: Path) -> tuple[str, ...]:
    values = tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )

    if not values:
        raise ValueError("accessions.txt is empty")

    if values != tuple(sorted(values)):
        raise ValueError("historical batch accessions are not sorted")

    if len(values) != len(set(values)):
        raise ValueError("historical batch accessions are not unique")

    for accession in values:
        if not CANONICAL_GCA_RE.fullmatch(accession):
            raise ValueError("historical batch contains invalid GCA accession")

    return values


def _verify_small_provenance(
    batch_dir: Path,
    summary: Mapping[str, object],
) -> list[str]:
    failures: list[str] = []

    if str(summary.get("datasets_version")) != HISTORICAL_DATASETS_VERSION:
        failures.append("datasets_version")

    if (
        str(summary.get("environment_explicit_sha256"))
        != HISTORICAL_ENV_LOCK_SHA256
    ):
        failures.append("environment_explicit_sha256")

    script_sha = str(summary.get("snapshot_script_sha256", ""))

    if script_sha not in ALLOWED_SNAPSHOT_SCRIPT_SHA256:
        failures.append("snapshot_script_sha256")

    for field, filename in SMALL_PROVENANCE_HASHES.items():
        expected = summary.get(field)
        path = batch_dir / filename

        if not isinstance(expected, str) or not re.fullmatch(
            r"[0-9a-f]{64}",
            expected,
        ):
            failures.append(f"{field}:missing_or_invalid")
            continue

        if not path.is_file():
            failures.append(f"{field}:missing_file")
            continue

        if sha256_file(path) != expected:
            failures.append(f"{field}:sha256_mismatch")

    return failures


def verify_batch(
    batch_dir: Path,
) -> tuple[list[VerifiedFile], list[dict[str, str]], dict[str, object]]:
    """Fully re-hash one historical Project Finch sequence batch."""

    batch_dir = batch_dir.resolve()

    if not batch_dir.is_dir():
        raise ValueError("batch directory does not exist")

    summary_path = batch_dir / "batch-summary.json"

    if not summary_path.is_file():
        raise ValueError("batch summary is missing")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    if not isinstance(summary, dict):
        raise ValueError("batch summary must contain a JSON object")

    provenance_failures = _verify_small_provenance(
        batch_dir,
        summary,
    )

    accessions = _read_accessions(batch_dir / "accessions.txt")

    fields, package_rows = _read_tsv(batch_dir / "package-files.tsv")

    if fields != ["path", "size_bytes", "sha256"]:
        raise ValueError("unexpected package-files.tsv schema")

    verified_files = [
        verify_manifest_row(batch_dir, row)
        for row in package_rows
    ]

    accession_status: dict[str, list[VerifiedFile]] = {
        accession: []
        for accession in accessions
    }

    common_files: list[VerifiedFile] = []

    for verified in verified_files:
        if verified.scope == "batch_common":
            common_files.append(verified)
            continue

        if verified.accession not in accession_status:
            raise ValueError(
                "package manifest contains accession outside accessions.txt"
            )

        accession_status[verified.accession].append(verified)

    common_pass = (
        not provenance_failures
        and all(row.status == "pass" for row in common_files)
    )

    accession_rows: list[dict[str, str]] = []

    for accession in accessions:
        rows = accession_status[accession]

        if not rows:
            accession_pass = False
        else:
            accession_pass = all(
                row.status == "pass"
                for row in rows
            )

        final_pass = common_pass and accession_pass

        accession_rows.append(
            {
                "batch": batch_dir.name,
                "canonical_genbank_assembly_accession": accession,
                "package_file_count": str(len(rows)),
                "accession_package_files_pass": (
                    "1" if accession_pass else "0"
                ),
                "batch_common_provenance_pass": (
                    "1" if common_pass else "0"
                ),
                "cache_content_verification": (
                    "pass" if final_pass else "fallback_to_fresh"
                ),
            }
        )

    status_counts: dict[str, int] = {}

    for row in verified_files:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1

    batch_result = {
        "schema_version": 1,
        "batch": batch_dir.name,
        "accession_count": len(accessions),
        "package_manifest_rows": len(package_rows),
        "batch_common_package_files": len(common_files),
        "package_file_status_counts": dict(sorted(status_counts.items())),
        "small_provenance_failure_count": len(provenance_failures),
        "small_provenance_failures": sorted(provenance_failures),
        "cache_content_pass": sum(
            row["cache_content_verification"] == "pass"
            for row in accession_rows
        ),
        "cache_content_fallback_to_fresh": sum(
            row["cache_content_verification"] == "fallback_to_fresh"
            for row in accession_rows
        ),
    }

    return verified_files, accession_rows, batch_result


def _write_tsv(
    path: Path,
    fields: Sequence[str],
    rows: Iterable[Mapping[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_batch_verification(
    batch_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    verified_files, accession_rows, summary = verify_batch(batch_dir)

    output_dir.mkdir(parents=True, exist_ok=False)

    file_path = output_dir / "package-file-verification.tsv"
    accession_path = output_dir / "accession-cache-verification.tsv"
    summary_path = output_dir / "batch-cache-verification-summary.json"

    _write_tsv(
        file_path,
        FILE_FIELDS,
        (row.as_row() for row in verified_files),
    )
    _write_tsv(
        accession_path,
        ACCESSION_FIELDS,
        accession_rows,
    )

    summary = dict(summary)
    summary["package_file_verification_sha256"] = sha256_file(file_path)
    summary["accession_cache_verification_sha256"] = sha256_file(accession_path)

    summary_path.write_text(
        json.dumps(
            summary,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return summary


def aggregate_verifications(
    result_dirs: Sequence[Path],
    output_dir: Path,
    *,
    expected_batches: int | None = EXPECTED_HISTORICAL_BATCHES,
    expected_accessions: int | None = EXPECTED_HISTORICAL_ACCESSIONS,
    expected_package_rows: int | None = EXPECTED_PACKAGE_MANIFEST_ROWS,
) -> dict[str, object]:
    """Aggregate completed batch verifier outputs deterministically."""

    if expected_batches is not None and len(result_dirs) != expected_batches:
        raise ValueError(
            f"expected {expected_batches} batch results; "
            f"observed {len(result_dirs)}"
        )

    all_accession_rows: list[dict[str, str]] = []
    seen_accessions: set[str] = set()
    batches: list[str] = []
    package_rows = 0

    for result_dir in sorted(result_dirs, key=lambda path: path.name):
        summary_path = result_dir / "batch-cache-verification-summary.json"
        accession_path = result_dir / "accession-cache-verification.tsv"

        if not summary_path.is_file() or not accession_path.is_file():
            raise ValueError("batch verification output is incomplete")

        summary = json.loads(summary_path.read_text(encoding="utf-8"))

        if sha256_file(accession_path) != summary.get(
            "accession_cache_verification_sha256"
        ):
            raise ValueError("batch accession-verification SHA mismatch")

        _, rows = _read_tsv(accession_path)

        batch = str(summary.get("batch", ""))

        if not batch:
            raise ValueError("batch verification summary lacks batch")

        batches.append(batch)
        package_rows += int(summary.get("package_manifest_rows", -1))

        for row in rows:
            accession = row["canonical_genbank_assembly_accession"]

            if accession in seen_accessions:
                raise ValueError(
                    "duplicate accession across batch verification outputs"
                )

            seen_accessions.add(accession)
            all_accession_rows.append(row)

    all_accession_rows.sort(
        key=lambda row: row["canonical_genbank_assembly_accession"]
    )

    if expected_accessions is not None and len(all_accession_rows) != expected_accessions:
        raise ValueError(
            f"expected {expected_accessions} accessions; "
            f"observed {len(all_accession_rows)}"
        )

    if expected_package_rows is not None and package_rows != expected_package_rows:
        raise ValueError(
            f"expected {expected_package_rows} package rows; "
            f"observed {package_rows}"
        )

    output_dir.mkdir(parents=True, exist_ok=False)

    accession_output = (
        output_dir
        / "historical-cache-content-verification.tsv"
    )

    _write_tsv(
        accession_output,
        ACCESSION_FIELDS,
        all_accession_rows,
    )

    pass_count = sum(
        row["cache_content_verification"] == "pass"
        for row in all_accession_rows
    )
    fallback_count = len(all_accession_rows) - pass_count

    aggregate = {
        "schema_version": 1,
        "batch_count": len(result_dirs),
        "accession_count": len(all_accession_rows),
        "package_manifest_rows": package_rows,
        "cache_content_pass": pass_count,
        "cache_content_fallback_to_fresh": fallback_count,
        "accession_verification_sha256": sha256_file(accession_output),
    }

    summary_output = (
        output_dir
        / "historical-cache-content-verification-summary.json"
    )
    summary_output.write_text(
        json.dumps(
            aggregate,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return aggregate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify frozen historical Project Finch cache content."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    batch_parser = sub.add_parser("verify-batch")
    batch_parser.add_argument("--batch-dir", required=True, type=Path)
    batch_parser.add_argument("--output-dir", required=True, type=Path)

    aggregate_parser = sub.add_parser("aggregate")
    aggregate_parser.add_argument(
        "--results-root",
        required=True,
        type=Path,
    )
    aggregate_parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )

    args = parser.parse_args(argv)

    if args.command == "verify-batch":
        write_batch_verification(
            args.batch_dir,
            args.output_dir,
        )
        return 0

    result_dirs = sorted(
        path
        for path in args.results_root.glob("batch-*")
        if path.is_dir()
    )
    aggregate_verifications(
        result_dirs,
        args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
