from __future__ import annotations

from dipcount.cli import zone as zone_commands
from tests.cli.conftest import Run


def test_the_group_holds_the_zone_commands() -> None:
    assert set(zone_commands.zone.commands) == {"add", "list", "show"}


def test_a_zone_is_added_and_listed(started: Run) -> None:
    result = started("zone", "list")
    assert "north" in result.output
    assert "R. Vandeburg" in result.output
    assert "2 rows" in result.output


def test_a_zone_is_shown(started: Run) -> None:
    result = started("zone", "show", "north")
    assert "ZN-001" in result.output


def test_a_zone_name_is_not_reused(started: Run) -> None:
    result = started("zone", "add", "north", expect=1)
    assert result.exit_code != 0
