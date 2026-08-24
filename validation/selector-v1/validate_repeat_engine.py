#!/usr/bin/env python3
"""Differential validation of the vendored BacSelect repeat engine.

The unchanged Project Finch production implementation is compared directly
with its unchanged Python semantic reference across deliberate edge cases and
deterministic randomized multi-replicon genomes. No production BacSelect
genome is inspected by this validation.
"""

from __future__ import annotations

import csv
import importlib.util
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]

REFERENCE = (
    REPO
    / "vendor"
    / "project-finch"
    / "experiment-0"
    / "structural_features.py"
)

CPP_SOURCE = (
    REPO
    / "vendor"
    / "project-finch"
    / "experiment-0"
    / "structural_features_fast.cpp"
)

SEED = 20260822
RANDOM_CASES = 1000


spec = importlib.util.spec_from_file_location(
    "finch_structural_features_reference_fasttest",
    REFERENCE,
)

if spec is None or spec.loader is None:
    raise RuntimeError(
        f"cannot load reference module: {REFERENCE}"
    )

sf = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sf
spec.loader.exec_module(sf)


class FastKmerDifferentialTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        conda_prefix = os.environ.get(
            "CONDA_PREFIX"
        )

        if not conda_prefix:
            raise RuntimeError(
                "CONDA_PREFIX is not set; run this test "
                "inside the finch-features environment"
            )

        prefix = Path(conda_prefix)

        compiler = (
            prefix
            / "bin"
            / "x86_64-conda-linux-gnu-c++"
        )

        header = (
            prefix
            / "include"
            / "divsufsort.h"
        )

        library = (
            prefix
            / "lib"
            / "libdivsufsort.so"
        )

        for path in (
            compiler,
            header,
            library,
            CPP_SOURCE,
        ):
            if not path.exists():
                raise RuntimeError(
                    f"required file missing: {path}"
                )

        cls.tempdir = tempfile.TemporaryDirectory(
            prefix="finch-fast-test-"
        )

        cls.binary = (
            Path(cls.tempdir.name)
            / "structural_features_fast"
        )

        command = [
            str(compiler),
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            f"-I{prefix / 'include'}",
            str(CPP_SOURCE),
            f"-L{prefix / 'lib'}",
            f"-Wl,-rpath,{prefix / 'lib'}",
            "-ldivsufsort",
            "-o",
            str(cls.binary),
        ]

        subprocess.run(
            command,
            check=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tempdir.cleanup()

    def run_fast(
        self,
        replicons,
        k_values,
    ):
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=".tsv",
            delete=False,
        ) as handle:
            input_path = Path(
                handle.name
            )

            writer = csv.writer(
                handle,
                delimiter="\t",
                lineterminator="\n",
            )

            writer.writerow(
                [
                    "name",
                    "topology",
                    "sequence",
                ]
            )

            for replicon in replicons:
                writer.writerow(
                    [
                        replicon.name,
                        replicon.topology,
                        replicon.sequence,
                    ]
                )

        command = [
            str(self.binary),
            "--input",
            str(input_path),
        ]

        for k in k_values:
            command.extend(
                [
                    "--k",
                    str(k),
                ]
            )

        try:
            completed = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
            )
        finally:
            input_path.unlink(
                missing_ok=True
            )

        rows = list(
            csv.DictReader(
                completed.stdout.splitlines(),
                delimiter="\t",
            )
        )

        observed = {}

        for row in rows:
            k = int(
                row["k"]
            )

            observed[k] = {
                "valid_start_count": int(
                    row[
                        "valid_start_count"
                    ]
                ),
                "non_unique_start_count": int(
                    row[
                        "non_unique_start_count"
                    ]
                ),
                "non_unique_fraction": float(
                    row[
                        "non_unique_fraction"
                    ]
                ),
                "maximum_multiplicity": int(
                    row[
                        "maximum_multiplicity"
                    ]
                ),
                "inter_replicon_shared_start_count": int(
                    row[
                        "inter_replicon_shared_start_count"
                    ]
                ),
                "inter_replicon_shared_fraction": float(
                    row[
                        "inter_replicon_shared_fraction"
                    ]
                ),
            }

        return observed

    def compare_case(
        self,
        case_id,
        replicons,
        k_values,
    ) -> None:
        fast = self.run_fast(
            replicons,
            k_values,
        )

        expected_ks = sorted(
            set(k_values)
        )

        self.assertEqual(
            sorted(fast),
            expected_ks,
            msg=(
                f"{case_id}: returned k values "
                "differ"
            ),
        )

        for k in expected_ks:
            reference = sf.kmer_features(
                replicons,
                k,
            )

            observed = fast[k]

            for key in (
                "valid_start_count",
                "non_unique_start_count",
                "maximum_multiplicity",
                "inter_replicon_shared_start_count",
            ):
                self.assertEqual(
                    observed[key],
                    reference[key],
                    msg=(
                        f"{case_id}, k={k}, "
                        f"{key}"
                    ),
                )

            for key in (
                "non_unique_fraction",
                "inter_replicon_shared_fraction",
            ):
                self.assertTrue(
                    math.isclose(
                        observed[key],
                        reference[key],
                        rel_tol=0.0,
                        abs_tol=1e-15,
                    ),
                    msg=(
                        f"{case_id}, k={k}, {key}: "
                        f"reference={reference[key]!r}, "
                        f"fast={observed[key]!r}"
                    ),
                )

    def test_deliberate_edge_cases(self) -> None:
        edge_cases = [
            (
                [
                    sf.Replicon(
                        "r1",
                        "ACGT",
                        "circular",
                    )
                ],
                [1, 2, 3, 4, 5],
            ),
            (
                [
                    sf.Replicon(
                        "r1",
                        "AAAAA",
                        "linear",
                    )
                ],
                [1, 2, 3, 4, 5, 6],
            ),
            (
                [
                    sf.Replicon(
                        "r1",
                        "AAAAA",
                        "circular",
                    )
                ],
                [1, 2, 3, 4, 5, 6],
            ),
            (
                [
                    sf.Replicon(
                        "r1",
                        "AACG",
                        "linear",
                    ),
                    sf.Replicon(
                        "r2",
                        "CGTT",
                        "linear",
                    ),
                ],
                [1, 2, 3, 4, 5],
            ),
            (
                [
                    sf.Replicon(
                        "r1",
                        "ACGTTT",
                        "circular",
                    ),
                    sf.Replicon(
                        "r2",
                        "TTAC",
                        "linear",
                    ),
                ],
                [1, 2, 3, 4, 5, 6, 7],
            ),
            (
                [
                    sf.Replicon(
                        "r1",
                        "AACCGG",
                        "circular",
                    ),
                    sf.Replicon(
                        "r2",
                        "AACCGG",
                        "circular",
                    ),
                ],
                [1, 2, 3, 4, 5, 6, 7],
            ),
        ]

        for index, (
            replicons,
            k_values,
        ) in enumerate(
            edge_cases,
            start=1,
        ):
            with self.subTest(
                case=index
            ):
                self.compare_case(
                    f"edge-{index}",
                    replicons,
                    k_values,
                )

    def test_randomized_differential_cases(self) -> None:
        rng = random.Random(
            SEED
        )

        alphabet = "ACGT"

        for case_number in range(
            1,
            RANDOM_CASES + 1,
        ):
            replicon_count = rng.randint(
                1,
                4,
            )

            replicons = []
            maximum_length = 0

            for replicon_index in range(
                replicon_count
            ):
                length = rng.randint(
                    1,
                    30,
                )

                maximum_length = max(
                    maximum_length,
                    length,
                )

                sequence = "".join(
                    rng.choice(alphabet)
                    for _ in range(length)
                )

                topology = rng.choice(
                    [
                        "linear",
                        "circular",
                    ]
                )

                replicons.append(
                    sf.Replicon(
                        f"r{replicon_index + 1}",
                        sequence,
                        topology,
                    )
                )

            candidate_ks = {
                1,
                2,
                3,
                maximum_length,
                maximum_length + 1,
                rng.randint(
                    1,
                    maximum_length + 3,
                ),
                rng.randint(
                    1,
                    maximum_length + 3,
                ),
            }

            with self.subTest(
                case=case_number
            ):
                self.compare_case(
                    f"random-{case_number}",
                    replicons,
                    sorted(candidate_ks),
                )


    def run_fast_longest_repeat(
        self,
        replicons,
    ) -> int:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=".tsv",
            delete=False,
        ) as handle:
            input_path = Path(
                handle.name
            )

            writer = csv.writer(
                handle,
                delimiter="\t",
                lineterminator="\n",
            )

            writer.writerow(
                [
                    "name",
                    "topology",
                    "sequence",
                ]
            )

            for replicon in replicons:
                writer.writerow(
                    [
                        replicon.name,
                        replicon.topology,
                        replicon.sequence,
                    ]
                )

        try:
            completed = subprocess.run(
                [
                    str(self.binary),
                    "--input",
                    str(input_path),
                    "--k",
                    "1",
                    "--longest-repeat",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        finally:
            input_path.unlink(
                missing_ok=True
            )

        rows = list(
            csv.DictReader(
                completed.stdout.splitlines(),
                delimiter="\t",
            )
        )

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertIn(
            "longest_exact_repeat_length",
            rows[0],
        )

        return int(
            rows[0][
                "longest_exact_repeat_length"
            ]
        )

    def compare_longest_repeat_case(
        self,
        case_id,
        replicons,
    ) -> None:
        reference = (
            sf.longest_exact_repeat_reference(
                replicons
            )
        )

        observed = (
            self.run_fast_longest_repeat(
                replicons
            )
        )

        self.assertEqual(
            observed,
            reference,
            msg=(
                f"{case_id}: longest-repeat mismatch; "
                f"reference={reference}, "
                f"fast={observed}, "
                f"replicons={replicons!r}"
            ),
        )

    def test_threefold_periodic_circle_full_length_regression(
        self,
    ) -> None:
        replicons = [
            sf.Replicon(
                "circle",
                "AAACGAAACGAAACG",
                "circular",
            )
        ]

        observed = self.run_fast(
            replicons,
            [
                15,
                16,
            ],
        )

        self.assertEqual(
            observed[15][
                "valid_start_count"
            ],
            15,
        )

        self.assertEqual(
            observed[15][
                "non_unique_start_count"
            ],
            15,
        )

        self.assertEqual(
            observed[15][
                "maximum_multiplicity"
            ],
            3,
        )

        # A circular k-mer may cross the recorded origin but may not
        # traverse any source coordinate more than once.
        self.assertEqual(
            observed[16][
                "valid_start_count"
            ],
            0,
        )

        self.assertEqual(
            self.run_fast_longest_repeat(
                replicons
            ),
            15,
        )

    def test_longest_repeat_differential(self) -> None:
        edge_cases = [
            [
                sf.Replicon(
                    "r1",
                    "AC",
                    "linear",
                )
            ],
            [
                sf.Replicon(
                    "r1",
                    "AAAAA",
                    "linear",
                )
            ],
            [
                sf.Replicon(
                    "r1",
                    "AACG",
                    "linear",
                ),
                sf.Replicon(
                    "r2",
                    "CGTT",
                    "linear",
                ),
            ],
            [
                sf.Replicon(
                    "circle",
                    "ACGTTT",
                    "circular",
                ),
                sf.Replicon(
                    "linear",
                    "TTAC",
                    "linear",
                ),
            ],
            [
                sf.Replicon(
                    "r1",
                    "AAAA",
                    "circular",
                )
            ],
            [
                sf.Replicon(
                    "r1",
                    "AACCGG",
                    "circular",
                ),
                sf.Replicon(
                    "r2",
                    "AACCGG",
                    "circular",
                ),
            ],
            [
                sf.Replicon(
                    "r1",
                    "ACGT",
                    "circular",
                )
            ],
            [
                sf.Replicon(
                    "r1",
                    "A",
                    "linear",
                )
            ],
        ]

        for index, replicons in enumerate(
            edge_cases,
            start=1,
        ):
            with self.subTest(
                edge_case=index
            ):
                self.compare_longest_repeat_case(
                    f"edge-{index}",
                    replicons,
                )

        rng = random.Random(
            SEED
        )

        alphabet = "ACGT"

        for case_number in range(
            1,
            RANDOM_CASES + 1,
        ):
            replicons = []

            for replicon_index in range(
                rng.randint(1, 4)
            ):
                length = rng.randint(
                    1,
                    30,
                )

                sequence = "".join(
                    rng.choice(alphabet)
                    for _ in range(length)
                )

                topology = rng.choice(
                    [
                        "linear",
                        "circular",
                    ]
                )

                replicons.append(
                    sf.Replicon(
                        f"r{replicon_index + 1}",
                        sequence,
                        topology,
                    )
                )

            with self.subTest(
                random_case=case_number
            ):
                self.compare_longest_repeat_case(
                    f"random-{case_number}",
                    replicons,
                )



if __name__ == "__main__":
    unittest.main()
