"""Validation-input provenance utilities."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InputArtifact:
    """One immutable external validation input."""

    artifact: str
    path: Path
    sha256: str
    data_rows: int
    notes: str


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)

    return digest.hexdigest()


def count_data_rows(path: Path) -> int:
    """Return line count excluding one header row."""
    with path.open("rb") as handle:
        lines = sum(1 for _ in handle)

    if lines == 0:
        raise ValueError(f"Input file is empty: {path}")

    return lines - 1


def read_input_manifest(path: Path) -> list[InputArtifact]:
    """Read and validate a BacSelect input manifest."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        expected = {"artifact", "path", "sha256", "data_rows", "notes"}

        if reader.fieldnames is None or set(reader.fieldnames) != expected:
            raise ValueError(
                f"Unexpected manifest columns: {reader.fieldnames!r}"
            )

        rows = [
            InputArtifact(
                artifact=row["artifact"],
                path=Path(row["path"]),
                sha256=row["sha256"],
                data_rows=int(row["data_rows"]),
                notes=row["notes"],
            )
            for row in reader
        ]

    if not rows:
        raise ValueError("Input manifest contains no artifacts")

    names = [row.artifact for row in rows]
    if len(names) != len(set(names)):
        raise ValueError("Input manifest contains duplicate artifact names")

    return rows


def verify_input_artifact(artifact: InputArtifact) -> None:
    """Fail if an immutable validation input differs from its manifest."""
    if not artifact.path.is_file():
        raise FileNotFoundError(artifact.path)

    observed_sha256 = sha256_file(artifact.path)
    if observed_sha256 != artifact.sha256:
        raise ValueError(
            f"SHA-256 mismatch for {artifact.artifact}: "
            f"expected {artifact.sha256}, observed {observed_sha256}"
        )

    observed_rows = count_data_rows(artifact.path)
    if observed_rows != artifact.data_rows:
        raise ValueError(
            f"Row-count mismatch for {artifact.artifact}: "
            f"expected {artifact.data_rows}, observed {observed_rows}"
        )


def verify_input_manifest(path: Path) -> list[InputArtifact]:
    """Verify every immutable input declared by a manifest."""
    artifacts = read_input_manifest(path)

    for artifact in artifacts:
        verify_input_artifact(artifact)

    return artifacts
