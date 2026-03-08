from __future__ import annotations

import click
import pytest

from dipcount.tools import check_cli


def test_the_program_passes_its_own_check() -> None:
    assert check_cli.findings() == []


def test_every_group_that_exists_can_be_typed() -> None:
    assert check_cli.unregistered() == []


def test_every_command_says_what_it_does() -> None:
    assert check_cli.commands_without_help() == []


def test_every_option_says_what_it_is_for() -> None:
    assert check_cli.options_without_help() == []


def test_the_groups_are_the_ones_on_the_main_command() -> None:
    found = check_cli.groups()
    for name in ("site", "dip", "trap", "pool", "treat", "spray", "report"):
        assert name in found
        assert isinstance(found[name], click.Group)


def test_every_defined_group_is_registered() -> None:
    defined = set(check_cli.defined_groups())
    assert defined <= set(check_cli.groups())


def test_the_program_is_counted() -> None:
    groups, commands = check_cli.counted()
    assert groups > 10
    assert commands > 60


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_cli.main()
    assert raised.value.code == 0
