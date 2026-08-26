#!/usr/bin/env python3
"""Execute the frozen BacSelect selector-v1 taxonomy acquisition.

This wrapper binds execution to the frozen prospective method and taxonomy
acquisition implementation. Importing it performs no network access.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

from bacselect.source_taxonomy_acquisition import (
    ACQUISITION_METHOD_SHA256,
    SOURCE_TAXONOMY_SHA256,
    acquire_taxonomy_snapshot,
)


EXPECTED_ACQUISITION_IMPLEMENTATION_SHA256 = (
    "c76f04ab3ab0149d5ede2e1069e547e99588ebba98f6ac1aac0ee5727015cef9"
)

EXPECTED_ACQUISITION_METHOD_SHA256 = (
    "4cdf7347be4e660e8ed8ea94bfe7a0e6c36b06c25f1ff399bd264eaf7c841f88"
)

EXPECTED_SOURCE_TAXONOMY_SHA256 = (
    "9c8c4149c5db2a757e8c201a6523bdb113511b5f72a4dd2893572dd8c7928e4d"
)

METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-taxonomy-snapshot-acquisition-method.md"
)

ACQUISITION_RELATIVE = Path(
    "src/bacselect/source_taxonomy_acquisition.py"
)

SOURCE_TAXONOMY_RELATIVE = Path(
    "src/bacselect/source_taxonomy.py"
)


class ExecutionError(RuntimeError):
    """Raised when frozen taxonomy execution preflight fails."""


def sha256_file(
    path: Path,
    block_size: int = 8 * 1024 * 1024,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                block_size
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def git_text(
    repo: Path,
    *args: str,
) -> str:
    try:
        completed = subprocess.run(
            (
                "git",
                "-C",
                str(repo),
                *args,
            ),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ExecutionError(
            "Git preflight failed: "
            + exc.stderr.strip()
        ) from exc

    return completed.stdout.strip()


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    if (
        not path.is_file()
        or path.is_symlink()
    ):
        raise ExecutionError(
            f"{label} is not a regular file: {path}"
        )

    observed = sha256_file(
        path
    )

    if observed != expected:
        raise ExecutionError(
            f"{label} SHA256 mismatch: "
            f"expected={expected} observed={observed}"
        )

    return observed


def preflight(
    *,
    repo: Path,
    expected_commit: str,
) -> str:
    """Verify exact repository and frozen implementation identities."""

    repo = repo.resolve()

    if not repo.is_dir():
        raise ExecutionError(
            f"repository directory missing: {repo}"
        )

    head = git_text(
        repo,
        "rev-parse",
        "HEAD",
    )

    if head != expected_commit:
        raise ExecutionError(
            "repository HEAD differs from expected execution commit: "
            f"expected={expected_commit} observed={head}"
        )

    origin_main = git_text(
        repo,
        "rev-parse",
        "origin/main",
    )

    if origin_main != expected_commit:
        raise ExecutionError(
            "origin/main differs from expected execution commit: "
            f"expected={expected_commit} observed={origin_main}"
        )

    status = git_text(
        repo,
        "status",
        "--porcelain",
    )

    if status:
        raise ExecutionError(
            "repository working tree is not clean"
        )

    method_sha = require_sha256(
        repo
        / METHOD_RELATIVE,
        EXPECTED_ACQUISITION_METHOD_SHA256,
        "prospective taxonomy acquisition method",
    )

    implementation_sha = require_sha256(
        repo
        / ACQUISITION_RELATIVE,
        EXPECTED_ACQUISITION_IMPLEMENTATION_SHA256,
        "taxonomy acquisition implementation",
    )

    resolver_sha = require_sha256(
        repo
        / SOURCE_TAXONOMY_RELATIVE,
        EXPECTED_SOURCE_TAXONOMY_SHA256,
        "taxonomy resolver implementation",
    )

    if method_sha != ACQUISITION_METHOD_SHA256:
        raise ExecutionError(
            "runtime acquisition-method constant differs from frozen method"
        )

    if resolver_sha != SOURCE_TAXONOMY_SHA256:
        raise ExecutionError(
            "runtime resolver constant differs from frozen resolver"
        )

    return implementation_sha


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire the frozen BacSelect selector-v1 "
            "NCBI taxonomy snapshot."
        )
    )

    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--expected-commit",
        required=True,
    )

    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
    )

    return parser.parse_args(
        argv
    )


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(
        argv
    )

    implementation_sha = preflight(
        repo=args.repo,
        expected_commit=args.expected_commit,
    )

    snapshot_dir = args.snapshot_dir.resolve()

    print(
        "PASS | taxonomy acquisition execution preflight"
    )
    print(
        f"bacselect_git_commit={args.expected_commit}"
    )
    print(
        "taxonomy_acquisition_implementation_sha256="
        f"{implementation_sha}"
    )
    print(
        "taxonomy_acquisition_method_sha256="
        f"{EXPECTED_ACQUISITION_METHOD_SHA256}"
    )
    print(
        f"snapshot_dir={snapshot_dir}"
    )

    result = acquire_taxonomy_snapshot(
        snapshot_dir,
        bacselect_git_commit=args.expected_commit,
        timeout_seconds=args.timeout_seconds,
    )

    print(
        "PASS | taxonomy snapshot acquired and frozen"
    )
    print(
        f"taxonomy_snapshot_id={result.snapshot_id}"
    )
    print(
        f"archive_sha256={result.archive_sha256}"
    )
    print(
        f"nodes_sha256={result.nodes_sha256}"
    )
    print(
        f"merged_sha256={result.merged_sha256}"
    )
    print(
        f"delnodes_sha256={result.delnodes_sha256}"
    )
    print(
        "acquisition_provenance_sha256="
        f"{result.acquisition_provenance_sha256}"
    )
    print(
        "content_manifest_sha256="
        f"{result.content_manifest_sha256}"
    )
    print(
        "freeze_record_sha256="
        f"{result.freeze_record_sha256}"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except ExecutionError as exc:
        print(
            f"ERROR | {exc}",
            file=sys.stderr,
        )
        raise SystemExit(
            1
        )
