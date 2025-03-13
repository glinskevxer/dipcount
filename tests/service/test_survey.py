from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock
from dipcount.model.inspection import Inspection, Tally
from dipcount.model.site import Site
from dipcount.service import survey
from dipcount.store import Book, upgrade, zones
from dipcount.store import sites as site_store
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)
AT = clock.moment("2025-06-04 09:15")


def a_site(habitat: str = "catch_basin", extent: str = "14 each") -> Site:
    return Site(
        id="SI-0001",
        zone="ZN-001",
        name="Weller Road basins",
        habitat=habitat,
        extent=quantity(extent),
        listed_on=LISTED,
    )


def an_inspection(**changes: object) -> Inspection:
    fields: dict[str, object] = {
        "id": "IN-250604-01",
        "site": "SI-0001",
        "at": AT,
        "inspector": "K. Brennaman",
        "water": True,
        "dips": 10,
    }
    fields.update(changes)
    return Inspection(**fields)  # type: ignore[arg-type]


def test_a_dry_site_needs_nothing_and_keeps_its_interval() -> None:
    found = survey.assess(a_site(), an_inspection(water=False, dips=0))
    assert found.verdict == survey.DRY
    assert found.reasons == ("larval.dry",)
    assert found.next_visit == dt.date(2025, 6, 25)
    assert not found.treatable


def test_nothing_in_the_dipper_is_nothing_to_do() -> None:
    found = survey.assess(a_site(), an_inspection())
    assert found.verdict == survey.NOTHING
    assert found.per_dip == 0


def test_a_count_over_the_figure_is_a_treatment() -> None:
    found = survey.assess(a_site(), an_inspection(tallies=(Tally("", "2", 8),)))
    assert found.verdict == survey.TREAT
    assert found.per_dip == Decimal("0.8")
    assert found.threshold == Decimal("0.5")
    assert "larval.threshold" in found.reasons
    assert found.treatable


def test_a_count_under_the_figure_is_not() -> None:
    found = survey.assess(a_site(), an_inspection(tallies=(Tally("", "2", 4),)))
    assert found.verdict == survey.NOTHING
    assert found.per_dip == Decimal("0.4")


def test_a_vector_in_the_sample_halves_the_figure_it_is_measured_against() -> None:
    plain = survey.assess(a_site(), an_inspection(tallies=(Tally("AEVX", "2", 4),)))
    vector = survey.assess(a_site(), an_inspection(tallies=(Tally("CXPP", "2", 4),)))
    assert plain.verdict == survey.NOTHING
    assert vector.verdict == survey.TREAT
    assert vector.threshold == Decimal("0.25")
    assert "larval.vector" in vector.reasons


def test_the_vector_clause_is_named_even_when_nothing_is_treated() -> None:
    found = survey.assess(a_site(), an_inspection(tallies=(Tally("CXPP", "2", 2),)))
    assert found.verdict == survey.NOTHING
    assert found.reasons == ("larval.vector",)


def test_late_instars_make_a_treatment_urgent() -> None:
    found = survey.assess(
        a_site(),
        an_inspection(tallies=(Tally("", "1", 2), Tally("", "4", 18))),
    )
    assert found.verdict == survey.URGENT
    assert found.urgent
    assert "larval.late" in found.reasons


def test_a_brood_that_is_mostly_pupae_is_past_treating() -> None:
    found = survey.assess(
        a_site(),
        an_inspection(tallies=(Tally("", "4", 20), Tally("", "P", 40))),
    )
    assert found.verdict == survey.PAST
    assert not found.treatable
    assert "larval.pupal" in found.reasons
    assert found.next_visit == dt.date(2025, 6, 7)


def test_two_larvae_and_two_pupae_is_not_a_brood_at_all() -> None:
    found = survey.assess(
        a_site(),
        an_inspection(dips=40, tallies=(Tally("", "2", 2), Tally("", "P", 2))),
    )
    assert found.verdict == survey.NOTHING
    assert "larval.pupal" not in found.reasons


def test_the_pupal_stop_uses_the_halved_figure_when_a_vector_is_there() -> None:
    tallies = (Tally("CXPP", "4", 3), Tally("CXPP", "P", 4))
    found = survey.assess(a_site(), an_inspection(dips=20, tallies=tallies))
    assert found.verdict == survey.PAST


def test_the_same_sample_without_a_vector_is_under_everything() -> None:
    tallies = (Tally("AEVX", "4", 3), Tally("AEVX", "P", 4))
    found = survey.assess(a_site(), an_inspection(dips=20, tallies=tallies))
    assert found.verdict == survey.NOTHING


