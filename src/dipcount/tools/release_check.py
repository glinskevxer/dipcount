"""The last gate: everything the package says about itself is true.

The individual checks each answer one question. This one answers the question
somebody asks before tagging: is there anything in here that should not ship.

Debugging leftovers are the interesting part. A ``print`` in a service is
invisible in a test run and prints into somebody's terminal in the middle of a
report. A ``TODO`` is a promise nobody will keep once it is a year old. A
``breakpoint`` will stop a nightly job dead. None of these fail a test and all
of them fail a release.
"""

from __future__ import annotations

import re
from typing import Final

from dipcount import __version__
from dipcount.tools import (
    build_glossary,
    build_rules,
    check_cli,
    check_design,
    check_docstrings,
    check_errors,
    check_indexes,
    check_layers,
    check_migrations,
    check_naming,
    check_package,
    check_readme,
    check_rules,
    check_sql,
    check_tests,
    check_wiring,
    schema_dump,
    source,
)

CHECK = "release_check"

LEFTOVERS: Final[tuple[str, ...]] = ("breakpoint(", "pdb.set_trace", "TODO", "FIXME", "XXX")

PRINTING_ALLOWED: Final[frozenset[str]] = frozenset({"dipcount.tools"})

CHECKS: Final = (
    check_docstrings,
    check_layers,
    check_wiring,
    check_tests,
    check_cli,
    check_sql,
    check_indexes,
    check_migrations,
    check_naming,
    check_errors,
    check_design,
    check_rules,
    check_package,
    check_readme,
)


def every_check() -> list[source.Finding]:
    """Everything all the other checks object to."""
    out: list[source.Finding] = []
    for module in CHECKS:
        out.extend(module.findings())
    return out


def leftovers() -> list[source.Finding]:
    """Every debugging leftover in the package."""
    out: list[source.Finding] = []
    for path in source.modules():
        if source.dotted(path).startswith("dipcount.tools"):
            continue
        for number, line in enumerate(source.source_of(path).splitlines(), start=1):
            for word in LEFTOVERS:
                if word in line:
                    out.append(source.Finding(source.where(path), f"has a {word}", number))
    return out


def printing() -> list[source.Finding]:
    """Every ``print`` outside the checks, which print on purpose."""
    out: list[source.Finding] = []
    pattern = re.compile(r"(?<![\w.])print\(")
    for path in source.modules():
        if source.dotted(path).startswith(tuple(PRINTING_ALLOWED)):
            continue
        for number, line in enumerate(source.source_of(path).splitlines(), start=1):
            if pattern.search(line):
                out.append(source.Finding(source.where(path), "prints", number))
    return out


def documents() -> list[source.Finding]:
    """Every generated document that is not what the code would produce."""
    out: list[source.Finding] = []
    if not build_rules.matches():
        out.append(source.Finding(build_rules.DOCUMENT, "is not what the clause table says"))
    if not build_glossary.matches():
        out.append(source.Finding(build_glossary.DOCUMENT, "is not what the term table says"))
    if not schema_dump.matches():
        out.append(source.Finding(schema_dump.DOCUMENT, "is not the schema the code builds"))
    return out


def changelog() -> list[source.Finding]:
    """Whether the changelog carries an entry for this version."""
    path = source.project_root() / "CHANGELOG.md"
    if not path.exists():
        return [source.Finding("CHANGELOG.md", "is missing")]
    if f"## {__version__}" not in path.read_text():
        return [source.Finding("CHANGELOG.md", f"has no entry for {__version__}")]
    return []


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return every_check() + leftovers() + printing() + documents() + changelog()


def main() -> None:
    """Run the check."""
    print(f"{CHECK}: {len(CHECKS)} checks, version {__version__}")
    source.run(CHECK, findings(), counted=len(CHECKS))


if __name__ == "__main__":
    main()
