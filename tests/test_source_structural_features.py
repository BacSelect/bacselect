from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from bacselect import source_structural_features
from bacselect import source_truth_execution


def sha256_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


class Stage6PackageBindingTests(
    unittest.TestCase
):
    def setUp(
        self,
    ) -> None:
        self.temp = (
            tempfile.TemporaryDirectory(
                prefix=(
                    "bacselect-stage6-binding-test-"
                )
            )
        )

        self.root = Path(
            self.temp.name
        )

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    def write_manifest(
        self,
        path: Path,
        rows,
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        fields = list(
            source_truth_execution.PACKAGE_FIELDS
        )

        with path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fields,
                delimiter="\t",
                lineterminator="\n",
            )

            writer.writeheader()

            for row in rows:
                writer.writerow(
                    row
                )

    def make_batch(
        self,
        *,
        batch_name: str,
        source_group: str,
        accession: str,
        nested_package: bool,
        report_subdir: str | None = None,
        extra_candidate: str | None = None,
    ):
        batch_dir = (
            self.root
            / batch_name
        )

        batch_dir.mkdir(
            parents=True,
        )

        candidate_audit = (
            batch_dir
            / "candidate-sequence-audit.tsv"
        )

        component_audit = (
            batch_dir
            / "component-sequence-audit.tsv"
        )

        package_manifest = (
            batch_dir
            / (
                "source-package-files.tsv"
                if source_group
                == "fresh-recovery"
                else "package-files.tsv"
            )
        )

        candidate_audit.write_text(
            "synthetic\n",
            encoding="utf-8",
        )

        component_audit.write_text(
            "synthetic\n",
            encoding="utf-8",
        )

        relative_root = (
            Path("ncbi_dataset")
            / "data"
            / accession
        )

        physical_root = (
            batch_dir
            / (
                "package"
                if nested_package
                else ""
            )
            / relative_root
        )

        physical_root.mkdir(
            parents=True,
        )

        fasta_name = (
            f"{accession}_genomic.fna"
        )

        fasta_bytes = (
            b">replicon\nACGTACGT\n"
        )

        fasta_path = (
            physical_root
            / fasta_name
        )

        fasta_path.write_bytes(
            fasta_bytes
        )

        if report_subdir is None:
            report_dir = physical_root
            report_relative = (
                relative_root
                / "sequence_report.jsonl"
            )
        else:
            report_dir = (
                physical_root
                / report_subdir
            )

            report_dir.mkdir(
                parents=True,
            )

            report_relative = (
                relative_root
                / report_subdir
                / "sequence_report.jsonl"
            )

        report_bytes = (
            b'{"synthetic":true}\n'
        )

        report_path = (
            report_dir
            / "sequence_report.jsonl"
        )

        report_path.write_bytes(
            report_bytes
        )

        rows = [
            {
                "path":
                    str(
                        relative_root
                        / fasta_name
                    ),
                "size_bytes":
                    str(
                        len(
                            fasta_bytes
                        )
                    ),
                "sha256":
                    sha256_bytes(
                        fasta_bytes
                    ),
            },
            {
                "path":
                    str(
                        report_relative
                    ),
                "size_bytes":
                    str(
                        len(
                            report_bytes
                        )
                    ),
                "sha256":
                    sha256_bytes(
                        report_bytes
                    ),
            },
        ]

        self.write_manifest(
            package_manifest,
            rows,
        )

        candidate = (
            source_truth_execution.CandidateAudit(
                accession=accession,
                audit_path=(
                    candidate_audit
                ),
                fasta_file=(
                    fasta_name
                ),
                fasta_sha256=(
                    sha256_bytes(
                        fasta_bytes
                    )
                ),
                primary_assembly_records=1,
            )
        )

        candidates = [
            candidate
        ]

        if extra_candidate is not None:
            candidates.append(
                source_truth_execution.CandidateAudit(
                    accession=(
                        extra_candidate
                    ),
                    audit_path=(
                        candidate_audit
                    ),
                    fasta_file=(
                        f"{extra_candidate}_genomic.fna"
                    ),
                    fasta_sha256=(
                        "0" * 64
                    ),
                    primary_assembly_records=1,
                )
            )

        batch = SimpleNamespace(
            source_group=source_group,
            batch=batch_name,
            candidate_audit=(
                candidate_audit
            ),
            component_audit=(
                component_audit
            ),
            package_manifest=(
                package_manifest
            ),
            candidates=tuple(
                candidates
            ),
        )

        return (
            batch,
            candidate,
            physical_root,
        )

    def test_historical_direct_layout(
        self,
    ) -> None:
        accession = (
            "GCA_000000001.1"
        )

        batch, _, expected = (
            self.make_batch(
                batch_name="historical-001",
                source_group="historical",
                accession=accession,
                nested_package=False,
            )
        )

        bundle = SimpleNamespace(
            batches=(
                batch,
            )
        )

        result = (
            source_structural_features.build_package_bindings(
                bundle=bundle,
                accessions=(
                    accession,
                ),
            )
        )

        self.assertEqual(
            len(result),
            1,
        )

        self.assertEqual(
            result[0].source_group,
            "historical",
        )

        self.assertEqual(
            result[0].candidate_dir,
            expected,
        )

    def test_fresh_nested_package_layout(
        self,
    ) -> None:
        accession = (
            "GCA_000000002.1"
        )

        batch, _, expected = (
            self.make_batch(
                batch_name="fresh-001",
                source_group="fresh",
                accession=accession,
                nested_package=True,
            )
        )

        result = (
            source_structural_features.build_package_bindings(
                bundle=SimpleNamespace(
                    batches=(
                        batch,
                    )
                ),
                accessions=(
                    accession,
                ),
            )
        )

        self.assertEqual(
            result[0].source_group,
            "fresh",
        )

        self.assertEqual(
            result[0].candidate_dir,
            expected,
        )

    def test_recovery_nested_package_layout(
        self,
    ) -> None:
        accession = (
            "GCA_000000003.1"
        )

        batch, _, expected = (
            self.make_batch(
                batch_name="recovery-001",
                source_group=(
                    "fresh-recovery"
                ),
                accession=accession,
                nested_package=True,
            )
        )

        result = (
            source_structural_features.build_package_bindings(
                bundle=SimpleNamespace(
                    batches=(
                        batch,
                    )
                ),
                accessions=(
                    accession,
                ),
            )
        )

        self.assertEqual(
            result[0].source_group,
            "fresh-recovery",
        )

        self.assertEqual(
            result[0].candidate_dir,
            expected,
        )

    def test_nonrequested_candidate_is_not_resolved(
        self,
    ) -> None:
        wanted = (
            "GCA_000000004.1"
        )

        not_wanted = (
            "GCA_000000005.1"
        )

        batch, _, _ = (
            self.make_batch(
                batch_name="fresh-isolation",
                source_group="fresh",
                accession=wanted,
                nested_package=True,
                extra_candidate=(
                    not_wanted
                ),
            )
        )

        result = (
            source_structural_features.build_package_bindings(
                bundle=SimpleNamespace(
                    batches=(
                        batch,
                    )
                ),
                accessions=(
                    wanted,
                ),
            )
        )

        self.assertEqual(
            tuple(
                item.accession
                for item in result
            ),
            (
                wanted,
            ),
        )

    def test_missing_requested_accession_fails(
        self,
    ) -> None:
        present = (
            "GCA_000000006.1"
        )

        missing = (
            "GCA_000000007.1"
        )

        batch, _, _ = (
            self.make_batch(
                batch_name="fresh-missing",
                source_group="fresh",
                accession=present,
                nested_package=True,
            )
        )

        with self.assertRaises(
            source_structural_features.StructuralFeatureBindingError
        ):
            source_structural_features.build_package_bindings(
                bundle=SimpleNamespace(
                    batches=(
                        batch,
                    )
                ),
                accessions=(
                    missing,
                ),
            )

    def test_duplicate_authoritative_candidate_fails(
        self,
    ) -> None:
        accession = (
            "GCA_000000008.1"
        )

        first, _, _ = (
            self.make_batch(
                batch_name="duplicate-a",
                source_group="fresh",
                accession=accession,
                nested_package=True,
            )
        )

        second, _, _ = (
            self.make_batch(
                batch_name="duplicate-b",
                source_group="historical",
                accession=accession,
                nested_package=False,
            )
        )

        with self.assertRaises(
            source_structural_features.StructuralFeatureBindingError
        ):
            source_structural_features.build_package_bindings(
                bundle=SimpleNamespace(
                    batches=(
                        first,
                        second,
                    )
                ),
                accessions=(
                    accession,
                ),
            )

    def test_duplicate_requested_accession_fails(
        self,
    ) -> None:
        accession = (
            "GCA_000000009.1"
        )

        batch, _, _ = (
            self.make_batch(
                batch_name="duplicate-request",
                source_group="fresh",
                accession=accession,
                nested_package=True,
            )
        )

        with self.assertRaises(
            source_structural_features.StructuralFeatureBindingError
        ):
            source_structural_features.build_package_bindings(
                bundle=SimpleNamespace(
                    batches=(
                        batch,
                    )
                ),
                accessions=(
                    accession,
                    accession,
                ),
            )

    def test_fasta_and_report_must_share_candidate_directory(
        self,
    ) -> None:
        accession = (
            "GCA_000000010.1"
        )

        batch, _, _ = (
            self.make_batch(
                batch_name="split-source",
                source_group="historical",
                accession=accession,
                nested_package=False,
                report_subdir="metadata",
            )
        )

        with self.assertRaises(
            source_structural_features.StructuralFeatureBindingError
        ):
            source_structural_features.build_package_bindings(
                bundle=SimpleNamespace(
                    batches=(
                        batch,
                    )
                ),
                accessions=(
                    accession,
                ),
            )

    def test_invalid_source_group_fails(
        self,
    ) -> None:
        accession = (
            "GCA_000000011.1"
        )

        batch, _, _ = (
            self.make_batch(
                batch_name="invalid-source",
                source_group="fresh",
                accession=accession,
                nested_package=True,
            )
        )

        batch.source_group = (
            "unknown"
        )

        with self.assertRaises(
            source_structural_features.StructuralFeatureBindingError
        ):
            source_structural_features.build_package_bindings(
                bundle=SimpleNamespace(
                    batches=(
                        batch,
                    )
                ),
                accessions=(
                    accession,
                ),
            )

    def test_package_file_hash_mismatch_fails(
        self,
    ) -> None:
        accession = (
            "GCA_000000012.1"
        )

        batch, _, expected = (
            self.make_batch(
                batch_name="hash-mismatch",
                source_group="fresh",
                accession=accession,
                nested_package=True,
            )
        )

        fasta = (
            expected
            / f"{accession}_genomic.fna"
        )

        fasta.write_bytes(
            b">replicon\nTTTT\n"
        )

        with self.assertRaises(
            source_structural_features.StructuralFeatureBindingError
        ):
            source_structural_features.build_package_bindings(
                bundle=SimpleNamespace(
                    batches=(
                        batch,
                    )
                ),
                accessions=(
                    accession,
                ),
            )


if __name__ == "__main__":
    unittest.main()
