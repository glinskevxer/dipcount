from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock, formulary, rules
from dipcount.model.applicator import AQUATIC, CERTIFIED, CORE, PUBLIC_HEALTH
from dipcount.model.bioassay import CONTROL, FIELD, RESISTANT, SUSCEPTIBLE, Reading
from dipcount.service import larvicide, resistance
from dipcount.store import Book, applicators, bioassays, inventory, sites, upgrade, zones
from dipcount.units import quantity

ON = dt.date(2025, 8, 12)
LISTED = dt.date(2025, 3, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    sites.add(book, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    sites.add(book, "north", "Kettle bottom", "floodplain", quantity("40 acre"), LISTED)
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Bactilore WSP", "24W-0801", quantity("500 each"), LISTED)
    inventory.receive(book, "Hesper 30 briquets", "24H-0110", quantity("400 each"), LISTED)
    inventory.receive(book, "Sphaerix WG", "24S-0042", quantity("200 lb"), LISTED)
    applicators.add(
        book,
        "K. Brennaman",
        "PA-44192",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH, AQUATIC),
        dt.date(2024, 3, 1),
        dt.date(2027, 3, 1),
    )
    return book


def assay(
    book: Book,
    active: str,
    code: str,
    knocked: int,
    on: dt.date = ON,
    control: int | None = None,
) -> str:
    readings = [Reading(str(one + 1), 30, knocked, 25) for one in range(4)]
    if control is not None:
        readings.append(Reading(CONTROL, 30, control, 25))
    made = bioassays.start(
        book,
        active,
        code,
        FIELD,
        on,
        "K. Brennaman",
        43.0,
        30,
        zone_id="north",
        readings=readings,
    )
    return made.id


def test_nothing_assayed_reads_as_untested(district: Book) -> None:
    found = resistance.standing(district, "S-methoprene", "CXPP", ON)
    assert found.verdict == "untested"
    assert not found.suspect
    assert "untested" in found.line()


def test_a_flat_assay_is_susceptible(district: Book) -> None:
    assay(district, "S-methoprene", "CXPP", 25)
    found = resistance.standing(district, "S-methoprene", "CXPP", ON)
    assert found.verdict == SUSCEPTIBLE
    assert not found.suspect


def test_survivors_make_the_active_suspect(district: Book) -> None:
    assay(district, "S-methoprene", "CXPP", 20)
    found = resistance.standing(district, "S-methoprene", "CXPP", ON)
    assert found.verdict == RESISTANT
    assert found.suspect


def test_a_void_run_is_not_a_finding(district: Book) -> None:
    assay(district, "S-methoprene", "CXPP", 25, on=dt.date(2025, 6, 1))
    assay(district, "S-methoprene", "CXPP", 20, control=8)
    found = resistance.standing(district, "S-methoprene", "CXPP", ON)
    assert found.verdict == SUSCEPTIBLE
    assert found.assay is not None
    assert found.assay.on == dt.date(2025, 6, 1)


def test_a_finding_from_three_seasons_ago_is_history(district: Book) -> None:
    assay(district, "S-methoprene", "CXPP", 20, on=dt.date(2022, 8, 12))
    found = resistance.standing(district, "S-methoprene", "CXPP", ON)
    assert found.verdict == RESISTANT
    assert found.stale
    assert not found.suspect
    assert "stale" in found.line()


def test_a_finding_inside_the_shelf_life_still_counts(district: Book) -> None:
    assay(district, "S-methoprene", "CXPP", 20, on=dt.date(2024, 8, 12))
    found = resistance.standing(district, "S-methoprene", "CXPP", ON)
    assert not found.stale
    assert found.suspect


def test_the_board_covers_every_pair_run(district: Book) -> None:
    assay(district, "S-methoprene", "CXPP", 20)
    assay(district, "permethrin", "CXPP", 25)
    found = resistance.board(district, ON)
    assert [(one.active, one.species) for one in found] == [
        ("S-methoprene", "CXPP"),
        ("permethrin", "CXPP"),
    ]


def test_the_suspect_actives_are_the_ones_in_doubt(district: Book) -> None:
    assay(district, "S-methoprene", "CXPP", 20)
    assay(district, "permethrin", "CXPP", 25)
    assert resistance.suspect_actives(district, ON) == ["S-methoprene"]


def test_a_finding_bears_on_a_site_that_makes_that_species(district: Book) -> None:
    assay(district, "S-methoprene", "CXPP", 20)
    warned = resistance.warn(district, "SI-0001", "Hesper 30 briquets", ON)
    assert warned is not None
    assert warned.rule == "resistance.species"


def test_a_finding_about_another_species_says_nothing_here(district: Book) -> None:
    assay(district, "S-methoprene", "AEVX", 20)
    assert resistance.warn(district, "SI-0001", "Hesper 30 briquets", ON) is None


def test_a_finding_about_this_water_but_a_different_active(district: Book) -> None:
    assay(district, "permethrin", "CXPP", 20)
    assert resistance.warn(district, "SI-0001", "Hesper 30 briquets", ON) is None


def test_only_the_findings_that_exist_come_back(district: Book) -> None:
    assay(district, "S-methoprene", "CXPP", 20)
    found = resistance.bearing_on(district, "SI-0001", "Hesper 30 briquets", ON)
    assert [one.species for one in found] == ["CXPP"]


def test_the_modes_of_action_group_the_actives() -> None:
    assert rules.mode_of("Bacillus sphaericus") == rules.mode_of(
        "Bacillus thuringiensis subspecies israelensis",
    )
    assert rules.mode_of("permethrin") != rules.mode_of("S-methoprene")
    assert "pyrethroid" in rules.modes()
    assert "sumithrin" in rules.actives_in("pyrethroid")


def test_two_bacterials_running_are_one_mode_of_action(district: Book) -> None:
    for day in (4, 12):
        larvicide.treat(
            district,
            "AP-001",
            "SI-0001",
            "LT-0001" if day == 4 else "LT-0003",
            clock.moment(f"2025-06-{day:02d} 10:40"),
        )
    modes = resistance.rotation(district, "SI-0001", ON)
    assert modes == ["bacterial toxin", "bacterial toxin"]


def test_a_third_application_in_one_mode_is_a_rotation_warning(district: Book) -> None:
    for day in (4, 12):
        larvicide.treat(
            district,
            "AP-001",
            "SI-0001",
            "LT-0001" if day == 4 else "LT-0003",
            clock.moment(f"2025-06-{day:02d} 10:40"),
        )
    warned = resistance.rotation_warning(district, "SI-0001", "Bactilore WSP", ON)
    assert warned is not None
    assert warned.rule == "resistance.rotation"


def test_changing_mode_clears_the_rotation(district: Book) -> None:
    for day in (4, 12):
        larvicide.treat(
            district,
            "AP-001",
            "SI-0001",
            "LT-0001" if day == 4 else "LT-0003",
            clock.moment(f"2025-06-{day:02d} 10:40"),
        )
    assert resistance.rotation_warning(district, "SI-0001", "Hesper 30 briquets", ON) is None


def test_a_site_never_treated_has_no_rotation(district: Book) -> None:
    assert resistance.rotation(district, "SI-0002", ON) == []
    assert resistance.rotation_warning(district, "SI-0002", "Bactilore G", ON) is None


def test_the_alternatives_are_in_another_mode(district: Book) -> None:
    found = resistance.alternatives(district, "SI-0001", "Bactilore WSP", ON)
    modes = {rules.mode_of(one.active) for one in found}
    assert rules.mode_of("Bacillus thuringiensis subspecies israelensis") not in modes
    assert "Hesper 30 briquets" in [one.name for one in found]


def test_the_coverage_says_what_each_mode_has_been_run_on(district: Book) -> None:
    assay(district, "S-methoprene", "CXPP", 25)
    found = resistance.coverage(district, ON)
    assert found["growth regulator"] == ["CXPP"]
    assert found["pyrethroid"] == []


def test_what_has_never_been_run_at_a_site_is_listed(district: Book) -> None:
    found = resistance.untested_here(district, "SI-0001", ON)
    assert ("S-methoprene", "CXPP") in found
    assay(district, "S-methoprene", "CXPP", 25)
    after = resistance.untested_here(district, "SI-0001", ON)
    assert ("S-methoprene", "CXPP") not in after


def test_the_species_behind_a_finding_can_be_looked_up() -> None:
    assert resistance.species_of("CXPP").binomial == "Culex pipiens"
