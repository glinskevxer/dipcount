from __future__ import annotations

import pytest

from dipcount.store import Book, upgrade
from dipcount.tools import check_indexes


@pytest.fixture
def built(book: Book) -> Book:
    upgrade(book)
    return book


def test_the_schema_passes_its_own_check() -> None:
    assert check_indexes.findings() == []


def test_every_foreign_key_has_an_index_behind_it(built: Book) -> None:
    assert check_indexes.unindexed_keys(built) == []


def test_no_two_indexes_cover_the_same_columns(built: Book) -> None:
    assert check_indexes.duplicate_indexes(built) == []


def test_the_keys_are_read_out_of_the_built_book(built: Book) -> None:
    found = check_indexes.keys(built)
    assert any(one.table == "site" and one.parent == "zone" for one in found)
    assert any(one.table == "treatment" and one.parent == "lot" for one in found)


def test_the_three_that_were_missing_are_indexed_now(built: Book) -> None:
    assert "supervisor" in check_indexes.indexed_columns(built, "applicator")
    assert "product" in check_indexes.indexed_columns(built, "run")
    assert "inspection" in check_indexes.indexed_columns(built, "treatment")


def test_a_table_with_no_index_reports_none(built: Book) -> None:
    built.run("CREATE TABLE plain (a INTEGER)")
    assert check_indexes.indexed_columns(built, "plain") == set()


def test_the_index_list_is_the_one_the_book_holds(built: Book) -> None:
    assert check_indexes.indexes(built) == built.indexes()


def test_the_schema_holds_a_good_many_keys() -> None:
    assert check_indexes.counted() > 20


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_indexes.main()
    assert raised.value.code == 0
