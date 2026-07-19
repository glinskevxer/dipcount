"""The seams between the services, which no single test looks at.

Each service has its own tests and they all pass. What none of them asks is
whether the answers agree: whether what came off the shelf is what the
treatments say went on, whether the return adds up to what the book holds,
whether the audit trail has a line for everything that happened. Those are the
questions that catch a service that is right on its own and wrong beside the
one next to it.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock, estimate, formulary, species
from dipcount.model.applicator import AQUATIC, CERTIFIED, CORE, PUBLIC_HEALTH
from dipcount.model.block import PHONE
from dipcount.model.exclusion import APIARY
from dipcount.model.inspection import Tally
from dipcount.model.pool import POSITIVE
from dipcount.model.trap import Catch
from dipcount.report import use_report, weekly
from dipcount.service import adulticide, larvicide, survey, trapping, virus
from dipcount.store import (
    Book,
    applicators,
    audit,
    blocks,
    exclusions,
    inventory,
    pools,
    products,
    runs,
    sites,
    traps,
    treatments,
    upgrade,
    zones,
)
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)


@pytest.fixture
def season(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    sites.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    sites.add(book, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    blocks.add(book, "north", "Ardmore east grid", 640.0, LISTED)
    exclusions.add(book, APIARY, "Ferrand apiary", "north", LISTED, contact="M. Ferrand")
    blocks.link(book, "BK-0001", "EX-0001")
    traps.add(book, "north", "Ambrose gravid 1", "gravid", LISTED)
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Bactilore G", "24G-1187", quantity("400 lb"), LISTED)
    inventory.receive(book, "Kestrel ULV", "25K-0114", quantity("30 gal"), LISTED)
    applicators.add(
        book,
        "K. Brennaman",
        "PA-44192",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH, AQUATIC),
        dt.date(2024, 3, 1),
        dt.date(2027, 3, 1),
    )
    for day in (4, 12, 20):
        survey.inspect(
            book,
            "K. Brennaman",
            "SI-0001",
            clock.moment(f"2025-06-{day:02d} 09:00"),
            dips=10,
            tallies=(Tally("CXPP", "2", 12),),
        )
        larvicide.treat(
            book,
            "AP-001",
            "SI-0001",
            "LT-0001",
            clock.moment(f"2025-06-{day:02d} 10:40"),
        )
    jar = trapping.collect(
        book,
        "D. Uzoma",
        "TR-0001",
        clock.moment("2025-06-03 16:30"),
        clock.moment("2025-06-04 08:15"),
        catches=(Catch("CXPP", "F", 120), Catch("AEVX", "F", 300)),
    )
    for outcome in (POSITIVE, "negative"):
        pool = pools.submit(book, jar.id, "CXPP", 50, dt.date(2025, 6, 5))
        pools.report(book, pool.id, species.WNV, outcome, dt.date(2025, 6, 9))
    blocks.give(
        book,
        "EX-0001",
        "BK-0001",
        clock.moment("2025-07-08 09:00"),
        clock.moment("2025-07-10 20:00"),
        clock.moment("2025-07-11 02:00"),
        PHONE,
        "T. Okwuosa",
    )
    adulticide.spray(
        book,
        "AP-001",
        "BK-0001",
        "LT-0002",
        clock.moment("2025-07-10 21:10"),
        clock.moment("2025-07-10 22:40"),
        quantity("1.4 gal"),
        wind_mph=4.5,
        temperature=74.0,
    )
    return book


def test_what_came_off_the_shelf_is_what_went_on_the_ground(season: Book) -> None:
    applied = treatments.for_lot(season, "LT-0001")
    total = applied[0].amount
    for one in applied[1:]:
        total = total + one.amount
    drawn = inventory.stock(season, "LT-0001").drawn
    assert drawn == total


def test_the_fogging_lot_agrees_with_the_run(season: Book) -> None:
    made = runs.for_lot(season, "LT-0002")
    assert len(made) == 1
    assert inventory.stock(season, "LT-0002").drawn == made[0].amount


def test_every_draw_names_the_record_it_belongs_to(season: Book) -> None:
    for one in inventory.draws(season, "LT-0001"):
        assert one.reference.startswith("TX-")
        assert treatments.get(season, one.reference)


def test_the_return_adds_up_to_what_the_book_holds(season: Book) -> None:
    filed = use_report.season(season, 2025)
    applied = treatments.between(season, dt.date(2025, 1, 1), dt.date(2025, 12, 31))
    made = runs.between(season, dt.date(2025, 1, 1), dt.date(2025, 12, 31))
    assert len(filed.filed) == len(applied) + len(made)


def test_the_product_totals_on_the_return_match_the_treatments(season: Book) -> None:
    filed = use_report.season(season, 2025)
    applied = treatments.for_lot(season, "LT-0001")
    total = applied[0].amount
    for one in applied[1:]:
        total = total + one.amount
    assert filed.by_product()["Bactilore G"] == total


def test_the_weekly_report_counts_the_week_the_book_holds(season: Book) -> None:
    found = weekly.weekly(season, 2025, 23)
    assert found.work.treatments == len(treatments.in_week(season, 2025, 23))
    assert found.larval.visits == 1


def test_the_audit_trail_has_a_line_for_every_treatment(season: Book) -> None:
    lines = [one for one in audit.about(season, "SI-0001") if one.action == "treated"]
    assert len(lines) == len(treatments.for_site(season, "SI-0001"))


def test_the_audit_trail_has_a_line_for_the_run(season: Book) -> None:
    lines = [one for one in audit.about(season, "BK-0001") if one.action == "sprayed"]
    assert len(lines) == 1


def test_no_site_took_more_than_its_season_cap(season: Book) -> None:
    site = sites.get(season, "SI-0001")
    product = products.get(season, "PD-0001")
    label = product.label_for(site.habitat)
    assert label is not None
    assert label.season_max is not None
    used = treatments.season_total(season, site.id, product.id, 2025, unit="lb")
    per_acre = used.amount / site.extent.amount
    assert per_acre <= label.season_max.amount


def test_the_vector_index_is_the_product_of_its_two_halves(season: Book) -> None:
    found = virus.picture(season, 2025, 23, species.WNV)
    assert found.vector_index == estimate.vector_index(
        found.abundance.value,
        found.rate.rate,
    )


def test_the_abundance_leaves_out_what_cannot_carry_the_virus(season: Book) -> None:
    found = virus.picture(season, 2025, 23, species.WNV)
    whole = trapping.week_index(season, 2025, 23, "gravid")
    assert found.abundance.value == Decimal("120")
    assert whole.value == Decimal("420")


def test_the_pools_never_exceed_what_was_in_the_jar(season: Book) -> None:
    jar = traps.get_collection(season, "CO-250604-01")
    pooled = pools.pooled(season, jar.id, "CXPP")
    assert pooled <= jar.females_of("CXPP")


def test_the_run_happened_inside_the_notice_window(season: Book) -> None:
    made = runs.get(season, "RN-250710-01")
    covering = blocks.covering(season, made.block, "EX-0001", made.started_at)
    assert covering is not None
    assert covering.hours_given >= exclusions.get(season, "EX-0001").hours


def test_the_licence_on_every_record_is_the_one_the_holder_held(season: Book) -> None:
    holder = applicators.get(season, "AP-001")
    window = (dt.date(2025, 1, 1), dt.date(2025, 12, 31))
    licences = [one.licence for one in treatments.between(season, *window)]
    licences += [one.licence for one in runs.between(season, *window)]
    assert licences
    assert set(licences) == {holder.licence}


def test_every_treatment_names_a_site_that_was_on_the_list(season: Book) -> None:
    for one in treatments.between(season, dt.date(2025, 1, 1), dt.date(2025, 12, 31)):
        assert sites.get(season, one.site).is_open(one.on)
