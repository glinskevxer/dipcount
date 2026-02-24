"""Nothing in this package is written and then left with no caller.

There are two ways for work to be unreached and they look nothing alike. A
whole module can sit there with green tests and no importer, which happens
when a layer is built ahead of the layer that was going to use it. And a
single function can be written, tested, and never called from anywhere, which
happens when a service grows an entry point that the command line was going to
use and then did not.

Coverage sees neither. A module with its own tests is covered; a function with
its own test is covered. What is missing is not execution, it is a caller, and
the difference matters because an untested caller is where the interesting
defects are.

A function called only from inside its own module counts as wired: it is a
helper that happens to be spelled without an underscore, and the check that
belongs to it is the naming one. What this check is looking for is a name
nothing anywhere refers to.

Tests count as callers on purpose, but separately. A function only a test
calls is still worth knowing about, so it is reported as a note rather than
passed over in silence.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

from dipcount.tools import source

CHECK = "check_wiring"

EXEMPT: Final[frozenset[str]] = frozenset(
    {
        "main",
        "findings",
    },
)


def _registered(node: ast.FunctionDef) -> bool:
    """Whether a decorator wires this function up somewhere else.

    A command line command is never called by name: the decorator hands it to
    the group, and the group is what gets called. Reporting those as having no
    caller would bury the ones that really have none.
    """
    return any(
        "command" in ast.unparse(one) or "group" in ast.unparse(one) for one in node.decorator_list
    )


def _module_functions(path: Path) -> list[tuple[str, int]]:
    tree = source.parse(path)
    return [
        (node.name, node.lineno)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and source.is_public(node.name)
        and not _registered(node)
    ]


def _names_used(path: Path) -> set[str]:
    tree = source.parse(path)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.ImportFrom):
            out.update(alias.name for alias in node.names)
    return out


def _modules_imported(path: Path) -> set[str]:
    tree = source.parse(path)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
            out.update(f"{node.module}.{alias.name}" for alias in node.names)
    return out


def unimported_modules() -> list[source.Finding]:
    """Every module in the package that nothing else imports."""
    every = source.modules()
    imported: set[str] = set()
    for path in every:
        imported |= _modules_imported(path)
    out: list[source.Finding] = []
    for path in every:
        module = source.dotted(path)
        if path.name == "__init__.py":
            continue
        if module.startswith(("dipcount.tools", "dipcount.cli")):
            continue
        if module not in imported:
            out.append(source.Finding(source.where(path), "nothing in the package imports it"))
    return out


def uncalled_functions() -> tuple[list[source.Finding], list[source.Finding]]:
    """Functions nothing calls, and functions only a test calls."""
    every = source.modules()
    package_names: dict[Path, set[str]] = {one: _names_used(one) for one in every}
    test_names: set[str] = set()
    for one in source.test_modules():
        test_names |= _names_used(one)

    used: set[str] = set()
    for names in package_names.values():
        used |= names

    nowhere: list[source.Finding] = []
    tests_only: list[source.Finding] = []
    for path in every:
        place = source.where(path)
        elsewhere = used
        for name, line in _module_functions(path):
            if name in EXEMPT:
                continue
            if name in elsewhere:
                continue
            if name in test_names:
                tests_only.append(source.Finding(place, f"{name} is only called by a test", line))
            else:
                nowhere.append(source.Finding(place, f"{name} has no caller", line))
    return nowhere, tests_only


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    nowhere, _ = uncalled_functions()
    return unimported_modules() + nowhere


def notes() -> list[source.Finding]:
    """What this check reports without failing on."""
    _, tests_only = uncalled_functions()
    return tests_only


def main() -> None:
    """Run the check."""
    for one in notes():
        print(f"note{one.line_text()}")
    source.run(CHECK, findings(), counted=len(source.modules()))


if __name__ == "__main__":
    main()
