from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from bacselect import monthly_sequence_recovery_authority as authority
from bacselect.monthly_sequence_acquisition_completion import (
    MonthlySequenceAcquisitionCompletionError,
    build_sequence_acquisition_completion_record,
)
from bacselect.monthly_sequence_ordinary_provider import (
    MonthlySequenceOrdinaryProviderError,
    SOURCE_CLASS_FRESH,
    audit_completed_transport_provider,
)


ROOT = Path(__file__).resolve().parents[1]


def load_fixture():
    path = (
        ROOT
        / "tests"
        / "test_monthly_sequence_acquisition_completion.py"
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            "_bacselect_ordinary_provider_v1_fixture",
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "could not load frozen v1 completion fixture"
        )

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    sys.modules[
        spec.name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


fixture = load_fixture()


def make_values(
    count=3,
):
    (
        plan,
        manifest,
        targets,
    ) = fixture.make_plan(
        count
    )

    batch_count = (
        (
            count
            + fixture.FRESH_BATCH_SIZE
            - 1
        )
        // fixture.FRESH_BATCH_SIZE
        if count
        else 0
    )

    batches = tuple(
        fixture.make_batch(
            plan,
            manifest,
            targets,
            index,
        )
        for index in range(
            1,
            batch_count
            + 1,
        )
    )

    return {
        "plan":
            plan,
        "manifest":
            manifest,
        "targets":
            targets,
        "batch_count":
            batch_count,
        "batches":
            batches,
    }


def adapter_kwargs(
    values,
    *,
    batch_index=1,
):
    start = (
        batch_index
        - 1
    ) * fixture.FRESH_BATCH_SIZE

    stop = min(
        start
        + fixture.FRESH_BATCH_SIZE,
        len(
            values[
                "targets"
            ]
        ),
    )

    return {
        "batch_index":
            batch_index,
        "expected_batch_count":
            values[
                "batch_count"
            ],
        "expected_fresh_count":
            len(
                values[
                    "targets"
                ]
            ),
        "batch_targets":
            values[
                "targets"
            ][
                start:
                stop
            ],
        "source_snapshot_id":
            fixture.SNAPSHOT,
        "source_snapshot_record_sha256":
            fixture.SNAPSHOT_SHA,
        "stage2_sequence_plan_record_sha256":
            hashlib.sha256(
                values[
                    "plan"
                ]
            ).hexdigest(),
        "stage2_fresh_target_manifest_sha256":
            hashlib.sha256(
                values[
                    "manifest"
                ]
            ).hexdigest(),
        "source_production_commit":
            fixture.COMMIT,
        "environment_explicit_sha256":
            fixture.ENVIRONMENT_SHA,
    }


def v1_kwargs(
    values,
    *,
    batches=None,
):
    batch_values = (
        values[
            "batches"
        ]
        if batches is None
        else tuple(
            batches
        )
    )

    ids = tuple(
        value.batch_id
        for value in batch_values
    )

    return {
        "source_snapshot_id":
            fixture.SNAPSHOT,
        "source_snapshot_record_sha256":
            fixture.SNAPSHOT_SHA,
        "stage2_sequence_plan_record":
            values[
                "plan"
            ],
        "stage2_fresh_target_manifest":
            values[
                "manifest"
            ],
        "origin_git_commit":
            fixture.COMMIT,
        "environment_explicit_sha256":
            fixture.ENVIRONMENT_SHA,
        "batches":
            batch_values,
        "discovered_final_batch_ids":
            ids,
        "discovered_partial_batch_ids":
            (),
        "unexpected_batch_entries":
            (),
    }


def rewritten_summary(
    evidence,
    **changes,
):
    payload = json.loads(
        evidence.summary_payload.decode(
            "ascii"
        )
    )

    payload.update(
        changes
    )

    return replace(
        evidence,
        summary_payload=(
            fixture.transport_json(
                payload
            )
        ),
    )


def test_source_class_matches_frozen_authority():
    assert SOURCE_CLASS_FRESH == (
        authority.SOURCE_CLASS_FRESH
    )


def test_accepted_ordinary_provider_matches_v1_completion_row():
    values = make_values(
        3
    )

    evidence = values[
        "batches"
    ][0]

    audited = (
        audit_completed_transport_provider(
            evidence,
            **adapter_kwargs(
                values
            ),
        )
    )

    v1 = (
        build_sequence_acquisition_completion_record(
            **v1_kwargs(
                values
            )
        )
    )

    row = v1[
        "batches"
    ][0]

    assert audited.batch_id == (
        row[
            "batch_id"
        ]
    )

    assert audited.source_class == (
        SOURCE_CLASS_FRESH
    )

    assert audited.requested_accessions == (
        row[
            "requested_accessions"
        ]
    )

    assert audited.first_accession == (
        row[
            "first_accession"
        ]
    )

    assert audited.last_accession == (
        row[
            "last_accession"
        ]
    )

    assert (
        audited.observed_batch_target_manifest_sha256
        == row[
            "batch_target_manifest_sha256"
        ]
    )

    assert (
        audited.observed_accessions_sha256
        == row[
            "accessions_sha256"
        ]
    )

    assert (
        audited.observed_candidate_audit_sha256
        == row[
            "candidate_sequence_audit_sha256"
        ]
    )

    assert (
        audited.observed_component_audit_sha256
        == row[
            "component_sequence_audit_sha256"
        ]
    )

    assert (
        audited.provider_summary_sha256
        == row[
            "batch_summary_sha256"
        ]
    )

    assert (
        audited.package_manifest_sha256
        == row[
            "package_files_sha256"
        ]
    )

    assert (
        audited.package_file_count
        == row[
            "package_files"
        ]
    )

    assert (
        audited.package_file_readback_count
        == row[
            "package_file_readback_count"
        ]
    )

    assert (
        audited.package_file_readback_sha256
        == row[
            "package_file_readback_sha256"
        ]
    )


def test_final_short_batch_matches_v1():
    count = (
        fixture.FRESH_BATCH_SIZE
        + 1
    )

    values = make_values(
        count
    )

    evidence = values[
        "batches"
    ][1]

    audited = (
        audit_completed_transport_provider(
            evidence,
            **adapter_kwargs(
                values,
                batch_index=2,
            ),
        )
    )

    assert (
        audited.requested_accessions
        == 1
    )

    assert (
        audited.batch_id
        == "batch-00002"
    )


def test_origin_commit_tamper_rejected_by_both_contracts():
    values = make_values()

    changed = rewritten_summary(
        values[
            "batches"
        ][0],
        origin_git_commit=(
            "f" * 40
        ),
    )

    with pytest.raises(
        MonthlySequenceOrdinaryProviderError,
        match="origin Git commit changed",
    ):
        audit_completed_transport_provider(
            changed,
            **adapter_kwargs(
                values
            ),
        )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="origin Git commit changed",
    ):
        build_sequence_acquisition_completion_record(
            **v1_kwargs(
                values,
                batches=(
                    changed,
                ),
            )
        )


