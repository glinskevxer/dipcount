"""All the SQL is in the store, and none of it selects everything.

Two rules, and the second one is the one people argue about.

SQL outside ``dipcount.store`` means a service or a command has reached past
the layer that owns the tables. It works until the schema moves, at which
point the migration that should have been one file is a search across the
package.

``SELECT *`` means the code takes whatever columns happen to be there, in
whatever order they happen to be in. Adding a column to a table then changes
the shape of every row a reader gets back, and a reader that indexes by
position starts returning the wrong field without an error anywhere.

The check also looks for table names that no migration creates, which catches
a typo in a query that would otherwise wait for the code path to be run.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

from dipcount.store.migrations import MIGRATIONS
from dipcount.tools import source

CHECK = "check_sql"

_KEYWORDS: Final = re.compile(
    r"\b(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE)\b",
    re.IGNORECASE,
)
_TABLES: Final = re.compile(
    r"\b(?:FROM|INTO|UPDATE|JOIN)\s+([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
_STAR: Final = re.compile(r"SELECT\s+\*", re.IGNORECASE)
_PRAGMA: Final = re.compile(r"^\s*PRAGMA\b", re.IGNORECASE)

ALLOWED_TABLES: Final[frozenset[str]] = frozenset({"sqlite_master", "sqlite_sequence"})


def known_tables() -> set[str]:
    """Every table any migration creates."""
    out: set[str] = set()
    for step in MIGRATIONS:
        out.update(re.findall(r"CREATE TABLE (\w+)", step.sql))
    return out | ALLOWED_TABLES


def _strings(tree: ast.Module) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((node.value, node.lineno))
    return out


def sql_strings(path: Path) -> list[tuple[str, int]]:
    """Every string in a file that reads as SQL."""
    return [
        (text, line)
        for text, line in _strings(source.parse(path))
        if _KEYWORDS.search(text) and not _PRAGMA.match(text)
    ]


def package_modules() -> list[Path]:
    """Every module a query could legitimately live in.

    The checks themselves are left out. They quote SQL in their own prose to
    say what they object to, and a check that fails on its own explanation is
    a check nobody keeps.
    """
    return [one for one in source.modules() if not source.dotted(one).startswith("dipcount.tools")]


def sql_outside_the_store() -> list[source.Finding]:
    """Every query written somewhere other than the store."""
    out: list[source.Finding] = []
    for path in package_modules():
        module = source.dotted(path)
        if module.startswith("dipcount.store"):
            continue
        for _, line in sql_strings(path):
            out.append(source.Finding(source.where(path), "writes SQL outside the store", line))
    return out


def select_star() -> list[source.Finding]:
    """Every query that takes whatever columns happen to be there."""
    out: list[source.Finding] = []
    for path in package_modules():
        for text, line in sql_strings(path):
            if _STAR.search(text):
                out.append(source.Finding(source.where(path), "selects every column", line))
    return out


def unknown_tables() -> list[source.Finding]:
    """Every query naming a table no migration creates."""
    tables = known_tables()
    out: list[source.Finding] = []
    for path in source.modules(under="store"):
        if path.name == "migrations.py":
            continue
        for text, line in sql_strings(path):
            for name in _TABLES.findall(text):
                if name.lower() not in tables:
                    out.append(
                        source.Finding(source.where(path), f"names the table {name}", line),
                    )
    return out


def counted() -> int:
    """How many queries the package holds."""
    return sum(len(sql_strings(one)) for one in package_modules())


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    return sql_outside_the_store() + select_star() + unknown_tables()


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=counted())


if __name__ == "__main__":
    main()
