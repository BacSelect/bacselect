#!/usr/bin/env python3
"""Execute recovery-aware BacSelect monthly Stage 4 source truth."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from types import ModuleType
from typing import Mapping, Sequence

from bacselect import monthly_sequence_cache_catalogue as cache_v1
from bacselect import monthly_sequence_cache_catalogue_v2 as cache_v2
from bacselect import monthly_source_truth


SOURCE_TRUTH_STAGE_NAME = "source-truth"
DECISIONS_NAME = "source-truth-decisions.tsv"
RELATIONS_NAME = "source-truth-relations.tsv"
RECORD_NAME = "monthly-source-truth-record.json"

COMPLETION_NAME = "source-truth-completion-v2.json"
COMPLETION_TEMP_NAME = ".source-truth-completion-v2.json.tmp"

COMPLETION_SCHEMA = (
    "bacselect-monthly-source-truth-completion-v2"
)

COMPLETION_STATUS = (
    "SOURCE_TRUTH_EXECUTION_COMPLETE"
)

CATALOGUE_NAME = (
    "sequence-cache-catalogue-v2.json"
)

COMPLETION_V2_NAME = (
    "sequence-acquisition-completion-v2.json"
)

EXPECTED_MONTHLY_SOURCE_TRUTH_SHA256 = (
    "0876620b8516c0d8aa7aa26f5b4567de17170aa5456caf57cee7b6718a4158a7"
)

EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256 = (
    "83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92"
)

EXPECTED_STAGE4_V1_WRAPPER_SHA256 = (
    "f13b6e82e2e750902fe528a5d1fdab2dc4e829dac5b5aedd717045ab2084d3b5"
)

EXPECTED_CACHE_V2_CORE_SHA256 = (
    "1a7f9c2015c73e0cbada26064ad137fd6468ce5592dd5c518095d8f20d2937ca"
)

EXPECTED_CACHE_V2_EXECUTOR_SHA256 = (
    "87b3b32f260abf26acd49deaa2665991bd77e409d6fac7ded7bdf87b2c15a15c"
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class MonthlySourceTruthV2ExecutionError(
    RuntimeError
):
    """Raised when recovery-aware Stage 4 execution fails closed."""


@dataclass(
    frozen=True,
)
class ProviderBatchContextV2:
    batch_id: str
    provider_root: Path
    candidate_audit_path: Path
    batch: object
    observations: tuple[
        object,
        ...,
    ]


@dataclass(
    frozen=True,
)
class MonthlySourceTruthV2ExecutionResult:
    release_id: str
    source_snapshot_id: str
    stage_root: Path
    completion_path: Path
    retained_count: int
    sequence_eligible_count: int
    sequence_ineligible_count: int
    decision_count: int
    relation_count: int
    decisions_sha256: str
    relations_sha256: str
    record_sha256: str
    completion_sha256: str


def _fail(
    message: str,
) -> None:
    raise MonthlySourceTruthV2ExecutionError(
        message
    )


def _canonical_json_bytes(
    value: Mapping[
        str,
        object,
    ],
) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        for block in iter(
            lambda:
                handle.read(
                    8
                    * 1024
                    * 1024
                ),
            b"",
        ):
            digest.update(
                block
            )

    return digest.hexdigest()


def validate_sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        _fail(
            f"{label} is not a SHA256"
        )

    return value


def validate_commit(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        _fail(
            f"{label} is not a Git commit"
        )

    return value


def _load_module(
    path: Path,
    *,
    module_name: str,
    expected_sha256: str,
) -> ModuleType:
    if (
        not path.is_file()
        or path.is_symlink()
    ):
        _fail(
            "frozen module is not a regular file: "
            f"{path}"
        )

    observed = sha256_file(
        path
    )

    if (
        observed
        != expected_sha256
    ):
        _fail(
            "frozen module SHA256 changed: "
            f"{path}"
        )

    spec = (
        importlib.util
        .spec_from_file_location(
            module_name,
            path,
        )
    )

    if (
        spec is None
        or spec.loader
        is None
    ):
        _fail(
            "cannot load frozen module: "
            f"{path}"
        )

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    sys.modules[
        module_name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


def load_stage4_v1(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo
        / "validation"
        / "selector-v1"
        / "run_monthly_source_truth.py",
        module_name=(
            "_bacselect_stage4_v1_for_v2"
        ),
        expected_sha256=(
            EXPECTED_STAGE4_V1_WRAPPER_SHA256
        ),
    )


def load_cache_v2_execution(
    repo: Path,
) -> ModuleType:
    return _load_module(
        repo
        / "validation"
        / "selector-v1"
        / (
            "run_monthly_"
            "sequence_cache_catalogue_v2.py"
        ),
        module_name=(
            "_bacselect_cache_v2_for_stage4_v2"
        ),
        expected_sha256=(
            EXPECTED_CACHE_V2_EXECUTOR_SHA256
        ),
    )


def _git(
    repo: Path,
    *args: str,
) -> str:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(
                repo
            ),
            *args,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return result.stdout.strip()


def repository_preflight(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> None:
    commit = validate_commit(
        expected_commit,
        label=(
            "Stage 4 v2 execution commit"
        ),
    )

    wrapper_sha = validate_sha256(
        expected_wrapper_sha256,
        label=(
            "Stage 4 v2 wrapper SHA256"
        ),
    )

    test_sha = validate_sha256(
        expected_wrapper_test_sha256,
        label=(
            "Stage 4 v2 wrapper-test SHA256"
        ),
    )

    if (
        _git(
            repo,
            "rev-parse",
            "HEAD",
        )
        != commit
    ):
        _fail(
            "repository HEAD differs from "
            "Stage 4 v2 execution commit"
        )

    if _git(
        repo,
        "status",
        "--porcelain",
    ):
        _fail(
            "Stage 4 v2 execution repository "
            "is not clean"
        )

    wrapper = Path(
        __file__
    ).resolve()

    test = (
        repo
        / "tests"
        / (
            "test_run_monthly_"
            "source_truth_v2.py"
        )
    )

    if (
        sha256_file(
            wrapper
        )
        != wrapper_sha
    ):
        _fail(
            "Stage 4 v2 wrapper SHA256 differs "
            "from authorized identity"
        )

    if (
        sha256_file(
            test
        )
        != test_sha
    ):
        _fail(
            "Stage 4 v2 wrapper-test SHA256 differs "
            "from authorized identity"
        )

    frozen = {
        (
            repo
            / "src"
            / "bacselect"
            / "monthly_source_truth.py"
        ):
            EXPECTED_MONTHLY_SOURCE_TRUTH_SHA256,
        (
            repo
            / "src"
            / "bacselect"
            / "source_truth_execution.py"
        ):
            EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256,
        (
            repo
            / "validation"
            / "selector-v1"
            / "run_monthly_source_truth.py"
        ):
            EXPECTED_STAGE4_V1_WRAPPER_SHA256,
        (
            repo
            / "src"
            / "bacselect"
            / "monthly_sequence_cache_catalogue_v2.py"
        ):
            EXPECTED_CACHE_V2_CORE_SHA256,
        (
            repo
            / "validation"
            / "selector-v1"
            / (
                "run_monthly_"
                "sequence_cache_catalogue_v2.py"
            )
        ):
            EXPECTED_CACHE_V2_EXECUTOR_SHA256,
    }

    for path, expected in (
        frozen.items()
    ):
        if (
            sha256_file(
                path
            )
            != expected
        ):
            _fail(
                "Stage 4 v2 frozen dependency changed: "
                f"{path}"
            )


def _require_regular_file_under(
    stage1_root: Path,
    logical_path: str,
    *,
    label: str,
) -> Path:
    logical = PurePosixPath(
        logical_path
    )

    if (
        logical.is_absolute()
        or not logical.parts
        or ".."
        in logical.parts
    ):
        _fail(
            f"{label} logical path is unsafe"
        )

    path = stage1_root.joinpath(
        *logical.parts
    )

    if (
        not path.is_file()
        or path.is_symlink()
    ):
        _fail(
            f"{label} is not a regular file"
        )

    resolved_root = (
        stage1_root.resolve()
    )

    resolved = path.resolve()

    try:
        resolved.relative_to(
            resolved_root
        )

    except ValueError as exc:
        raise (
            MonthlySourceTruthV2ExecutionError(
                f"{label} escapes Stage 1 root"
            )
        ) from exc

    return path


def _read_artifact_reference(
    stage1_root: Path,
    reference: object,
    *,
    expected_sha256: object,
    label: str,
):
    if not isinstance(
        reference,
        Mapping,
    ):
        _fail(
            f"{label} reference is malformed"
        )

    logical_path = (
        reference.get(
            "logical_path"
        )
    )

    if (
        not isinstance(
            logical_path,
            str,
        )
        or not logical_path
    ):
        _fail(
            f"{label} logical path is malformed"
        )

    reference_sha = (
        validate_sha256(
            reference.get(
                "sha256"
            ),
            label=(
                f"{label} reference SHA256"
            ),
        )
    )

    expected = (
        validate_sha256(
            expected_sha256,
            label=(
                f"{label} expected SHA256"
            ),
        )
    )

    if (
        reference_sha
        != expected
    ):
        _fail(
            f"{label} reference differs "
            "from completion identity"
        )

    path = (
        _require_regular_file_under(
            stage1_root,
            logical_path,
            label=label,
        )
    )

    payload = (
        path.read_bytes()
    )

    observed_sha = (
        hashlib.sha256(
            payload
        ).hexdigest()
    )

    if (
        observed_sha
        != expected
    ):
        _fail(
            f"{label} payload differs "
            "from authenticated identity"
        )

    size_value = (
        reference.get(
            "size_bytes"
        )
    )

    if size_value is not None:
        if (
            not isinstance(
                size_value,
                int,
            )
            or size_value < 0
        ):
            _fail(
                f"{label} reference size is malformed"
            )

        if (
            len(
                payload
            )
            != size_value
        ):
            _fail(
                f"{label} payload size differs "
                "from authenticated identity"
            )

    return (
        path,
        payload,
        (
            path,
            observed_sha,
            len(
                payload
            ),
        ),
    )


def _completion_rows_by_batch(
    completion_record: Mapping[
        str,
        object,
    ],
) -> dict[
    str,
    Mapping[
        str,
        object,
    ],
]:
    values = (
        completion_record.get(
            "batches"
        )
    )

    if not isinstance(
        values,
        list,
    ):
        _fail(
            "completion-v2 batch list is malformed"
        )

    result = {}

    for value in values:
        if not isinstance(
            value,
            Mapping,
        ):
            _fail(
                "completion-v2 batch row is malformed"
            )

        batch_id = (
            value.get(
                "batch_id"
            )
        )

        if (
            not isinstance(
                batch_id,
                str,
            )
            or not batch_id
        ):
            _fail(
                "completion-v2 batch ID is malformed"
            )

        if batch_id in result:
            _fail(
                "completion-v2 contains duplicate batch ID"
            )

        result[
            batch_id
        ] = value

    return result


def _provider_batch_context_v2(
    *,
    stage1_root: Path,
    cache_execution,
    provenance: Mapping[
        str,
        object,
    ],
    completion_batch: Mapping[
        str,
        object,
    ],
    release_id: str,
    source_snapshot_id: str,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    completion_sha256: str,
) -> ProviderBatchContextV2:
    batch_id = str(
        provenance.get(
            "batch_id",
            "",
        )
    )

    if (
        not batch_id
        or completion_batch.get(
            "batch_id"
        )
        != batch_id
    ):
        _fail(
            "provider batch identity differs "
            "from completion-v2"
        )

    identity_checks = (
        (
            provenance.get(
                "cache_origin_release_id"
            ),
            release_id,
            "release",
        ),
        (
            provenance.get(
                "cache_origin_source_snapshot_id"
            ),
            source_snapshot_id,
            "source snapshot",
        ),
        (
            provenance.get(
                "cache_origin_source_production_commit"
            ),
            source_production_commit,
            "source production commit",
        ),
        (
            provenance.get(
                "cache_origin_completion_execution_commit"
            ),
            completion_execution_commit,
            "completion execution commit",
        ),
        (
            provenance.get(
                "cache_origin_execution_commit"
            ),
            cache_execution_commit,
            "cache execution commit",
        ),
        (
            provenance.get(
                "origin_sequence_acquisition_completion_sha256"
            ),
            completion_sha256,
            "completion SHA256",
        ),
    )

    for observed, expected, label in (
        identity_checks
    ):
        if (
            observed
            != expected
        ):
            _fail(
                f"provider {label} differs "
                "from authenticated current release"
            )

    direct_fields = (
        "requested_accessions",
        "accessions_sha256",
        "source_class",
        "recovery_class",
        "recovery_commit",
        "source_batch_sha256",
        "source_package_sha256",
        "recovery_package_sha256",
        "recovery_summary_sha256",
        "cause_evidence_sha256",
        "transport_record_sha256",
        "source_partial_name",
    )

    for field in direct_fields:
        if (
            provenance.get(
                field
            )
            != completion_batch.get(
                field
            )
        ):
            _fail(
                f"provider {field} differs "
                "from completion-v2"
            )

    artifacts = (
        (
            "provider_summary",
            "provider_summary_sha256",
            "provider summary",
        ),
        (
            "candidate_audit",
            "candidate_sequence_audit_sha256",
            "candidate audit",
        ),
        (
            "component_audit",
            "component_sequence_audit_sha256",
            "component audit",
        ),
        (
            "package_manifest",
            "package_manifest_sha256",
            "package manifest",
        ),
    )

    payloads = {}
    paths = {}
    observations = []
    parents = set()

    for (
        provenance_key,
        completion_key,
        label,
    ) in artifacts:
        (
            path,
            payload,
            observation,
        ) = _read_artifact_reference(
            stage1_root,
            provenance.get(
                provenance_key
            ),
            expected_sha256=(
                completion_batch.get(
                    completion_key
                )
            ),
            label=(
                f"{batch_id} {label}"
            ),
        )

        paths[
            provenance_key
        ] = path

        payloads[
            provenance_key
        ] = payload

        observations.append(
            observation
        )

        parents.add(
            path.parent.resolve()
        )

    if len(
        parents
    ) != 1:
        _fail(
            "authenticated provider artifacts "
            "do not share one batch directory"
        )

    provider_root = next(
        iter(
            parents
        )
    )

    if (
        paths[
            "provider_summary"
        ].name
        != completion_batch.get(
            "provider_summary_name"
        )
    ):
        _fail(
            "provider-summary basename differs "
            "from completion-v2"
        )

    if (
        paths[
            "package_manifest"
        ].name
        != completion_batch.get(
            "package_manifest_name"
        )
    ):
        _fail(
            "package-manifest basename differs "
            "from completion-v2"
        )

    if (
        provenance.get(
            "origin_package_file_readback_sha256"
        )
        != completion_batch.get(
            "package_file_readback_sha256"
        )
    ):
        _fail(
            "provider package read-back SHA256 "
            "differs from completion-v2"
        )

    parser = getattr(
        cache_v1,
        "_parse_tsv",
        None,
    )

    if not callable(
        parser
    ):
        _fail(
            "frozen cache-v1 TSV parser disappeared"
        )

    batch = (
        cache_execution.BatchEvidence(
            provenance=(
                provenance
            ),
            candidate_rows=tuple(
                parser(
                    payloads[
                        "candidate_audit"
                    ],
                    fields=(
                        cache_execution
                        .CANDIDATE_AUDIT_FIELDS
                    ),
                    label=(
                        f"{batch_id} candidate audit"
                    ),
                )
            ),
            component_rows=tuple(
                parser(
                    payloads[
                        "component_audit"
                    ],
                    fields=(
                        cache_execution
                        .COMPONENT_AUDIT_FIELDS
                    ),
                    label=(
                        f"{batch_id} component audit"
                    ),
                )
            ),
            package_rows=tuple(
                parser(
                    payloads[
                        "package_manifest"
                    ],
                    fields=(
                        cache_execution
                        .PACKAGE_FILE_FIELDS
                    ),
                    label=(
                        f"{batch_id} package manifest"
                    ),
                )
            ),
        )
    )

    return (
        ProviderBatchContextV2(
            batch_id=(
                batch_id
            ),
            provider_root=(
                provider_root
            ),
            candidate_audit_path=(
                paths[
                    "candidate_audit"
                ]
            ),
            batch=(
                batch
            ),
            observations=tuple(
                observations
            ),
        )
    )


def _evaluate_provider_candidate(
    stage4_v1,
    *,
    bridge,
    provider: ProviderBatchContextV2,
):
    candidate_audit = (
        provider.candidate_audit_path
    )

    (
        candidate,
        components,
        package_manifest,
    ) = (
        stage4_v1
        ._source_truth_objects(
            bridge,
            audit_path=(
                candidate_audit
            ),
        )
    )

    try:
        decision = (
            stage4_v1
            .source_truth_execution
            .evaluate_candidate(
                candidate,
                components,
                package_manifest,
            )
        )

        resolver = getattr(
            stage4_v1
            .source_truth_execution,
            "resolve_manifest_path",
            None,
        )

        if not callable(
            resolver
        ):
            _fail(
                "frozen source-truth manifest "
                "resolver disappeared"
            )

        fasta_path = resolver(
            candidate.batch_dir,
            bridge.fasta_package_path,
        )

    except (
        MonthlySourceTruthV2ExecutionError
    ):
        raise

    except Exception as exc:
        raise (
            MonthlySourceTruthV2ExecutionError(
                "source-truth evaluation failed for "
                f"{bridge.accession}"
            )
        ) from exc

    observation = (
        stage4_v1
        ._observe_exact_file(
            fasta_path,
            expected_sha256=(
                bridge.fasta_sha256
            ),
            expected_size_bytes=(
                bridge.fasta_size_bytes
            ),
        )
    )

    return (
        decision,
        observation,
    )


def catalogue_chain_sha256_v2(
    signature: Sequence[
        tuple[
            str,
            str,
            str,
        ]
    ],
) -> str:
    payload = (
        _canonical_json_bytes(
            {
                "items": [
                    {
                        "cache_execution_commit":
                            cache_commit,
                        "catalogue_sha256":
                            catalogue_sha,
                        "release_id":
                            release_id,
                    }
                    for (
                        release_id,
                        cache_commit,
                        catalogue_sha,
                    )
                    in signature
                ],
                "schema_version":
                    (
                        "bacselect-sequence-cache-"
                        "chain-signature-v2"
                    ),
            }
        )
    )

    return (
        hashlib.sha256(
            payload
        ).hexdigest()
    )


def build_completion_receipt_v2(
    **kwargs,
) -> bytes:
    required_sha_fields = (
        "source_snapshot_record_sha256",
        "metadata_record_sha256",
        "metadata_completion_sha256",
        "sequence_acquisition_completion_sha256",
        "catalogue_chain_sha256",
        "sequence_cache_catalogue_sha256",
        "sequence_cache_entries_sha256",
        "retained_accessions_sha256",
        "sequence_eligible_accessions_sha256",
        "sequence_ineligible_accessions_sha256",
        "decisions_sha256",
        "relations_sha256",
        "record_sha256",
    )

    for field in required_sha_fields:
        validate_sha256(
            kwargs[
                field
            ],
            label=(
                field.replace(
                    "_",
                    " ",
                )
            ),
        )

    for field in (
        "source_production_commit",
        "completion_execution_commit",
        "cache_execution_commit",
        "source_truth_execution_commit",
    ):
        validate_commit(
            kwargs[
                field
            ],
            label=(
                field.replace(
                    "_",
                    " ",
                )
            ),
        )

    count_fields = (
        "catalogue_chain_count",
        "retained_count",
        "sequence_eligible_count",
        "sequence_ineligible_count",
        "decision_count",
        "relation_count",
    )

    for field in count_fields:
        value = (
            kwargs[
                field
            ]
        )

        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
            or value < 0
        ):
            _fail(
                field.replace(
                    "_",
                    " ",
                )
                + " is invalid"
            )

    if (
        kwargs[
            "catalogue_chain_count"
        ]
        == 0
    ):
        _fail(
            "catalogue chain count must be positive"
        )

    if (
        kwargs[
            "retained_count"
        ]
        != (
            kwargs[
                "sequence_eligible_count"
            ]
            + kwargs[
                "sequence_ineligible_count"
            ]
        )
    ):
        _fail(
            "completion population accounting "
            "is inconsistent"
        )

    if (
        kwargs[
            "decision_count"
        ]
        != kwargs[
            "sequence_eligible_count"
        ]
    ):
        _fail(
            "completion decision count differs "
            "from eligible count"
        )

    record = {
        **kwargs,
        "monthly_source_truth_sha256":
            EXPECTED_MONTHLY_SOURCE_TRUTH_SHA256,
        "schema_version":
            COMPLETION_SCHEMA,
        "source_truth_execution_sha256":
            EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256,
        "status":
            COMPLETION_STATUS,
    }

    return (
        _canonical_json_bytes(
            record
        )
    )


def audit_completion_receipt_v2(
    payload: bytes,
    **kwargs,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "source-truth completion-v2 receipt "
            "must be bytes"
        )

    expected = (
        build_completion_receipt_v2(
            **kwargs
        )
    )

    if (
        payload
        != expected
    ):
        _fail(
            "source-truth completion-v2 "
            "receipt changed"
        )

    value = json.loads(
        payload.decode(
            "ascii"
        )
    )

    if (
        value.get(
            "schema_version"
        )
        != COMPLETION_SCHEMA
        or value.get(
            "status"
        )
        != COMPLETION_STATUS
    ):
        _fail(
            "source-truth completion-v2 "
            "schema/status changed"
        )

    return value


def _audit_scientific_payloads_v2(
    *,
    decisions_payload: bytes,
    relations_payload: bytes,
    record_payload: bytes,
    catalogue_record: Mapping[
        str,
        object,
    ],
    catalogue_sha256: str,
    current_metadata: Mapping[
        str,
        str,
    ],
    release_id: str,
    source_snapshot_id: str,
    execution_commit: str,
    metadata_record_sha256: str,
    metadata_completion_sha256: str,
) -> Mapping[
    str,
    object,
]:
    monthly_source_truth.audit_monthly_source_truth_decisions(
        decisions_payload
    )

    monthly_source_truth.audit_monthly_source_truth_relations(
        relations_payload
    )

    return (
        monthly_source_truth
        .audit_monthly_source_truth_record_from_audited_catalogue(
            record_payload,
            catalogue_record=(
                catalogue_record
            ),
            catalogue_sha256=(
                catalogue_sha256
            ),
            current_metadata=(
                current_metadata
            ),
            release_id=(
                release_id
            ),
            source_snapshot_id=(
                source_snapshot_id
            ),
            origin_git_commit=(
                execution_commit
            ),
            metadata_record_sha256=(
                metadata_record_sha256
            ),
            metadata_completion_sha256=(
                metadata_completion_sha256
            ),
            decisions_payload=(
                decisions_payload
            ),
            relations_payload=(
                relations_payload
            ),
        )
    )


def _publish_completion_v2(
    stage4_v1,
    *,
    stage1_root: Path,
    payload: bytes,
    auditor,
    stability_check,
) -> Path:
    final = (
        stage1_root
        / COMPLETION_NAME
    )

    temp = (
        stage1_root
        / COMPLETION_TEMP_NAME
    )

    if (
        os.path.lexists(
            final
        )
        or os.path.lexists(
            temp
        )
    ):
        _fail(
            "source-truth completion-v2 "
            "output already exists"
        )

    try:
        stage4_v1._write_bytes_exclusive(
            temp,
            payload,
        )

        observed = (
            temp.read_bytes()
        )

        if (
            observed
            != payload
        ):
            _fail(
                "source-truth completion-v2 "
                "temporary readback changed"
            )

        auditor(
            observed
        )

        stability_check()

        try:
            os.link(
                temp,
                final,
            )

        except FileExistsError as exc:
            raise (
                MonthlySourceTruthV2ExecutionError(
                    "source-truth completion-v2 "
                    "appeared before publication"
                )
            ) from exc

        temp.unlink()

        stage4_v1.fsync_directory(
            stage1_root
        )

        final_payload = (
            final.read_bytes()
        )

        if (
            final_payload
            != payload
        ):
            _fail(
                "published source-truth completion-v2 "
                "readback changed"
            )

        auditor(
            final_payload
        )

        return final

    except Exception:
        if (
            os.path.lexists(
                temp
            )
            and temp.is_file()
            and not temp.is_symlink()
        ):
            temp.unlink()

        raise


def execute_monthly_source_truth_v2(
    *,
    repo: Path,
    source_repo: Path,
    production_root: Path,
    stage1_root: Path,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
) -> MonthlySourceTruthV2ExecutionResult:
    root = Path(
        repo
    ).resolve()

    source_root = Path(
        source_repo
    ).resolve()

    production = Path(
        production_root
    )

    stage1_input = Path(
        stage1_root
    )

    if (
        not production.is_absolute()
        or not stage1_input.is_absolute()
    ):
        _fail(
            "production and Stage 1 roots "
            "must be absolute"
        )

    if (
        not source_root.is_dir()
        or source_root.is_symlink()
    ):
        _fail(
            "source repository is not a real directory"
        )

    if (
        not stage1_input.is_dir()
        or stage1_input.is_symlink()
    ):
        _fail(
            "Stage 1 root is not a real directory"
        )

    source_commit = (
        validate_commit(
            source_production_commit,
            label=(
                "source production commit"
            ),
        )
    )

    completion_commit = (
        validate_commit(
            completion_execution_commit,
            label=(
                "completion execution commit"
            ),
        )
    )

    cache_commit = (
        validate_commit(
            cache_execution_commit,
            label=(
                "cache execution commit"
            ),
        )
    )

    stage4_commit = (
        validate_commit(
            source_truth_execution_commit,
            label=(
                "source-truth execution commit"
            ),
        )
    )

    expected_completion_sha = (
        validate_sha256(
            expected_completion_sha256,
            label=(
                "expected completion-v2 SHA256"
            ),
        )
    )

    expected_catalogue_sha = (
        validate_sha256(
            expected_catalogue_sha256,
            label=(
                "expected cache-v2 SHA256"
            ),
        )
    )

    stage4_v1 = (
        load_stage4_v1(
            root
        )
    )

    cache_v2_execution = (
        load_cache_v2_execution(
            root
        )
    )

    cache_execution = (
        stage4_v1
        .load_frozen_cache_execution(
            source_root
        )
    )

    if (
        _git(
            source_root,
            "rev-parse",
            "HEAD",
        )
        != source_commit
    ):
        _fail(
            "source repository HEAD differs "
            "from source production commit"
        )

    if _git(
        source_root,
        "status",
        "--porcelain",
    ):
        _fail(
            "source production repository "
            "is not clean"
        )

    try:
        metadata = (
            cache_execution
            .load_current_metadata_context(
                repo=(
                    source_root
                ),
                production_root=(
                    production
                ),
                stage1_root=(
                    stage1_input
                ),
                execution_commit=(
                    source_commit
                ),
            )
        )

    except Exception as exc:
        raise (
            MonthlySourceTruthV2ExecutionError(
                "current metadata re-audit failed"
            )
        ) from exc

    stage1 = (
        metadata
        .stage1_root
        .resolve()
    )

    if (
        stage1
        != stage1_input.resolve()
    ):
        _fail(
            "metadata audit changed Stage 1 root"
        )

    stage4_v1.require_output_paths_clear(
        stage1
    )

    for extra in (
        stage1
        / COMPLETION_NAME,
        stage1
        / COMPLETION_TEMP_NAME,
    ):
        if os.path.lexists(
            extra
        ):
            _fail(
                "Stage 4 v2 output path already exists"
            )

    completion_path = (
        stage1
        / COMPLETION_V2_NAME
    )

    completion_payload = (
        completion_path.read_bytes()
    )

    completion_sha = (
        hashlib.sha256(
            completion_payload
        ).hexdigest()
    )

    if (
        completion_sha
        != expected_completion_sha
    ):
        _fail(
            "completion-v2 SHA256 differs "
            "from authorized identity"
        )

    completion_record = (
        cache_v2
        ._audit_completion_v2_payload_internal(
            completion_payload
        )
    )

    if (
        completion_record.get(
            "source_snapshot_id"
        )
        != metadata.source_snapshot_id
    ):
        _fail(
            "completion-v2 snapshot differs "
            "from current metadata"
        )

    if (
        completion_record.get(
            "source_snapshot_record_sha256"
        )
        != metadata.source_snapshot_record_sha256
    ):
        _fail(
            "completion-v2 source-snapshot record "
            "differs from current metadata"
        )

    if (
        completion_record.get(
            "source_production_commit"
        )
        != source_commit
    ):
        _fail(
            "completion-v2 source-production "
            "identity changed"
        )

    if (
        completion_record.get(
            "completion_execution_commit"
        )
        != completion_commit
    ):
        _fail(
            "completion-v2 execution identity changed"
        )

    plan_path = (
        stage1
        / stage4_v1.SEQUENCE_PLAN_DIR
        / stage4_v1.SEQUENCE_PLAN_RECORD_NAME
    )

    targets_path = (
        stage1
        / stage4_v1.SEQUENCE_PLAN_DIR
        / stage4_v1.FRESH_TARGET_NAME
    )

    if (
        sha256_file(
            plan_path
        )
        != completion_record.get(
            "stage2_sequence_plan_record_sha256"
        )
    ):
        _fail(
            "completion-v2 sequence-plan "
            "binding changed"
        )

    if (
        sha256_file(
            targets_path
        )
        != completion_record.get(
            "stage2_fresh_target_manifest_sha256"
        )
    ):
        _fail(
            "completion-v2 fresh-target "
            "binding changed"
        )

    catalogue_path = (
        stage1
        / CATALOGUE_NAME
    )

    catalogue_payload = (
        catalogue_path.read_bytes()
    )

    catalogue_sha = (
        hashlib.sha256(
            catalogue_payload
        ).hexdigest()
    )

    if (
        catalogue_sha
        != expected_catalogue_sha
    ):
        _fail(
            "cache-v2 SHA256 differs "
            "from authorized identity"
        )

    catalogue_record = (
        cache_v2
        .audit_sequence_cache_catalogue_v2(
            catalogue_payload
        )
    )

    catalogue_checks = (
        (
            catalogue_record.get(
                "release_id"
            ),
            metadata.release_id,
            "release",
        ),
        (
            catalogue_record.get(
                "source_snapshot_id"
            ),
            metadata.source_snapshot_id,
            "source snapshot",
        ),
        (
            catalogue_record.get(
                "source_production_commit"
            ),
            source_commit,
            "source production commit",
        ),
        (
            catalogue_record.get(
                "completion_execution_commit"
            ),
            completion_commit,
            "completion execution commit",
        ),
        (
            catalogue_record.get(
                "cache_execution_commit"
            ),
            cache_commit,
            "cache execution commit",
        ),
        (
            catalogue_record.get(
                "sequence_acquisition_completion_sha256"
            ),
            completion_sha,
            "completion SHA256",
        ),
    )

    for (
        observed,
        expected,
        label,
    ) in catalogue_checks:
        if (
            observed
            != expected
        ):
            _fail(
                f"cache-v2 {label} binding changed"
            )

    chain = (
        cache_v2_execution
        .discover_catalogue_chain_v2(
            production,
            current_release_id=(
                metadata.release_id
            ),
            include_current=True,
            current_catalogue_path=(
                catalogue_path
            ),
        )
    )

    signature = (
        cache_v2_execution
        .chain_signature(
            chain
        )
    )

    if (
        len(
            chain
        )
        != 1
        or signature
        != (
            (
                metadata.release_id,
                cache_commit,
                catalogue_sha,
            ),
        )
    ):
        _fail(
            "September Stage 4 v2 requires "
            "one current GENESIS catalogue"
        )

    if (
        catalogue_record.get(
            "catalogue_mode"
        )
        != cache_v2.GENESIS
    ):
        _fail(
            "September Stage 4 v2 requires "
            "GENESIS catalogue"
        )

    if (
        catalogue_record.get(
            "carried_forward_entry_count"
        )
        != 0
    ):
        _fail(
            "September Stage 4 v2 does not permit "
            "historical cache entries"
        )

    if (
        catalogue_record.get(
            "previous_catalogue_release_id"
        )
        is not None
        or catalogue_record.get(
            "previous_catalogue_sha256"
        )
        is not None
    ):
        _fail(
            "September GENESIS catalogue "
            "unexpectedly has predecessor"
        )

    compatibility_catalogue = dict(
        catalogue_record
    )

    compatibility_catalogue[
        "origin_git_commit"
    ] = stage4_commit

    try:
        population = (
            monthly_source_truth
            .build_monthly_source_truth_population_from_audited_catalogue(
                compatibility_catalogue,
                catalogue_sha256=(
                    catalogue_sha
                ),
                current_metadata=(
                    metadata.retained_metadata
                ),
                release_id=(
                    metadata.release_id
                ),
                source_snapshot_id=(
                    metadata.source_snapshot_id
                ),
                origin_git_commit=(
                    stage4_commit
                ),
            )
        )

    except Exception as exc:
        raise (
            MonthlySourceTruthV2ExecutionError(
                "pure monthly source-truth "
                "population audit failed"
            )
        ) from exc

    entries_by_accession = (
        stage4_v1
        ._catalogue_entries_by_accession(
            catalogue_record
        )
    )

    provenance_by_sha = (
        stage4_v1
        ._catalogue_provenance_by_sha(
            catalogue_record
        )
    )

    completion_by_batch = (
        _completion_rows_by_batch(
            completion_record
        )
    )

    decisions = []
    observations = []

    provider_cache = {}

    for accession in (
        population
        .sequence_eligible_accessions
    ):
        entry = (
            entries_by_accession.get(
                accession
            )
        )

        if entry is None:
            _fail(
                "eligible accession disappeared "
                "from current catalogue"
            )

        provenance_sha = (
            stage4_v1
            .validate_sha256(
                entry.get(
                    "origin_batch_provenance_sha256"
                ),
                label=(
                    "entry batch-provenance SHA256"
                ),
            )
        )

        provenance = (
            provenance_by_sha.get(
                provenance_sha
            )
        )

        if provenance is None:
            _fail(
                "eligible catalogue entry references "
                "missing provenance"
            )

        if (
            provenance.get(
                "cache_origin_release_id"
            )
            != metadata.release_id
        ):
            _fail(
                "September Stage 4 v2 encountered "
                "historical-origin entry"
            )

        provider = (
            provider_cache.get(
                provenance_sha
            )
        )

        if provider is None:
            batch_id = str(
                provenance.get(
                    "batch_id",
                    "",
                )
            )

            completion_batch = (
                completion_by_batch.get(
                    batch_id
                )
            )

            if completion_batch is None:
                _fail(
                    "catalogue provenance batch is "
                    "missing from completion-v2"
                )

            provider = (
                _provider_batch_context_v2(
                    stage1_root=(
                        stage1
                    ),
                    cache_execution=(
                        cache_execution
                    ),
                    provenance=(
                        provenance
                    ),
                    completion_batch=(
                        completion_batch
                    ),
                    release_id=(
                        metadata.release_id
                    ),
                    source_snapshot_id=(
                        metadata.source_snapshot_id
                    ),
                    source_production_commit=(
                        source_commit
                    ),
                    completion_execution_commit=(
                        completion_commit
                    ),
                    cache_execution_commit=(
                        cache_commit
                    ),
                    completion_sha256=(
                        completion_sha
                    ),
                )
            )

            provider_cache[
                provenance_sha
            ] = provider

            for (
                path,
                digest,
                size,
            ) in provider.observations:
                observations.append(
                    stage4_v1.InputObservation(
                        path=(
                            path
                        ),
                        sha256=(
                            digest
                        ),
                        size_bytes=(
                            size
                        ),
                    )
                )

        bridge = (
            stage4_v1
            .validate_candidate_bridge(
                cache_execution,
                entry=(
                    entry
                ),
                batch=(
                    provider.batch
                ),
            )
        )

        (
            decision,
            observation,
        ) = _evaluate_provider_candidate(
            stage4_v1,
            bridge=(
                bridge
            ),
            provider=(
                provider
            ),
        )

        decisions.append(
            decision
        )

        observations.append(
            observation
        )

    build = (
        monthly_source_truth
        .build_monthly_source_truth(
            population,
            decisions,
        )
    )

    decisions_payload = (
        monthly_source_truth
        .serialize_monthly_source_truth_decisions(
            build
        )
    )

    relations_payload = (
        monthly_source_truth
        .serialize_monthly_source_truth_relations(
            build
        )
    )

    record_payload = (
        monthly_source_truth
        .serialize_monthly_source_truth_record(
            build,
            metadata_record_sha256=(
                metadata.metadata_record_sha256
            ),
            metadata_completion_sha256=(
                metadata.metadata_completion_sha256
            ),
        )
    )

    audited_record = (
        _audit_scientific_payloads_v2(
            decisions_payload=(
                decisions_payload
            ),
            relations_payload=(
                relations_payload
            ),
            record_payload=(
                record_payload
            ),
            catalogue_record=(
                compatibility_catalogue
            ),
            catalogue_sha256=(
                catalogue_sha
            ),
            current_metadata=(
                metadata.retained_metadata
            ),
            release_id=(
                metadata.release_id
            ),
            source_snapshot_id=(
                metadata.source_snapshot_id
            ),
            execution_commit=(
                stage4_commit
            ),
            metadata_record_sha256=(
                metadata.metadata_record_sha256
            ),
            metadata_completion_sha256=(
                metadata.metadata_completion_sha256
            ),
        )
    )

    decisions_sha = (
        hashlib.sha256(
            decisions_payload
        ).hexdigest()
    )

    relations_sha = (
        hashlib.sha256(
            relations_payload
        ).hexdigest()
    )

    record_sha = (
        hashlib.sha256(
            record_payload
        ).hexdigest()
    )

    metadata_identity = (
        cache_execution
        .metadata_context_identity(
            metadata
        )
    )

    chain_sha = (
        catalogue_chain_sha256_v2(
            signature
        )
    )

    def stability_check() -> None:
        observed_metadata = (
            cache_execution
            .load_current_metadata_context(
                repo=(
                    source_root
                ),
                production_root=(
                    production
                ),
                stage1_root=(
                    stage1
                ),
                execution_commit=(
                    source_commit
                ),
            )
        )

        if (
            cache_execution
            .metadata_context_identity(
                observed_metadata
            )
            != metadata_identity
        ):
            _fail(
                "metadata identity changed during "
                "Stage 4 v2 execution"
            )

        if (
            completion_path.read_bytes()
            != completion_payload
        ):
            _fail(
                "completion-v2 changed during "
                "Stage 4 v2 execution"
            )

        if (
            catalogue_path.read_bytes()
            != catalogue_payload
        ):
            _fail(
                "cache-v2 changed during "
                "Stage 4 v2 execution"
            )

        observed_chain = (
            cache_v2_execution
            .discover_catalogue_chain_v2(
                production,
                current_release_id=(
                    metadata.release_id
                ),
                include_current=True,
                current_catalogue_path=(
                    catalogue_path
                ),
            )
        )

        if (
            cache_v2_execution
            .chain_signature(
                observed_chain
            )
            != signature
        ):
            _fail(
                "cache-v2 chain changed during "
                "Stage 4 v2 execution"
            )

        stage4_v1.reverify_observations(
            observations
        )

    payloads = {
        DECISIONS_NAME:
            decisions_payload,
        RELATIONS_NAME:
            relations_payload,
        RECORD_NAME:
            record_payload,
    }

    def scientific_auditor(
        values: Mapping[
            str,
            bytes,
        ],
    ):
        return (
            _audit_scientific_payloads_v2(
                decisions_payload=(
                    values[
                        DECISIONS_NAME
                    ]
                ),
                relations_payload=(
                    values[
                        RELATIONS_NAME
                    ]
                ),
                record_payload=(
                    values[
                        RECORD_NAME
                    ]
                ),
                catalogue_record=(
                    compatibility_catalogue
                ),
                catalogue_sha256=(
                    catalogue_sha
                ),
                current_metadata=(
                    metadata.retained_metadata
                ),
                release_id=(
                    metadata.release_id
                ),
                source_snapshot_id=(
                    metadata.source_snapshot_id
                ),
                execution_commit=(
                    stage4_commit
                ),
                metadata_record_sha256=(
                    metadata.metadata_record_sha256
                ),
                metadata_completion_sha256=(
                    metadata.metadata_completion_sha256
                ),
            )
        )

    stage_root = (
        stage4_v1
        .publish_scientific_stage(
            stage1_root=(
                stage1
            ),
            payloads=(
                payloads
            ),
            auditor=(
                scientific_auditor
            ),
            stability_check=(
                stability_check
            ),
        )
    )

    completion_kwargs = {
        "release_id":
            metadata.release_id,
        "source_snapshot_id":
            metadata.source_snapshot_id,
        "source_snapshot_record_sha256":
            metadata.source_snapshot_record_sha256,
        "source_production_commit":
            source_commit,
        "completion_execution_commit":
            completion_commit,
        "cache_execution_commit":
            cache_commit,
        "source_truth_execution_commit":
            stage4_commit,
        "metadata_record_sha256":
            metadata.metadata_record_sha256,
        "metadata_completion_sha256":
            metadata.metadata_completion_sha256,
        "sequence_acquisition_completion_sha256":
            completion_sha,
        "catalogue_chain_count":
            len(
                chain
            ),
        "catalogue_chain_sha256":
            chain_sha,
        "sequence_cache_catalogue_sha256":
            catalogue_sha,
        "sequence_cache_entries_sha256":
            str(
                catalogue_record[
                    "entries_sha256"
                ]
            ),
        "retained_count":
            int(
                audited_record[
                    "retained_count"
                ]
            ),
        "sequence_eligible_count":
            int(
                audited_record[
                    "sequence_eligible_count"
                ]
            ),
        "sequence_ineligible_count":
            int(
                audited_record[
                    "sequence_ineligible_count"
                ]
            ),
        "retained_accessions_sha256":
            str(
                audited_record[
                    "retained_accessions_sha256"
                ]
            ),
        "sequence_eligible_accessions_sha256":
            str(
                audited_record[
                    "sequence_eligible_accessions_sha256"
                ]
            ),
        "sequence_ineligible_accessions_sha256":
            str(
                audited_record[
                    "sequence_ineligible_accessions_sha256"
                ]
            ),
        "decision_count":
            int(
                audited_record[
                    "decision_count"
                ]
            ),
        "relation_count":
            int(
                audited_record[
                    "relation_count"
                ]
            ),
        "decisions_sha256":
            decisions_sha,
        "relations_sha256":
            relations_sha,
        "record_sha256":
            record_sha,
    }

    completion_payload_out = (
        build_completion_receipt_v2(
            **completion_kwargs
        )
    )

    def completion_auditor(
        payload: bytes,
    ):
        return (
            audit_completion_receipt_v2(
                payload,
                **completion_kwargs
            )
        )

    try:
        completion_out = (
            _publish_completion_v2(
                stage4_v1,
                stage1_root=(
                    stage1
                ),
                payload=(
                    completion_payload_out
                ),
                auditor=(
                    completion_auditor
                ),
                stability_check=(
                    stability_check
                ),
            )
        )

    except Exception:
        stage4_v1._remove_stage_directory(
            stage_root
        )

        stage4_v1.fsync_directory(
            stage1
        )

        raise

    return (
        MonthlySourceTruthV2ExecutionResult(
            release_id=(
                metadata.release_id
            ),
            source_snapshot_id=(
                metadata.source_snapshot_id
            ),
            stage_root=(
                stage_root
            ),
            completion_path=(
                completion_out
            ),
            retained_count=(
                int(
                    audited_record[
                        "retained_count"
                    ]
                )
            ),
            sequence_eligible_count=(
                int(
                    audited_record[
                        "sequence_eligible_count"
                    ]
                )
            ),
            sequence_ineligible_count=(
                int(
                    audited_record[
                        "sequence_ineligible_count"
                    ]
                )
            ),
            decision_count=(
                int(
                    audited_record[
                        "decision_count"
                    ]
                )
            ),
            relation_count=(
                int(
                    audited_record[
                        "relation_count"
                    ]
                )
            ),
            decisions_sha256=(
                decisions_sha
            ),
            relations_sha256=(
                relations_sha
            ),
            record_sha256=(
                record_sha
            ),
            completion_sha256=(
                hashlib.sha256(
                    completion_payload_out
                ).hexdigest()
            ),
        )
    )


def main(
    argv: Sequence[
        str
    ]
    | None = None,
) -> int:
    parser = (
        argparse.ArgumentParser(
            description=(
                "Execute recovery-aware BacSelect "
                "monthly Stage 4 source truth."
            )
        )
    )

    parser.add_argument(
        "--expected-commit",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-test-sha256",
        required=True,
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
        "--source-production-commit",
        required=True,
    )

    parser.add_argument(
        "--completion-execution-commit",
        required=True,
    )

    parser.add_argument(
        "--cache-execution-commit",
        required=True,
    )

    parser.add_argument(
        "--expected-completion-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-catalogue-sha256",
        required=True,
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    args = parser.parse_args(
        argv
    )

    if not (
        args.authorize_real_execution
    ):
        _fail(
            "production Stage 4 v2 execution "
            "requires explicit authorization"
        )

    repo = (
        Path(
            __file__
        )
        .resolve()
        .parents[
            2
        ]
    )

    repository_preflight(
        repo,
        expected_commit=(
            args.expected_commit
        ),
        expected_wrapper_sha256=(
            args.expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            args.expected_wrapper_test_sha256
        ),
    )

    result = (
        execute_monthly_source_truth_v2(
            repo=(
                repo
            ),
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
                args.source_production_commit
            ),
            completion_execution_commit=(
                args.completion_execution_commit
            ),
            cache_execution_commit=(
                args.cache_execution_commit
            ),
            source_truth_execution_commit=(
                args.expected_commit
            ),
            expected_completion_sha256=(
                args.expected_completion_sha256
            ),
            expected_catalogue_sha256=(
                args.expected_catalogue_sha256
            ),
        )
    )

    print(
        "PASS | BacSelect monthly "
        "source-truth v2 execution complete"
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        "source_snapshot_id="
        f"{result.source_snapshot_id}"
    )

    print(
        f"stage_root={result.stage_root}"
    )

    print(
        "completion_path="
        f"{result.completion_path}"
    )

    print(
        f"retained_count={result.retained_count}"
    )

    print(
        "sequence_eligible_count="
        f"{result.sequence_eligible_count}"
    )

    print(
        "sequence_ineligible_count="
        f"{result.sequence_ineligible_count}"
    )

    print(
        f"decision_count={result.decision_count}"
    )

    print(
        f"relation_count={result.relation_count}"
    )

    print(
        "decisions_sha256="
        f"{result.decisions_sha256}"
    )

    print(
        "relations_sha256="
        f"{result.relations_sha256}"
    )

    print(
        f"record_sha256={result.record_sha256}"
    )

    print(
        "completion_sha256="
        f"{result.completion_sha256}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
