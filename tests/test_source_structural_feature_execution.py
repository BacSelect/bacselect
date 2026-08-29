from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import textwrap
import unittest

from bacselect import (
    source_structural_feature_execution,
)
from bacselect.source_structural_features import (
    CandidatePackageBinding,
)


def load_frozen_basic_module():
    path = Path(
        "vendor/project-finch/experiment-0/"
        "basic_structural_features.py"
    ).resolve()

    spec = (
        importlib.util.spec_from_file_location(
            "stage6_test_frozen_basic",
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "could not load frozen basic module"
        )

    module = (
        importlib.util.module_from_spec(
            spec
        )
    )

    import sys

    sys.modules[
        spec.name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


BASIC = load_frozen_basic_module()


class FakeFinch:
    def __init__(
        self,
        *,
        binding,
        replicons,
        accession=None,
        fasta_path=None,
        report_path=None,
    ):
        self.binding = binding
        self.replicons = tuple(
            replicons
        )
        self.accession = (
            accession
            if accession is not None
            else binding.accession
        )
        self.fasta_path = (
            fasta_path
            if fasta_path is not None
            else binding.fasta_path
        )
        self.report_path = (
            report_path
            if report_path is not None
            else binding.sequence_report_path
        )
        self.calls = []

    def load_replicons(
        self,
        candidate_dir,
        candidate_audit_path,
        component_audit_path,
    ):
        self.calls.append(
            (
                candidate_dir,
                candidate_audit_path,
                component_audit_path,
            )
        )

        return (
            self.accession,
            self.replicons,
            self.fasta_path,
            self.report_path,
        )


class Stage6FeatureExecutionTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.temp = (
            tempfile.TemporaryDirectory(
                prefix=(
                    "bacselect-stage6-feature-test-"
                )
            )
        )

        self.root = Path(
            self.temp.name
        )

        self.accession = (
            "GCA_000000101.1"
        )

        self.candidate_dir = (
            self.root
            / self.accession
        )

        self.candidate_dir.mkdir(
            parents=True
        )

        self.fasta = (
            self.candidate_dir
            / f"{self.accession}_genomic.fna"
        )

        self.report = (
            self.candidate_dir
            / "sequence_report.jsonl"
        )

        self.candidate_audit = (
            self.root
            / "candidate-sequence-audit.tsv"
        )

        self.component_audit = (
            self.root
            / "component-sequence-audit.tsv"
        )

        self.package_manifest = (
            self.root
            / "package-files.tsv"
        )

        for path in (
            self.fasta,
            self.report,
            self.candidate_audit,
            self.component_audit,
            self.package_manifest,
        ):
            path.write_text(
                "synthetic\n",
                encoding="utf-8",
            )

        self.binding = (
            CandidatePackageBinding(
                accession=(
                    self.accession
                ),
                source_group="fresh",
                batch="synthetic",
                candidate_dir=(
                    self.candidate_dir
                ),
                candidate_audit=(
                    self.candidate_audit
                ),
                component_audit=(
                    self.component_audit
                ),
                package_manifest=(
                    self.package_manifest
                ),
                fasta_path=(
                    self.fasta
                ),
                sequence_report_path=(
                    self.report
                ),
                fasta_sha256=(
                    "1" * 64
                ),
                sequence_report_sha256=(
                    "2" * 64
                ),
            )
        )

        self.replicons = (
            BASIC.ClassifiedReplicon(
                name="chromosome",
                sequence="ACGT",
                topology="circular",
                molecule_location_type=(
                    "Chromosome"
                ),
            ),
            BASIC.ClassifiedReplicon(
                name="plasmid",
                sequence="GGGG",
                topology="linear",
                molecule_location_type=(
                    "Plasmid"
                ),
            ),
        )

    def tearDown(
        self,
    ):
        self.temp.cleanup()

    def make_engine(
        self,
        *,
        rows=None,
    ) -> Path:
        if rows is None:
            rows = (
                (
                    300,
                    4,
                    2,
                    "0.5",
                    2,
                    2,
                    "0.5",
                    4,
                ),
                (
                    2400,
                    0,
                    0,
                    "0",
                    0,
                    0,
                    "0",
                    4,
                ),
            )

        engine = (
            self.root
            / (
                "synthetic-engine-"
                + str(
                    len(
                        list(
                            self.root.glob(
                                "synthetic-engine-*"
                            )
                        )
                    )
                )
            )
        )

        body = textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys

            args = sys.argv[1:]

            if "--input" not in args:
                raise SystemExit(21)

            if args.count("--k") != 2:
                raise SystemExit(22)

            ks = [
                int(args[index + 1])
                for index, value in enumerate(args)
                if value == "--k"
            ]

            if ks != [300, 2400]:
                raise SystemExit(23)

            if "--longest-repeat" not in args:
                raise SystemExit(24)

            print(
                "k\\tvalid_start_count\\t"
                "non_unique_start_count\\t"
                "non_unique_fraction\\t"
                "maximum_multiplicity\\t"
                "inter_replicon_shared_start_count\\t"
                "inter_replicon_shared_fraction\\t"
                "longest_exact_repeat_length"
            )

            rows = {rows!r}

            for row in rows:
                print(
                    "\\t".join(
                        str(value)
                        for value in row
                    )
                )
            """
        )

        engine.write_text(
            body,
            encoding="utf-8",
        )

        engine.chmod(
            0o755
        )

        return engine

    def finch(
        self,
        **kwargs,
    ):
        return FakeFinch(
            binding=self.binding,
            replicons=self.replicons,
            **kwargs,
        )

    def test_exact_feature_record(
        self,
    ):
        finch = self.finch()
        engine = self.make_engine()

        record = (
            source_structural_feature_execution.compute_stage6_feature_record(
                binding=self.binding,
                species_taxid="123",
                finch=finch,
                basic=BASIC,
                engine=engine,
            )
        )

        self.assertEqual(
            record.accession,
            self.accession,
        )

        self.assertEqual(
            record.species_taxid,
            "123",
        )

        self.assertEqual(
            tuple(
                record.features
            ),
            source_structural_feature_execution.FEATURE_FIELDS,
        )

        self.assertEqual(
            record.features[
                "01_total_genome_length"
            ],
            8,
        )

        self.assertEqual(
            record.features[
                "02_whole_genome_gc_fraction"
            ],
            0.75,
        )

        self.assertEqual(
            record.features[
                "03_replicon_count"
            ],
            2,
        )

        self.assertEqual(
            record.features[
                "04_non_chromosomal_replicon_count"
            ],
            1,
        )

        self.assertEqual(
            record.features[
                "05_non_chromosomal_sequence_fraction"
            ],
            0.5,
        )

        self.assertEqual(
            record.features[
                "06_non_unique_canonical_300mer_fraction"
            ],
            0.5,
        )

        self.assertEqual(
            record.features[
                "07_non_unique_canonical_2400mer_fraction"
            ],
            0.0,
        )

        self.assertEqual(
            record.features[
                "08_maximum_canonical_300mer_multiplicity"
            ],
            2,
        )

        self.assertEqual(
            record.features[
                "09_maximum_canonical_2400mer_multiplicity"
            ],
            0,
        )

        self.assertEqual(
            record.features[
                "10_longest_exact_repeat_length"
            ],
            4,
        )

        self.assertEqual(
            record.features[
                "11_inter_replicon_shared_canonical_300mer_fraction"
            ],
            0.5,
        )

        self.assertEqual(
            record.features[
                "12_inter_replicon_shared_canonical_2400mer_fraction"
            ],
            0.0,
        )

        self.assertEqual(
            finch.calls,
            [
                (
                    self.binding.candidate_dir,
                    self.binding.candidate_audit,
                    self.binding.component_audit,
                )
            ],
        )

    def test_loader_accession_mismatch_fails(
        self,
    ):
        with self.assertRaises(
            source_structural_feature_execution.StructuralFeatureExecutionError
        ):
            source_structural_feature_execution.compute_stage6_feature_record(
                binding=self.binding,
                species_taxid="123",
                finch=self.finch(
                    accession=(
                        "GCA_000000999.1"
                    )
                ),
                basic=BASIC,
                engine=self.make_engine(),
            )

    def test_loader_fasta_path_mismatch_fails(
        self,
    ):
        alternate = (
            self.root
            / "alternate.fna"
        )

        alternate.write_text(
            "synthetic\n",
            encoding="utf-8",
        )

        with self.assertRaises(
            source_structural_feature_execution.StructuralFeatureExecutionError
        ):
            source_structural_feature_execution.compute_stage6_feature_record(
                binding=self.binding,
                species_taxid="123",
                finch=self.finch(
                    fasta_path=alternate
                ),
                basic=BASIC,
                engine=self.make_engine(),
            )

    def test_loader_report_path_mismatch_fails(
        self,
    ):
        alternate = (
            self.root
            / "alternate.jsonl"
        )

        alternate.write_text(
            "synthetic\n",
            encoding="utf-8",
        )

        with self.assertRaises(
            source_structural_feature_execution.StructuralFeatureExecutionError
        ):
            source_structural_feature_execution.compute_stage6_feature_record(
                binding=self.binding,
                species_taxid="123",
                finch=self.finch(
                    report_path=alternate
                ),
                basic=BASIC,
                engine=self.make_engine(),
            )

    def test_fraction_count_disagreement_fails(
        self,
    ):
        engine = self.make_engine(
            rows=(
                (
                    300,
                    4,
                    2,
                    "0.4",
                    2,
                    2,
                    "0.5",
                    4,
                ),
                (
                    2400,
                    0,
                    0,
                    "0",
                    0,
                    0,
                    "0",
                    4,
                ),
            )
        )

        with self.assertRaises(
            source_structural_feature_execution.StructuralFeatureExecutionError
        ):
            source_structural_feature_execution.compute_stage6_feature_record(
                binding=self.binding,
                species_taxid="123",
                finch=self.finch(),
                basic=BASIC,
                engine=engine,
            )

    def test_longest_repeat_disagreement_fails(
        self,
    ):
        engine = self.make_engine(
            rows=(
                (
                    300,
                    0,
                    0,
                    "0",
                    0,
                    0,
                    "0",
                    4,
                ),
                (
                    2400,
                    0,
                    0,
                    "0",
                    0,
                    0,
                    "0",
                    5,
                ),
            )
        )

        with self.assertRaises(
            source_structural_feature_execution.StructuralFeatureExecutionError
        ):
            source_structural_feature_execution.compute_stage6_feature_record(
                binding=self.binding,
                species_taxid="123",
                finch=self.finch(),
                basic=BASIC,
                engine=engine,
            )

    def test_wrong_k_set_fails(
        self,
    ):
        engine = self.make_engine(
            rows=(
                (
                    300,
                    0,
                    0,
                    "0",
                    0,
                    0,
                    "0",
                    4,
                ),
                (
                    400,
                    0,
                    0,
                    "0",
                    0,
                    0,
                    "0",
                    4,
                ),
            )
        )

        with self.assertRaises(
            source_structural_feature_execution.StructuralFeatureExecutionError
        ):
            source_structural_feature_execution.compute_stage6_feature_record(
                binding=self.binding,
                species_taxid="123",
                finch=self.finch(),
                basic=BASIC,
                engine=engine,
            )

    def test_nonfinite_basic_feature_fails(
        self,
    ):
        class BadBasic:
            @staticmethod
            def basic_structural_features(
                replicons,
            ):
                return {
                    "total_genome_length": 8,
                    "whole_genome_gc_fraction":
                        float("nan"),
                    "replicon_count": 2,
                    "non_chromosomal_replicon_count":
                        1,
                    "non_chromosomal_sequence_fraction":
                        0.5,
                }

        with self.assertRaises(
            source_structural_feature_execution.StructuralFeatureExecutionError
        ):
            source_structural_feature_execution.compute_stage6_feature_record(
                binding=self.binding,
                species_taxid="123",
                finch=self.finch(),
                basic=BadBasic,
                engine=self.make_engine(),
            )

    def test_invalid_species_taxid_fails(
        self,
    ):
        with self.assertRaises(
            source_structural_feature_execution.StructuralFeatureExecutionError
        ):
            source_structural_feature_execution.compute_stage6_feature_record(
                binding=self.binding,
                species_taxid="0",
                finch=self.finch(),
                basic=BASIC,
                engine=self.make_engine(),
            )


if __name__ == "__main__":
    unittest.main()
