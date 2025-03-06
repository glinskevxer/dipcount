from __future__ import annotations

from decimal import Decimal

import pytest

from dipcount import habitat as hb
from dipcount import rules
from dipcount.errors import NotFound


def test_every_clause_name_has_two_parts() -> None:
    for one in rules.CLAUSES:
        assert "." in one.name
        assert one.name == one.name.lower()


def test_clause_names_are_unique() -> None:
    names = [one.name for one in rules.CLAUSES]
    assert len(set(names)) == len(names)


def test_a_clause_is_found_by_name() -> None:
    assert rules.clause("larval.pupal").area == "larval"
    with pytest.raises(NotFound):
        rules.clause("larval.nothing")


def test_the_areas_gather_the_clauses() -> None:
    assert "larval" in rules.areas()
    counted = sum(len(rules.clauses_in(area)) for area in rules.areas())
    assert counted == len(rules.CLAUSES)


def test_every_clause_says_something() -> None:
    for one in rules.CLAUSES:
        assert len(one.text) > 40
        assert one.heading


def test_every_habitat_has_a_figure() -> None:
    for one in hb.known():
        assert rules.base_threshold(one.key) > 0
    assert set(rules.thresholds()) == set(hb.keys())


def test_an_unknown_habitat_has_no_figure() -> None:
    with pytest.raises(NotFound):
        rules.base_threshold("swimming_pool")


def test_the_containers_are_the_lowest_figures() -> None:
    container = rules.base_threshold("container")
    ditch = rules.base_threshold("roadside_ditch")
    assert container < ditch


def test_a_vector_halves_the_figure() -> None:
    plain = rules.threshold("catch_basin", vector_present=False)
    halved = rules.threshold("catch_basin", vector_present=True)
    assert plain == Decimal("0.5")
    assert halved == Decimal("0.25")


def test_the_culex_carry_something_and_vexans_does_not() -> None:
    assert rules.carries_a_vector(["CXPP"])
    assert not rules.carries_a_vector(["AEVX"])
    assert rules.carries_a_vector(["AEVX", "CXTR"])


def test_an_unidentified_sample_carries_nothing() -> None:
    assert not rules.carries_a_vector([])
    assert not rules.carries_a_vector([""])
    assert not rules.carries_a_vector(["ZZZZ"])


def test_the_pupal_stop_and_the_late_share_are_where_they_are() -> None:
    assert Decimal("0.5") == rules.PUPAL_STOP
    assert Decimal("0.75") == rules.LATE_URGENT
    assert rules.RAFT_INTERVAL == 4


def test_the_raft_interval_is_shorter_than_every_habitat_interval() -> None:
    for one in hb.known():
        assert one.interval_days >= rules.RAFT_INTERVAL
