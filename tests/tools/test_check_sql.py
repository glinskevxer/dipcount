from __future__ import annotations

from pathlib import Path

import pytest

from dipcount.tools import check_sql, source


def test_the_package_passes_its_own_check() -> None:
    assert check_sql.findings() == []


def test_all_the_sql_is_in_the_store() -> None:
    assert check_sql.sql_outside_the_store() == []


def test_nothing_selects_every_column() -> None:
    assert check_sql.select_star() == []


def test_every_table_named_is_one_a_migration_makes() -> None:
    assert check_sql.unknown_tables() == []


def test_the_known_tables_come_off_the_migrations() -> None:
    found = check_sql.known_tables()
    for name in ("site", "trap", "treatment", "run", "bioassay"):
        assert name in found
    assert "sqlite_master" in found


def test_a_query_is_recognised_and_a_sentence_is_not(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\nQ = "SELECT id FROM site"\nT = "a sentence about sites"\n')
    found = check_sql.sql_strings(path)
    assert [text for text, _ in found] == ["SELECT id FROM site"]


def test_a_pragma_is_not_counted_as_a_query(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\nQ = "PRAGMA table_info(site)"\n')
    assert check_sql.sql_strings(path) == []


def test_the_checks_are_left_out_of_their_own_rules() -> None:
    walked = {source.dotted(one) for one in check_sql.package_modules()}
    assert not any(one.startswith("dipcount.tools") for one in walked)
    assert "dipcount.store.sites" in walked


def test_the_package_holds_a_good_many_queries() -> None:
    assert check_sql.counted() > 100


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_sql.main()
    assert raised.value.code == 0
