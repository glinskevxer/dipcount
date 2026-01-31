"""Every module, class and public function says what it is for.

A private helper can go without, because whoever reads it is already reading
the function above it. Everything else is read by somebody who has not opened
the file, and a name is not a sentence however carefully it was chosen.

The check also refuses a docstring that is only a restatement of the name.
A docstring reading "week start" on a function called ``week_start`` costs a
line and says nothing, and it turns the absence of an explanation into
something that looks like one.
"""

from __future__ import annotations

import ast
from pathlib import Path

from dipcount.tools import source

CHECK = "check_docstrings"


def _restates(name: str, text: str) -> bool:
    """Whether a docstring is just the name with the underscores taken out."""
    words = name.replace("_", " ").strip().lower()
    first = text.strip().split(".")[0].strip().lower()
    return first in (words, f"the {words}", f"a {words}")


def _findings_for(path: Path) -> list[source.Finding]:
    tree = source.parse(path)
    place = source.where(path)
    out: list[source.Finding] = []
    for node in source.walk_definitions(tree):
        name = source.name_of(node)
        if name != "module" and not source.is_public(name):
            continue
        text = ast.get_docstring(node)
        if not text:
            out.append(source.Finding(place, f"{name} has no docstring", source.line_of(node)))
            continue
        if not text.strip().endswith((".", '"', "`", ":")):
            out.append(
                source.Finding(
                    place,
                    f"{name} docstring does not end a sentence",
                    source.line_of(node),
                ),
            )
        if name != "module" and _restates(name, text):
            out.append(
                source.Finding(
                    place,
                    f"{name} docstring only restates the name",
                    source.line_of(node),
                ),
            )
    return out


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    out: list[source.Finding] = []
    for path in source.modules():
        out.extend(_findings_for(path))
    return out


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=len(source.modules()))


if __name__ == "__main__":
    main()
