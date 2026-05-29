"""A floor under the whole package, and a floor under every file in it.

The total on its own hides things. A package at ninety eight per cent can hold
one module at sixty, and the module at sixty is always the one that was added
last week, which is the one nobody has used yet. The per file floor is what
catches it, and it has to be lower than the total floor or nothing would ever
pass: a small module with two uncovered refusal branches is a long way below
the average and is not a problem.

Reads ``coverage.json``, which ``pytest --cov --cov-report=json`` writes.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dipcount.tools import source

CHECK = "coverage_gate"
REPORT = "coverage.json"

FLOOR: Final = 95.0
FILE_FLOOR: Final = 80.0
WORST = 6


@dataclass(frozen=True)
class Measured:
    """One file and what share of it the suite reached."""

    name: str
    percent: float
    missing: int

    def line(self) -> str:
        """One line for the gate's output."""
        return f"  {self.percent:6.2f}%  {self.name}  ({self.missing} lines missed)"


def report_path() -> Path:
    """Where the coverage report lives."""
    return source.project_root() / REPORT


def read(path: Path | None = None) -> tuple[float, list[Measured]]:
    """The total and every file, out of the coverage report."""
    where = path or report_path()
    data = json.loads(where.read_text())
    total = float(data["totals"]["percent_covered"])
    files = [
        Measured(
            name=name,
            percent=float(one["summary"]["percent_covered"]),
            missing=int(one["summary"]["missing_lines"]),
        )
        for name, one in sorted(data["files"].items())
    ]
    return total, files


def below(files: list[Measured], floor: float) -> list[Measured]:
    """Every file under a floor, worst first."""
    return sorted(
        (one for one in files if one.percent < floor),
        key=lambda one: one.percent,
    )


def worst(files: list[Measured], how_many: int = WORST) -> list[Measured]:
    """The least covered files, worst first."""
    return sorted(files, key=lambda one: one.percent)[:how_many]


def _argument(args: list[str], name: str, fallback: float) -> float:
    if name in args:
        return float(args[args.index(name) + 1])
    return fallback


def main(argv: list[str] | None = None) -> None:
    """Run the gate."""
    args = sys.argv[1:] if argv is None else argv
    floor = _argument(args, "--floor", FLOOR)
    file_floor = _argument(args, "--file-floor", FILE_FLOOR)
    how_many = int(_argument(args, "--worst", WORST))
    path = report_path()
    if not path.exists():
        print(f"{CHECK}: no {REPORT}, run pytest --cov --cov-report=json first")
        sys.exit(1)
    total, files = read(path)
    short = below(files, file_floor)
    print(f"{CHECK}: {total:.2f}% over {len(files)} files")
    for one in worst(files, how_many):
        print(one.line())
    failed = False
    if total < floor:
        print(f"{CHECK}: the total is under the {floor:.0f}% floor")
        failed = True
    if short:
        print(f"{CHECK}: {len(short)} file(s) under the {file_floor:.0f}% file floor")
        failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
