from __future__ import annotations

import pytest

from dipcount.rules import BY_NAME
from dipcount.tools import check_errors, source


def test_the_package_passes_its_own_check() -> None:
    assert check_errors.findings() == []


def test_nothing_raises_a_builtin() -> None:
    assert check_errors.raised_builtins() == []


def test_every_refusal_names_a_clause_the_rule_book_holds() -> None:
    assert check_errors.unknown_clauses() == []


def test_no_handler_catches_everything_in_silence() -> None:
    assert check_errors.broad_excepts() == []


def test_the_clause_names_are_read_off_the_refusals() -> None:
    path = source.package_root() / "service" / "larvicide.py"
    found = [name for name, _ in check_errors.clause_names(path)]
    assert "label.rate" in found
    assert "label.season" in found
    for name in found:
        assert name in BY_NAME


def test_the_four_clauses_the_check_found_missing_are_written_down() -> None:
    for name in ("pool.jar", "product.withdrawn", "trap.retired", "weather.station"):
        assert name in BY_NAME


def test_the_sheet_renderer_is_the_only_place_a_builtin_is_allowed() -> None:
    assert frozenset({"dipcount.report.sheet"}) == check_errors.ALLOWED_BUILTINS


def test_a_good_many_refusals_name_a_clause() -> None:
    assert check_errors.counted() > 40


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_errors.main()
    assert raised.value.code == 0
