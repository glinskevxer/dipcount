"""Writing the rule book out as a document, from the clause table.

The rule book people read and the rule book the code enforces have to be the
same rule book. Keeping two of them in step by hand lasts about one season:
somebody tightens a threshold, the code changes, and the document goes on
saying what the district used to do.

So there is one clause table and this writes the document off it. In ``--check``
mode it says whether the file on disk is what the table would produce, which
is what ci runs, and without it the file is rewritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dipcount import rules
from dipcount.tools import source

DOCUMENT = "docs/RULES.md"


def path() -> Path:
    """Where the generated rule book lives."""
    return source.project_root() / DOCUMENT


def _section(area: str) -> list[str]:
    out = [f"## {area}", ""]
    for clause in rules.clauses_in(area):
        out.append(f"### {clause.name}")
        out.append("")
        out.append(f"*{clause.heading}*")
        out.append("")
        out.append(clause.text)
        out.append("")
    return out


def document() -> str:
    """The whole rule book as the clause table would write it."""
    lines = [
        "# The rule book",
        "",
        "Generated from `dipcount.rules` by `python -m dipcount.tools.build_rules`.",
        "Edit the clause table, not this file.",
        "",
        f"{len(rules.CLAUSES)} clauses in {len(rules.areas())} areas.",
        "",
    ]
    for area in rules.areas():
        lines.extend(_section(area))
    lines.extend(_figures())
    return "\n".join(lines).rstrip() + "\n"


def _figures() -> list[str]:
    out = ["## the figures the clauses use", ""]
    out.append("| figure | value |")
    out.append("| --- | --- |")
    for name, value in sorted(figures().items()):
        out.append(f"| {name} | {value} |")
    out.append("")
    return out


def figures() -> dict[str, str]:
    """Every number the rule book turns on."""
    return {
        "larval thresholds": ", ".join(
            f"{key} {value}" for key, value in sorted(rules.thresholds().items())
        ),
        "pupal stop": str(rules.PUPAL_STOP),
        "late instar share": str(rules.LATE_URGENT),
        "raft interval": f"{rules.RAFT_INTERVAL} days",
        "flood rain": f"{rules.FLOOD_INCHES} inch",
        "adult thresholds": ", ".join(
            f"{key} {value}" for key, value in sorted(rules.adult_thresholds().items())
        ),
        "elevated ratio": str(rules.ELEVATED),
        "wind band": f"{rules.WIND_LOW} to {rules.WIND_HIGH} mph",
        "temperature floor": str(rules.TEMP_FLOOR),
        "night hours": f"{rules.NIGHT_FROM}:00 to {rules.NIGHT_TO:02d}:00",
        "response ladder": ", ".join(f"{name} {floor}" for name, floor in rules.ladder()),
        "retention": f"{rules.RETENTION_YEARS} years",
        "resistance shelf life": f"{rules.STALE_DAYS} days",
        "rotation run": str(rules.ROTATION_RUN),
    }


def write() -> Path:
    """Write the document and say where it went."""
    made = path()
    made.parent.mkdir(parents=True, exist_ok=True)
    made.write_text(document())
    return made


def matches() -> bool:
    """Whether the file on disk is what the clause table would produce."""
    made = path()
    return made.exists() and made.read_text() == document()


def main(argv: list[str] | None = None) -> None:
    """Write the rule book, or check the one on disk."""
    args = sys.argv[1:] if argv is None else argv
    if "--check" in args:
        if matches():
            print(f"build_rules: ok ({len(rules.CLAUSES)} clauses)")
            sys.exit(0)
        print(f"build_rules: {DOCUMENT} is not what the clause table says")
        sys.exit(1)
    print(f"build_rules: wrote {write()}")


if __name__ == "__main__":
    main()
