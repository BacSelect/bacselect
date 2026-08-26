from __future__ import annotations

from email.message import Message
import io
import json
from pathlib import Path
import tarfile

import pytest

from bacselect.source_taxonomy_acquisition import (
    ACQUISITION_PROVENANCE_NAME,
    ARCHIVE_NAME,
    CONTENT_MANIFEST_NAME,
    FREEZE_RECORD_NAME,
    REQUIRED_MEMBERS,
    SOURCE_ACQUISITION_SHA256,
    SOURCE_RAW_SHA256,
    SOURCE_SNAPSHOT_ID,
    TAXONOMY_URL,
    TaxonomyAcquisitionError,
    acquire_taxonomy_snapshot,
    extract_required_members,
    file_identity,
    snapshot_id_from_started_utc,
    stream_http_response,
    validate_archive,
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


class FakeResponse:
    def __init__(
        self,
        payload,
        *,
        status=200,
        final_url=TAXONOMY_URL,
        etag='"synthetic-etag"',
        last_modified="Wed, 26 Aug 2026 00:00:00 GMT",
    ):
        self.payload = io.BytesIO(
            payload
        )
        self.status = status
        self.final_url = final_url
        self.closed = False

        headers = Message()

        if etag is not None:
            headers["ETag"] = etag

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


def build_archive(
    path,
    *,
    omit=(),
    duplicate=(),
    special=None,
    extra_members=(),
):
    omit = set(
        omit
    )

    duplicate = set(
        duplicate
    )

    payloads = {
        "nodes.dmp": VALID_NODES,
        "merged.dmp": VALID_MERGED,
        "delnodes.dmp": VALID_DELNODES,
    }

    with tarfile.open(
        path,
        mode="w:gz",
    ) as archive:
        for name in REQUIRED_MEMBERS:
            if name in omit:
                continue

            if (
                special is not None
                and special[0] == name
            ):
                kind = special[
                    1
                ]

                info = tarfile.TarInfo(
                    name=name
                )

                if kind == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = "target"

                elif kind == "hardlink":
                    info.type = tarfile.LNKTYPE
                    info.linkname = "target"

                elif kind == "directory":
                    info.type = tarfile.DIRTYPE

                else:
                    raise AssertionError(
                        f"unknown special member type: {kind}"
                    )

                archive.addfile(
                    info
                )

            else:
                add_regular_member(
                    archive,
                    name,
                    payloads[
                        name
                    ],
                )

            if name in duplicate:
                add_regular_member(
                    archive,
                    name,
                    payloads[
                        name
                    ],
                )

        for name, payload in extra_members:
            add_regular_member(
                archive,
                name,
                payload,
            )


def archive_bytes(
    tmp_path,
    **kwargs,
):
    path = (
        tmp_path
        / "fixture.tar.gz"
    )

    build_archive(
        path,
        **kwargs,
    )

    return path.read_bytes()


def fixed_timestamps():
    values = iter(
        (
            "2026-08-26T07:00:00Z",
            "2026-08-26T07:00:01Z",
        )
    )

    return lambda: next(
        values
    )


def test_valid_archive_is_accepted(
    tmp_path,
):
    archive = (
        tmp_path
        / ARCHIVE_NAME
    )

    build_archive(
        archive
    )

    result = validate_archive(
        archive
    )

    assert result.member_count == 3

    assert tuple(
        member.name
        for member in result.required_members
    ) == REQUIRED_MEMBERS


def test_safe_unexpected_archive_member_is_allowed(
    tmp_path,
):
    archive = (
        tmp_path
        / ARCHIVE_NAME
    )

    build_archive(
        archive,
        extra_members=(
            (
                "names.dmp",
                b"synthetic\n",
            ),
        ),
    )

    result = validate_archive(
        archive
    )

    assert result.member_count == 4


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "/absolute/path",
        "../escape",
        "safe/../../escape",
        r"windows\escape",
        "C:/escape",
    ],
)
def test_unsafe_archive_member_path_fails_closed(
    tmp_path,
    unsafe_name,
):
    archive = (
        tmp_path
        / ARCHIVE_NAME
    )

    build_archive(
        archive,
        extra_members=(
            (
                unsafe_name,
                b"bad\n",
            ),
        ),
    )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="unsafe archive member|backslash",
    ):
        validate_archive(
            archive
        )


@pytest.mark.parametrize(
    "missing",
    REQUIRED_MEMBERS,
)
def test_missing_required_member_fails_closed(
    tmp_path,
    missing,
):
    archive = (
        tmp_path
        / ARCHIVE_NAME
    )

    build_archive(
        archive,
        omit=(
            missing,
        ),
    )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="must occur exactly once",
    ):
        validate_archive(
            archive
        )


