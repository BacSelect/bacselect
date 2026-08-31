from __future__ import annotations

from dataclasses import FrozenInstanceError
import ast
import hashlib
from email.message import Message
import io
import json
from pathlib import Path
import tarfile

import pytest

from bacselect import monthly_authoritative_storage
from bacselect import monthly_release_start
from bacselect import monthly_taxonomy_snapshot
from bacselect import monthly_taxonomy_snapshot_execution as module


COMMIT = (
    "a" * 40
)

WRAPPER_SHA = (
    "d" * 64
)

RAW_RESPONSE = (
    b'{"reports":[]}\n'
)

VALID_NODES = (
    b"1\t|\t1\t|\tno rank\t|\n"
    b"2\t|\t1\t|\tsuperkingdom\t|\n"
    b"10\t|\t2\t|\tspecies\t|\n"
)

VALID_MERGED = (
    b"20\t|\t10\t|\n"
)

VALID_DELNODES = (
    b"30\t|\n"
)


def canonical_json(
    value,
):
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def source_payload(
    *,
    raw_response=RAW_RESPONSE,
    release_id="2026.09",
    snapshot_start="2026-09-01T00:17:00Z",
    commit=COMMIT,
):
    return canonical_json(
        {
            "architecture_schema_version":
                monthly_release_start
                .ARCHITECTURE_SCHEMA_VERSION,
            "expected_git_commit":
                commit,
            "ncbi_datasets_environment_sha256":
                "1" * 64,
            "ncbi_datasets_version":
                "18.35.0",
            "raw_response_bytes":
                len(
                    raw_response
                ),
            "raw_response_sha256":
                hashlib.sha256(
                    raw_response
                ).hexdigest(),
            "release_id":
                release_id,
            "release_start_checkpoint_sha256":
                "3" * 64,
            "schema_version":
                monthly_release_start
                .SOURCE_SNAPSHOT_SCHEMA_VERSION,
            "selector":
                monthly_release_start.SELECTOR,
            "selector_version":
                monthly_release_start
                .SELECTOR_VERSION,
            "snapshot_start_utc":
                snapshot_start,
            "source_query_command":
                [
                    "datasets",
                    "summary",
                    "genome",
                    "taxon",
                    "2",
                ],
            "source_query_completed_utc":
                "2026-09-01T00:18:00Z",
            "source_query_specification":
                {},
            "source_query_started_utc":
                "2026-09-01T00:17:01Z",
            "source_snapshot_id":
                (
                    monthly_release_start
                    .source_snapshot_id_from_start(
                        snapshot_start
                    )
                ),
            "status":
                monthly_release_start
                .SOURCE_SNAPSHOT_STATUS,
        }
    )


def upstream(
    *,
    raw_response=RAW_RESPONSE,
    payload=None,
):
    if payload is None:
        payload = source_payload(
            raw_response=raw_response
        )

    return (
        module
        .build_authenticated_upstream_context(
            source_snapshot_record_payload=(
                payload
            ),
            raw_source_response_payload=(
                raw_response
            ),
            expected_release_id="2026.09",
            expected_source_snapshot_id=(
                "bacselect-source-2026.09-"
                "20260901T001700Z"
            ),
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            chromosome_integrity_decisions_sha256=(
                "4" * 64
            ),
            chromosome_integrity_record_sha256=(
                "5" * 64
            ),
            chromosome_integrity_completion_sha256=(
                "6" * 64
            ),
            execution_git_commit=COMMIT,
        )
    )


class FakeResponse:
    def __init__(
        self,
        payload,
        *,
        status=200,
        final_url=(
            monthly_taxonomy_snapshot
            .TAXONOMY_URL
        ),
        etag='"synthetic-etag"',
        last_modified=(
            "Wed, 26 Aug 2026 "
            "00:00:00 GMT"
        ),
    ):
        self.payload = io.BytesIO(
            payload
        )

        self.status = status

        self.final_url = (
            final_url
        )

        self.closed = False

        headers = Message()

        if etag is not None:
            headers[
                "ETag"
            ] = etag

        if last_modified is not None:
            headers[
                "Last-Modified"
            ] = last_modified

        self.headers = headers

    def read(
        self,
        size=-1,
    ):
        return self.payload.read(
            size
        )

    def geturl(
        self,
    ):
        return self.final_url

    def close(
        self,
    ):
        self.closed = True


