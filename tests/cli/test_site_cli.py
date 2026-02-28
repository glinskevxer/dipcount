from __future__ import annotations

from tests.cli.conftest import Run


def test_a_site_is_added_under_a_zone(started: Run) -> None:
    result = started(
        "site",
        "add",
        "north",
        "Weller Road basins",
        "--habitat",
        "catch_basin",
        "--extent",
        "14 each",
        "--on",
        "2025-03-01",
    )
    assert "SI-0001" in result.output
    assert "storm drain catch basin" in result.output


def test_the_extent_unit_has_to_suit_the_habitat(started: Run) -> None:
    result = started(
        "site",
        "add",
        "north",
        "Sawyer marsh",
        "--habitat",
        "cattail_marsh",
        "--extent",
        "14 each",
        expect=1,
    )
    assert result.exit_code != 0


def test_an_unknown_habitat_is_refused_by_the_option(started: Run) -> None:
    result = started(
        "site",
        "add",
        "north",
        "Pool",
        "--habitat",
        "swimming_pool",
        "--extent",
        "1 each",
        expect=2,
    )
    assert result.exit_code != 0


def add_two(started: Run) -> None:
    started(
        "site",
        "add",
        "north",
        "Weller Road basins",
        "--habitat",
        "catch_basin",
        "--extent",
        "14 each",
        "--on",
        "2025-03-01",
    )
    started(
        "site",
        "add",
        "south",
        "Sawyer marsh",
        "--habitat",
        "cattail_marsh",
        "--extent",
        "6.5 acre",
        "--on",
        "2025-03-01",
    )


def test_the_list_narrows_by_zone_and_habitat(started: Run) -> None:
    add_two(started)
    assert "2 rows" in started("site", "list").output
    assert "1 row" in started("site", "list", "--zone", "north").output
    assert "1 row" in started("site", "list", "--habitat", "cattail_marsh").output


def test_a_site_is_shown_with_its_trail(started: Run) -> None:
    add_two(started)
    result = started("site", "show", "SI-0001")
    assert "Weller Road basins" in result.output
    assert "listed site" in result.output


def test_a_site_is_retired_and_drops_off_the_open_list(started: Run) -> None:
    add_two(started)
    started("site", "retire", "SI-0001", "--on", "2025-08-01", "--why", "basins rebuilt")
    later = started("site", "list", "--open-on", "2025-09-01")
    assert "1 row" in later.output
    assert "SI-0002" in later.output


def test_a_site_is_remeasured(started: Run) -> None:
    add_two(started)
    result = started("site", "remeasure", "SI-0001", "18 each")
    assert "18 each" in result.output


def test_a_site_is_moved(started: Run) -> None:
    add_two(started)
    result = started("site", "move", "SI-0001", "south")
    assert "ZN-002" in result.output


def test_the_actor_reaches_the_trail(started: Run) -> None:
    started(
        "site",
        "add",
        "north",
        "Weller Road basins",
        "--habitat",
        "catch_basin",
        "--extent",
        "14 each",
        actor="K. Brennaman",
    )
    assert "K. Brennaman" in started("site", "show", "SI-0001").output