def test_rafts_alone_bring_the_visit_forward_without_a_treatment() -> None:
    found = survey.assess(a_site(), an_inspection(tallies=(Tally("CXPP", "R", 6),)))
    assert found.verdict == survey.WATCH
    assert found.next_visit == dt.date(2025, 6, 8)
    assert "larval.raft" in found.reasons


def test_rafts_with_larvae_over_the_figure_are_a_treatment() -> None:
    found = survey.assess(
        a_site(),
        an_inspection(tallies=(Tally("CXPP", "R", 6), Tally("CXPP", "2", 6))),
    )
    assert found.verdict == survey.TREAT


def test_the_habitat_moves_both_the_figure_and_the_interval() -> None:
    marsh = a_site("cattail_marsh", "6 acre")
    pile = a_site("tyre_pile", "40 each")
    sample = an_inspection(tallies=(Tally("", "2", 3),))
    assert survey.assess(marsh, sample).verdict == survey.NOTHING
    assert survey.assess(pile, sample).verdict == survey.TREAT


def test_the_reasons_read_back_as_sentences() -> None:
    found = survey.assess(a_site(), an_inspection(tallies=(Tally("CXPP", "2", 8),)))
    text = " ".join(found.why())
    assert "halved" in text
    assert "larvae per dip" in text


def test_a_finding_prints_a_round_sheet_line() -> None:
    found = survey.assess(a_site(), an_inspection(tallies=(Tally("", "2", 8),)))
    assert "SI-0001" in found.line()
    assert "0.80/dip against 0.50" in found.line()


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    site_store.add(book, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    site_store.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    return book


def test_inspecting_writes_the_record_and_the_trail(district: Book) -> None:
    made, found = survey.inspect(
        district,
        "K. Brennaman",
        "SI-0001",
        AT,
        dips=10,
        tallies=(Tally("CXPP", "2", 8),),
    )
    assert made.id == "IN-250604-01"
    assert found.verdict == survey.TREAT
    lines = survey.trail_for(district, "SI-0001")
    assert len(lines) == 1
    assert "treat" in lines[0].detail


def test_judging_again_from_the_book_gives_the_same_answer(district: Book) -> None:
    made, found = survey.inspect(
        district,
        "K. Brennaman",
        "SI-0001",
        AT,
        dips=10,
        tallies=(Tally("CXPP", "2", 8),),
    )
    assert survey.judge(district, made.id) == found


def test_a_site_never_visited_is_due_from_the_day_it_was_listed(district: Book) -> None:
    waiting = survey.due(district, dt.date(2025, 6, 4))
    assert [site.id for site, _ in waiting] == ["SI-0001", "SI-0002"]


def test_a_visited_site_drops_out_until_its_interval_is_up(district: Book) -> None:
    survey.inspect(district, "K. B", "SI-0001", AT, dips=10)
    waiting = survey.due(district, dt.date(2025, 6, 10))
    assert [site.id for site, _ in waiting] == ["SI-0002"]
    # SI-0002 has never been visited, so it has been due since it was listed
    # and sorts ahead of the one that came back round on its interval.
    later = survey.due(district, dt.date(2025, 6, 26))
    assert [site.id for site, _ in later] == ["SI-0002", "SI-0001"]


def test_rafts_bring_the_site_back_sooner_than_the_interval(district: Book) -> None:
    survey.inspect(
        district,
        "K. B",
        "SI-0001",
        AT,
        dips=10,
        tallies=(Tally("CXPP", "R", 4),),
    )
    assert "SI-0001" in [site.id for site, _ in survey.due(district, dt.date(2025, 6, 9))]


def test_the_round_is_narrowed_to_one_zone(district: Book) -> None:
    zones.add(district, "south")
    site_store.add(district, "south", "Dunlap", "catch_basin", quantity("9 each"), LISTED)
    waiting = survey.due(district, dt.date(2025, 6, 4), zone_id="ZN-002")
    assert [site.id for site, _ in waiting] == ["SI-0003"]


def test_a_retired_site_leaves_the_round(district: Book) -> None:
    site_store.retire(district, "SI-0002", dt.date(2025, 5, 1))
    waiting = survey.due(district, dt.date(2025, 6, 4))
    assert [site.id for site, _ in waiting] == ["SI-0001"]


def test_the_history_of_a_site_is_judged_again(district: Book) -> None:
    survey.inspect(district, "K. B", "SI-0001", AT, dips=10, tallies=(Tally("", "2", 8),))
    survey.inspect(
        district,
        "K. B",
        "SI-0001",
        clock.moment("2025-06-26 09:00"),
        water=False,
    )
    verdicts = [one.verdict for one in survey.history(district, "SI-0001")]
    assert verdicts == [survey.TREAT, survey.DRY]