@pytest.mark.parametrize(
    "duplicate",
    REQUIRED_MEMBERS,
)
def test_duplicate_required_member_fails_closed(
    tmp_path,
    duplicate,
):
    archive = (
        tmp_path
        / ARCHIVE_NAME
    )

    build_archive(
        archive,
        duplicate=(
            duplicate,
        ),
    )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="must occur exactly once",
    ):
        validate_archive(
            archive
        )


@pytest.mark.parametrize(
    "kind",
    [
        "symlink",
        "hardlink",
        "directory",
    ],
)
def test_required_member_must_be_regular_file(
    tmp_path,
    kind,
):
    archive = (
        tmp_path
        / ARCHIVE_NAME
    )

    build_archive(
        archive,
        special=(
            "nodes.dmp",
            kind,
        ),
    )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="not a regular file",
    ):
        validate_archive(
            archive
        )


def test_truncated_gzip_fails_closed(
    tmp_path,
):
    archive = (
        tmp_path
        / ARCHIVE_NAME
    )

    build_archive(
        archive
    )

    payload = archive.read_bytes()

    archive.write_bytes(
        payload[
            :-8
        ]
    )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="gzip integrity",
    ):
        validate_archive(
            archive
        )


def test_gzip_containing_non_tar_data_fails_closed(
    tmp_path,
):
    import gzip

    archive = (
        tmp_path
        / ARCHIVE_NAME
    )

    with gzip.open(
        archive,
        "wb",
    ) as handle:
        handle.write(
            b"not a tar archive"
        )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="tar validation",
    ):
        validate_archive(
            archive
        )


def test_controlled_extraction_writes_only_required_members(
    tmp_path,
):
    archive = (
        tmp_path
        / ARCHIVE_NAME
    )

    build_archive(
        archive,
        extra_members=(
            (
                "names.dmp",
                b"must not extract\n",
            ),
        ),
    )

    output = (
        tmp_path
        / "out"
    )

    output.mkdir()

    identities = extract_required_members(
        archive,
        output,
    )

    assert set(
        identities
    ) == set(
        REQUIRED_MEMBERS
    )

    assert (
        output
        / "nodes.dmp"
    ).read_bytes() == VALID_NODES

    assert (
        output
        / "merged.dmp"
    ).read_bytes() == VALID_MERGED

    assert (
        output
        / "delnodes.dmp"
    ).read_bytes() == VALID_DELNODES

    assert not (
        output
        / "names.dmp"
    ).exists()


def test_controlled_extraction_refuses_overwrite(
    tmp_path,
):
    archive = (
        tmp_path
        / ARCHIVE_NAME
    )

    build_archive(
        archive
    )

    output = (
        tmp_path
        / "out"
    )

    output.mkdir()

    (
        output
        / "nodes.dmp"
    ).write_bytes(
        b"existing"
    )

    with pytest.raises(
        TaxonomyAcquisitionError,
    ):
        extract_required_members(
            archive,
            output,
        )


def test_stream_response_records_exact_body_identity(
    tmp_path,
):
    payload = b"synthetic archive bytes"

    response = FakeResponse(
        payload
    )

    partial = (
        tmp_path
        / "archive.partial"
    )

    result = stream_http_response(
        response,
        partial,
        requested_url=TAXONOMY_URL,
    )

    observed = file_identity(
        partial
    )

    assert result.sha256 == observed.sha256
    assert result.size_bytes == len(
        payload
    )
    assert result.http_status == 200
    assert result.requested_url == TAXONOMY_URL
    assert result.final_url == TAXONOMY_URL
    assert result.etag == '"synthetic-etag"'
    assert partial.read_bytes() == payload


@pytest.mark.parametrize(
    "status",
    [
        199,
        300,
        404,
        500,
    ],
)
def test_non_success_http_status_fails_closed(
    tmp_path,
    status,
):
    response = FakeResponse(
        b"body",
        status=status,
    )

    partial = (
        tmp_path
        / "archive.partial"
    )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="non-success HTTP status",
    ):
        stream_http_response(
            response,
            partial,
            requested_url=TAXONOMY_URL,
        )

    assert not partial.exists()


def test_non_https_final_url_fails_closed(
    tmp_path,
):
    response = FakeResponse(
        b"body",
        final_url="http://example.invalid/archive",
    )

    partial = (
        tmp_path
        / "archive.partial"
    )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="final URL is not HTTPS",
    ):
        stream_http_response(
            response,
            partial,
            requested_url=TAXONOMY_URL,
        )

    assert not partial.exists()


