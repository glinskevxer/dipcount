from __future__ import annotations

import pytest

from dipcount import habitat as hb
from dipcount import species
from dipcount.errors import NotFound


def test_keys_are_unique_and_lower_case() -> None:
    for one in hb.known():
        assert one.key == one.key.lower()
        assert " " not in one.key
    assert len(set(hb.keys())) == len(hb.keys())


def test_a_habitat_is_found_by_key() -> None:
    assert hb.habitat("catch_basin").name == "storm drain catch basin"


def test_an_unknown_habitat_is_not_found() -> None:
    with pytest.raises(NotFound):
        hb.habitat("swimming pool")


def test_extent_is_measured_in_ground_or_in_structures() -> None:
    for one in hb.known():
        assert one.extent_unit in {"acre", "each"}


def test_the_structures_are_the_ones_counted_one_at_a_time() -> None:
    keys = {one.key for one in hb.counted_one_at_a_time()}
    assert "catch_basin" in keys
    assert "cattail_marsh" not in keys
    for one in hb.counted_one_at_a_time():
        assert one.extent_unit == "each"


def test_permanence_is_one_of_three() -> None:
    for one in hb.known():
        assert one.permanence in {hb.PERMANENT, hb.SEMI, hb.TEMPORARY}


def test_temporary_water_is_looked_at_more_often_than_permanent() -> None:
    temporary = [one.interval_days for one in hb.known() if one.permanence == hb.TEMPORARY]
    permanent = [one.interval_days for one in hb.known() if one.permanence == hb.PERMANENT]
    assert max(temporary) <= min(permanent) + 7
    assert sum(temporary) / len(temporary) < sum(permanent) / len(permanent)


def test_nothing_that_floats_is_allowed_on_a_cattail_marsh() -> None:
    marsh = hb.habitat("cattail_marsh")
    assert not marsh.allows(hb.OIL)
    assert not marsh.allows(hb.FILM)
    assert marsh.allows(hb.GRANULE)


def test_the_lagoon_is_the_only_place_a_film_goes() -> None:
    assert {one.key for one in hb.accepting(hb.FILM)} == {"lagoon"}


def test_every_habitat_accepts_something() -> None:
    for one in hb.known():
        assert one.forms


def test_every_listed_form_is_allowed_somewhere() -> None:
    for form in hb.forms():
        assert hb.accepting(form)


def test_the_forms_a_habitat_takes_are_all_real_forms() -> None:
    every = set(hb.forms())
    for one in hb.known():
        assert set(one.forms) <= every


def test_a_trough_takes_nothing_that_is_not_cleared_for_drinking_water() -> None:
    trough = hb.habitat("livestock_trough")
    assert set(trough.forms) == {hb.POUCH, hb.LIQUID}
    assert not trough.allows(hb.GRANULE)
    assert not trough.allows(hb.OIL)
    assert not trough.public


def test_habitats_name_the_species_that_would_be_in_them() -> None:
    basin = hb.habitat("catch_basin")
    codes = {one.code for one in basin.species_here()}
    assert "CXPP" in codes
    assert "AETR" not in codes


def test_a_tyre_pile_produces_the_container_species() -> None:
    pile = hb.habitat("tyre_pile")
    codes = {one.code for one in pile.species_here()}
    assert codes == {one.code for one in species.in_guild(species.CONTAINER)}


def test_the_ponds_with_fish_in_them_are_marked() -> None:
    keys = {one.key for one in hb.holding_fish()}
    assert keys == {"cattail_marsh", "retention_pond", "ornamental_pond"}


def test_every_guild_named_by_a_habitat_is_a_real_guild() -> None:
    guilds = {species.FLOODWATER, species.CONTAINER, species.PERMANENT, species.WOODLAND}
    for one in hb.known():
        assert set(one.guilds) <= guilds
        assert one.guilds


def test_the_dip_method_matches_how_big_the_water_is() -> None:
    for one in hb.known():
        if one.extent_unit == "each":
            assert one.dip_method in {hb.PIPETTE, hb.VISUAL}
        else:
            assert one.dip_method == hb.DIPPER
