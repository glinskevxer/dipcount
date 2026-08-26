"""What every check needs: finding the source, parsing it, and reporting.

The checks all want the same three things, and the reason they share them
rather than each doing it their own way is that "which files count as the
package" has to be one answer. A check that walks a different set of files
from its neighbours is a check that will one day pass because it missed the
file with the problem in it.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


def package_root() -> Path:
    """The directory holding the package source."""
    return Path(__file__).resolve().parent.parent


def project_root() -> Path:
    """The checkout root, which holds ``pyproject.toml``."""
    return package_root().parent.parent


def modules(*, under: str = "") -> list[Path]:
    """Every source file in the package, in path order."""
    root = package_root() / under if under else package_root()
    return sorted(one for one in root.rglob("*.py") if "__pycache__" not in one.parts)


def test_modules() -> list[Path]:
    """Every test file, in path order."""
    root = project_root() / "tests"
    return sorted(one for one in root.rglob("*.py") if "__pycache__" not in one.parts)


def dotted(path: Path) -> str:
    """The import name of a source file.

    A path from outside the package comes back as its own stem rather than
    raising. The checks are given made up files by their own tests, and a
    helper that throws on one of those makes the test about the helper.
    """
    try:
        relative = path.relative_to(package_root().parent).with_suffix("")
    except ValueError:
        return path.stem
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def parse(path: Path) -> ast.Module:
    """The syntax tree of one file."""
    return ast.parse(path.read_text(), filename=str(path))


def source_of(path: Path) -> str:
    """The text of one file."""
    return path.read_text()


def is_public(name: str) -> bool:
    """Whether a name is part of the package's surface."""
    return not name.startswith("_")


Definition = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


def walk_definitions(tree: ast.Module) -> list[Definition]:
    """Every module, class and function definition in a tree, outermost first."""
    out: list[Definition] = [tree]
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            out.append(node)
    return out


def name_of(node: ast.AST) -> str:
    """What a definition is called, or ``module`` for a whole file."""
    if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
        return node.name
    return "module"


def line_of(node: ast.AST) -> int:
    """Which line a definition starts on."""
    return getattr(node, "lineno", 1)


@dataclass(frozen=True)
class Finding:
    """One thing a check objects to."""

    where: str
    what: str
    line: int = 0

    def line_text(self) -> str:
        """One line for the check's output."""
        place = f"{self.where}:{self.line}" if self.line else self.where
        return f"  {place}  {self.what}"


def report(check: str, findings: list[Finding], *, counted: int = 0) -> int:
    """Print what a check found and give the exit status it should use."""
    if not findings:
        tail = f" ({counted} checked)" if counted else ""
        print(f"{check}: ok{tail}")
        return 0
    print(f"{check}: {len(findings)} finding{'' if len(findings) == 1 else 's'}")
    for one in findings:
        print(one.line_text())
    return 1


def run(check: str, findings: list[Finding], *, counted: int = 0) -> None:
    """Report and leave the process with the right status."""
    sys.exit(report(check, findings, counted=counted))


def where(path: Path) -> str:
    """A path as it should be printed, relative to the checkout."""
    try:
        return str(path.relative_to(project_root()))
    except ValueError:
        return str(path)
