"""Bringing a book up to the schema this code expects."""

from __future__ import annotations

from dipcount.errors import MigrationError
from dipcount.store.book import Book
from dipcount.store.migrations import MIGRATIONS, Migration, latest


def pending(book: Book) -> list[Migration]:
    """The steps this book has not run yet."""
    at = book.version
    if at > latest():
        raise MigrationError(
            f"the book is at schema {at} and this code only knows {latest()}",
        )
    return [step for step in MIGRATIONS if step.number > at]


def upgrade(book: Book) -> list[Migration]:
    """Run every pending step, and say which ones ran.

    Each step runs inside its own savepoint, so a step that fails halfway
    leaves the book at the version before it rather than somewhere between.
    """
    ran: list[Migration] = []
    for step in pending(book):
        if step.number != book.version + 1:
            raise MigrationError(
                f"migration {step.number} cannot follow schema {book.version}",
            )
        with book.writing():
            book.script(step.sql)
            book.version = step.number
        ran.append(step)
    return ran


def ready(book: Book) -> bool:
    """Whether the book is at the version this code expects."""
    return book.version == latest()


def require_ready(book: Book) -> None:
    """Refuse to work against a book that is not migrated."""
    if book.version == 0:
        raise MigrationError("this book has no schema: run book init first")
    if not ready(book):
        raise MigrationError(
            f"the book is at schema {book.version} and this code expects {latest()}",
        )
