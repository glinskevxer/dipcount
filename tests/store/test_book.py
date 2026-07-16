from __future__ import annotations

from pathlib import Path

import pytest

from dipcount.errors import BookError
from dipcount.store import Book
from dipcount.store.book import MEMORY, _split_statements


def test_opening_a_book_that_is_not_there_is_refused(book_path: Path) -> None:
    with pytest.raises(BookError):
        Book(book_path)


def test_creating_makes_the_file(book_path: Path) -> None:
    with Book.create(book_path) as made:
        made.run("CREATE TABLE t (a INTEGER)")
    assert book_path.exists()


def test_a_write_survives_closing_the_connection(book_path: Path) -> None:
    with Book.create(book_path) as first:
        first.run("CREATE TABLE t (a INTEGER)")
        first.run("INSERT INTO t VALUES (7)")
    with Book(book_path) as second:
        assert second.value("SELECT a FROM t") == 7


def test_a_grouped_write_rolls_back_together(book: Book) -> None:
    book.run("CREATE TABLE t (a INTEGER)")
    with pytest.raises(ValueError, match="stop"), book.writing():
        book.run("INSERT INTO t VALUES (1)")
        book.run("INSERT INTO t VALUES (2)")
        raise ValueError("stop")
    assert book.count("t") == 0


def test_a_grouped_write_that_finishes_lands(book: Book) -> None:
    book.run("CREATE TABLE t (a INTEGER)")
    with book.writing():
        book.run("INSERT INTO t VALUES (1)")
    assert book.count("t") == 1


def test_grouped_writes_nest_as_savepoints(book: Book) -> None:
    book.run("CREATE TABLE t (a INTEGER)")
    with book.writing():
        book.run("INSERT INTO t VALUES (1)")
        with pytest.raises(ValueError, match="inner"), book.writing():
            book.run("INSERT INTO t VALUES (2)")
            raise ValueError("inner")
        book.run("INSERT INTO t VALUES (3)")
    assert sorted(row["a"] for row in book.all("SELECT a FROM t")) == [1, 3]


def test_a_script_does_not_commit_the_open_savepoint(book: Book) -> None:
    book.run("CREATE TABLE t (a INTEGER)")
    with pytest.raises(ValueError, match="stop"), book.writing():
        book.script("INSERT INTO t VALUES (1); INSERT INTO t VALUES (2);")
        raise ValueError("stop")
    assert book.count("t") == 0


def test_a_script_keeps_semicolons_inside_strings(book: Book) -> None:
    book.run("CREATE TABLE t (a TEXT)")
    book.script("INSERT INTO t VALUES ('one; two'); INSERT INTO t VALUES ('three');")
    assert sorted(row["a"] for row in book.all("SELECT a FROM t")) == ["one; two", "three"]


def test_splitting_drops_comments_and_blank_pieces() -> None:
    pieces = _split_statements("-- a note\nSELECT 1;\n\n-- another\nSELECT 2;\n")
    assert pieces == ["SELECT 1", "SELECT 2"]


def test_splitting_keeps_a_doubled_quote() -> None:
    pieces = _split_statements("INSERT INTO t VALUES ('it''s here; really');")
    assert pieces == ["INSERT INTO t VALUES ('it''s here; really')"]


def test_bad_sql_comes_back_as_a_book_error(book: Book) -> None:
    with pytest.raises(BookError, match="no such table"):
        book.run("SELECT * FROM absent")


def test_one_statement_runs_over_many_rows(book: Book) -> None:
    book.run("CREATE TABLE t (a INTEGER)")
    book.run_many("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
    assert book.count("t") == 3
    with pytest.raises(BookError):
        book.run_many("INSERT INTO absent VALUES (?)", [(1,)])


def test_counting_under_a_condition(book: Book) -> None:
    book.run("CREATE TABLE t (a INTEGER)")
    book.run_many("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
    assert book.count("t", "a > ?", (1,)) == 2


def test_foreign_keys_are_on(book: Book) -> None:
    book.script(
        "CREATE TABLE parent (id INTEGER PRIMARY KEY);"
        "CREATE TABLE child (id INTEGER PRIMARY KEY,"
        " parent INTEGER REFERENCES parent(id));",
    )
    with pytest.raises(BookError):
        book.run("INSERT INTO child VALUES (1, 99)")


def test_the_shape_of_the_book_can_be_read_back(book: Book) -> None:
    book.script(
        "CREATE TABLE site (id TEXT PRIMARY KEY, name TEXT);"
        "CREATE INDEX site_by_name ON site (name);",
    )
    assert book.tables() == ["site"]
    assert book.indexes() == ["site_by_name"]
    assert book.columns("site") == ["id", "name"]


def test_the_version_is_read_and_written(book: Book) -> None:
    assert book.version == 0
    book.version = 4
    assert book.version == 4


def test_an_empty_query_gives_nothing(book: Book) -> None:
    book.run("CREATE TABLE t (a INTEGER)")
    assert book.one("SELECT a FROM t") is None
    assert book.value("SELECT a FROM t") is None
    assert book.all("SELECT a FROM t") == []


def test_a_fresh_book_passes_its_own_integrity_check(book: Book) -> None:
    assert book.integrity() == "ok"


def test_a_book_in_a_read_only_directory_refuses_cleanly(tmp_path: Path) -> None:
    into = tmp_path / "locked"
    into.mkdir()
    into.chmod(0o500)
    try:
        with pytest.raises(BookError):
            Book.create(into / "district.sqlite3")
    finally:
        into.chmod(0o700)


def test_every_book_a_test_opens_is_closed(book: Book) -> None:
    book.run("CREATE TABLE t (a INTEGER)")
    book.close()
    with pytest.raises(BookError):
        book.count("t")


def test_closing_twice_is_not_an_error(book: Book) -> None:
    book.close()
    book.close()
    assert book.path == MEMORY
