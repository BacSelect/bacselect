from __future__ import annotations

import contextlib
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import tempfile
import unittest

from bacselect import (
    source_structural_feature_execution,
)
from bacselect import (
    source_truth_execution,
)
from bacselect.source_structural_features import (
    CandidatePackageBinding,
)


WRAPPER_PATH = Path(
    "validation/selector-v1/"
    "run_structural_feature_execution.py"
).resolve()

STAGE1_WRAPPER_PATH = Path(
    "validation/selector-v1/"
    "run_source_truth_execution.py"
).resolve()


def load_wrapper():
    spec = importlib.util.spec_from_file_location(
        "_bacselect_stage6_wrapper_test_module",
        WRAPPER_PATH,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "could not load Stage 6 wrapper"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    import sys

    sys.modules[
        spec.name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


WRAPPER = load_wrapper()


def load_stage1_wrapper():
    spec = importlib.util.spec_from_file_location(
        "_bacselect_stage1_wrapper_for_stage6_tests",
        STAGE1_WRAPPER_PATH,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "could not load frozen Stage 1 wrapper"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    import sys

    sys.modules[
        spec.name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


STAGE1 = load_stage1_wrapper()


class Stage6WrapperTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.temp = (
            tempfile.TemporaryDirectory(
                prefix=(
                    "bacselect-stage6-wrapper-test-"
                )
            )
        )

        self.root = Path(
            self.temp.name
        )

        self.repo = (
            self.root
            / "repo"
        )

        self.repo.mkdir()

        self.output_root = (
            self.root
            / "output"
        )

        self.commit = (
            "a" * 40
        )

        self.accessions = (
            "GCA_000001001.1",
            "GCA_000001002.1",
        )

        self.species = {
            self.accessions[0]:
                "11",
            self.accessions[1]:
                "22",
        }

        self.holdout = (
            self.root
            / "external-decision-holdout.tsv"
        )

        with self.holdout.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(
                    WRAPPER.HOLDOUT_FIELDS
                ),
                delimiter="\t",
                lineterminator="\n",
            )

            writer.writeheader()

            for accession in self.accessions:
                writer.writerow(
                    {
                        "canonical_genbank_assembly_accession":
                            accession,
                        "species_taxid":
                            self.species[
                                accession
                            ],
                    }
                )

        self.expectations = (
            WRAPPER.HoldoutExpectations(
                artifact_sha256=(
                    WRAPPER.sha256_file(
                        self.holdout
                    )
                ),
                count=2,
                distinct_species_count=2,
                membership_sha256=(
                    source_truth_execution
                    .accession_membership_sha256(
                        self.accessions
                    )
                ),
            )
        )

        self.engine = (
            self.root
            / "engine"
        )

        self.engine.write_text(
            "#!/bin/sh\nexit 0\n",
            encoding="ascii",
        )

        self.engine.chmod(
            0o755
        )

        self.engine_sha = (
            WRAPPER.sha256_file(
                self.engine
            )
        )

        self.bundle = SimpleNamespace(
            batches=(),
            input_evidence_rows=(),
        )

        self.binding_by_accession = {}

        for accession in self.accessions:
            candidate_dir = (
                self.root
                / "source"
                / accession
            )

            candidate_dir.mkdir(
                parents=True
            )

            fasta = (
                candidate_dir
                / (
                    accession
                    + "_genomic.fna"
                )
            )

            report = (
                candidate_dir
                / "sequence_report.jsonl"
            )

            candidate_audit = (
                self.root
                / (
                    accession
                    + ".candidate.tsv"
                )
            )

            component_audit = (
                self.root
                / (
                    accession
                    + ".component.tsv"
                )
            )

            package_manifest = (
                self.root
                / (
                    accession
                    + ".package.tsv"
                )
            )

            for path in (
                fasta,
                report,
                candidate_audit,
                component_audit,
                package_manifest,
            ):
                path.write_text(
                    "synthetic\n",
                    encoding="ascii",
                )

            self.binding_by_accession[
                accession
            ] = (
                CandidatePackageBinding(
                    accession=accession,
                    source_group="fresh",
                    batch="synthetic",
                    candidate_dir=(
                        candidate_dir
                    ),
                    candidate_audit=(
                        candidate_audit
                    ),
                    component_audit=(
                        component_audit
                    ),
                    package_manifest=(
                        package_manifest
                    ),
                    fasta_path=(
                        fasta
                    ),
                    sequence_report_path=(
                        report
                    ),
                    fasta_sha256=(
                        hashlib.sha256(
                            fasta.read_bytes()
                        ).hexdigest()
                    ),
                    sequence_report_sha256=(
                        hashlib.sha256(
                            report.read_bytes()
                        ).hexdigest()
                    ),
                )
            )

    def tearDown(
        self,
    ):
        self.temp.cleanup()

    def binding_builder(
        self,
        *,
        bundle,
        accessions,
    ):
        self.assertIs(
            bundle,
            self.bundle,
        )

        return tuple(
            self.binding_by_accession[
                accession
            ]
            for accession in sorted(
                accessions
            )
        )

    def source_metadata_builder(
        self,
        *,
        bundle,
        accessions,
        stage1,
    ):
        self.assertIs(
            bundle,
            self.bundle,
        )

        return {
            accession:
                WRAPPER.SourceMetadata(
                    accession=accession,
                    source_group="fresh",
                    batch="synthetic",
                    source_evidence_sha256=(
                        hashlib.sha256(
                            (
                                accession
                                + "\n"
                            ).encode(
                                "ascii"
                            )
                        ).hexdigest()
                    ),
                    topology_circular_records=1,
                    topology_linear_records=1,
                )
            for accession in accessions
        }

    @staticmethod
    def features(
        accession,
    ):
        offset = (
            0
            if accession.endswith(
                "001.1"
            )
            else 1
        )

        return {
            "01_total_genome_length":
                8 + offset,
            "02_whole_genome_gc_fraction":
                (
                    1.0 / 3.0
                    if offset == 0
                    else 0.5
                ),
            "03_replicon_count":
                2,
            "04_non_chromosomal_replicon_count":
                1,
            "05_non_chromosomal_sequence_fraction":
                0.5,
            "06_non_unique_canonical_300mer_fraction":
                0.25,
            "07_non_unique_canonical_2400mer_fraction":
                0.0,
            "08_maximum_canonical_300mer_multiplicity":
                2,
            "09_maximum_canonical_2400mer_multiplicity":
                0,
            "10_longest_exact_repeat_length":
                4,
            "11_inter_replicon_shared_canonical_300mer_fraction":
                0.25,
            "12_inter_replicon_shared_canonical_2400mer_fraction":
                0.0,
        }

    def feature_computer(
        self,
        *,
        binding,
        species_taxid,
        finch,
        basic,
        engine,
    ):
        return (
            source_structural_feature_execution
            .Stage6FeatureRecord(
                accession=(
                    binding.accession
                ),
                species_taxid=(
                    species_taxid
                ),
                features=self.features(
                    binding.accession
                ),
                retained_replicon_count=2,
                total_sequence_length=(
                    self.features(
                        binding.accession
                    )[
                        "01_total_genome_length"
                    ]
                ),
            )
        )

    def execute(
        self,
        *,
        population_factory=None,
        feature_computer=None,
        output_root=None,
    ):
        if population_factory is None:
            population_factory = (
                lambda:
                    self.bundle
            )

        if feature_computer is None:
            feature_computer = (
                self.feature_computer
            )

        return WRAPPER.execute_to_scratch(
            repo=self.repo,
            expected_commit=(
                self.commit
            ),
            expected_wrapper_sha256=(
                "1" * 64
            ),
            expected_wrapper_test_sha256=(
                "2" * 64
            ),
            output_root=(
                self.output_root
                if output_root is None
                else output_root
            ),
            holdout_path=(
                self.holdout
            ),
            holdout_expectations=(
                self.expectations
            ),
            frozen_repo_sha256={},
            stage1=(
                STAGE1
            ),
            finch=object(),
            basic=object(),
            engine=self.engine,
            expected_engine_sha256=(
                self.engine_sha
            ),
            population_factory=(
                population_factory
            ),
            binding_builder=(
                self.binding_builder
            ),
            source_metadata_builder=(
                self.source_metadata_builder
            ),
            feature_computer=(
                feature_computer
            ),
        )

    def test_success_finalizes_exact_seven_files(
        self,
    ):
        final_dir = self.execute()

        observed = {
            path.name
            for path in final_dir.iterdir()
            if path.is_file()
        }

        self.assertEqual(
            observed,
            WRAPPER.FINAL_FILES,
        )

        self.assertFalse(
            (
                self.output_root
                / (
                    "."
                    + self.commit
                    + ".partial"
                )
            ).exists()
        )

    def test_predecision_exists_before_population_factory(
        self,
    ):
        partial = (
            self.output_root
            / (
                "."
                + self.commit
                + ".partial"
            )
        )

        def factory():
            predecision = (
                partial
                / "stage6-predecision-provenance.json"
            )

            self.assertTrue(
                predecision.is_file()
            )

            payload = json.loads(
                predecision.read_text(
                    encoding="utf-8"
                )
            )

            self.assertFalse(
                payload[
                    "holdout_rows_parsed"
                ]
            )

            self.assertFalse(
                payload[
                    "source_package_manifests_parsed"
                ]
            )

            self.assertFalse(
                payload[
                    "structural_features_calculated"
                ]
            )

            return self.bundle

        self.execute(
            population_factory=factory
        )

    def test_malformed_holdout_preserves_predecision_partial(
        self,
    ):
        self.holdout.write_text(
            "wrong\theader\nx\ty\n",
            encoding="utf-8",
        )

        self.expectations = (
            WRAPPER.HoldoutExpectations(
                artifact_sha256=(
                    WRAPPER.sha256_file(
                        self.holdout
                    )
                ),
                count=2,
                distinct_species_count=2,
                membership_sha256=(
                    "3" * 64
                ),
            )
        )

        called = False

        def factory():
            nonlocal called
            called = True
            return self.bundle

        with self.assertRaises(
            WRAPPER.Stage6WrapperError
        ):
            self.execute(
                population_factory=(
                    factory
                )
            )

        self.assertFalse(
            called
        )

        partial = (
            self.output_root
            / (
                "."
                + self.commit
                + ".partial"
            )
        )

        self.assertTrue(
            (
                partial
                / "stage6-predecision-provenance.json"
            ).is_file()
        )

        self.assertFalse(
            (
                self.output_root
                / self.commit
            ).exists()
        )

    def test_feature_failure_preserves_partial(
        self,
    ):
        def fail_feature(
            **kwargs,
        ):
            raise RuntimeError(
                "synthetic identity-bearing failure"
            )

        with self.assertRaisesRegex(
            WRAPPER.Stage6WrapperError,
            "candidate structural-feature execution failed closed",
        ):
            self.execute(
                feature_computer=(
                    fail_feature
                )
            )

        partial = (
            self.output_root
            / (
                "."
                + self.commit
                + ".partial"
            )
        )

        self.assertTrue(
            (
                partial
                / "stage6-predecision-provenance.json"
            ).is_file()
        )

        self.assertFalse(
            (
                self.output_root
                / self.commit
            ).exists()
        )

    def test_matrix_schema_order_and_float_serialization(
        self,
    ):
        final_dir = self.execute()

        matrix = (
            final_dir
            / "structural-feature-matrix-300-2400.tsv"
        )

        lines = matrix.read_text(
            encoding="ascii"
        ).splitlines()

        self.assertEqual(
            tuple(
                lines[
                    0
                ].split(
                    "\t"
                )
            ),
            WRAPPER.MATRIX_FIELDS,
        )

        rows = [
            line.split(
                "\t"
            )
            for line in lines[
                1:
            ]
        ]

        self.assertEqual(
            [
                row[
                    0
                ]
                for row in rows
            ],
            sorted(
                self.accessions
            ),
        )

        gc_index = (
            WRAPPER.MATRIX_FIELDS.index(
                "02_whole_genome_gc_fraction"
            )
        )

        self.assertEqual(
            rows[
                0
            ][
                gc_index
            ],
            format(
                1.0 / 3.0,
                ".17g",
            ),
        )

    def test_numeric_array_sha_is_little_endian_float64_c_order(
        self,
    ):
        final_dir = self.execute()

        summary = json.loads(
            (
                final_dir
                / "stage6-aggregate-summary.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        digest = hashlib.sha256()

        for accession in sorted(
            self.accessions
        ):
            features = self.features(
                accession
            )

            for field in (
                source_structural_feature_execution
                .FEATURE_FIELDS
            ):
                digest.update(
                    struct.pack(
                        "<d",
                        float(
                            features[
                                field
                            ]
                        ),
                    )
                )

        self.assertEqual(
            summary[
                "raw_feature_matrix_numeric_array_sha256"
            ],
            digest.hexdigest(),
        )

    def test_candidate_evidence_feature_record_sha_matches_matrix_row(
        self,
    ):
        final_dir = self.execute()

        matrix_lines = (
            final_dir
            / "structural-feature-matrix-300-2400.tsv"
        ).read_bytes().splitlines(
            keepends=True
        )

        by_accession = {
            line.split(
                b"\t",
                1,
            )[
                0
            ].decode(
                "ascii"
            ):
                line
            for line in matrix_lines[
                1:
            ]
        }

        with (
            final_dir
            / "stage6-candidate-evidence.tsv"
        ).open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            rows = list(
                csv.DictReader(
                    handle,
                    delimiter="\t",
                )
            )

        for row in rows:
            accession = row[
                "canonical_genbank_assembly_accession"
            ]

            self.assertEqual(
                row[
                    "feature_record_sha256"
                ],
                hashlib.sha256(
                    by_accession[
                        accession
                    ]
                ).hexdigest(),
            )

    def test_content_manifest_covers_exact_six_files(
        self,
    ):
        final_dir = self.execute()

        with (
            final_dir
            / "stage6-content-manifest.tsv"
        ).open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            rows = list(
                csv.DictReader(
                    handle,
                    delimiter="\t",
                )
            )

        self.assertEqual(
            tuple(
                row[
                    "path"
                ]
                for row in rows
            ),
            tuple(
                sorted(
                    WRAPPER.CONTENT_COVERED_FILES
                )
            ),
        )

        self.assertNotIn(
            "stage6-content-manifest.tsv",
            {
                row[
                    "path"
                ]
                for row in rows
            },
        )

    def test_existing_final_directory_is_not_overwritten(
        self,
    ):
        self.execute()

        with self.assertRaisesRegex(
            WRAPPER.Stage6WrapperError,
            "already exists",
        ):
            self.execute()

    def test_output_root_inside_repo_fails(
        self,
    ):
        with self.assertRaisesRegex(
            WRAPPER.Stage6WrapperError,
            "outside repository",
        ):
            self.execute(
                output_root=(
                    self.repo
                    / "stage6-output"
                )
            )

    def test_stdout_is_identity_safe(
        self,
    ):
        output = io.StringIO()

        with contextlib.redirect_stdout(
            output
        ):
            self.execute()

        text = output.getvalue()

        self.assertNotIn(
            "GCA_",
            text,
        )

        self.assertNotIn(
            "\t11",
            text,
        )

        self.assertIn(
            "successful_feature_row_count=2",
            text,
        )

    def test_species_taxid_is_preserved_exactly(
        self,
    ):
        final_dir = self.execute()

        with (
            final_dir
            / "structural-feature-matrix-300-2400.tsv"
        ).open(
            "r",
            encoding="ascii",
            newline="",
        ) as handle:
            rows = list(
                csv.DictReader(
                    handle,
                    delimiter="\t",
                )
            )

        self.assertEqual(
            {
                row[
                    "canonical_genbank_assembly_accession"
                ]:
                    row[
                        "species_taxid"
                    ]
                for row in rows
            },
            self.species,
        )


if __name__ == "__main__":
    unittest.main()
