from pathlib import Path

import pytest

from bacselect.provenance import (
    InputArtifact,
    count_data_rows,
    read_input_manifest,
    sha256_file,
    verify_input_artifact,
)


def test_sha256_and_row_count(tmp_path: Path) -> None:
    path = tmp_path / "data.tsv"
    path.write_text("a\tb\n1\t2\n3\t4\n", encoding="utf-8")

    assert count_data_rows(path) == 2
    assert sha256_file(path) == (
        "8137d66b376d4bce4335a6759a564db799331d30be807539bcacb2ad3ccd3d29"
    )


def test_read_input_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "inputs.tsv"
    manifest.write_text(
        "artifact\tpath\tsha256\tdata_rows\tnotes\n"
        "example\t/tmp/example.tsv\tabc\t12\tnote\n",
        encoding="utf-8",
    )

    rows = read_input_manifest(manifest)

    assert len(rows) == 1
    assert rows[0].artifact == "example"
    assert rows[0].path == Path("/tmp/example.tsv")
    assert rows[0].data_rows == 12


def test_manifest_rejects_bad_columns(tmp_path: Path) -> None:
    manifest = tmp_path / "inputs.tsv"
    manifest.write_text(
        "artifact\tpath\tsha256\n"
        "example\t/tmp/example.tsv\tabc\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unexpected manifest columns"):
        read_input_manifest(manifest)


def test_verify_input_artifact_detects_hash_change(tmp_path: Path) -> None:
    path = tmp_path / "data.tsv"
    path.write_text("a\n1\n", encoding="utf-8")

    artifact = InputArtifact(
        artifact="example",
        path=path,
        sha256="0" * 64,
        data_rows=1,
        notes="",
    )

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_input_artifact(artifact)
