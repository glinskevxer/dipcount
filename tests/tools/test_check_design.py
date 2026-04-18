from __future__ import annotations

import pytest

from dipcount.tools import check_design


def test_the_package_passes_its_own_check() -> None:
    assert check_design.findings() == []


def test_every_record_is_frozen() -> None:
    assert check_design.mutable_records() == []


def test_nothing_shares_a_mutable_default() -> None:
    assert check_design.shared_defaults() == []


def test_nothing_outside_the_book_uses_any() -> None:
    assert check_design.loose_typing() == []


def test_no_module_is_long_enough_to_be_two() -> None:
    assert check_design.long_modules() == []


def test_no_function_is_long_enough_to_be_two() -> None:
    assert check_design.long_functions() == []


def test_the_builder_is_the_only_record_allowed_to_change() -> None:
    assert frozenset({"Sheet"}) == check_design.BUILDERS


def test_the_row_values_are_the_only_place_any_belongs() -> None:
    assert frozenset({"dipcount.store.book"}) == check_design.ANY_ALLOWED


def test_the_caps_are_where_they_are() -> None:
    assert check_design.LONGEST_FUNCTION == 60
    assert check_design.LONGEST_MODULE == 700


def test_the_package_holds_a_good_many_records() -> None:
    assert check_design.counted() > 30


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_design.main()
    assert raised.value.code == 0
