"""Refusals name a clause that exists, and nothing raises a builtin.

The clause check is the one worth having. Every refusal in this package
carries the name of the rule that produced it, and those names are printed in
reports and read by whoever is arguing about a decision. A refusal naming
``label.rates`` when the rule book says ``label.rate`` looks right in the
source, prints something plausible, and cannot be looked up.

The rest is layering again. A ``ValueError`` out of a service says nothing
about the district and cannot be caught by anything that wants to tell a bad
request from a broken book. The one place a builtin is allowed is the sheet
renderer, which is a table and not a rule.

Catching everything is allowed where a comment says why, beside the handler or
on the line above it. There are three places in this package that legitimately
do. What the check refuses is the silent one.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

from dipcount.rules import BY_NAME
from dipcount.tools import source

CHECK = "check_errors"

BUILTINS: Final[frozenset[str]] = frozenset(
    {"ValueError", "TypeError", "KeyError", "RuntimeError", "Exception", "AssertionError"},
)

NAMING: Final[frozenset[str]] = frozenset({"RuleViolation", "LabelViolation", "Refusal"})

ALLOWED_BUILTINS: Final[frozenset[str]] = frozenset({"dipcount.report.sheet"})


def _called(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def raised_builtins() -> list[source.Finding]:
    """Every place the package raises something that is not one of ours."""
    out: list[source.Finding] = []
    for path in source.modules():
        module = source.dotted(path)
        if module in ALLOWED_BUILTINS or module.startswith("dipcount.tools"):
            continue
        for node in ast.walk(source.parse(path)):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            name = _called(node.exc) if isinstance(node.exc, ast.Call) else ""
            if isinstance(node.exc, ast.Name):
                name = node.exc.id
            if name in BUILTINS:
                out.append(source.Finding(source.where(path), f"raises {name}", node.lineno))
    return out


def clause_names(path: Path) -> list[tuple[str, int]]:
    """Every clause name a file passes to a refusal."""
    out: list[tuple[str, int]] = []
    for node in ast.walk(source.parse(path)):
        if not isinstance(node, ast.Call) or _called(node) not in NAMING:
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            out.append((first.value, node.lineno))
    return out


def unknown_clauses() -> list[source.Finding]:
    """Every refusal naming a rule the rule book does not hold."""
    out: list[source.Finding] = []
    for path in source.modules():
        if source.dotted(path).startswith("dipcount.tools"):
            continue
        for name, line in clause_names(path):
            if name not in BY_NAME:
                out.append(source.Finding(source.where(path), f"names the clause {name}", line))
    return out


def broad_excepts() -> list[source.Finding]:
    """Every handler that catches everything without saying why."""
    out: list[source.Finding] = []
    for path in source.modules():
        text = source.source_of(path)
        for node in ast.walk(source.parse(path)):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is None:
                out.append(source.Finding(source.where(path), "catches everything", node.lineno))
                continue
            caught = ast.unparse(node.type)
            if caught in ("Exception", "BaseException"):
                lines = text.splitlines()
                beside = lines[node.lineno - 1]
                above = lines[node.lineno - 2] if node.lineno > 1 else ""
                if "#" not in beside and "#" not in above:
                    out.append(
                        source.Finding(
                            source.where(path),
                            f"catches {caught} without a reason beside it",
                            node.lineno,
                        ),
                    )
    return out


def counted() -> int:
    """How many refusals name a clause."""
    return sum(len(clause_names(one)) for one in source.modules())


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return raised_builtins() + unknown_clauses() + broad_excepts()


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=counted())


if __name__ == "__main__":
    main()
