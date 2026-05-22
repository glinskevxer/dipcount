from __future__ import annotations

import click
import pytest

from dipcount.cli.main import cli
from dipcount.tools import check_readme


def test_the_readme_passes_its_own_check() -> None:
    assert check_readme.findings() == []


def test_every_command_in_the_readme_resolves() -> None:
    assert check_readme.bad_commands() == []


def test_every_group_is_mentioned() -> None:
    assert check_readme.unmentioned_groups() == []


def test_the_expected_sections_are_there() -> None:
    assert check_readme.sections() == []


def test_the_readme_shows_a_good_many_commands() -> None:
    assert len(check_readme.commands()) > 25


def test_the_global_options_are_taken_off_before_resolving() -> None:
    words = ["--book", "district.sqlite3", "zone", "add", "north"]
    assert check_readme._strip_globals(words) == ["zone", "add", "north"]


def test_a_command_that_is_not_there_is_found() -> None:
    found, why = check_readme._resolve(["zone", "nonsense"])
    assert found is None
    assert "not a command of zone" in why


def test_a_line_that_stops_at_a_group_is_found() -> None:
    found, why = check_readme._resolve(["zone"])
    assert found is None
    assert "stops at a group" in why


def test_a_real_command_resolves_to_the_command() -> None:
    found, why = check_readme._resolve(["zone", "add", "north"])
    assert isinstance(found, click.Command)
    assert why == ""


def test_the_option_names_come_off_the_command() -> None:
    zone = cli.commands["zone"]
    assert isinstance(zone, click.Group)
    names = check_readme._option_names(zone.commands["add"])
    assert "--supervisor" in names


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_readme.main()
    assert raised.value.code == 0