class FakeOpener:
    def __init__(
        self,
        response,
    ):
        self.response = response
        self.calls = []

    def __call__(
        self,
        url,
        *,
        timeout,
    ):
        self.calls.append(
            (
                url,
                timeout,
            )
        )

        return self.response


def add_regular_member(
    archive,
    name,
    payload,
):
    info = tarfile.TarInfo(
        name=name
    )

    info.size = len(
        payload
    )

    archive.addfile(
        info,
        io.BytesIO(
            payload
        ),
    )


def archive_bytes(
    tmp_path,
    *,
    malformed_nodes=False,
):
    path = (
        tmp_path
        / "fixture.tar.gz"
    )

    nodes = (
        b"malformed\n"
        if malformed_nodes
        else VALID_NODES
    )

    with tarfile.open(
        path,
        mode="w:gz",
    ) as archive:
        add_regular_member(
            archive,
            "nodes.dmp",
            nodes,
        )

        add_regular_member(
            archive,
            "merged.dmp",
            VALID_MERGED,
        )

        add_regular_member(
            archive,
            "delnodes.dmp",
            VALID_DELNODES,
        )

    return path.read_bytes()


def timestamps():
    values = iter(
        (
            "2026-09-01T00:30:00Z",
            "2026-09-01T00:31:00Z",
        )
    )

    return lambda: next(
        values
    )


def successful_execution(
    tmp_path,
    *,
    authoritative_root=None,
    workspace_name="taxonomy-snapshot.partial",
    payload=None,
):
    if payload is None:
        payload = archive_bytes(
            tmp_path
        )

    if authoritative_root is None:
        authoritative_root = (
            tmp_path
            / "authoritative"
        )

        authoritative_root.mkdir()

    workspace = (
        tmp_path
        / workspace_name
    )

    workspace.mkdir()

    response = FakeResponse(
        payload
    )

    opener = FakeOpener(
        response
    )

    stability = []

    result = (
        module
        .execute_monthly_taxonomy_support(
            workspace=workspace,
            authoritative_root=(
                authoritative_root
            ),
            upstream=upstream(),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
            upstream_stability_check=(
                lambda:
                    stability.append(
                        "checked"
                    )
            ),
            opener=opener,
            timestamp_provider=(
                timestamps()
            ),
            timeout=15.0,
        )
    )

    return (
        result,
        workspace,
        authoritative_root,
        response,
        opener,
        stability,
    )


def test_authenticated_upstream_is_frozen():
    value = upstream()

    with pytest.raises(
        FrozenInstanceError,
    ):
        value.release_id = (
            "2026.10"
        )


def test_authenticated_upstream_binds_stage1_and_stage6():
    value = upstream()

    assert value.release_id == "2026.09"

    assert (
        value.source_snapshot_id
        == (
            "bacselect-source-2026.09-"
            "20260901T001700Z"
        )
    )

    assert (
        value.source_raw_response_sha256
        == hashlib.sha256(
            RAW_RESPONSE
        ).hexdigest()
    )

    assert (
        value.chromosome_integrity_decisions_sha256
        == "4" * 64
    )

    assert (
        value.chromosome_integrity_record_sha256
        == "5" * 64
    )

    assert (
        value.chromosome_integrity_completion_sha256
        == "6" * 64
    )