def test_empty_response_body_fails_closed(
    tmp_path,
):
    response = FakeResponse(
        b""
    )

    partial = (
        tmp_path
        / "archive.partial"
    )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="response body is empty",
    ):
        stream_http_response(
            response,
            partial,
            requested_url=TAXONOMY_URL,
        )


def test_snapshot_id_is_deterministic():
    assert snapshot_id_from_started_utc(
        "2026-08-26T07:00:00Z"
    ) == "taxonomy-20260826T070000Z"


def test_successful_synthetic_acquisition_freezes_snapshot(
    tmp_path,
):
    payload = archive_bytes(
        tmp_path
    )

    response = FakeResponse(
        payload,
        final_url=(
            "https://ftp.ncbi.nlm.nih.gov/"
            "pub/taxonomy/new_taxdump/new_taxdump.tar.gz"
        ),
    )

    calls = []

    def opener(
        url,
        *,
        timeout,
    ):
        calls.append(
            (
                url,
                timeout,
            )
        )

        return response

    snapshot_dir = (
        tmp_path
        / "snapshot"
    )

    result = acquire_taxonomy_snapshot(
        snapshot_dir,
        bacselect_git_commit=(
            "d974ed4f62baf4c27d1795ff002a8034b31e2fb7"
        ),
        opener=opener,
        timestamp_provider=fixed_timestamps(),
        timeout_seconds=17,
    )

    assert calls == [
        (
            TAXONOMY_URL,
            17,
        )
    ]

    assert response.closed is True

    assert result.snapshot_id == (
        "taxonomy-20260826T070000Z"
    )

    assert not (
        snapshot_dir
        / (
            ARCHIVE_NAME
            + ".partial"
        )
    ).exists()

    for name in (
        ARCHIVE_NAME,
        *REQUIRED_MEMBERS,
        ACQUISITION_PROVENANCE_NAME,
        CONTENT_MANIFEST_NAME,
        FREEZE_RECORD_NAME,
    ):
        assert (
            snapshot_dir
            / name
        ).is_file()

    assert (
        snapshot_dir
        / ARCHIVE_NAME
    ).read_bytes() == payload

    assert result.archive_sha256 == file_identity(
        snapshot_dir
        / ARCHIVE_NAME
    ).sha256

    assert result.nodes_sha256 == file_identity(
        snapshot_dir
        / "nodes.dmp"
    ).sha256

    assert result.merged_sha256 == file_identity(
        snapshot_dir
        / "merged.dmp"
    ).sha256

    assert result.delnodes_sha256 == file_identity(
        snapshot_dir
        / "delnodes.dmp"
    ).sha256

    provenance = json.loads(
        (
            snapshot_dir
            / ACQUISITION_PROVENANCE_NAME
        ).read_text(
            encoding="utf-8"
        )
    )

    assert provenance[
        "taxonomy_snapshot_id"
    ] == result.snapshot_id

    assert provenance[
        "bound_source_snapshot_id"
    ] == SOURCE_SNAPSHOT_ID

    assert provenance[
        "bound_source_raw_report_sha256"
    ] == SOURCE_RAW_SHA256

    assert provenance[
        "bound_source_acquisition_sha256"
    ] == SOURCE_ACQUISITION_SHA256

    assert provenance[
        "http_status"
    ] == 200

    assert provenance[
        "started_utc"
    ] == "2026-08-26T07:00:00Z"

    assert provenance[
        "completed_utc"
    ] == "2026-08-26T07:00:01Z"

    assert provenance[
        "structural_validation"
    ] == "pass"

    assert provenance[
        "taxonomy_resolution_performed"
    ] is False

    assert provenance[
        "structural_features_calculated"
    ] is False

    assert provenance[
        "selector_outcomes_calculated"
    ] is False

    freeze = json.loads(
        (
            snapshot_dir
            / FREEZE_RECORD_NAME
        ).read_text(
            encoding="utf-8"
        )
    )

    assert freeze[
        "snapshot_status"
    ] == "FROZEN_TAXONOMY_INPUT"

    assert freeze[
        "snapshot_id"
    ] == result.snapshot_id

    assert freeze[
        "archive_sha256"
    ] == result.archive_sha256

    assert freeze[
        "nodes_sha256"
    ] == result.nodes_sha256

    assert freeze[
        "merged_sha256"
    ] == result.merged_sha256

    assert freeze[
        "delnodes_sha256"
    ] == result.delnodes_sha256

    assert freeze[
        "acquisition_provenance_sha256"
    ] == result.acquisition_provenance_sha256

    assert freeze[
        "content_manifest_sha256"
    ] == result.content_manifest_sha256

    assert freeze[
        "taxonomy_resolution_performed"
    ] is False

    manifest_lines = (
        snapshot_dir
        / CONTENT_MANIFEST_NAME
    ).read_text(
        encoding="ascii"
    ).splitlines()

    assert manifest_lines[
        0
    ] == "sha256\tsize_bytes\tpath"

    assert len(
        manifest_lines
    ) == 6


