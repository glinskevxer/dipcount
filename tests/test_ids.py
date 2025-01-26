from __future__ import annotations

import datetime as dt

import pytest

from dipcount import ids
from dipcount.errors import UsageError


def test_every_kind_has_a_distinct_prefix() -> None:
    prefixes = [kind.prefix for kind in ids.KINDS.values()]
    assert len(set(prefixes)) == len(prefixes)


def test_a_kind_is_looked_up_by_name() -> None:
    assert ids.kind_of("trap").prefix == "TR"
    with pytest.raises(UsageError):
        ids.kind_of("hedgehog")


def test_serial_ids_start_at_one() -> None:
    assert ids.next_serial("site", []) == "SI-0001"
    assert ids.next_serial("zone", []) == "ZN-001"


def test_serial_ids_take_the_highest_and_not_the_count() -> None:
    taken = ["SI-0001", "SI-0009", "SI-0004"]
    assert ids.next_serial("site", taken) == "SI-0010"


def test_serial_minting_ignores_other_kinds() -> None:
    taken = ["TR-0007", "SI-0002", "DP-250604-01"]
    assert ids.next_serial("site", taken) == "SI-0003"


def test_dated_ids_number_within_the_day() -> None:
    on = dt.date(2025, 6, 4)
    assert ids.next_dated("dip", on, []) == "DP-250604-01"
    assert ids.next_dated("dip", on, ["DP-250604-01"]) == "DP-250604-02"


def test_a_different_day_starts_again_at_one() -> None:
    taken = ["DP-250604-01", "DP-250604-02"]
    assert ids.next_dated("dip", dt.date(2025, 6, 5), taken) == "DP-250605-01"


def test_a_dated_kind_cannot_be_minted_as_a_serial() -> None:
    with pytest.raises(UsageError):
        ids.next_serial("dip", [])
    with pytest.raises(UsageError):
        ids.next_dated("site", dt.date(2025, 6, 4), [])


def test_the_hundredth_record_of_a_day_is_refused() -> None:
    taken = [f"CO-250604-{n:02d}" for n in range(1, 100)]
    with pytest.raises(UsageError):
        ids.next_dated("collection", dt.date(2025, 6, 4), taken)


def test_serial_numbers_run_out_at_the_width() -> None:
    with pytest.raises(UsageError):
        ids.next_serial("zone", ["ZN-999"])


def test_shapes_are_checked_not_guessed() -> None:
    assert ids.looks_like("site", "SI-0042")
    assert not ids.looks_like("site", "SI-42")
    assert not ids.looks_like("site", "si-0042")
    assert not ids.looks_like("dip", "DP-2025-06-04-01")


def test_require_returns_the_id_or_refuses() -> None:
    assert ids.require("trap", "TR-0004") == "TR-0004"
    with pytest.raises(UsageError):
        ids.require("trap", "SI-0004")


def test_the_kind_is_read_back_off_the_id() -> None:
    assert ids.kind_from("TX-250712-03") == "treatment"
    assert ids.kind_from("AP-014") == "applicator"
    with pytest.raises(UsageError):
        ids.kind_from("nonsense")


def test_the_day_comes_back_out_of_a_dated_id() -> None:
    assert ids.day_of("RN-250712-02") == dt.date(2025, 7, 12)
    with pytest.raises(UsageError):
        ids.day_of("SI-0001")


def test_ids_sort_in_the_order_they_were_issued() -> None:
    unsorted = ["DP-250704-01", "DP-250604-10", "DP-250604-02"]
    assert sorted(unsorted, key=ids.sort_key) == [
        "DP-250604-02",
        "DP-250604-10",
        "DP-250704-01",
    ]


def test_serials_sort_by_number_and_not_by_text() -> None:
    unsorted = ["SI-0100", "SI-0020", "SI-0003"]
    assert sorted(unsorted, key=ids.sort_key) == ["SI-0003", "SI-0020", "SI-0100"]


def test_minting_a_run_of_ids_never_repeats() -> None:
    taken: list[str] = []
    for _ in range(30):
        taken.append(ids.next_serial("site", taken))
    assert len(set(taken)) == 30
