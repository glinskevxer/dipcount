from __future__ import annotations

import pytest

from dipcount.tools import check_naming


def test_the_suite_passes_its_own_check() -> None:
    assert check_naming.findings() == []


def test_no_test_name_is_a_shrug() -> None:
    assert check_naming.vague_tests() == []


def test_every_test_name_is_a_sentence() -> None:
    assert check_naming.thin_tests() == []


def test_every_module_is_named_in_lower_case() -> None:
    assert check_naming.module_names() == []


def test_every_test_file_is_called_test_something() -> None:
    assert check_naming.test_file_names() == []


def test_the_vague_list_is_phrases_and_not_single_words() -> None:
    for one in check_naming.VAGUE:
        assert one.startswith("_")
        assert one.count("_") >= 1


def test_a_domain_word_on_its_own_is_not_flagged() -> None:
    for name in (
        "test_a_work_card_names_the_product",
        "test_every_code_is_upper_case_here",
        "test_a_path_outside_the_checkout_prints",
        "test_a_technician_works_under_somebody",
    ):
        assert not [one for one in check_naming.VAGUE if one in name]
        assert not [one for one in check_naming.ENDINGS if name.endswith(one)]


def test_a_real_shrug_is_flagged() -> None:
    for name in ("test_it_works", "test_the_thing_is_correct", "test_the_happy_path_here"):
        found = [one for one in check_naming.VAGUE if one in name]
        found += [one for one in check_naming.ENDINGS if name.endswith(one)]
        assert found


def test_the_shortest_name_is_four_words() -> None:
    assert check_naming.SHORTEST == 4
    assert check_naming._words("test_a_b_c_d") == ["a", "b", "c", "d"]


def test_the_suite_is_counted() -> None:
    assert check_naming.counted() > 500


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_naming.main()
    assert raised.value.code == 0
