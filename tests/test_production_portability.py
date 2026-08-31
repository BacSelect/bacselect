from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

CHECKER = (
    ROOT
    / "validation"
    / "selector-v1"
    / "check_production_portability.py"
)


def test_production_portability_contract():
    result = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        result.stdout
        + result.stderr
    )

    assert (
        "GitHub-hosted infrastructure only"
        in result.stdout
    )
