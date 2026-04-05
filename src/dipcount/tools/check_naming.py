"""Names say what they are, and test names say what they assert.

The one that earns its keep is the test name check. ``test_it_works`` tells a
reader nothing, and worse, it tells the person who broke it nothing: a failing
test whose name is a shrug means opening the file to find out what the
district is supposed to do. A test name that is a sentence about the domain
means the failure output is already half the diagnosis.

The vague list is phrases and not words, on purpose. A single word list
catches the vocabulary: "work" is in a work card, "case" is in lower case,
"path" is in a file path, and a check that flags those is a check people learn
to work around. What is always a shrug is the whole phrase, so that is what is
matched.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

from dipcount.tools import source

CHECK = "check_naming"

VAGUE: Final[tuple[str, ...]] = (
    "_it_works",
    "_works_correctly",
    "_is_correct",
    "_correctly",
    "_happy_path",
    "_sanity",
    "_basic",
    "_simple",
    "_misc",
    "_various",
    "_stuff",
    "_smoke_test",
)

ENDINGS: Final[tuple[str, ...]] = ("_works", "_is_ok", "_passes_ok")

SHORTEST: Final = 4


def _test_functions(path: Path) -> list[tuple[str, int]]:
    tree = source.parse(path)
    return [
        (node.name, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]


def _words(name: str) -> list[str]:
    return name[len("test_") :].split("_")


def vague_tests() -> list[source.Finding]:
    """Every test whose name is a shrug."""
    out: list[source.Finding] = []
    for path in source.test_modules():
        place = source.where(path)
        for name, line in _test_functions(path):
            found = [one for one in VAGUE if one in name]
            found += [one for one in ENDINGS if name.endswith(one)]
            if found:
                out.append(
                    source.Finding(place, f"{name} says {', '.join(sorted(set(found)))}", line),
                )
    return out


def thin_tests() -> list[source.Finding]:
    """Every test whose name is too short to be a sentence."""
    out: list[source.Finding] = []
    for path in source.test_modules():
        place = source.where(path)
        for name, line in _test_functions(path):
            if len([one for one in _words(name) if one]) < SHORTEST:
                out.append(source.Finding(place, f"{name} is not a sentence", line))
    return out


def module_names() -> list[source.Finding]:
    """Every module whose file name breaks the convention."""
    out: list[source.Finding] = []
    for path in [*source.modules(), *source.test_modules()]:
        stem = path.stem
        if stem != stem.lower() or "-" in stem or " " in stem:
            out.append(source.Finding(source.where(path), "is not a lower case name"))
    return out


def test_file_names() -> list[source.Finding]:
    """Every test file that is not called ``test_something``."""
    out: list[source.Finding] = []
    for path in source.test_modules():
        if path.name in ("__init__.py", "conftest.py"):
            continue
        if not path.stem.startswith("test_"):
            out.append(source.Finding(source.where(path), "is not called test_something"))
    return out


def counted() -> int:
    """How many test names were read."""
    return sum(len(_test_functions(one)) for one in source.test_modules())


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return vague_tests() + thin_tests() + module_names() + test_file_names()


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=counted())


if __name__ == "__main__":
    main()
