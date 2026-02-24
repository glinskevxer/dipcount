from __future__ import annotations

import pytest

from dipcount.tools import check_wiring


def test_the_package_passes_its_own_check() -> None:
    assert check_wiring.findings() == []


def test_every_module_has_an_importer() -> None:
    assert check_wiring.unimported_modules() == []


def test_the_notes_are_reported_without_failing() -> None:
    nowhere, tests_only = check_wiring.uncalled_functions()
    assert nowhere == []
    assert check_wiring.notes() == tests_only


def test_something_only_a_test_calls_is_a_note_and_not_a_failure() -> None:
    notes = check_wiring.notes()
    assert notes
    for one in notes:
        assert "only called by a test" in one.what


def test_a_command_registered_by_a_decorator_is_not_reported() -> None:
    named = {one.what for one in check_wiring.notes()}
    assert "list_them has no caller" not in named
    assert "init has no caller" not in named


def test_the_helpers_that_had_no_caller_are_gone() -> None:
    from dipcount.cli import options

    for name in ("read_day", "read_moment", "today_option", "one_of"):
        assert not hasattr(options, name)


def test_the_service_entry_points_that_had_no_caller_are_gone() -> None:
    from dipcount.service import adulticide, virus

    assert not hasattr(virus, "rate_for")
    assert not hasattr(adulticide, "unregistered_blocks")


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_wiring.main()
    assert raised.value.code == 0
