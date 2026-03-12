from __future__ import annotations

import pytest

from dipcount.store.migrations import MIGRATIONS, lock_text
from dipcount.tools import check_migrations


def test_the_package_passes_its_own_check() -> None:
    assert check_migrations.findings() == []


def test_the_lock_file_matches_the_steps() -> None:
    assert check_migrations.lock_matches() == []
    assert check_migrations.lock_path().read_text() == lock_text()


def test_the_steps_are_numbered_without_a_gap() -> None:
    assert check_migrations.numbering() == []


def test_no_step_is_empty() -> None:
    assert check_migrations.empty_steps() == []


def test_every_step_runs_against_an_empty_book() -> None:
    assert check_migrations.steps_run() == []


def test_an_edited_step_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    first = MIGRATIONS[0]
    changed = type(first)(first.number, first.name, first.sql + "\n-- a comment\n")
    monkeypatch.setattr(
        "dipcount.store.migrations.MIGRATIONS",
        (changed, *MIGRATIONS[1:]),
    )
    monkeypatch.setattr("dipcount.tools.check_migrations.MIGRATIONS", (changed, *MIGRATIONS[1:]))
    found = check_migrations.lock_matches()
    assert found
    assert "line 2" in found[0].what


def test_a_broken_step_stops_the_build(monkeypatch: pytest.MonkeyPatch) -> None:
    broken = type(MIGRATIONS[0])(1, "broken", "CREATE TABLE oops (")
    monkeypatch.setattr("dipcount.tools.check_migrations.MIGRATIONS", (broken,))
    found = check_migrations.steps_run()
    assert found
    assert "step 1 failed" in found[0].what


def test_a_gap_in_the_numbering_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    skipped = type(MIGRATIONS[0])(4, "skipped", "CREATE TABLE t (a INTEGER)")
    monkeypatch.setattr("dipcount.tools.check_migrations.MIGRATIONS", (skipped,))
    found = check_migrations.numbering()
    assert found


def test_the_lock_file_can_be_written_back() -> None:
    path = check_migrations.write_lock()
    assert path.read_text() == lock_text()


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_migrations.main()
    assert raised.value.code == 0
