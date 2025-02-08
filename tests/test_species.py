from __future__ import annotations

import pytest

from dipcount import species as sp
from dipcount.errors import NotFound


def test_every_code_is_four_upper_case_letters() -> None:
    for one in sp.known():
        assert len(one.code) == 4
        assert one.code.isupper()


def test_codes_are_unique() -> None:
    codes = [one.code for one in sp.known()]
    assert len(set(codes)) == len(codes)


def test_binomials_are_unique() -> None:
    names = [one.binomial for one in sp.known()]
    assert len(set(names)) == len(names)


def test_a_species_is_found_by_code_either_case() -> None:
    assert sp.species("CXPP").name == "pipiens"
    assert sp.species("cxpp").code == "CXPP"


def test_an_unknown_code_is_not_found() -> None:
    with pytest.raises(NotFound):
        sp.species("ZZZZ")


def test_the_binomial_reads_the_way_a_report_prints_it() -> None:
    assert sp.species("AEVX").binomial == "Aedes vexans"


def test_resolving_takes_several_spellings() -> None:
    for text in ("CXTR", "Culex tarsalis", "tarsalis", "Cx. tarsalis"):
        assert sp.resolve(text).code == "CXTR"


def test_resolving_something_unheard_of_is_not_found() -> None:
    with pytest.raises(NotFound):
        sp.resolve("the big grey one")


def test_the_guilds_partition_the_table() -> None:
    guilds = {sp.FLOODWATER, sp.CONTAINER, sp.PERMANENT, sp.WOODLAND}
    for one in sp.known():
        assert one.guild in guilds
    counted = sum(len(sp.in_guild(guild)) for guild in guilds)
    assert counted == len(sp.known())


def test_west_nile_vectors_are_the_culex(  # the district's whole virus programme
) -> None:
    vectors = sp.vectors_of(sp.WNV)
    assert {one.code for one in vectors} == {"CXPP", "CXRS", "CXTR", "CXSA"}
    for one in vectors:
        assert one.genus == "Culex"


def test_eastern_equine_runs_through_a_bird_feeder() -> None:
    melanura = sp.species("CSML")
    assert melanura.carries_virus(sp.EEE)
    assert melanura.hosts == sp.BIRD


def test_the_flood_nuisance_species_carries_nothing() -> None:
    vexans = sp.species("AEVX")
    assert not vexans.is_vector
    assert vexans.carries == ()


def test_every_listed_virus_has_at_least_one_vector() -> None:
    for virus in sp.viruses():
        assert sp.vectors_of(virus)


def test_the_container_species_do_not_fly_far() -> None:
    for one in sp.in_guild(sp.CONTAINER):
        assert one.flight_km <= 1.0


def test_the_floodwater_species_fly_further_than_the_container_ones() -> None:
    flood = max(one.flight_km for one in sp.in_guild(sp.FLOODWATER))
    container = max(one.flight_km for one in sp.in_guild(sp.CONTAINER))
    assert flood > container


def test_overwintering_is_one_of_three_stages() -> None:
    for one in sp.known():
        assert one.overwinters in {"egg", "adult", "larva"}


def test_the_species_that_breathe_off_roots_are_named() -> None:
    perturbans = sp.species("CQPR")
    assert perturbans.overwinters == "larva"
    assert "cattail" in perturbans.note
