"""Deterministic BacSelect cache-reuse and fresh-acquisition manifests.

This module reconstructs the frozen metadata-retained source universe from the
frozen raw NCBI summary JSONL, reconciles it against verified historical
Project Finch sequence evidence, and writes the final operational acquisition
partition.

It performs no network access, no sequence download, no structural-feature
calculation, and no selector comparison.
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

from bacselect.source_eligibility import (
    CANONICAL_GCA_RE,
    RETAIN,
    assess_records,
    iter_jsonl_records,
)
from bacselect.source_sequence_plan import (
    EXPECTED_CACHE_CANDIDATES,
    EXPECTED_FRESH_BATCHES,
    EXPECTED_METADATA_RETAINED,
    EXPECTED_UNCACHED,
    FRESH_BATCH_SIZE,
    SequencePlan,
    accession_manifest_bytes,
    batch_accessions,
    cache_reuse_eligible,
)


EXPECTED_RAW_SOURCE_SHA256 = (
    "b1b016891ae4e976d03606dfb2f35f74b03d21cf3ec82832f77f4d113bd622d5"
)
EXPECTED_CACHE_VERIFICATION_SHA256 = (
    "7b2fa38ff2c1f43fc0536cabfa68091fdde9d4d3677092d49405bbac113fd752"
)

EXPECTED_SOURCE_RECORDS = 70_850
EXPECTED_HISTORICAL_BATCHES = 111
EXPECTED_HISTORICAL_ACCESSIONS = 55_426
EXPECTED_CACHE_VERIFICATION_PASS = 55_426
EXPECTED_CACHE_VERIFICATION_FALLBACK = 0
EXPECTED_LAST_FRESH_BATCH_SIZE = 326

REQUIRED_HISTORICAL_FIELDS = frozenset(
    {
        "canonical_genbank_assembly_accession",
        "current_accession",
        "assembly_status",
        "assembly_level",
        "expected_biosample",
        "observed_biosample",
        "sequence_eligibility",
        "exclusion_reasons",
    }
)

CACHE_FIELDS = (
    "batch",
    "canonical_genbank_assembly_accession",
    "package_file_count",
    "accession_package_files_pass",
    "batch_common_provenance_pass",
    "cache_content_verification",
)

CACHE_MANIFEST_FIELDS = (
    "canonical_genbank_assembly_accession",
    "fresh_biosample",
    "historical_batch",
    "historical_sequence_eligibility",
    "historical_exclusion_reasons",
)

FRESH_MANIFEST_FIELDS = (
    "canonical_genbank_assembly_accession",
    "fresh_biosample",
    "acquisition_reason",
)

BATCH_INDEX_FIELDS = (
    "batch",
    "accession_count",
    "accessions_sha256",
)

AUDIT_HASH_FIELDS = (
    "batch",
    "candidate_sequence_audit_sha256",
)


@dataclass(frozen=True)
class HistoricalAudit:
    batch: str
    row: Mapping[str, str]


@dataclass(frozen=True)
class CacheVerification:
    batch: str
    package_file_count: int
    accession_package_files_pass: bool
    batch_common_provenance_pass: bool
    cache_content_verification: str


@dataclass(frozen=True)
class AcquisitionBuild:
    plan: SequencePlan
    cache_rows: tuple[dict[str, str], ...]
    fresh_rows: tuple[dict[str, str], ...]
    source_record_count: int
    candidate_audit_hashes: tuple[tuple[str, str], ...]


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)

    return digest.hexdigest()


def _write_tsv(
    path: Path,
    fields: Sequence[str],
    rows: Iterable[Mapping[str, str]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _bool01(value: str, *, field: str) -> bool:
    if value == "1":
        return True
    if value == "0":
        return False
    raise ValueError(f"invalid {field}: expected 0 or 1")


def _read_cache_verification(
    path: Path,
) -> dict[str, CacheVerification]:
    if sha256_file(path) != EXPECTED_CACHE_VERIFICATION_SHA256:
        raise ValueError("historical cache-verification TSV SHA256 mismatch")

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")

        if tuple(reader.fieldnames or ()) != CACHE_FIELDS:
            raise ValueError("unexpected cache-verification TSV schema")

        result: dict[str, CacheVerification] = {}

        for row in reader:
            accession = row["canonical_genbank_assembly_accession"]

            if not CANONICAL_GCA_RE.fullmatch(accession):
                raise ValueError("invalid GCA in cache-verification TSV")

            if accession in result:
                raise ValueError("duplicate GCA in cache-verification TSV")

            try:
                package_file_count = int(row["package_file_count"])
            except ValueError:
                raise ValueError(
                    "invalid package_file_count in cache-verification TSV"
                ) from None

            if package_file_count <= 0:
                raise ValueError(
                    "cache-verification accession has no package files"
                )

            state = row["cache_content_verification"]

            if state not in {"pass", "fallback_to_fresh"}:
                raise ValueError("unexpected cache verification state")

            accession_files_pass = _bool01(
                row["accession_package_files_pass"],
                field="accession_package_files_pass",
            )
            batch_common_pass = _bool01(
                row["batch_common_provenance_pass"],
                field="batch_common_provenance_pass",
            )

            if state == "pass" and not (
                accession_files_pass
                and batch_common_pass
            ):
                raise ValueError(
                    "cache state pass conflicts with component pass flags"
                )

            result[accession] = CacheVerification(
                batch=row["batch"],
                package_file_count=package_file_count,
                accession_package_files_pass=accession_files_pass,
                batch_common_provenance_pass=batch_common_pass,
                cache_content_verification=state,
            )

    if len(result) != EXPECTED_HISTORICAL_ACCESSIONS:
        raise ValueError(
            "unexpected number of historical cache-verification accessions"
        )

    pass_count = sum(
        item.cache_content_verification == "pass"
        for item in result.values()
    )
    fallback_count = len(result) - pass_count

    if pass_count != EXPECTED_CACHE_VERIFICATION_PASS:
        raise ValueError("unexpected historical cache pass count")

    if fallback_count != EXPECTED_CACHE_VERIFICATION_FALLBACK:
        raise ValueError("unexpected historical cache fallback count")

    return result


def _read_historical_candidate_audits(
    snapshot_root: Path,
) -> tuple[
    dict[str, HistoricalAudit],
    tuple[tuple[str, str], ...],
]:
    result: dict[str, HistoricalAudit] = {}
    audit_hashes: list[tuple[str, str]] = []

    for batch_number in range(1, EXPECTED_HISTORICAL_BATCHES + 1):
        batch = f"batch-{batch_number:03d}"
        batch_dir = snapshot_root / batch
        audit_path = batch_dir / "candidate-sequence-audit.tsv"
        summary_path = batch_dir / "batch-summary.json"

        if not batch_dir.is_dir():
            raise ValueError(f"missing historical batch: {batch}")

        if not audit_path.is_file():
            raise ValueError(
                f"missing historical candidate audit: {batch}"
            )

        if not summary_path.is_file():
            raise ValueError(
                f"missing historical batch summary: {batch}"
            )

        summary = json.loads(
            summary_path.read_text(encoding="utf-8")
        )

        if not isinstance(summary, dict):
            raise ValueError(
                f"historical batch summary is not an object: {batch}"
            )

        expected_sha = summary.get(
            "candidate_sequence_audit_sha256"
        )

        if not isinstance(expected_sha, str) or not re.fullmatch(
            r"[0-9a-f]{64}",
            expected_sha,
        ):
            raise ValueError(
                f"invalid candidate audit SHA in batch summary: {batch}"
            )

        observed_sha = sha256_file(audit_path)

        if observed_sha != expected_sha:
            raise ValueError(
                f"candidate audit SHA mismatch: {batch}"
            )

        audit_hashes.append((batch, observed_sha))

        with audit_path.open(
            newline="",
            encoding="utf-8",
        ) as handle:
            reader = csv.DictReader(
                handle,
                delimiter="\t",
            )

            fields = set(reader.fieldnames or ())

            missing = REQUIRED_HISTORICAL_FIELDS - fields

            if missing:
                raise ValueError(
                    f"{batch}: candidate audit missing required fields: "
                    + ",".join(sorted(missing))
                )

            for row in reader:
                accession = row[
                    "canonical_genbank_assembly_accession"
                ]

                if not CANONICAL_GCA_RE.fullmatch(accession):
                    raise ValueError(
                        f"{batch}: invalid GCA in candidate audit"
                    )

                if accession in result:
                    raise ValueError(
                        "duplicate GCA across historical candidate audits"
                    )

                result[accession] = HistoricalAudit(
                    batch=batch,
                    row=dict(row),
                )

    if len(result) != EXPECTED_HISTORICAL_ACCESSIONS:
        raise ValueError(
            "unexpected historical candidate-audit accession count"
        )

    return result, tuple(audit_hashes)


def _retained_source_biosamples(
    raw_jsonl: Path,
) -> tuple[dict[str, str], int]:
    if sha256_file(raw_jsonl) != EXPECTED_RAW_SOURCE_SHA256:
        raise ValueError("raw source JSONL SHA256 mismatch")

    assessments = assess_records(
        iter_jsonl_records(raw_jsonl)
    )

    if len(assessments) != EXPECTED_SOURCE_RECORDS:
        raise ValueError(
            f"expected {EXPECTED_SOURCE_RECORDS} source records; "
            f"observed {len(assessments)}"
        )

    retained: dict[str, str] = {}

    for assessment in assessments:
        if assessment.decision != RETAIN:
            continue

        accession = assessment.accession
        biosample = assessment.biosample

        if not CANONICAL_GCA_RE.fullmatch(accession):
            raise ValueError(
                "retained metadata assessment has invalid GCA"
            )

        if not biosample:
            raise ValueError(
                "retained metadata assessment has no BioSample"
            )

        if accession in retained:
            raise ValueError(
                "duplicate retained accession after metadata assessment"
            )

        retained[accession] = biosample

    if len(retained) != EXPECTED_METADATA_RETAINED:
        raise ValueError(
            f"expected {EXPECTED_METADATA_RETAINED} retained records; "
            f"observed {len(retained)}"
        )

    return retained, len(assessments)


def _reuse_failure_reason(
    fresh_biosample: str,
    historical: Mapping[str, str],
    verification: CacheVerification,
) -> str:
    if verification.cache_content_verification != "pass":
        return "cache_content_not_verified"

    if not (
        verification.accession_package_files_pass
        and verification.batch_common_provenance_pass
    ):
        return "cache_content_not_verified"

    accession = historical.get(
        "canonical_genbank_assembly_accession",
        "",
    )

    if historical.get("current_accession") != accession:
        return "historical_current_accession_mismatch"

    if historical.get("assembly_status") != "current":
        return "historical_assembly_not_current"

    if historical.get("assembly_level") != "Complete Genome":
        return "historical_assembly_level_mismatch"

    if historical.get("expected_biosample") != fresh_biosample:
        return "fresh_historical_expected_biosample_mismatch"

    if historical.get("observed_biosample") != fresh_biosample:
        return "fresh_historical_observed_biosample_mismatch"

    return "cache_reuse_contract_failed"


def build_acquisition_partition(
    *,
    raw_jsonl: Path,
    historical_snapshot_root: Path,
    cache_verification_tsv: Path,
) -> AcquisitionBuild:
    retained, source_record_count = _retained_source_biosamples(
        raw_jsonl
    )
    historical, audit_hashes = _read_historical_candidate_audits(
        historical_snapshot_root
    )
    cache_verification = _read_cache_verification(
        cache_verification_tsv
    )

    if set(historical) != set(cache_verification):
        raise ValueError(
            "historical candidate audits and verified cache have "
            "different accession sets"
        )

    cache_accessions: list[str] = []
    fresh_accessions: list[str] = []
    cache_rows: list[dict[str, str]] = []
    fresh_rows: list[dict[str, str]] = []

    for accession in sorted(retained):
        biosample = retained[accession]

        if accession not in historical:
            fresh_accessions.append(accession)
            fresh_rows.append(
                {
                    "canonical_genbank_assembly_accession": accession,
                    "fresh_biosample": biosample,
                    "acquisition_reason": "not_in_historical_cache",
                }
            )
            continue

        historical_entry = historical[accession]
        verification = cache_verification[accession]

        if verification.batch != historical_entry.batch:
            raise ValueError(
                "historical cache-verification batch differs from "
                "candidate-audit batch"
            )

        package_integrity_verified = (
            verification.cache_content_verification == "pass"
            and verification.accession_package_files_pass
            and verification.batch_common_provenance_pass
        )

        reusable = cache_reuse_eligible(
            fresh_biosample=biosample,
            historical_row=historical_entry.row,
            package_integrity_verified=package_integrity_verified,
        )

        if reusable:
            cache_accessions.append(accession)
            cache_rows.append(
                {
                    "canonical_genbank_assembly_accession": accession,
                    "fresh_biosample": biosample,
                    "historical_batch": historical_entry.batch,
                    "historical_sequence_eligibility": historical_entry.row[
                        "sequence_eligibility"
                    ],
                    "historical_exclusion_reasons": historical_entry.row[
                        "exclusion_reasons"
                    ],
                }
            )
        else:
            fresh_accessions.append(accession)
            fresh_rows.append(
                {
                    "canonical_genbank_assembly_accession": accession,
                    "fresh_biosample": biosample,
                    "acquisition_reason": _reuse_failure_reason(
                        biosample,
                        historical_entry.row,
                        verification,
                    ),
                }
            )

    plan = SequencePlan(
        cache_candidates=tuple(cache_accessions),
        fresh_downloads=tuple(fresh_accessions),
    )

    if len(plan.cache_candidates) != EXPECTED_CACHE_CANDIDATES:
        raise ValueError(
            f"expected {EXPECTED_CACHE_CANDIDATES} cache-reuse accessions; "
            f"observed {len(plan.cache_candidates)}"
        )

    if len(plan.fresh_downloads) != EXPECTED_UNCACHED:
        raise ValueError(
            f"expected {EXPECTED_UNCACHED} fresh-download accessions; "
            f"observed {len(plan.fresh_downloads)}"
        )

    if set(plan.cache_candidates) & set(plan.fresh_downloads):
        raise RuntimeError("cache and fresh acquisition sets overlap")

    if (
        len(plan.cache_candidates)
        + len(plan.fresh_downloads)
        != EXPECTED_METADATA_RETAINED
    ):
        raise RuntimeError(
            "cache/fresh acquisition sets are not exhaustive"
        )

    return AcquisitionBuild(
        plan=plan,
        cache_rows=tuple(cache_rows),
        fresh_rows=tuple(fresh_rows),
        source_record_count=source_record_count,
        candidate_audit_hashes=audit_hashes,
    )


def write_acquisition_manifests(
    build: AcquisitionBuild,
    output_dir: Path,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=False)

    cache_accessions_path = output_dir / "cache-reuse-accessions.txt"
    fresh_accessions_path = output_dir / "fresh-download-accessions.txt"
    cache_manifest_path = output_dir / "cache-reuse-manifest.tsv"
    fresh_manifest_path = output_dir / "fresh-download-manifest.tsv"
    audit_hash_path = (
        output_dir
        / "historical-candidate-audits-sha256.tsv"
    )
    batch_index_path = output_dir / "fresh-batch-index.tsv"
    batches_root = output_dir / "fresh-batches"

    cache_accessions_path.write_bytes(
        accession_manifest_bytes(build.plan.cache_candidates)
    )
    fresh_accessions_path.write_bytes(
        accession_manifest_bytes(build.plan.fresh_downloads)
    )

    _write_tsv(
        cache_manifest_path,
        CACHE_MANIFEST_FIELDS,
        build.cache_rows,
    )
    _write_tsv(
        fresh_manifest_path,
        FRESH_MANIFEST_FIELDS,
        build.fresh_rows,
    )

    _write_tsv(
        audit_hash_path,
        AUDIT_HASH_FIELDS,
        (
            {
                "batch": batch,
                "candidate_sequence_audit_sha256": sha,
            }
            for batch, sha in build.candidate_audit_hashes
        ),
    )

    batches = batch_accessions(
        build.plan.fresh_downloads,
        batch_size=FRESH_BATCH_SIZE,
    )

    if len(batches) != EXPECTED_FRESH_BATCHES:
        raise RuntimeError("unexpected fresh acquisition batch count")

    if len(batches[-1]) != EXPECTED_LAST_FRESH_BATCH_SIZE:
        raise RuntimeError("unexpected final fresh acquisition batch size")

    batches_root.mkdir()

    batch_index_rows: list[dict[str, str]] = []

    for index, accessions in enumerate(batches, 1):
        batch = f"batch-{index:03d}"
        batch_dir = batches_root / batch
        batch_dir.mkdir()

        path = batch_dir / "accessions.txt"
        path.write_bytes(
            accession_manifest_bytes(accessions)
        )

        batch_index_rows.append(
            {
                "batch": batch,
                "accession_count": str(len(accessions)),
                "accessions_sha256": sha256_file(path),
            }
        )

    _write_tsv(
        batch_index_path,
        BATCH_INDEX_FIELDS,
        batch_index_rows,
    )

    top_level_paths = {
        "cache_reuse_accessions_sha256": cache_accessions_path,
        "fresh_download_accessions_sha256": fresh_accessions_path,
        "cache_reuse_manifest_sha256": cache_manifest_path,
        "fresh_download_manifest_sha256": fresh_manifest_path,
        "historical_candidate_audits_manifest_sha256": audit_hash_path,
        "fresh_batch_index_sha256": batch_index_path,
    }

    summary: dict[str, object] = {
        "schema_version": 1,
        "source_records": build.source_record_count,
        "metadata_retained": EXPECTED_METADATA_RETAINED,
        "cache_reuse": len(build.plan.cache_candidates),
        "fresh_downloads": len(build.plan.fresh_downloads),
        "fresh_batch_size": FRESH_BATCH_SIZE,
        "fresh_batches": len(batches),
        "final_fresh_batch_size": len(batches[-1]),
        "raw_source_sha256": EXPECTED_RAW_SOURCE_SHA256,
        "cache_verification_sha256": EXPECTED_CACHE_VERIFICATION_SHA256,
    }

    for field, path in top_level_paths.items():
        summary[field] = sha256_file(path)

    summary_path = output_dir / "acquisition-plan-summary.json"
    summary_path.write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build frozen BacSelect cache-reuse and fresh-download manifests."
        )
    )
    parser.add_argument("--raw-jsonl", required=True, type=Path)
    parser.add_argument(
        "--historical-snapshot-root",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--cache-verification-tsv",
        required=True,
        type=Path,
    )
    parser.add_argument("--output-dir", required=True, type=Path)

    args = parser.parse_args(argv)

    build = build_acquisition_partition(
        raw_jsonl=args.raw_jsonl,
        historical_snapshot_root=args.historical_snapshot_root,
        cache_verification_tsv=args.cache_verification_tsv,
    )
    summary = write_acquisition_manifests(
        build,
        args.output_dir,
    )

    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
