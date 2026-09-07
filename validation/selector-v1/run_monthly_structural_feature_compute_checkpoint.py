#!/usr/bin/env python3
"""Resumable non-production compute checkpoint for monthly Stage 10.

This program computes only accessions already frozen as COMPUTE by the
monthly Stage 10 production-input adapter.

Each completed candidate is written atomically as one canonical JSON record.
Existing candidate records are authenticated and reused on restart.

This program does not publish Stage 10.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


EXPECTED_ADAPTER_SHA256 = (
    "f7b71663a468e104b30acf34b3f5c038f8e19733ace76dacd27ba7a1fab0abd8"
)

EXPECTED_ENGINE_SHA256 = (
    "e0b5ea3a892aee3f9af80e5676010f1e1145563ca900058485e07d6433988968"
)

EXPECTED_COMPUTE_COUNT = 333

EXPECTED_COMPUTE_MEMBERSHIP_SHA256 = (
    "8eaead6f7ad348864b63d2574fc1e4fa590ac698c123bf2aa9e498e2e382b4c5"
)

SCHEMA = (
    "bacselect-monthly-stage10-compute-checkpoint-v1"
)

RUN_SCHEMA = (
    "bacselect-monthly-stage10-compute-run-v1"
)

RUN_PROVENANCE_NAME = "run-provenance.json"
CANDIDATE_DIR_NAME = "candidates"
RESULTS_NAME = "candidate-results.tsv"
SUMMARY_NAME = "compute-summary.json"


class CheckpointError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def canonical_json(payload: dict) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def atomic_write_fresh(
    path: Path,
    payload: bytes,
) -> None:
    temporary = path.with_name(
        path.name + ".partial"
    )

    if (
        path.exists()
        or path.is_symlink()
        or temporary.exists()
        or temporary.is_symlink()
    ):
        raise CheckpointError(
            f"refusing fresh write over existing path: {path}"
        )

    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())

    os.rename(
        temporary,
        path,
    )

    descriptor = os.open(
        path.parent,
        os.O_RDONLY,
    )

    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def ensure_exact_file(
    path: Path,
    payload: bytes,
) -> None:
    if path.exists():
        if (
            path.is_symlink()
            or not path.is_file()
            or path.read_bytes() != payload
        ):
            raise CheckpointError(
                f"existing checkpoint provenance changed: {path}"
            )

        return

    atomic_write_fresh(
        path,
        payload,
    )


def load_module(
    path: Path,
    name: str,
):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise CheckpointError(
            f"cannot load module: {path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[name] = module
    spec.loader.exec_module(module)

    return module


def validate_checkpoint_record(
    payload: bytes,
    *,
    accession: str,
    species_taxid: str,
    component_identity_sha256: str,
    execution_commit: str,
    feature_fields,
):
    try:
        record = json.loads(
            payload.decode("ascii")
        )
    except Exception as exc:
        raise CheckpointError(
            f"{accession}: invalid checkpoint JSON"
        ) from exc

    if record.get("schema_version") != SCHEMA:
        raise CheckpointError(
            f"{accession}: checkpoint schema changed"
        )

    expected_identity = {
        "accession":
            accession,
        "species_taxid":
            species_taxid,
        "component_identity_sha256":
            component_identity_sha256,
        "execution_commit":
            execution_commit,
        "engine_sha256":
            EXPECTED_ENGINE_SHA256,
    }

    for field, expected in (
        expected_identity.items()
    ):
        if record.get(field) != expected:
            raise CheckpointError(
                f"{accession}: checkpoint {field} changed"
            )

    features = record.get(
        "features"
    )

    if (
        not isinstance(features, dict)
        or tuple(features) != tuple(
            feature_fields
        )
    ):
        raise CheckpointError(
            f"{accession}: checkpoint feature schema changed"
        )

    retained = record.get(
        "retained_replicon_count"
    )

    total = record.get(
        "total_sequence_length"
    )

    if (
        not isinstance(retained, int)
        or retained <= 0
        or not isinstance(total, int)
        or total <= 0
    ):
        raise CheckpointError(
            f"{accession}: checkpoint structural counts invalid"
        )

    return record


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repo",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--source-repo",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--production-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--stage1-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--checkpoint-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--repeat-env-prefix",
        required=True,
        type=Path,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo = args.repo.resolve()

    if (
        repo.is_symlink()
        or not repo.is_dir()
    ):
        raise CheckpointError(
            "repository root invalid"
        )

    execution_commit = git(
        repo,
        "rev-parse",
        "HEAD",
    )

    remote = git(
        repo,
        "rev-parse",
        "origin/recovery/monthly-missing-datasets-gbff",
    )

    if execution_commit != remote:
        raise CheckpointError(
            "HEAD differs from frozen remote branch"
        )

    if git(
        repo,
        "status",
        "--porcelain",
    ):
        raise CheckpointError(
            "repository is not clean"
        )

    adapter_path = (
        repo
        / "validation"
        / "selector-v1"
        / "build_monthly_structural_feature_inputs.py"
    )

    if (
        not adapter_path.is_file()
        or adapter_path.is_symlink()
        or sha256_file(adapter_path)
        != EXPECTED_ADAPTER_SHA256
    ):
        raise CheckpointError(
            "Stage10 production-input adapter identity changed"
        )

    adapter = load_module(
        adapter_path,
        "_stage10_checkpoint_adapter",
    )

    stage10 = adapter.load_stage10_wrapper(
        repo
    )

    tier1_root = Path(
        "/NGS/scratch/EXT/Rhys_wkdir/bacselect/"
        "selector-v1/final-feature-space/"
        "0f75c51edc37259f168ad10faf44d536dd9b75a5"
    )

    tier2_root = Path(
        "/NGS/scratch/EXT/Rhys_wkdir/bacselect/"
        "selector-v1/stage6-structural-feature-execution/"
        "01c957b73b9802f284f6f61c28e6cd6e85bbf59a"
    )

    plan = adapter.build_production_plan(
        repo=repo,
        source_repo=(
            args.source_repo
        ),
        production_root=(
            args.production_root
        ),
        stage1_root=(
            args.stage1_root
        ),
        source_production_commit=(
            "abefc3b70d7fe7e079eeb52b762542dae565edf6"
        ),
        completion_execution_commit=(
            "10f86bf8fe079b284d52128e1b29f977e2214f7f"
        ),
        cache_execution_commit=(
            "80bd001371f430cfbc044f4a048f34689c2defdd"
        ),
        source_truth_execution_commit=(
            "6ff6bc3edb48489167571c9e0ef883992e0db4cf"
        ),
        biosample_execution_commit=(
            "e8d01bb93eb496859aeb02ffd89695ad10032435"
        ),
        expected_completion_sha256=(
            "9199c7dd24d53ed6e88683d657f6b2ae8c7b0c48e279a3283b79b89b83cfe5e5"
        ),
        expected_catalogue_sha256=(
            "1ee3cce9b47304d0832bc6f794d0af41e88442b859e66c99de7d67e38577dda7"
        ),
        expected_source_truth_completion_sha256=(
            "8603f684915dd561396307cee090634adcfaeedf2db4211f51cab8e8387007fd"
        ),
        expected_biosample_completion_sha256=(
            "d5fd9b803faee209a77c36528ab8617eea6683b4263fa57662fbcb100c86b850"
        ),
        tier1_matrix=(
            tier1_root
            / "structural-feature-matrix-300-2400.tsv"
        ),
        tier1_row_audit=(
            tier1_root
            / "feature-space-row-audit.tsv"
        ),
        tier1_historical_component_root=Path(
            "/NGS/scratch/EXT/Rhys_wkdir/"
            "project-finch/experiment-0/"
            "ncbi-sequence-validation-snapshot"
        ),
        tier2_matrix=(
            tier2_root
            / "structural-feature-matrix-300-2400.tsv"
        ),
        tier2_candidate_evidence=(
            tier2_root
            / "stage6-candidate-evidence.tsv"
        ),
        tier2_input_manifest=(
            tier2_root
            / "stage6-input-evidence-manifest.tsv"
        ),
        tier2_execution_provenance=(
            tier2_root
            / "stage6-execution-provenance.json"
        ),
        tier2_provider_search_roots=(
            Path(
                "/NGS/scratch/EXT/Rhys_wkdir/"
                "project-finch/experiment-0"
            ),
            Path(
                "/NGS/scratch/EXT/Rhys_wkdir/"
                "bacselect/selector-v1"
            ),
        ),
    )

    if len(
        plan.compute_accessions
    ) != EXPECTED_COMPUTE_COUNT:
        raise CheckpointError(
            "COMPUTE count changed"
        )

    compute_sha = (
        adapter.monthly
        .accession_membership_sha256(
            plan.compute_accessions
        )
    )

    if compute_sha != (
        EXPECTED_COMPUTE_MEMBERSHIP_SHA256
    ):
        raise CheckpointError(
            "COMPUTE membership changed"
        )

    structural_wrapper = (
        adapter
        .load_historical_structural_wrapper(
            repo
        )
    )

    finch = (
        structural_wrapper
        .load_finch_driver(
            repo
        )
    )

    basic = finch.basic

    checkpoint_root = (
        args.checkpoint_root.resolve()
    )

    checkpoint_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    if checkpoint_root.is_symlink():
        raise CheckpointError(
            "checkpoint root is symlink"
        )

    candidate_dir = (
        checkpoint_root
        / CANDIDATE_DIR_NAME
    )

    candidate_dir.mkdir(
        exist_ok=True
    )

    provenance = {
        "schema_version":
            RUN_SCHEMA,
        "execution_commit":
            execution_commit,
        "release_id":
            plan.context.release_id,
        "source_snapshot_id":
            plan.context.source_snapshot_id,
        "compute_count":
            EXPECTED_COMPUTE_COUNT,
        "compute_membership_sha256":
            EXPECTED_COMPUTE_MEMBERSHIP_SHA256,
        "component_identity_mapping_sha256":
            adapter
            .component_identity_mapping_sha256(
                plan
                .current_component_identity_by_accession
            ),
        "production_input_adapter_sha256":
            EXPECTED_ADAPTER_SHA256,
        "engine_sha256":
            EXPECTED_ENGINE_SHA256,
        "stage10_published":
            False,
    }

    ensure_exact_file(
        checkpoint_root
        / RUN_PROVENANCE_NAME,
        canonical_json(
            provenance
        ),
    )

    results = []
    computed = 0
    reused = 0

    with tempfile.TemporaryDirectory(
        prefix="bacselect-stage10-engine-"
    ) as temporary:
        engine, engine_sha = (
            structural_wrapper
            .compile_frozen_engine(
                repo=repo,
                env_prefix=(
                    args.repeat_env_prefix
                ),
                build_dir=(
                    Path(temporary)
                    / "build"
                ),
            )
        )

        if engine_sha != (
            EXPECTED_ENGINE_SHA256
        ):
            raise CheckpointError(
                "compiled engine identity changed"
            )

        for index, accession in enumerate(
            plan.compute_accessions,
            start=1,
        ):
            path = (
                candidate_dir
                / f"{accession}.json"
            )

            species_taxid = (
                plan
                .stage9
                .species_by_accession[
                    accession
                ]
            )

            component_sha = (
                plan
                .current_component_identity_by_accession[
                    accession
                ]
            )

            if path.exists():
                record = (
                    validate_checkpoint_record(
                        path.read_bytes(),
                        accession=accession,
                        species_taxid=(
                            species_taxid
                        ),
                        component_identity_sha256=(
                            component_sha
                        ),
                        execution_commit=(
                            execution_commit
                        ),
                        feature_fields=(
                            adapter.monthly
                            .FEATURE_FIELDS
                        ),
                    )
                )

                reused += 1

            else:
                binding = (
                    adapter
                    .build_compute_binding(
                        plan=plan,
                        accession=accession,
                    )
                )

                feature_record = (
                    adapter
                    .feature_execution
                    .compute_stage6_feature_record(
                        binding=binding,
                        species_taxid=(
                            species_taxid
                        ),
                        finch=finch,
                        basic=basic,
                        engine=engine,
                    )
                )

                record = {
                    "schema_version":
                        SCHEMA,
                    "accession":
                        accession,
                    "species_taxid":
                        species_taxid,
                    "component_identity_sha256":
                        component_sha,
                    "execution_commit":
                        execution_commit,
                    "engine_sha256":
                        EXPECTED_ENGINE_SHA256,
                    "retained_replicon_count":
                        feature_record
                        .retained_replicon_count,
                    "total_sequence_length":
                        feature_record
                        .total_sequence_length,
                    "features":
                        dict(
                            feature_record
                            .features
                        ),
                }

                payload = canonical_json(
                    record
                )

                atomic_write_fresh(
                    path,
                    payload,
                )

                validate_checkpoint_record(
                    path.read_bytes(),
                    accession=accession,
                    species_taxid=(
                        species_taxid
                    ),
                    component_identity_sha256=(
                        component_sha
                    ),
                    execution_commit=(
                        execution_commit
                    ),
                    feature_fields=(
                        adapter.monthly
                        .FEATURE_FIELDS
                    ),
                )

                computed += 1

            results.append(
                (
                    index,
                    accession,
                    sha256_file(path),
                )
            )

            if (
                index % 25 == 0
                or index
                == EXPECTED_COMPUTE_COUNT
            ):
                print(
                    f"completed={index}/"
                    f"{EXPECTED_COMPUTE_COUNT} "
                    f"computed={computed} "
                    f"reused={reused}",
                    flush=True,
                )

    adapter.reauthenticate_observations(
        observation
        for provider in (
            plan
            .providers_by_provenance
            .values()
        )
        for observation
        in provider.observations
    )

    results_payload = (
        "position\t"
        "canonical_genbank_assembly_accession\t"
        "checkpoint_sha256\n"
        + "".join(
            f"{position}\t"
            f"{accession}\t"
            f"{digest}\n"
            for (
                position,
                accession,
                digest,
            )
            in results
        )
    ).encode("ascii")

    results_path = (
        checkpoint_root
        / RESULTS_NAME
    )

    if results_path.exists():
        if (
            results_path.read_bytes()
            != results_payload
        ):
            raise CheckpointError(
                "existing results manifest changed"
            )
    else:
        atomic_write_fresh(
            results_path,
            results_payload,
        )

    summary = {
        "schema_version":
            RUN_SCHEMA,
        "status":
            "STAGE10_COMPUTE_CHECKPOINT_COMPLETE",
        "execution_commit":
            execution_commit,
        "compute_count":
            EXPECTED_COMPUTE_COUNT,
        "compute_membership_sha256":
            EXPECTED_COMPUTE_MEMBERSHIP_SHA256,
        "candidate_results_sha256":
            sha256_file(
                results_path
            ),
        "candidate_checkpoint_count":
            len(results),
        "stage10_published":
            False,
    }

    summary_path = (
        checkpoint_root
        / SUMMARY_NAME
    )

    ensure_exact_file(
        summary_path,
        canonical_json(
            summary
        ),
    )

    print(
        "PASS | Stage10 compute checkpoint complete"
    )

    print(
        "candidate_checkpoint_count="
        + str(len(results))
    )

    print(
        "computed_this_run="
        + str(computed)
    )

    print(
        "reused_this_run="
        + str(reused)
    )

    print(
        "candidate_results_sha256="
        + sha256_file(
            results_path
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