def test_authenticated_upstream_rejects_replacement_source_record_sha():
    payload = source_payload()

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
        match="Stage 1 context",
    ):
        module.build_authenticated_upstream_context(
            source_snapshot_record_payload=(
                payload
            ),
            raw_source_response_payload=(
                RAW_RESPONSE
            ),
            expected_release_id="2026.09",
            expected_source_snapshot_id=(
                "bacselect-source-2026.09-"
                "20260901T001700Z"
            ),
            expected_source_snapshot_record_sha256=(
                "f" * 64
            ),
            chromosome_integrity_decisions_sha256=(
                "4" * 64
            ),
            chromosome_integrity_record_sha256=(
                "5" * 64
            ),
            chromosome_integrity_completion_sha256=(
                "6" * 64
            ),
            execution_git_commit=COMMIT,
        )


def test_authenticated_upstream_rejects_replacement_raw_response():
    payload = source_payload()

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
        match="raw source response differs",
    ):
        module.build_authenticated_upstream_context(
            source_snapshot_record_payload=(
                payload
            ),
            raw_source_response_payload=(
                b"different\n"
            ),
            expected_release_id="2026.09",
            expected_source_snapshot_id=(
                "bacselect-source-2026.09-"
                "20260901T001700Z"
            ),
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            chromosome_integrity_decisions_sha256=(
                "4" * 64
            ),
            chromosome_integrity_record_sha256=(
                "5" * 64
            ),
            chromosome_integrity_completion_sha256=(
                "6" * 64
            ),
            execution_git_commit=COMMIT,
        )


def test_support_module_sha_matches_repository_file():
    expected = hashlib.sha256(
        Path(
            module.__file__
        ).read_bytes()
    ).hexdigest()

    assert (
        module
        .execution_support_module_sha256()
        == expected
    )


def test_execution_method_identity_is_frozen():
    assert (
        module.EXECUTION_METHOD_SHA256
        == (
            "0dd4105b1360117cc79b185a55c69b5d"
            "519f058178b35635cd5e1d3a28aa342c"
        )
    )


