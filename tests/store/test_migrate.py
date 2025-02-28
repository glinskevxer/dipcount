from __future__ import annotations

from pathlib import Path

import pytest

from dipcount.errors import BookError, MigrationError
from dipcount.store import Book
from dipcount.store.migrate import pending, ready, require_ready, upgrade
from dipcount.store.migrations import MIGRATIONS, latest, lock_text

LOCK = Path(__file__).resolve().parents[2] / "migrations.lock"


def test_a_fresh_book_is_at_version_zero(book: Book) -> None:
    assert book.version == 0
    assert not ready(book)


def test_migrating_brings_the_book_to_the_latest(book: Book) -> None:
    ran = upgrade(book)
    assert [step.number for step in ran] == [step.number for step in MIGRATIONS]
    assert book.version == latest()
    assert ready(book)


def test_migrating_twice_does_nothing_the_second_time(book: Book) -> None:
    upgrade(book)
    assert upgrade(book) == []
    assert pending(book) == []


def test_the_steps_make_every_table_the_package_reads(book: Book) -> None:
    upgrade(book)
    made = set(book.tables())
    assert {"audit", "site", "zone", "inspection", "larvae"} <= made


def test_an_unmigrated_book_is_refused(book: Book) -> None:
    with pytest.raises(MigrationError, match="book init"):
        require_ready(book)


def test_a_book_from_the_future_is_refused(book: Book) -> None:
    book.version = latest() + 1
    with pytest.raises(MigrationError, match="only knows"):
        pending(book)


def test_a_half_migrated_book_is_refused(book: Book) -> None:
    if latest() < 2:
        pytest.skip("needs two steps to be half way")
    book.version = latest() - 1
    with pytest.raises(MigrationError):
        require_ready(book)


def test_the_steps_are_numbered_from_one_without_a_gap() -> None:
    assert [step.number for step in MIGRATIONS] == list(range(1, len(MIGRATIONS) + 1))


def test_every_step_has_its_own_name() -> None:
    names = [step.name for step in MIGRATIONS]
    assert len(set(names)) == len(names)


def test_the_lock_file_matches_the_steps() -> None:
    assert LOCK.read_text() == lock_text()


def test_a_digest_moves_when_the_sql_does() -> None:
    first = MIGRATIONS[0]
    changed = type(first)(first.number, first.name, first.sql + "\n-- a comment\n")
    assert changed.digest() != first.digest()


def test_a_failed_step_leaves_the_version_behind(
    book: Book,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = type(MIGRATIONS[0])(1, "broken", "CREATE TABLE oops (")
    monkeypatch.setattr("dipcount.store.migrate.MIGRATIONS", (broken,))
    with pytest.raises(BookError):
        upgrade(book)
    assert book.version == 0
    assert "oops" not in book.tables()
