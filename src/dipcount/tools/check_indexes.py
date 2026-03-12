"""Every foreign key has an index on the side that needs one.

Sqlite indexes the parent of a foreign key, because that side is a primary
key. It does not index the child. So "every treatment of this site" is a table
scan, and it stays a table scan while the table is small enough for nobody to
notice, which is the whole of the first two seasons.

The check builds the schema in an empty book, reads the foreign keys back out
of sqlite rather than out of the migration text, and asks whether each child
column has an index starting with it. Reading it back matters: a migration
that creates a column and a later one that renames the table would otherwise
be checked against something the book does not hold.
"""

from __future__ import annotations

from dataclasses import dataclass

from dipcount.store.book import Book
from dipcount.store.migrate import upgrade
from dipcount.tools import source

CHECK = "check_indexes"


@dataclass(frozen=True)
class Key:
    """One foreign key, from a child column to a parent table."""

    table: str
    column: str
    parent: str


def _built() -> Book:
    book = Book.memory()
    upgrade(book)
    return book


def keys(book: Book) -> list[Key]:
    """Every foreign key the built schema holds."""
    out: list[Key] = []
    for table in book.tables():
        for row in book.all(f"PRAGMA foreign_key_list({table})"):
            out.append(Key(table, str(row["from"]), str(row["table"])))
    return sorted(out, key=lambda one: (one.table, one.column))


def indexed_columns(book: Book, table: str) -> set[str]:
    """Every column an index on a table starts with."""
    out: set[str] = set()
    for row in book.all(f"PRAGMA index_list({table})"):
        name = str(row["name"])
        columns = book.all(f"PRAGMA index_info({name})")
        if columns:
            first = columns[0]["name"]
            if first is not None:
                out.add(str(first))
    return out


def unindexed_keys(book: Book) -> list[source.Finding]:
    """Every foreign key whose child column nothing indexes."""
    out: list[source.Finding] = []
    for key in keys(book):
        if key.column not in indexed_columns(book, key.table):
            out.append(
                source.Finding(
                    "schema",
                    f"{key.table}.{key.column} points at {key.parent} with no index behind it",
                ),
            )
    return out


def indexes(book: Book) -> list[str]:
    """Every index the schema makes, in name order."""
    return book.indexes()


def duplicate_indexes(book: Book) -> list[source.Finding]:
    """Every pair of indexes on one table covering the same columns."""
    seen: dict[tuple[str, tuple[str, ...]], str] = {}
    out: list[source.Finding] = []
    for table in book.tables():
        for row in book.all(f"PRAGMA index_list({table})"):
            name = str(row["name"])
            columns = tuple(str(one["name"]) for one in book.all(f"PRAGMA index_info({name})"))
            key = (table, columns)
            if key in seen:
                out.append(
                    source.Finding("schema", f"{name} covers the same columns as {seen[key]}"),
                )
            else:
                seen[key] = name
    return out


def findings() -> list[source.Finding]:
    """Everything this check objects to."""
    book = _built()
    try:
        return unindexed_keys(book) + duplicate_indexes(book)
    finally:
        book.close()


def counted() -> int:
    """How many foreign keys the schema holds."""
    book = _built()
    try:
        return len(keys(book))
    finally:
        book.close()


def main() -> None:
    """Run the check."""
    source.run(CHECK, findings(), counted=counted())


if __name__ == "__main__":
    main()