def test_support_module_has_no_validation_import():
    tree = ast.parse(
        Path(
            module.__file__
        ).read_text(
            encoding="utf-8"
        )
    )

    observed = []

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            observed.extend(
                alias.name
                for alias in node.names
                if (
                    alias.name == "validation"
                    or alias.name.startswith(
                        "validation."
                    )
                )
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            imported = (
                node.module
                or ""
            )

            if (
                imported == "validation"
                or imported.startswith(
                    "validation."
                )
            ):
                observed.append(
                    imported
                )

    assert observed == []


def test_support_module_does_not_call_historical_top_level_acquisition():
    source = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    called_attributes = {
        node.func.attr
        for node in ast.walk(
            tree
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
        )
    }

    assert (
        "acquire_taxonomy_snapshot"
        not in called_attributes
    )


def test_successful_support_execution_freezes_nine_file_partial_bundle(
    tmp_path,
):
    (
        result,
        workspace,
        authoritative_root,
        response,
        opener,
        stability,
    ) = successful_execution(
        tmp_path
    )

    assert response.closed is True

    assert opener.calls == [
        (
            monthly_taxonomy_snapshot
            .TAXONOMY_URL,
            15.0,
        )
    ]

    assert stability == [
        "checked",
        "checked",
    ]

    assert {
        child.name
        for child in workspace.iterdir()
    } == module.LOCAL_STAGE_FILES

    assert (
        not (
            workspace
            / module.PARTIAL_ARCHIVE_NAME
        ).exists()
    )

    assert (
        result.authoritative_verified_object_count
        == 8
    )

    assert (
        result.taxonomy_snapshot_id
        .startswith(
            "bacselect-taxonomy-2026.09-"
            "20260901T003000Z-"
        )
    )

    assert (
        result.workspace
        == workspace.resolve()
    )

    assert authoritative_root.is_dir()


def test_successful_pure_record_audits_and_stage7_false_state_is_exact(
    tmp_path,
):
    (
        result,
        workspace,
        _,
        _,
        _,
        _,
    ) = successful_execution(
        tmp_path
    )

    record_payload = (
        workspace
        / module.RECORD_NAME
    ).read_bytes()

    record = (
        monthly_taxonomy_snapshot
        .audit_monthly_taxonomy_snapshot_record(
            record_payload,
            source_snapshot_record_payload=(
                upstream()
                .source_snapshot_record_payload
            ),
            expected_source_snapshot_record_sha256=(
                upstream()
                .source_snapshot_record_sha256
            ),
            origin_git_commit=COMMIT,
        )
    )

    assert (
        record[
            "taxonomy_snapshot_id"
        ]
        == result.taxonomy_snapshot_id
    )

    assert (
        record[
            "taxonomy_acquisition_implementation_sha256"
        ]
        == module.execution_support_module_sha256()
    )

    assert (
        record[
            "taxonomy_resolution_performed"
        ]
        is False
    )

    assert (
        record[
            "structural_features_calculated"
        ]
        is False
    )

    assert (
        record[
            "selector_outcomes_calculated"
        ]
        is False
    )


def test_acquisition_provenance_is_closed_and_binds_implementation_identities(
    tmp_path,
):
    (
        _,
        workspace,
        _,
        _,
        _,
        _,
    ) = successful_execution(
        tmp_path
    )

    provenance = json.loads(
        (
            workspace
            / module.ACQUISITION_PROVENANCE_NAME
        ).read_bytes()
    )

    assert set(
        provenance
    ) == module.ACQUISITION_FIELDS

    assert (
        provenance[
            "schema_version"
        ]
        == module.ACQUISITION_SCHEMA
    )

    assert (
        provenance[
            "status"
        ]
        == module.ACQUISITION_STATUS
    )

    assert (
        provenance[
            "execution_support_module_sha256"
        ]
        == module.execution_support_module_sha256()
    )

    assert (
        provenance[
            "validation_wrapper_sha256"
        ]
        == WRAPPER_SHA
    )

    assert (
        provenance[
            "execution_method_sha256"
        ]
        == module.EXECUTION_METHOD_SHA256
    )

    assert (
        provenance[
            "taxonomy_resolution_performed"
        ]
        is False
    )

    assert (
        provenance[
            "structural_features_calculated"
        ]
        is False
    )

    assert (
        provenance[
            "selector_outcomes_calculated"
        ]
        is False
    )


def test_acquisition_provenance_auditor_rejects_extra_field(
    tmp_path,
):
    (
        _,
        workspace,
        _,
        _,
        _,
        _,
    ) = successful_execution(
        tmp_path
    )

    path = (
        workspace
        / module.ACQUISITION_PROVENANCE_NAME
    )

    record = json.loads(
        path.read_bytes()
    )

    record[
        "unexpected"
    ] = "value"

    payload = canonical_json(
        record
    )

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
        match="schema changed",
    ):
        module.audit_acquisition_provenance(
            payload
        )


def test_authoritative_manifest_contains_exactly_seven_logical_artifacts(
    tmp_path,
):
    (
        result,
        workspace,
        authoritative_root,
        _,
        _,
        _,
    ) = successful_execution(
        tmp_path
    )

    manifest_payload = (
        workspace
        / module.AUTHORITATIVE_MANIFEST_LOCAL_NAME
    ).read_bytes()

    manifest = (
        monthly_authoritative_storage
        .audit_authoritative_manifest(
            manifest_payload
        )
    )

    assert (
        manifest[
            "artifact_count"
        ]
        == 7
    )

    assert tuple(
        value[
            "logical_path"
        ]
        for value in manifest[
            "artifacts"
        ]
    ) == tuple(
        sorted(
            module
            .AUTHORITATIVE_LOGICAL_PATHS
        )
    )

    assert (
        hashlib.sha256(
            manifest_payload
        ).hexdigest()
        == result.authoritative_manifest_sha256
    )

    stored_manifest = (
        authoritative_root
        / result.authoritative_manifest_key
    )

    assert (
        stored_manifest.read_bytes()
        == manifest_payload
    )


