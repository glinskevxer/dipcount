"""The packaging says the same thing as the code.

Four small things that each cost an afternoon when they go wrong.

The version in ``pyproject.toml`` and the one in ``__init__.py`` have to
agree, because one of them is what pip installs and the other is what
``--version`` prints, and a support call starts with somebody reading the
wrong one out.

Every direct dependency has to be pinned, and every pin has to appear in
``constraints.txt``. A dependency loose in one file and pinned in the other is
a build that passes here and fails on a machine that resolved it a week later.

Every name in an ``__all__`` has to exist. A re-export naming something that
has been renamed is an ImportError for whoever trusted the package surface.

And the console script has to point at something importable, which is the one
of the four that only shows up after installation.
"""

from __future__ import annotations

import ast
import importlib
import re
import tomllib
from pathlib import Path
from typing import Final

from dipcount.tools import source

CHECK = "check_package"

PIN: Final = re.compile(r"^([A-Za-z0-9_.\-]+)==([0-9][^\s;]*)$")


def pyproject() -> dict[str, object]:
    """The parsed project file."""
    return tomllib.loads((source.project_root() / "pyproject.toml").read_text())


def constraints() -> dict[str, str]:
    """Every pin in the constraints file."""
    path = source.project_root() / "constraints.txt"
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        found = PIN.match(stripped)
        if found:
            out[found.group(1).lower().replace("_", "-")] = found.group(2)
    return out


def _declared() -> list[str]:
    data = pyproject()
    project = data.get("project", {})
    assert isinstance(project, dict)
    out = list(project.get("dependencies", []))
    extras = project.get("optional-dependencies", {})
    assert isinstance(extras, dict)
    for group in extras.values():
        out.extend(group)
    return [str(one) for one in out]


def versions_agree() -> list[source.Finding]:
    """Whether the packaged version and the code version are the same."""
    data = pyproject()
    project = data.get("project", {})
    assert isinstance(project, dict)
    packaged = str(project.get("version", ""))
    module = importlib.import_module("dipcount")
    coded = str(module.__version__)
    if packaged != coded:
        return [
            source.Finding(
                "pyproject.toml",
                f"says version {packaged} and the package says {coded}",
            ),
        ]
    return []


def pins() -> list[source.Finding]:
    """Every dependency that is loose, or pinned and not constrained."""
    out: list[source.Finding] = []
    held = constraints()
    for one in _declared():
        found = PIN.match(one)
        if not found:
            out.append(source.Finding("pyproject.toml", f"{one} is not pinned"))
            continue
        name = found.group(1).lower().replace("_", "-")
        if name not in held:
            out.append(source.Finding("constraints.txt", f"does not carry {name}"))
        elif held[name] != found.group(2):
            out.append(
                source.Finding(
                    "constraints.txt",
                    f"pins {name} at {held[name]} and pyproject says {found.group(2)}",
                ),
            )
    return out


def _all_names(path: Path) -> list[str]:
    for node in ast.walk(source.parse(path)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    return [
                        one.value
                        for one in ast.walk(node.value)
                        if isinstance(one, ast.Constant) and isinstance(one.value, str)
                    ]
    return []


def exports() -> list[source.Finding]:
    """Every name a package re-exports that is not there."""
    out: list[source.Finding] = []
    for path in source.modules():
        names = _all_names(path)
        if not names:
            continue
        loaded = importlib.import_module(source.dotted(path))
        for name in names:
            if not hasattr(loaded, name):
                out.append(source.Finding(source.where(path), f"exports {name}, which is missing"))
    return out


def scripts() -> list[source.Finding]:
    """Every console script that does not point at something importable."""
    data = pyproject()
    project = data.get("project", {})
    assert isinstance(project, dict)
    entries = project.get("scripts", {})
    assert isinstance(entries, dict)
    out: list[source.Finding] = []
    for name, target in entries.items():
        module, _, attribute = str(target).partition(":")
        try:
            loaded = importlib.import_module(module)
        except ImportError:
            out.append(source.Finding("pyproject.toml", f"{name} points at {module}"))
            continue
        if not hasattr(loaded, attribute):
            out.append(source.Finding("pyproject.toml", f"{name} wants {target}"))
    return out


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return versions_agree() + pins() + exports() + scripts()


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=len(_declared()))


if __name__ == "__main__":
    main()
