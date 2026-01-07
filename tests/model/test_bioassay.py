from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount.errors import UsageError
from dipcount.model.bioassay import (
    COLONY,
    CONTROL,
    FIELD,
    POSSIBLE,
    RESISTANT,
    SUSCEPTIBLE,
    VOID,
    Bioassay,
    Reading,
    abbott,
)

ON = dt.date(2025, 8, 12)


def an_assay(**changes: object) -> Bioassay:
    fields: dict[str, object] = {
        "id": "BA-250812-01",
        "active": "permethrin",
        "species": "CXPP",
        "source": FIELD,
        "on": ON,
        "tested_by": "K. Brennaman",
        "dose_ug": 43.0,
        "diagnostic": 30,
    }
    fields.update(changes)
    return Bioassay(**fields)  # type: ignore[arg-type]


def bottles(knocked: int, total: int = 25, minute: int = 30, count: int = 4) -> tuple[Reading, ...]:
    return tuple(Reading(str(one + 1), minute, knocked, total) for one in range(count))


def test_abbott_asks_what_share_of_the_survivors_died() -> None:
    assert round(abbott(Decimal(90), Decimal(10)), 2) == Decimal("88.89")
    assert abbott(Decimal(90), Decimal(0)) == Decimal(90)


def test_correcting_always_moves_the_figure_down() -> None:
    for control in (Decimal(1), Decimal(5), Decimal(12)):
        assert abbott(Decimal(92), control) < Decimal(92)


def test_a_control_that_killed_everything_corrects_nothing() -> None:
    with pytest.raises(UsageError):
        abbott(Decimal(90), Decimal(100))


def test_a_reading_is_a_count_out_of_a_bottle() -> None:
    with pytest.raises(UsageError):
        Reading("1", 30, 30, 25)
    with pytest.raises(UsageError):
        Reading("1", 30, -1, 25)
    with pytest.raises(UsageError):
        Reading("1", 30, 4, 0)
    with pytest.raises(UsageError):
        Reading(" ", 30, 4, 25)
    with pytest.raises(UsageError):
        Reading("1", -1, 4, 25)


def test_the_control_bottle_is_marked_as_one() -> None:
    assert Reading(CONTROL, 30, 1, 25).is_control
    assert not Reading("1", 30, 1, 25).is_control


def test_an_assay_needs_a_dose_a_time_and_a_real_species() -> None:
    with pytest.raises(UsageError):
        an_assay(dose_ug=0.0)
    with pytest.raises(UsageError):
        an_assay(diagnostic=0)
    with pytest.raises(Exception, match="species"):
        an_assay(species="ZZZZ")
    with pytest.raises(UsageError):
        an_assay(source="somewhere")


def test_an_assay_carries_its_own_day_in_its_id() -> None:
    with pytest.raises(UsageError, match="does not carry"):
        an_assay(on=dt.date(2025, 8, 13))


def test_one_bottle_is_not_read_twice_at_one_minute() -> None:
    with pytest.raises(UsageError, match="twice"):
        an_assay(readings=(Reading("1", 30, 20, 25), Reading("1", 30, 22, 25)))


def test_a_flat_population_is_susceptible() -> None:
    made = an_assay(readings=bottles(25))
    assert made.mortality() == Decimal(100)
    assert made.verdict() == SUSCEPTIBLE


def test_survivors_at_the_diagnostic_time_are_the_finding() -> None:
    made = an_assay(readings=bottles(20))
    assert made.mortality() == Decimal(80)
    assert made.verdict() == RESISTANT


def test_the_band_between_is_possible_resistance() -> None:
    made = an_assay(readings=bottles(23))
    assert made.mortality() == Decimal(92)
    assert made.verdict() == POSSIBLE


def test_the_boundaries_fall_where_the_thresholds_say() -> None:
    assert an_assay(readings=bottles(49, total=50)).verdict() == SUSCEPTIBLE
    assert an_assay(readings=bottles(45, total=50)).verdict() == POSSIBLE
    assert an_assay(readings=bottles(44, total=50)).verdict() == RESISTANT


def test_only_the_diagnostic_minute_decides() -> None:
    early = bottles(10, minute=15)
    late = bottles(25, minute=30)
    made = an_assay(readings=(*early, *late))
    assert made.minutes() == [15, 30]
    assert made.treated_share(15) == Decimal(40)
    assert made.verdict() == SUSCEPTIBLE


def test_a_clean_control_leaves_the_figure_alone() -> None:
    made = an_assay(readings=(*bottles(23), Reading(CONTROL, 30, 0, 25)))
    assert not made.corrected()
    assert made.mortality() == Decimal(92)


def test_a_little_handling_death_takes_the_figure_down() -> None:
    made = an_assay(readings=(*bottles(23), Reading(CONTROL, 30, 2, 25)))
    assert made.corrected()
    found = made.mortality()
    assert found is not None
    assert found < Decimal(92)


def test_the_correction_can_move_the_verdict() -> None:
    plain = an_assay(readings=(*bottles(45, total=50), Reading(CONTROL, 30, 0, 50)))
    corrected = an_assay(readings=(*bottles(45, total=50), Reading(CONTROL, 30, 8, 50)))
    assert plain.verdict() == POSSIBLE
    assert corrected.verdict() == RESISTANT


def test_too_much_handling_death_voids_the_whole_thing() -> None:
    made = an_assay(readings=(*bottles(23), Reading(CONTROL, 30, 6, 25)))
    assert made.mortality() is None
    assert made.verdict() == VOID
    assert "no reading" in made.line()


def test_the_void_ceiling_and_the_correction_floor_are_different_places() -> None:
    at_floor = an_assay(readings=(*bottles(23), Reading(CONTROL, 30, 5, 100)))
    over_ceiling = an_assay(readings=(*bottles(23), Reading(CONTROL, 30, 21, 100)))
    assert at_floor.corrected()
    assert at_floor.verdict() != VOID
    assert over_ceiling.verdict() == VOID


def test_an_assay_with_nothing_read_at_the_diagnostic_time(  # says nothing rather than zero
) -> None:
    made = an_assay(readings=bottles(25, minute=15))
    assert made.mortality() is None
    assert made.verdict() == VOID


def test_a_colony_strain_is_the_thing_field_results_are_read_against() -> None:
    made = an_assay(source=COLONY, readings=bottles(25))
    assert made.source == COLONY
    assert made.verdict() == SUSCEPTIBLE


def test_the_line_carries_the_dose_and_the_time() -> None:
    line = an_assay(readings=bottles(25)).line()
    assert "43 ug" in line
    assert "at 30 min" in line
    assert "susceptible" in line