def test_authoritative_receipt_verifies_exactly_eight_objects(
    tmp_path,
):
    (
        result,
        workspace,
        authoritative_root,
        _,
        _,
        _,
    ) = successful_execution(
        tmp_path
    )

    manifest_payload = (
        workspace
        / module.AUTHORITATIVE_MANIFEST_LOCAL_NAME
    ).read_bytes()

    receipt_payload = (
        workspace
        / module.AUTHORITATIVE_RECEIPT_LOCAL_NAME
    ).read_bytes()

    receipt = (
        monthly_authoritative_storage
        .audit_authoritative_receipt(
            receipt_payload,
            manifest_payload=(
                manifest_payload
            ),
        )
    )

    assert (
        receipt[
            "verified_object_count"
        ]
        == 8
    )

    assert (
        len(
            receipt[
                "verified_objects"
            ]
        )
        == 8
    )

    assert (
        result.authoritative_verified_object_count
        == 8
    )

    stored_receipt = (
        authoritative_root
        / result.authoritative_receipt_key
    )

    assert (
        stored_receipt.read_bytes()
        == receipt_payload
    )


def test_matching_existing_authoritative_objects_are_reused(
    tmp_path,
):
    payload = archive_bytes(
        tmp_path
    )

    authoritative_root = (
        tmp_path
        / "authoritative"
    )

    authoritative_root.mkdir()

    first = successful_execution(
        tmp_path,
        authoritative_root=(
            authoritative_root
        ),
        workspace_name="first.partial",
        payload=payload,
    )[0]

    second = successful_execution(
        tmp_path,
        authoritative_root=(
            authoritative_root
        ),
        workspace_name="second.partial",
        payload=payload,
    )[0]

    assert (
        second.authoritative_manifest_key
        == first.authoritative_manifest_key
    )

    assert (
        second.authoritative_receipt_key
        == first.authoritative_receipt_key
    )


def test_mismatching_existing_authoritative_object_fails_without_overwrite(
    tmp_path,
):
    payload = archive_bytes(
        tmp_path
    )

    archive_sha = hashlib.sha256(
        payload
    ).hexdigest()

    object_key = (
        monthly_authoritative_storage
        .object_key_for_sha256(
            archive_sha
        )
    )

    authoritative_root = (
        tmp_path
        / "authoritative"
    )

    destination = (
        authoritative_root
        / object_key
    )

    destination.parent.mkdir(
        parents=True,
    )

    destination.write_bytes(
        b"wrong"
    )

    workspace = (
        tmp_path
        / "taxonomy-snapshot.partial"
    )

    workspace.mkdir()

    response = FakeResponse(
        payload
    )

    opener = FakeOpener(
        response
    )

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
    ):
        module.execute_monthly_taxonomy_support(
            workspace=workspace,
            authoritative_root=(
                authoritative_root
            ),
            upstream=upstream(),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
            upstream_stability_check=(
                lambda: None
            ),
            opener=opener,
            timestamp_provider=(
                timestamps()
            ),
        )

    assert (
        destination.read_bytes()
        == b"wrong"
    )


def test_nonempty_workspace_fails_before_network(
    tmp_path,
):
    workspace = (
        tmp_path
        / "taxonomy-snapshot.partial"
    )

    workspace.mkdir()

    (
        workspace
        / "existing"
    ).write_bytes(
        b"x"
    )

    authoritative_root = (
        tmp_path
        / "authoritative"
    )

    authoritative_root.mkdir()

    response = FakeResponse(
        b"unused"
    )

    opener = FakeOpener(
        response
    )

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
        match="workspace is not empty",
    ):
        module.execute_monthly_taxonomy_support(
            workspace=workspace,
            authoritative_root=(
                authoritative_root
            ),
            upstream=upstream(),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
            upstream_stability_check=(
                lambda: None
            ),
            opener=opener,
            timestamp_provider=(
                timestamps()
            ),
        )

    assert opener.calls == []


