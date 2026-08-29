from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from dipcount import clock
from dipcount.errors import BookError
from dipcount.store import Book, backup, latest, sites, upgrade, zones
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)
AT = clock.moment("2025-06-04 21:30")


@pytest.fixture
def district(book_path: Path) -> Book:
    made = Book.create(book_path)
    upgrade(made)
    zones.add(made, "north")
    sites.add(made, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    return made


def test_a_backup_is_named_for_the_moment_it_was_taken() -> None:
    assert backup.name_for(AT) == "district-20250604-2130.sqlite3"
    assert backup.name_for(AT, "north").startswith("north-")


def test_a_backup_opens_and_counts_what_is_in_it(district: Book, tmp_path: Path) -> None:
    made = backup.take(district, tmp_path / "backups", at=AT)
    district.close()
    assert made.path.name == "district-20250604-2130.sqlite3"
    assert made.sound
    assert made.version == latest()
    assert made.rows > 0
    assert "sound" in made.line()


def test_the_copy_holds_what_the_book_held(district: Book, tmp_path: Path) -> None:
    made = backup.take(district, tmp_path / "backups", at=AT)
    district.close()
    with Book(made.path) as opened:
        assert [one.name for one in sites.all_sites(opened)] == ["Sawyer marsh"]


def test_a_backup_inside_a_grouped_write_is_refused_rather_than_hanging(
    district: Book,
    tmp_path: Path,
) -> None:
    with pytest.raises(BookError, match="grouped write"), district.writing():
        sites.add(district, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
        backup.take(district, tmp_path / "backups", at=AT)
    district.close()


def test_a_backup_after_the_write_has_landed_carries_it(
    district: Book,
    tmp_path: Path,
) -> None:
    with district.writing():
        sites.add(district, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    made = backup.take(district, tmp_path / "backups", at=AT)
    district.close()
    with Book(made.path) as opened:
        assert len(sites.all_sites(opened)) == 2


def test_the_directory_is_made_if_it_is_not_there(district: Book, tmp_path: Path) -> None:
    into = tmp_path / "deep" / "down"
    backup.take(district, into, at=AT)
    district.close()
    assert into.exists()


def test_a_backup_that_is_not_there_cannot_be_verified(tmp_path: Path) -> None:
    with pytest.raises(BookError):
        backup.verify(tmp_path / "nothing.sqlite3")


def test_an_empty_book_backs_up_to_an_unsound_copy(
    book_path: Path,
    tmp_path: Path,
) -> None:
    made = Book.create(book_path)
    try:
        copy = backup.take(made, tmp_path / "backups", at=AT)
    finally:
        made.close()
    assert not copy.sound
    assert "NOT SOUND" in copy.line()


def test_the_backups_in_a_directory_are_listed(district: Book, tmp_path: Path) -> None:
    into = tmp_path / "backups"
    for hour in (20, 21, 22):
        backup.take(district, into, at=clock.moment(f"2025-06-04 {hour}:00"))
    district.close()
    assert [one.name for one in backup.kept(into)] == [
        "district-20250604-2000.sqlite3",
        "district-20250604-2100.sqlite3",
        "district-20250604-2200.sqlite3",
    ]


def test_a_directory_with_nothing_in_it_holds_no_backups(tmp_path: Path) -> None:
    assert backup.kept(tmp_path / "nothing") == []


def test_pruning_keeps_the_newest_few(district: Book, tmp_path: Path) -> None:
    into = tmp_path / "backups"
    for hour in (20, 21, 22, 23):
        backup.take(district, into, at=clock.moment(f"2025-06-04 {hour}:00"))
    district.close()
    gone = backup.prune(into, keep=2)
    assert [one.name for one in gone] == [
        "district-20250604-2000.sqlite3",
        "district-20250604-2100.sqlite3",
    ]
    assert len(backup.kept(into)) == 2


def test_pruning_nothing_leaves_everything(district: Book, tmp_path: Path) -> None:
    into = tmp_path / "backups"
    backup.take(district, into, at=AT)
    district.close()
    assert backup.prune(into, keep=5) == []
    assert len(backup.kept(into)) == 1


def test_a_rota_that_keeps_nothing_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BookError):
        backup.prune(tmp_path, keep=0)
