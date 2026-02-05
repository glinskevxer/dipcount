"""Imports only go one way.

The layering is model, store, service, report, command line, and underneath
all of them a handful of leaf modules that know about units and dates and the
rule book. Every import has to point at something at the same level or lower.

The direction that goes wrong quietly is a model reaching into the store. It
works, the tests pass, and what has happened is that the records can no longer
be built or reasoned about without a database open. This check is here because
that import was in this package for weeks before anybody noticed.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

from dipcount.tools import source

CHECK = "check_layers"

RANKS: Final[dict[str, int]] = {
    "errors": 0,
    "rows": 1,
    "clock": 1,
    "units": 1,
    "ids": 1,
    "species": 2,
    "habitat": 3,
    "estimate": 3,
    "glossary": 3,
    "rules": 4,
    "model": 5,
    "store": 6,
    "service": 7,
    "formulary": 7,
    "report": 8,
    "cli": 9,
    "tools": 10,
}


def layer_of(module: str) -> int | None:
    """Which layer a dotted module name belongs to."""
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "dipcount":
        return None
    return RANKS.get(parts[1])


def _imports(tree: ast.Module) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.append((node.module, node.lineno))
    return out


def findings_in(module: str, text: str, place: str) -> list[source.Finding]:
    """Every import in one file that points at a layer above it.

    This takes the dotted name rather than working it out from a path, so a
    test can hand it a made up module without putting a file inside the
    package to do it.
    """
    mine = layer_of(module)
    if mine is None:
        return []
    out: list[source.Finding] = []
    for imported, line in _imports(ast.parse(text)):
        theirs = layer_of(imported)
        if theirs is not None and theirs > mine:
            out.append(
                source.Finding(place, f"imports {imported}, which is a layer above", line),
            )
    return out


def _findings_for(path: Path) -> list[source.Finding]:
    return findings_in(source.dotted(path), source.source_of(path), source.where(path))


def unknown_layers() -> list[source.Finding]:
    """Every module the layer table has no rank for."""
    out: list[source.Finding] = []
    for path in source.modules():
        module = source.dotted(path)
        if module == "dipcount":
            continue
        if layer_of(module) is None:
            out.append(source.Finding(source.where(path), "is not in the layer table"))
    return out


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    out = unknown_layers()
    for path in source.modules():
        out.extend(_findings_for(path))
    return out


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=len(source.modules()))


if __name__ == "__main__":
    main()