@pytest.mark.parametrize(
    "timeout",
    [
        0,
        -1,
        float("inf"),
        float("nan"),
        True,
    ],
)
def test_invalid_network_timeout_fails_before_network(
    tmp_path,
    timeout,
):
    workspace = (
        tmp_path
        / "taxonomy-snapshot.partial"
    )

    workspace.mkdir()

    authoritative_root = (
        tmp_path
        / "authoritative"
    )

    authoritative_root.mkdir()

    response = FakeResponse(
        b"unused"
    )

    opener = FakeOpener(
        response
    )

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
        match="timeout",
    ):
        module.execute_monthly_taxonomy_support(
            workspace=workspace,
            authoritative_root=(
                authoritative_root
            ),
            upstream=upstream(),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
            upstream_stability_check=(
                lambda: None
            ),
            opener=opener,
            timestamp_provider=(
                timestamps()
            ),
            timeout=timeout,
        )

    assert opener.calls == []


def test_invalid_wrapper_sha_fails_before_network(
    tmp_path,
):
    workspace = (
        tmp_path
        / "taxonomy-snapshot.partial"
    )

    workspace.mkdir()

    authoritative_root = (
        tmp_path
        / "authoritative"
    )

    authoritative_root.mkdir()

    response = FakeResponse(
        b"unused"
    )

    opener = FakeOpener(
        response
    )

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
        match="validation-wrapper SHA256",
    ):
        module.execute_monthly_taxonomy_support(
            workspace=workspace,
            authoritative_root=(
                authoritative_root
            ),
            upstream=upstream(),
            validation_wrapper_sha256=(
                "not-a-sha"
            ),
            upstream_stability_check=(
                lambda: None
            ),
            opener=opener,
            timestamp_provider=(
                timestamps()
            ),
        )

    assert opener.calls == []


def test_non_https_final_url_fails_closed_and_response_is_closed(
    tmp_path,
):
    payload = archive_bytes(
        tmp_path
    )

    workspace = (
        tmp_path
        / "taxonomy-snapshot.partial"
    )

    workspace.mkdir()

    authoritative_root = (
        tmp_path
        / "authoritative"
    )

    authoritative_root.mkdir()

    response = FakeResponse(
        payload,
        final_url=(
            "http://example.invalid/"
            "new_taxdump.tar.gz"
        ),
    )

    opener = FakeOpener(
        response
    )

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
    ):
        module.execute_monthly_taxonomy_support(
            workspace=workspace,
            authoritative_root=(
                authoritative_root
            ),
            upstream=upstream(),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
            upstream_stability_check=(
                lambda: None
            ),
            opener=opener,
            timestamp_provider=(
                timestamps()
            ),
        )

    assert response.closed is True

    assert not (
        workspace
        / module.RECORD_NAME
    ).exists()


def test_malformed_taxonomy_cannot_produce_stage7_record(
    tmp_path,
):
    payload = archive_bytes(
        tmp_path,
        malformed_nodes=True,
    )

    workspace = (
        tmp_path
        / "taxonomy-snapshot.partial"
    )

    workspace.mkdir()

    authoritative_root = (
        tmp_path
        / "authoritative"
    )

    authoritative_root.mkdir()

    response = FakeResponse(
        payload
    )

    opener = FakeOpener(
        response
    )

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
    ):
        module.execute_monthly_taxonomy_support(
            workspace=workspace,
            authoritative_root=(
                authoritative_root
            ),
            upstream=upstream(),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
            upstream_stability_check=(
                lambda: None
            ),
            opener=opener,
            timestamp_provider=(
                timestamps()
            ),
        )

    assert response.closed is True

    assert not (
        workspace
        / module.RECORD_NAME
    ).exists()

    assert not (
        workspace
        / module.AUTHORITATIVE_RECEIPT_LOCAL_NAME
    ).exists()


