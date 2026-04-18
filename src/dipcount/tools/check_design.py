"""The shapes this package keeps to, checked rather than remembered.

Records are frozen. A record that can be edited in place is a record two
callers can be looking at while one of them changes it, and every bug that
comes out of that is found weeks later in something that never touched the
record at all. The exception is a builder: a sheet is filled a row at a time
and then printed, and freezing it would mean rebuilding it on every row.

Defaults are not shared. A list or a dict written as a default argument is one
object for the life of the process, and appending to it in one call changes
what the next caller gets.

And ``Any`` is a hole. There is one place it belongs, which is the row values
coming back out of sqlite, because the database really can hand back anything.
Everywhere else it means somebody stopped describing the shape.
"""

from __future__ import annotations

import ast
from typing import Final

from dipcount.tools import source

CHECK = "check_design"

ANY_ALLOWED: Final[frozenset[str]] = frozenset({"dipcount.store.book"})
BUILDERS: Final[frozenset[str]] = frozenset({"Sheet"})
LONGEST_MODULE: Final = 700
LONGEST_FUNCTION: Final = 60


def _decorator_names(node: ast.ClassDef) -> list[str]:
    return [ast.unparse(one) for one in node.decorator_list]


def mutable_records() -> list[source.Finding]:
    """Every dataclass that is not frozen."""
    out: list[source.Finding] = []
    for path in source.modules():
        for node in ast.walk(source.parse(path)):
            if not isinstance(node, ast.ClassDef):
                continue
            names = _decorator_names(node)
            if not any("dataclass" in one for one in names):
                continue
            if node.name in BUILDERS:
                continue
            if not any("frozen=True" in one for one in names):
                out.append(
                    source.Finding(
                        source.where(path),
                        f"{node.name} is a dataclass that is not frozen",
                        node.lineno,
                    ),
                )
    return out


def shared_defaults() -> list[source.Finding]:
    """Every default argument that is one object for the whole process."""
    out: list[source.Finding] = []
    for path in source.modules():
        for node in ast.walk(source.parse(path)):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for default in [*node.args.defaults, *node.args.kw_defaults]:
                if isinstance(default, ast.List | ast.Dict | ast.Set):
                    out.append(
                        source.Finding(
                            source.where(path),
                            f"{node.name} has a mutable default",
                            node.lineno,
                        ),
                    )
    return out


def loose_typing() -> list[source.Finding]:
    """Every use of ``Any`` outside the one place it belongs."""
    out: list[source.Finding] = []
    for path in source.modules():
        module = source.dotted(path)
        if module in ANY_ALLOWED or module.startswith("dipcount.tools"):
            continue
        for node in ast.walk(source.parse(path)):
            if isinstance(node, ast.Name) and node.id == "Any":
                out.append(source.Finding(source.where(path), "uses Any", node.lineno))
    return out


def long_modules() -> list[source.Finding]:
    """Every module long enough to be two modules."""
    out: list[source.Finding] = []
    for path in source.modules():
        lines = len(source.source_of(path).splitlines())
        if lines > LONGEST_MODULE:
            out.append(source.Finding(source.where(path), f"is {lines} lines long"))
    return out


def long_functions() -> list[source.Finding]:
    """Every function long enough to be two functions."""
    out: list[source.Finding] = []
    for path in source.modules():
        text = source.source_of(path).splitlines()
        for node in ast.walk(source.parse(path)):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            end = node.end_lineno or node.lineno
            length = end - node.lineno + 1
            if length > LONGEST_FUNCTION and not _is_command(node, text):
                out.append(
                    source.Finding(
                        source.where(path),
                        f"{node.name} is {length} lines long",
                        node.lineno,
                    ),
                )
    return out


def _is_command(node: ast.FunctionDef | ast.AsyncFunctionDef, text: list[str]) -> bool:
    """Whether a function is a command whose length is mostly its options."""
    return any("click" in ast.unparse(one) for one in node.decorator_list) or any(
        "@click" in text[line] for line in range(max(node.lineno - 20, 0), node.lineno)
    )


def counted() -> int:
    """How many records the package holds."""
    total = 0
    for path in source.modules():
        for node in ast.walk(source.parse(path)):
            if isinstance(node, ast.ClassDef) and any(
                "dataclass" in ast.unparse(one) for one in node.decorator_list
            ):
                total += 1
    return total


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return (
        mutable_records() + shared_defaults() + loose_typing() + long_modules() + long_functions()
    )


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=counted())


if __name__ == "__main__":
    main()
