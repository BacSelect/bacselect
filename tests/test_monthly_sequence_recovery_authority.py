from pathlib import Path

import pytest

from bacselect import (
    monthly_sequence_recovery_authority
    as authority,
)


SOURCE_COMMIT = (
    "a" * 40
)

RECOVERY_COMMIT = (
    "b" * 40
)

RECOVERY_COMMIT_2 = (
    "c" * 40
)

RELEASE = "2026.09"


def make_source_partial(
    tmp_path,
    batch="batch-00072",
):
    sequence_root = (
        tmp_path
        / "sequence-acquisition"
    )

    sequence_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    partial = (
        sequence_root
        / f"{batch}.partial"
    )

    package = (
        partial
        / "package"
        / "ncbi_dataset"
    )

    data = (
        package
        / "data"
        / "GCA_123456789.1"
    )

    data.mkdir(
        parents=True
    )

    (
        partial
        / "accessions.txt"
    ).write_text(
        "GCA_123456789.1\n",
        encoding="ascii",
    )

    (
        partial
        / "batch-targets.tsv"
    ).write_text(
        (
            "canonical_genbank_assembly_accession\t"
            "source_biosample\t"
            "acquisition_reason\n"
            "GCA_123456789.1\t"
            "SAMN12345678\t"
            "no_verified_cache\n"
        ),
        encoding="utf-8",
    )

    (
        partial
        / "attempt-origin.json"
    ).write_text(
        "{}\n",
        encoding="ascii",
    )

    (
        partial
        / "dehydrated.zip"
    ).write_bytes(
        b"synthetic zip\n"
    )

    (
        package
        / "fetch.txt"
    ).write_text(
        (
            "https://example.invalid/a\t"
            "data/GCA_123456789.1/"
            "sequence_report.jsonl\n"
        ),
        encoding="utf-8",
    )

    (
        data
        / "sequence_report.jsonl"
    ).write_text(
        "{}\n",
        encoding="utf-8",
    )

    return (
        sequence_root,
        partial,
    )


def make_finalized_recovery(
    tmp_path,
    *,
    sequence_root,
    source_partial,
    recovery_commit=RECOVERY_COMMIT,
    root_name="recovery-one",
):
    recovery_root = (
        tmp_path
        / root_name
    )

    workspace = (
        authority
        .prepare_recovery_workspace(
            source_partial_dir=(
                source_partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id=(
                source_partial.name[
                    :-len(
                        ".partial"
                    )
                ]
            ),
            release_id=(
                RELEASE
            ),
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                recovery_commit
            ),
        )
    )

    # Simulate recovery evidence being added only to the copied package.
    recovered_file = (
        workspace.partial_dir
        / "package"
        / "ncbi_dataset"
        / "data"
        / "GCA_123456789.1"
        / "GCA_123456789.1_efetch_components.gbff"
    )

    recovered_file.write_text(
        "LOCUS synthetic\n//\n",
        encoding="ascii",
    )

    (
        workspace.partial_dir
        / authority.CANDIDATE_AUDIT_NAME
    ).write_text(
        "candidate\n",
        encoding="utf-8",
    )

    (
        workspace.partial_dir
        / authority.COMPONENT_AUDIT_NAME
    ).write_text(
        "component\n",
        encoding="utf-8",
    )

    accepted = (
        authority
        .seal_recovery_workspace(
            workspace,
            release_id=(
                RELEASE
            ),
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                recovery_commit
            ),
        )
    )

    return (
        recovery_root,
        accepted,
    )