def test_candidate_identity_tamper_rejected_by_both_contracts():
    values = make_values()

    evidence = values[
        "batches"
    ][0]

    changed = replace(
        evidence,
        observed_candidate_audit_sha256=(
            "f" * 64
        ),
    )

    with pytest.raises(
        MonthlySequenceOrdinaryProviderError,
        match="candidate audit identity changed",
    ):
        audit_completed_transport_provider(
            changed,
            **adapter_kwargs(
                values
            ),
        )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="candidate audit identity changed",
    ):
        build_sequence_acquisition_completion_record(
            **v1_kwargs(
                values,
                batches=(
                    changed,
                ),
            )
        )


def test_package_manifest_tamper_rejected_by_both_contracts():
    values = make_values()

    evidence = values[
        "batches"
    ][0]

    changed = replace(
        evidence,
        package_files_payload=(
            evidence.package_files_payload
            + b"\n"
        ),
    )

    with pytest.raises(
        MonthlySequenceOrdinaryProviderError,
        match="package-files manifest identity changed",
    ):
        audit_completed_transport_provider(
            changed,
            **adapter_kwargs(
                values
            ),
        )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="package-files manifest identity changed",
    ):
        build_sequence_acquisition_completion_record(
            **v1_kwargs(
                values,
                batches=(
                    changed,
                ),
            )
        )


def test_package_readback_tamper_rejected_by_both_contracts():
    values = make_values()

    evidence = values[
        "batches"
    ][0]

    first = (
        evidence
        .package_file_observations[
            0
        ]
    )

    changed_observation = replace(
        first,
        observed_sha256=(
            "f" * 64
        ),
    )

    changed = replace(
        evidence,
        package_file_observations=(
            changed_observation,
            *evidence.package_file_observations[
                1:
            ],
        ),
    )

    with pytest.raises(
        MonthlySequenceOrdinaryProviderError,
        match="independent readback audit failed",
    ):
        audit_completed_transport_provider(
            changed,
            **adapter_kwargs(
                values
            ),
        )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="SHA256 changed during independent readback",
    ):
        build_sequence_acquisition_completion_record(
            **v1_kwargs(
                values,
                batches=(
                    changed,
                ),
            )
        )


def test_wrong_batch_index_fails_closed():
    values = make_values(
        fixture.FRESH_BATCH_SIZE
        + 1
    )

    with pytest.raises(
        MonthlySequenceOrdinaryProviderError,
        match="batch ID changed",
    ):
        audit_completed_transport_provider(
            values[
                "batches"
            ][0],
            **adapter_kwargs(
                values,
                batch_index=2,
            ),
        )


def test_wrong_stage2_plan_identity_fails_closed():
    values = make_values()

    kwargs = adapter_kwargs(
        values
    )

    kwargs[
        "stage2_sequence_plan_record_sha256"
    ] = "f" * 64

    with pytest.raises(
        MonthlySequenceOrdinaryProviderError,
        match="Stage 2 sequence-plan identity changed",
    ):
        audit_completed_transport_provider(
            values[
                "batches"
            ][0],
            **kwargs,
        )


def test_wrong_source_snapshot_identity_fails_closed():
    values = make_values()

    kwargs = adapter_kwargs(
        values
    )

    kwargs[
        "source_snapshot_record_sha256"
    ] = "f" * 64

    with pytest.raises(
        MonthlySequenceOrdinaryProviderError,
        match="source-snapshot-record SHA256 changed",
    ):
        audit_completed_transport_provider(
            values[
                "batches"
            ][0],
            **kwargs,
        )


def test_module_has_no_filesystem_or_execution_bindings():
    text = (
        ROOT
        / "src"
        / "bacselect"
        / "monthly_sequence_ordinary_provider.py"
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "/NGS/",
        "Rhys_wkdir",
        "subprocess",
        "requests.",
        "urllib.",
        "socket.",
        "sequence-acquisition-recovery",
        "batch-00072",
        "batch-00118",
        "batch-00130",
    ):
        assert token not in text
