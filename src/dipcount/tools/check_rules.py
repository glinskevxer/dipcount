"""Every clause is used, and everything used is a clause.

A rule book grows two kinds of rubbish. Clauses that nothing enforces, which
are a promise the code does not keep. And clause names in the code that the
rule book does not carry, which is the same problem read the other way and is
caught by the error check.

This one looks for the first. A clause nobody raises, nobody names in a
finding, and nobody quotes in a report is either a rule that has quietly
stopped being enforced or a rule that was written down and never implemented.
Both are worth knowing about, and neither shows up in a test.
"""

from __future__ import annotations

from typing import Final

from dipcount import rules
from dipcount.tools import source

CHECK = "check_rules"

DOCUMENTED_ONLY: Final[frozenset[str]] = frozenset(
    {
        "larval.dry",
        "report.retention",
        "report.completeness",
        "request.clock",
        "request.escalation",
        "virus.week",
        "virus.ladder",
        "weather.flood",
        "licence.credits",
    },
)


def _mentions() -> dict[str, int]:
    """How many times each clause name appears anywhere in the package."""
    counted = dict.fromkeys(rules.BY_NAME, 0)
    for path in source.modules():
        if source.dotted(path).startswith("dipcount.tools"):
            continue
        text = source.source_of(path)
        for name in counted:
            counted[name] += text.count(f'"{name}"')
    return counted


def unused_clauses() -> list[source.Finding]:
    """Every clause nothing in the package names."""
    counted = _mentions()
    out: list[source.Finding] = []
    for name, times in sorted(counted.items()):
        if name in DOCUMENTED_ONLY:
            continue
        # the rule table itself names every clause once, so one is nothing
        if times <= 1:
            out.append(source.Finding("rules", f"{name} is never used"))
    return out


def clause_shape() -> list[source.Finding]:
    """Every clause missing a heading or a sentence."""
    out: list[source.Finding] = []
    for clause in rules.CLAUSES:
        if not clause.heading.strip():
            out.append(source.Finding("rules", f"{clause.name} has no heading"))
        if len(clause.text) < 60:
            out.append(source.Finding("rules", f"{clause.name} says almost nothing"))
        if "." not in clause.name:
            out.append(source.Finding("rules", f"{clause.name} is not area.name"))
    return out


def documented_only_exists() -> list[source.Finding]:
    """Every name on the documented list that is not a clause."""
    return [
        source.Finding("rules", f"{name} is on the documented list and is not a clause")
        for name in sorted(DOCUMENTED_ONLY)
        if name not in rules.BY_NAME
    ]


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return unused_clauses() + clause_shape() + documented_only_exists()


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=len(rules.CLAUSES))


if __name__ == "__main__":
    main()
