from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from dipcount.cli import options
from dipcount.errors import BookError, NotFound
from dipcount.store import Book, upgrade, zones


@pytest.fixture
def desk(tmp_path: Path) -> options.Desk:
    path = tmp_path / "district.sqlite3"
    made = Book.create(path)
    try:
        upgrade(made)
        zones.add(made, "north")
    finally:
        made.close()
    return options.Desk(path=path, actor="office")


def test_a_desk_opens_the_book_and_closes_it(desk: options.Desk) -> None:
    with desk.book() as opened:
        assert opened.version > 0
    with pytest.raises(BookError):
        opened.count("zone")


def test_the_book_closes_even_when_the_command_fails(desk: options.Desk) -> None:
    with pytest.raises(ValueError, match="stop"), desk.book() as opened:
        assert opened.version > 0
        raise ValueError("stop")
    with pytest.raises(BookError):
        opened.count("zone")


def test_a_book_that_is_not_there_is_refused(tmp_path: Path) -> None:
    made = options.Desk(path=tmp_path / "nothing.sqlite3", actor="office")
    with pytest.raises(BookError), made.book() as opened:
        opened.count("zone")


def test_a_new_book_is_made_if_it_is_not_there(tmp_path: Path) -> None:
    made = options.Desk(path=tmp_path / "fresh.sqlite3", actor="office")
    with made.new_book() as opened:
        assert opened.version == 0
    assert (tmp_path / "fresh.sqlite3").exists()


def test_a_zone_option_that_was_not_given_is_nothing(desk: options.Desk) -> None:
    with desk.book() as opened:
        assert options.zone_id(opened, None) is None


def test_a_zone_option_resolves_to_an_id(desk: options.Desk) -> None:
    with desk.book() as opened:
        assert options.zone_id(opened, "north") == "ZN-001"
        assert options.zone_id(opened, "ZN-001") == "ZN-001"


def test_a_zone_that_is_not_there_is_refused(desk: options.Desk) -> None:
    with desk.book() as opened, pytest.raises(NotFound):
        options.zone_id(opened, "east")


def test_a_day_falls_back_to_today() -> None:
    assert options.day_or_today("2025-06-04").isoformat() == "2025-06-04"
    assert options.day_or_today(None) is not None


def test_a_moment_falls_back_to_now() -> None:
    assert options.moment_or_now("2025-06-04 09:00").hour == 9
    assert options.moment_or_now(None).tzinfo is not None


def test_a_quantity_is_read_off_the_option() -> None:
    assert str(options.read_quantity("6.5 acre")) == "6.5 acre"


def test_the_desk_is_frozen(desk: options.Desk) -> None:
    with pytest.raises(FrozenInstanceError):
        desk.actor = "somebody else"  # type: ignore[misc]
