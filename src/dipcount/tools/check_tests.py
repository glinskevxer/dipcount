"""Every module has a test that is about it.

Coverage answers a different question. A module can be executed to ninety per
cent by tests of the thing above it and still be a module nobody has written a
test about, and the difference shows up the first time somebody changes it: a
suite that exercises a module incidentally will go green on a change that
breaks it in every way that matters to a caller nobody wrote yet.

So this asks the narrower question. Is there a test file that names this
module. Not "was this line run", but "did somebody sit down and think about
this".

It also refuses a test file with no assertions in it, which sounds like it
could not happen and has happened twice: a test that builds a fixture, calls
the thing, and never says what it expected.
"""

from __future__ import annotations

import ast
from typing import Final

from dipcount.tools import source

CHECK = "check_tests"

EXEMPT: Final[frozenset[str]] = frozenset(
    {
        "dipcount",
        "dipcount.model",
        "dipcount.store",
        "dipcount.service",
        "dipcount.report",
        "dipcount.cli",
        "dipcount.tools",
    },
)

MINIMUM_ASSERTIONS: Final = 1


def _named_in_tests() -> set[str]:
    """Every dotted module name any test file mentions."""
    out: set[str] = set()
    for path in source.test_modules():
        tree = source.parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                out.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                out.add(node.module)
                out.update(f"{node.module}.{alias.name}" for alias in node.names)
    return out


def _test_file_names() -> set[str]:
    """Every test file stem, so a command module can be matched by name."""
    return {one.stem for one in source.test_modules()}


def untested_modules() -> list[source.Finding]:
    """Every module no test file names, or has a file of its own for.

    A command line module is never imported by a test: the tests drive the
    whole program through one entry point. So those are matched by file name
    instead, which is also the convention that makes a command test easy to
    find.
    """
    named = _named_in_tests()
    files = _test_file_names()
    out: list[source.Finding] = []
    for path in source.modules():
        module = source.dotted(path)
        if module in EXEMPT or path.name == "__init__.py":
            continue
        if module in named:
            continue
        if module.startswith("dipcount.cli."):
            wanted = {f"test_{path.stem}_cli", f"test_{path.stem}"}
            if wanted & files:
                continue
            out.append(
                source.Finding(source.where(path), f"no test file called test_{path.stem}_cli"),
            )
            continue
        out.append(source.Finding(source.where(path), "no test names it"))
    return out


def _tests_in(tree: ast.Module) -> list[ast.FunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]


def _assertions(node: ast.FunctionDef) -> int:
    count = 0
    for inner in ast.walk(node):
        if isinstance(inner, ast.Assert) or (
            isinstance(inner, ast.withitem) and "raises" in ast.unparse(inner.context_expr)
        ):
            count += 1
    return count


def silent_tests() -> list[source.Finding]:
    """Every test that never says what it expected."""
    out: list[source.Finding] = []
    for path in source.test_modules():
        place = source.where(path)
        for node in _tests_in(source.parse(path)):
            if _assertions(node) < MINIMUM_ASSERTIONS:
                out.append(
                    source.Finding(place, f"{node.name} asserts nothing", node.lineno),
                )
    return out


def counted() -> tuple[int, int]:
    """How many test files and test functions there are."""
    files = source.test_modules()
    total = sum(len(_tests_in(source.parse(one))) for one in files)
    return len(files), total


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return untested_modules() + silent_tests()


def main() -> None:
    """Run the check."""
    files, tests = counted()
    print(f"{CHECK}: {files} test files, {tests} tests")
    source.run(CHECK, findings(), counted=len(source.modules()))


if __name__ == "__main__":
    main()
