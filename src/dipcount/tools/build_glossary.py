"""Writing the glossary out as a document, from the term table.

Same reasoning as the rule book. Two districts arguing about whether a figure
is comparable are really arguing about what a word means, and the answer has
to be somewhere both of them can read it. Keeping the document and the code in
step by hand does not survive a season.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dipcount import glossary
from dipcount.tools import source

DOCUMENT = "docs/GLOSSARY.md"


def path() -> Path:
    """Where the generated glossary lives."""
    return source.project_root() / DOCUMENT


def document() -> str:
    """The whole glossary as the term table would write it."""
    lines = [
        "# What the district means",
        "",
        "Generated from `dipcount.glossary` by",
        "`python -m dipcount.tools.build_glossary`. Edit the term table, not",
        "this file.",
        "",
        f"{len(glossary.TERMS)} terms.",
        "",
        "| term | defined in | meaning |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| {one.word} | `{one.owner}` | {one.meaning} |"
        for one in sorted(glossary.TERMS, key=lambda term: term.word)
    )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write() -> Path:
    """Write the document and say where it went."""
    made = path()
    made.parent.mkdir(parents=True, exist_ok=True)
    made.write_text(document())
    return made


def matches() -> bool:
    """Whether the file on disk is what the term table would produce."""
    made = path()
    return made.exists() and made.read_text() == document()


def main(argv: list[str] | None = None) -> None:
    """Write the glossary, or check the one on disk."""
    args = sys.argv[1:] if argv is None else argv
    if "--check" in args:
        if matches():
            print(f"build_glossary: ok ({len(glossary.TERMS)} terms)")
            sys.exit(0)
        print(f"build_glossary: {DOCUMENT} is not what the term table says")
        sys.exit(1)
    print(f"build_glossary: wrote {write()}")


if __name__ == "__main__":
    main()