def test_workspace_is_copy_only_and_source_is_unchanged(
    tmp_path,
):
    (
        _,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    before = (
        authority
        .strict_tree_fingerprint(
            source_partial
        )
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    workspace = (
        authority
        .prepare_recovery_workspace(
            source_partial_dir=(
                source_partial
            ),
            recovery_root=(
                recovery_root
            ),
            batch_id="batch-00072",
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
        )
    )

    after = (
        authority
        .strict_tree_fingerprint(
            source_partial
        )
    )

    assert before == after

    assert (
        workspace.partial_dir
        / authority.SOURCE_BATCH_MANIFEST_NAME
    ).is_file()

    assert (
        workspace.partial_dir
        / authority.SOURCE_PACKAGE_MANIFEST_NAME
    ).is_file()

    source_package = (
        authority
        .strict_tree_fingerprint(
            source_partial
            / "package"
        )
    )

    copied_package = (
        authority
        .strict_tree_fingerprint(
            workspace.partial_dir
            / "package"
        )
    )

    assert (
        source_package
        == copied_package
    )


def test_seal_audits_then_atomically_finalizes(
    tmp_path,
):
    (
        sequence_root,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    before = (
        authority
        .strict_tree_fingerprint(
            source_partial
        )
    )

    (
        recovery_root,
        accepted,
    ) = make_finalized_recovery(
        tmp_path,
        sequence_root=(
            sequence_root
        ),
        source_partial=(
            source_partial
        ),
    )

    assert not (
        recovery_root
        / "batch-00072.partial"
    ).exists()

    assert (
        recovery_root
        / "batch-00072"
    ).is_dir()

    assert (
        accepted.source_production_commit
        == SOURCE_COMMIT
    )

    assert (
        accepted.recovery_commit
        == RECOVERY_COMMIT
    )

    after = (
        authority
        .strict_tree_fingerprint(
            source_partial
        )
    )

    assert before == after


def test_seal_fails_if_source_changes_after_copy(
    tmp_path,
):
    (
        _,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    workspace = (
        authority
        .prepare_recovery_workspace(
            source_partial_dir=(
                source_partial
            ),
            recovery_root=(
                tmp_path
                / "recovery"
            ),
            batch_id="batch-00072",
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
        )
    )

    (
        workspace.partial_dir
        / authority.CANDIDATE_AUDIT_NAME
    ).write_text(
        "candidate\n",
        encoding="utf-8",
    )

    (
        workspace.partial_dir
        / authority.COMPONENT_AUDIT_NAME
    ).write_text(
        "component\n",
        encoding="utf-8",
    )

    (
        source_partial
        / "accessions.txt"
    ).write_text(
        "MUTATED\n",
        encoding="ascii",
    )

    with pytest.raises(
        authority.MonthlySequenceRecoveryAuthorityError,
        match="source partial changed",
    ):
        authority.seal_recovery_workspace(
            workspace,
            release_id=RELEASE,
            source_production_commit=(
                SOURCE_COMMIT
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
        )


def test_resolver_accepts_ordinary_final_as_fresh(
    tmp_path,
):
    sequence_root = (
        tmp_path
        / "sequence-acquisition"
    )

    sequence_root.mkdir()

    (
        sequence_root
        / "batch-00001"
    ).mkdir()

    recovery_root = (
        tmp_path
        / "recovery"
    )

    recovery_root.mkdir()

    resolved = (
        authority
        .resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                "batch-00001",
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )
    )

    assert len(
        resolved
    ) == 1

    assert (
        resolved[
            0
        ].source_class
        == authority.SOURCE_CLASS_FRESH
    )

    assert (
        resolved[
            0
        ].source_partial_dir
        is None
    )


def test_resolver_accepts_exact_recovery_as_fresh_recovery(
    tmp_path,
):
    (
        sequence_root,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    (
        recovery_root,
        accepted,
    ) = make_finalized_recovery(
        tmp_path,
        sequence_root=(
            sequence_root
        ),
        source_partial=(
            source_partial
        ),
    )

    resolved = (
        authority
        .resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                "batch-00072",
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )
    )

    assert (
        resolved[
            0
        ].source_class
        == authority.SOURCE_CLASS_FRESH_RECOVERY
    )

    assert (
        resolved[
            0
        ].recovery_commit
        == RECOVERY_COMMIT
    )

    assert (
        resolved[
            0
        ].recovery_summary_sha256
        == accepted.summary_sha256
    )

    assert (
        resolved[
            0
        ].source_partial_dir
        == source_partial
    )


def test_resolver_rejects_ordinary_and_recovery_both_claiming_batch(
    tmp_path,
):
    (
        sequence_root,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    (
        recovery_root,
        _,
    ) = make_finalized_recovery(
        tmp_path,
        sequence_root=(
            sequence_root
        ),
        source_partial=(
            source_partial
        ),
    )

    source_partial.rename(
        sequence_root
        / "preserved-source"
    )

    (
        sequence_root
        / "batch-00072"
    ).mkdir()

    # Re-create a path with the expected preserved-partial name only so
    # authority sees the deliberately ambiguous ordinary+recovery claim.
    (
        sequence_root
        / "batch-00072.partial"
    ).mkdir()

    with pytest.raises(
        authority.MonthlySequenceRecoveryAuthorityError,
        match="ordinary final and source partial both exist|"
        "ordinary final and recovery both claim authority",
    ):
        authority.resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                "batch-00072",
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )


def test_resolver_rejects_partial_without_recovery(
    tmp_path,
):
    (
        sequence_root,
        _,
    ) = make_source_partial(
        tmp_path
    )

    recovery_root = (
        tmp_path
        / "recovery"
    )

    recovery_root.mkdir()

    with pytest.raises(
        authority.MonthlySequenceRecoveryAuthorityError,
        match="source partial exists without accepted recovery",
    ):
        authority.resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                "batch-00072",
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )


def test_resolver_rejects_neither_provider(
    tmp_path,
):
    sequence_root = (
        tmp_path
        / "sequence-acquisition"
    )

    sequence_root.mkdir()

    recovery_root = (
        tmp_path
        / "recovery"
    )

    recovery_root.mkdir()

    with pytest.raises(
        authority.MonthlySequenceRecoveryAuthorityError,
        match="no authoritative batch provider exists",
    ):
        authority.resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                "batch-00001",
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )


def test_resolver_rejects_multiple_recoveries(
    tmp_path,
):
    (
        sequence_root,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    (
        recovery_root_1,
        _,
    ) = make_finalized_recovery(
        tmp_path,
        sequence_root=(
            sequence_root
        ),
        source_partial=(
            source_partial
        ),
        recovery_commit=(
            RECOVERY_COMMIT
        ),
        root_name="recovery-one",
    )

    (
        recovery_root_2,
        _,
    ) = make_finalized_recovery(
        tmp_path,
        sequence_root=(
            sequence_root
        ),
        source_partial=(
            source_partial
        ),
        recovery_commit=(
            RECOVERY_COMMIT_2
        ),
        root_name="recovery-two",
    )

    with pytest.raises(
        authority.MonthlySequenceRecoveryAuthorityError,
        match="multiple recoveries claim authority",
    ):
        authority.resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root_1,
                recovery_root_2,
            ),
            expected_batch_ids=(
                "batch-00072",
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )


def test_resolver_rejects_source_mutation_after_recovery_finalized(
    tmp_path,
):
    (
        sequence_root,
        source_partial,
    ) = make_source_partial(
        tmp_path
    )

    (
        recovery_root,
        _,
    ) = make_finalized_recovery(
        tmp_path,
        sequence_root=(
            sequence_root
        ),
        source_partial=(
            source_partial
        ),
    )

    (
        source_partial
        / "attempt-origin.json"
    ).write_text(
        '{"changed":true}\n',
        encoding="ascii",
    )

    with pytest.raises(
        authority.MonthlySequenceRecoveryAuthorityError,
        match="source-batch manifest|source partial fingerprint",
    ):
        authority.resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                "batch-00072",
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )


def test_resolver_rejects_unfinished_recovery_partial(
    tmp_path,
):
    sequence_root = (
        tmp_path
        / "sequence-acquisition"
    )

    sequence_root.mkdir()

    (
        sequence_root
        / "batch-00001"
    ).mkdir()

    recovery_root = (
        tmp_path
        / "recovery"
    )

    recovery_root.mkdir()

    (
        recovery_root
        / "batch-00001.partial"
    ).mkdir()

    with pytest.raises(
        authority.MonthlySequenceRecoveryAuthorityError,
        match="unfinished recovery partial exists",
    ):
        authority.resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                "batch-00001",
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )


def test_resolver_preserves_expected_batch_order(
    tmp_path,
):
    sequence_root = (
        tmp_path
        / "sequence-acquisition"
    )

    sequence_root.mkdir()

    for batch in (
        "batch-00001",
        "batch-00002",
        "batch-00003",
    ):
        (
            sequence_root
            / batch
        ).mkdir()

    recovery_root = (
        tmp_path
        / "recovery"
    )

    recovery_root.mkdir()

    resolved = (
        authority
        .resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                "batch-00001",
                "batch-00002",
                "batch-00003",
            ),
            expected_release_id=(
                RELEASE
            ),
            expected_source_production_commit=(
                SOURCE_COMMIT
            ),
        )
    )

    assert tuple(
        value.batch_id
        for value
        in resolved
    ) == (
        "batch-00001",
        "batch-00002",
        "batch-00003",
    )


def test_fingerprint_rejects_symlinked_evidence(
    tmp_path,
):
    root = (
        tmp_path
        / "tree"
    )

    root.mkdir()

    real = (
        root
        / "real.txt"
    )

    real.write_text(
        "evidence\n",
        encoding="utf-8",
    )

    (
        root
        / "link.txt"
    ).symlink_to(
        real
    )

    with pytest.raises(
        authority.MonthlySequenceRecoveryAuthorityError,
        match="symlink",
    ):
        authority.strict_tree_fingerprint(
            root
        )