def test_acquisition_never_calls_default_network_with_injected_opener(
    tmp_path,
):
    payload = archive_bytes(
        tmp_path
    )

    called = []

    def synthetic_opener(
        url,
        *,
        timeout,
    ):
        called.append(
            url
        )

        return FakeResponse(
            payload
        )

    acquire_taxonomy_snapshot(
        tmp_path
        / "snapshot",
        bacselect_git_commit=(
            "d974ed4f62baf4c27d1795ff002a8034b31e2fb7"
        ),
        opener=synthetic_opener,
        timestamp_provider=fixed_timestamps(),
    )

    assert called == [
        TAXONOMY_URL
    ]


def test_network_failure_produces_no_frozen_snapshot(
    tmp_path,
):
    def failing_opener(
        url,
        *,
        timeout,
    ):
        raise OSError(
            "synthetic network failure"
        )

    snapshot_dir = (
        tmp_path
        / "failed"
    )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="HTTPS request failed",
    ):
        acquire_taxonomy_snapshot(
            snapshot_dir,
            bacselect_git_commit=(
                "d974ed4f62baf4c27d1795ff002a8034b31e2fb7"
            ),
            opener=failing_opener,
            timestamp_provider=fixed_timestamps(),
        )

    assert not (
        snapshot_dir
        / FREEZE_RECORD_NAME
    ).exists()

    assert not (
        snapshot_dir
        / (
            ARCHIVE_NAME
            + ".partial"
        )
    ).exists()


def test_empty_response_is_cleaned_by_acquisition(
    tmp_path,
):
    snapshot_dir = (
        tmp_path
        / "failed"
    )

    response = FakeResponse(
        b""
    )

    def opener(
        url,
        *,
        timeout,
    ):
        return response

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="response body is empty",
    ):
        acquire_taxonomy_snapshot(
            snapshot_dir,
            bacselect_git_commit=(
                "d974ed4f62baf4c27d1795ff002a8034b31e2fb7"
            ),
            opener=opener,
            timestamp_provider=fixed_timestamps(),
        )

    assert response.closed is True

    assert not (
        snapshot_dir
        / (
            ARCHIVE_NAME
            + ".partial"
        )
    ).exists()

    assert not (
        snapshot_dir
        / FREEZE_RECORD_NAME
    ).exists()


def test_malformed_taxonomy_cannot_be_frozen(
    tmp_path,
):
    archive = (
        tmp_path
        / "bad.tar.gz"
    )

    with tarfile.open(
        archive,
        mode="w:gz",
    ) as handle:
        add_regular_member(
            handle,
            "nodes.dmp",
            b"malformed\n",
        )

        add_regular_member(
            handle,
            "merged.dmp",
            VALID_MERGED,
        )

        add_regular_member(
            handle,
            "delnodes.dmp",
            VALID_DELNODES,
        )

    payload = archive.read_bytes()

    snapshot_dir = (
        tmp_path
        / "failed"
    )

    def opener(
        url,
        *,
        timeout,
    ):
        return FakeResponse(
            payload
        )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="structural validation failed",
    ):
        acquire_taxonomy_snapshot(
            snapshot_dir,
            bacselect_git_commit=(
                "d974ed4f62baf4c27d1795ff002a8034b31e2fb7"
            ),
            opener=opener,
            timestamp_provider=fixed_timestamps(),
        )

    assert not (
        snapshot_dir
        / FREEZE_RECORD_NAME
    ).exists()


def test_existing_snapshot_directory_fails_closed(
    tmp_path,
):
    snapshot_dir = (
        tmp_path
        / "existing"
    )

    snapshot_dir.mkdir()

    def opener(
        url,
        *,
        timeout,
    ):
        raise AssertionError(
            "opener must not be called"
        )

    with pytest.raises(
        TaxonomyAcquisitionError,
        match="refusing to reuse taxonomy snapshot directory",
    ):
        acquire_taxonomy_snapshot(
            snapshot_dir,
            bacselect_git_commit=(
                "d974ed4f62baf4c27d1795ff002a8034b31e2fb7"
            ),
            opener=opener,
            timestamp_provider=fixed_timestamps(),
        )
