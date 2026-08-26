#!/usr/bin/env python3
"""Aggregate original and recovery BacSelect fresh-sequence evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

REPO = Path("/home/rwhite/github/bacselect")
BASE_AUDITOR_PATH = REPO / "validation/selector-v1/audit_fresh_sequence_validation.py"
RECOVERY_PATH = REPO / "validation/selector-v1/recover_acquisition_unavailable.py"

SOURCE_COMMIT = "7aba4b0a2aa22c05ce808bf9b5811606bd3d2293"
SOURCE_ROOT = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/fresh-sequence-validation"
) / SOURCE_COMMIT

RECOVERY_BATCHES = (24, 28)
EXPECTED_BATCHES = 31
EXPECTED_TARGETS = 15_326
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def die(message: str) -> None:
    raise SystemExit(f"ERROR | {message}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        die(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_counts(target: Counter[str], values: Mapping[str, object]) -> None:
    for key, value in values.items():
        target[key] += int(value)


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recovery-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not GIT_SHA_RE.fullmatch(args.recovery_commit):
        die("invalid recovery commit")

    base = load_module(BASE_AUDITOR_PATH, "bacselect_base_auditor")
    recovery = load_module(RECOVERY_PATH, "bacselect_recovery")

    recovery_root = recovery.recovery_output_root(args.recovery_commit)

    acquisition: Counter[str] = Counter()
    eligibility: Counter[str] = Counter()
    exclusions: Counter[str] = Counter()
    topology: Counter[str] = Counter()
    gbff_sources: Counter[str] = Counter()

    total_requested = 0
    total_candidates = 0
    total_components = 0
    total_bases = 0
    total_ambiguous = 0

    for batch_number in range(1, EXPECTED_BATCHES + 1):
        if batch_number in RECOVERY_BATCHES:
            result = recovery.audit_recovery_batch(
                recovery_root,
                args.recovery_commit,
                batch_number,
                verify_package_content=True,
            )
            add_counts(acquisition, result["acquisition_status_counts"])
        else:
            result = base.validate_batch(
                SOURCE_ROOT,
                SOURCE_COMMIT,
                batch_number,
                verify_package_content=True,
            )
            acquisition["available"] += int(result["candidate_records"])

        total_requested += int(result["requested_accessions"])
        total_candidates += int(result["candidate_records"])
        total_components += int(result["component_records"])
        total_bases += int(result["total_sequence_bases"])
        total_ambiguous += int(result["ambiguous_base_count"])
        add_counts(eligibility, result["sequence_eligibility_counts"])
        add_counts(exclusions, result["sequence_exclusion_reason_counts"])
        add_counts(topology, result["topology_counts"])
        add_counts(gbff_sources, result["gbff_source_counts"])

    if total_requested != EXPECTED_TARGETS:
        die(
            f"requested target accounting mismatch: "
            f"{total_requested} != {EXPECTED_TARGETS}"
        )

    if acquisition["available"] + acquisition["unavailable"] != EXPECTED_TARGETS:
        die("acquisition status accounting does not equal frozen target count")

    if total_candidates != acquisition["available"]:
        die("candidate record count does not equal acquisition-available count")

    if sum(eligibility.values()) != total_candidates:
        die("sequence eligibility accounting does not equal candidate record count")

    if acquisition["unavailable"] <= 0:
        die("recovery aggregate unexpectedly contains no unavailable acquisition")

    payload = {
        "schema_version": 2,
        "source_production_commit": SOURCE_COMMIT,
        "recovery_commit": args.recovery_commit,
        "expected_batches": EXPECTED_BATCHES,
        "requested_accessions": total_requested,
        "acquisition_status_counts": dict(sorted(acquisition.items())),
        "candidate_records": total_candidates,
        "component_records": total_components,
        "total_sequence_bases": total_bases,
        "ambiguous_base_count": total_ambiguous,
        "sequence_eligibility_counts": dict(sorted(eligibility.items())),
        "sequence_exclusion_reason_counts": dict(sorted(exclusions.items())),
        "topology_counts": dict(sorted(topology.items())),
        "gbff_source_counts": dict(sorted(gbff_sources.items())),
        "recovery_batch_count": len(RECOVERY_BATCHES),
        "source_final_batch_count": EXPECTED_BATCHES - len(RECOVERY_BATCHES),
        "package_content_verified": True,
        "selector_outcome_generated": False,
        "completed_at_utc": utc_now(),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(payload, sort_keys=True))
    print(f"summary_sha256\t{sha256_file(args.output)}")
    print("PASS | complete fresh-sequence acquisition accounting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