def test_failed_second_stability_check_never_creates_terminal_completion(
    tmp_path,
):
    payload = archive_bytes(
        tmp_path
    )

    workspace = (
        tmp_path
        / "taxonomy-snapshot.partial"
    )

    workspace.mkdir()

    authoritative_root = (
        tmp_path
        / "authoritative"
    )

    authoritative_root.mkdir()

    response = FakeResponse(
        payload
    )

    opener = FakeOpener(
        response
    )

    calls = []

    def stability():
        calls.append(
            "checked"
        )

        if len(
            calls
        ) == 2:
            raise RuntimeError(
                "upstream changed"
            )

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
    ):
        module.execute_monthly_taxonomy_support(
            workspace=workspace,
            authoritative_root=(
                authoritative_root
            ),
            upstream=upstream(),
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
            upstream_stability_check=(
                stability
            ),
            opener=opener,
            timestamp_provider=(
                timestamps()
            ),
        )

    assert calls == [
        "checked",
        "checked",
    ]

    assert (
        workspace
        / module.AUTHORITATIVE_RECEIPT_LOCAL_NAME
    ).is_file()

    assert not (
        workspace
        / "taxonomy-snapshot-completion.json"
    ).exists()


def test_directly_constructed_inconsistent_upstream_fails_before_network(
    tmp_path,
):
    valid = upstream()

    fabricated = (
        module
        .AuthenticatedMonthlyTaxonomyUpstream(
            release_id=(
                valid.release_id
            ),
            source_snapshot_id=(
                valid.source_snapshot_id
            ),
            source_snapshot_record_payload=(
                valid.source_snapshot_record_payload
            ),
            source_snapshot_record_sha256=(
                valid.source_snapshot_record_sha256
            ),
            raw_source_response_payload=(
                b"not-the-bound-raw-response"
            ),
            source_raw_response_sha256=(
                valid.source_raw_response_sha256
            ),
            chromosome_integrity_decisions_sha256=(
                valid
                .chromosome_integrity_decisions_sha256
            ),
            chromosome_integrity_record_sha256=(
                valid
                .chromosome_integrity_record_sha256
            ),
            chromosome_integrity_completion_sha256=(
                valid
                .chromosome_integrity_completion_sha256
            ),
            execution_git_commit=(
                valid.execution_git_commit
            ),
        )
    )

    workspace = (
        tmp_path
        / "taxonomy-snapshot.partial"
    )

    workspace.mkdir()

    authoritative_root = (
        tmp_path
        / "authoritative"
    )

    authoritative_root.mkdir()

    response = FakeResponse(
        b"unused"
    )

    opener = FakeOpener(
        response
    )

    stability = []

    with pytest.raises(
        module.MonthlyTaxonomyExecutionError,
        match="raw source response differs",
    ):
        module.execute_monthly_taxonomy_support(
            workspace=workspace,
            authoritative_root=(
                authoritative_root
            ),
            upstream=fabricated,
            validation_wrapper_sha256=(
                WRAPPER_SHA
            ),
            upstream_stability_check=(
                lambda:
                    stability.append(
                        "checked"
                    )
            ),
            opener=opener,
            timestamp_provider=(
                timestamps()
            ),
            timeout=15.0,
        )

    assert opener.calls == []

    assert stability == []


