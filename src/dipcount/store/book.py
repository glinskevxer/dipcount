"""The sqlite file the district keeps its records in, and how it is opened.

Three decisions are worth stating because each of them was a defect first.

The connection runs in autocommit. Python's default leaves an implicit
transaction open around anything that writes, and nothing commits it until
somebody says so, so a season's work can sit in a connection and vanish when
the process ends. Every test still passes in that state, because a test reads
back through the same connection that wrote. Writes that have to land together
say so with :meth:`Book.writing`, which is a real savepoint.

``executescript`` commits whatever transaction is open before it runs, which
silently throws away a savepoint a migration is standing inside. So
:meth:`Book.script` splits the statements and runs them one at a time.

And a book is closed. An unclosed sqlite connection is silence on 3.12 and a
``ResourceWarning`` on 3.13, blamed on whichever test the collector happened
to run next.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from dipcount import rows
from dipcount.errors import BookError

Row = rows.Row
Params = Sequence[Any] | dict[str, Any]

MEMORY = ":memory:"


def _split_statements(text: str) -> list[str]:
    """Split a script into statements, leaving string literals alone."""
    out: list[str] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote is not None:
            current.append(char)
            if char == quote:
                if index + 1 < len(text) and text[index + 1] == quote:
                    current.append(text[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in ("'", '"'):
            quote = char
            current.append(char)
        elif char == "-" and text[index : index + 2] == "--":
            while index < len(text) and text[index] != "\n":
                index += 1
            current.append("\n")
        elif char == ";":
            out.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    out.append("".join(current))
    return [piece.strip() for piece in out if piece.strip()]


class Book:
    """An open connection to the district's records."""

    def __init__(self, path: str | Path, *, create: bool = False) -> None:
        self.path = MEMORY if str(path) == MEMORY else Path(path)
        if isinstance(self.path, Path) and not create and not self.path.exists():
            raise BookError(f"there is no book at {self.path}")
        target = MEMORY if self.path == MEMORY else str(self.path)
        self._db = sqlite3.connect(target, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA busy_timeout = 4000")
        self._depth = 0

    @classmethod
    def create(cls, path: str | Path) -> Self:
        """Open a book, making the file if it is not there yet."""
        return cls(path, create=True)

    @classmethod
    def memory(cls) -> Self:
        """A book that lives only as long as the process, for tests."""
        return cls(MEMORY, create=True)

    def close(self) -> None:
        """Close the connection. Calling twice is not an error."""
        self._db.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()

    @contextmanager
    def writing(self) -> Iterator[Book]:
        """Group writes so they land together or not at all.

        Nesting is a savepoint, so a service can call another service that
        also writes without either of them needing to know.
        """
        name = f"sp{self._depth}"
        self._depth += 1
        self._db.execute(f"SAVEPOINT {name}")
        try:
            yield self
        except BaseException:
            self._db.execute(f"ROLLBACK TO {name}")
            self._db.execute(f"RELEASE {name}")
            self._depth -= 1
            raise
        self._db.execute(f"RELEASE {name}")
        self._depth -= 1

    def run(self, sql: str, params: Params = ()) -> sqlite3.Cursor:
        """Run one statement."""
        try:
            return self._db.execute(sql, params)
        except sqlite3.Error as exc:
            raise BookError(f"{exc} while running: {sql.strip().splitlines()[0]}") from exc

    def run_many(self, sql: str, rows: Sequence[Params]) -> None:
        """Run one statement over many rows."""
        try:
            self._db.executemany(sql, rows)
        except sqlite3.Error as exc:
            raise BookError(f"{exc} while running: {sql.strip().splitlines()[0]}") from exc

    def script(self, text: str) -> None:
        """Run a script one statement at a time, inside whatever is open."""
        for statement in _split_statements(text):
            self.run(statement)

    def one(self, sql: str, params: Params = ()) -> Row | None:
        """The first row of a query, or nothing."""
        cursor = self.run(sql, params)
        row: Row | None = cursor.fetchone()
        return row

    def all(self, sql: str, params: Params = ()) -> list[Row]:
        """Every row of a query."""
        return list(self.run(sql, params).fetchall())

    def value(self, sql: str, params: Params = ()) -> Any:
        """The first column of the first row, or nothing."""
        row = self.one(sql, params)
        return None if row is None else row[0]

    def count(self, table: str, where: str = "", params: Params = ()) -> int:
        """How many rows a table holds, optionally under a condition."""
        clause = f" WHERE {where}" if where else ""
        found = self.value(f"SELECT count(*) FROM {table}{clause}", params)
        return int(found or 0)

    def tables(self) -> list[str]:
        """Every table in the book, in name order."""
        rows = self.all(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name",
        )
        return [str(row["name"]) for row in rows]

    def indexes(self) -> list[str]:
        """Every index this package made, in name order."""
        rows = self.all(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name",
        )
        return [str(row["name"]) for row in rows]

    def columns(self, table: str) -> list[str]:
        """The column names of a table, in declaration order."""
        return [str(row["name"]) for row in self.all(f"PRAGMA table_info({table})")]

    @property
    def version(self) -> int:
        """The schema version the book is migrated to."""
        return int(self.value("PRAGMA user_version") or 0)

    @version.setter
    def version(self, number: int) -> None:
        """Write the schema version the book is migrated to."""
        self.run(f"PRAGMA user_version = {int(number)}")

    def integrity(self) -> str:
        """What sqlite says about the file, which is ``ok`` when it is fine."""
        return str(self.value("PRAGMA integrity_check"))