def test_acquisition_provenance_audit_uses_recorded_runtime_identities(
    tmp_path,
    monkeypatch,
):
    (
        _,
        workspace,
        _,
        _,
        _,
        _,
    ) = successful_execution(
        tmp_path
    )

    payload = (
        workspace
        / module.ACQUISITION_PROVENANCE_NAME
    ).read_bytes()

    record = json.loads(
        payload
    )

    bound_upstream = upstream()

    download = (
        module
        .source_taxonomy_acquisition
        .DownloadIdentity(
            requested_url=(
                record[
                    "requested_url"
                ]
            ),
            final_url=(
                record[
                    "final_url"
                ]
            ),
            http_status=(
                record[
                    "http_status"
                ]
            ),
            etag=(
                record[
                    "etag"
                ]
            ),
            last_modified=(
                record[
                    "last_modified"
                ]
            ),
            sha256=(
                record[
                    "archive_sha256"
                ]
            ),
            size_bytes=(
                record[
                    "archive_size_bytes"
                ]
            ),
        )
    )

    archive_validation = (
        module
        .source_taxonomy_acquisition
        .ArchiveValidation(
            required_members=(
                module
                .source_taxonomy_acquisition
                .ArchiveMemberIdentity(
                    name="nodes.dmp",
                    size_bytes=(
                        record[
                            "nodes_size_bytes"
                        ]
                    ),
                ),
                module
                .source_taxonomy_acquisition
                .ArchiveMemberIdentity(
                    name="merged.dmp",
                    size_bytes=(
                        record[
                            "merged_size_bytes"
                        ]
                    ),
                ),
                module
                .source_taxonomy_acquisition
                .ArchiveMemberIdentity(
                    name="delnodes.dmp",
                    size_bytes=(
                        record[
                            "delnodes_size_bytes"
                        ]
                    ),
                ),
            ),
            member_count=(
                record[
                    "archive_member_count"
                ]
            ),
        )
    )

    archive_identity = (
        module
        .source_taxonomy_acquisition
        .FileIdentity(
            sha256=(
                record[
                    "archive_sha256"
                ]
            ),
            size_bytes=(
                record[
                    "archive_size_bytes"
                ]
            ),
        )
    )

    member_identities = {
        "nodes.dmp":
            module
            .source_taxonomy_acquisition
            .FileIdentity(
                sha256=(
                    record[
                        "nodes_sha256"
                    ]
                ),
                size_bytes=(
                    record[
                        "nodes_size_bytes"
                    ]
                ),
            ),
        "merged.dmp":
            module
            .source_taxonomy_acquisition
            .FileIdentity(
                sha256=(
                    record[
                        "merged_sha256"
                    ]
                ),
                size_bytes=(
                    record[
                        "merged_size_bytes"
                    ]
                ),
            ),
        "delnodes.dmp":
            module
            .source_taxonomy_acquisition
            .FileIdentity(
                sha256=(
                    record[
                        "delnodes_sha256"
                    ]
                ),
                size_bytes=(
                    record[
                        "delnodes_size_bytes"
                    ]
                ),
            ),
    }

    kwargs = {
        "upstream":
            bound_upstream,
        "validation_wrapper_sha256":
            record[
                "validation_wrapper_sha256"
            ],
        "execution_support_sha256":
            record[
                "execution_support_module_sha256"
            ],
        "execution_method_sha256":
            record[
                "execution_method_sha256"
            ],
        "source_taxonomy_sha256":
            record[
                "source_taxonomy_sha256"
            ],
        "acquisition_started_utc":
            record[
                "acquisition_started_utc"
            ],
        "acquisition_completed_utc":
            record[
                "acquisition_completed_utc"
            ],
        "download":
            download,
        "downloader_identity":
            record[
                "downloader_identity"
            ],
        "archive_validation":
            archive_validation,
        "archive_identity":
            archive_identity,
        "member_identities":
            member_identities,
    }

    monkeypatch.setattr(
        module.platform,
        "python_version",
        lambda:
            "99.99.99",
    )

    monkeypatch.setattr(
        module.ssl,
        "OPENSSL_VERSION",
        "OpenSSL FUTURE-AUDIT",
    )

    audited = (
        module
        .audit_acquisition_provenance(
            payload,
            **kwargs,
        )
    )

    assert (
        audited[
            "python_version"
        ]
        == record[
            "python_version"
        ]
    )

    assert (
        audited[
            "openssl_version"
        ]
        == record[
            "openssl_version"
        ]
    )

    assert (
        audited[
            "python_version"
        ]
        != "99.99.99"
    )

    assert (
        audited[
            "openssl_version"
        ]
        != "OpenSSL FUTURE-AUDIT"
    )
