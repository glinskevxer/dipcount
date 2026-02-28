from __future__ import annotations

import pytest

from dipcount.tools import check_tests


def test_the_package_passes_its_own_check() -> None:
    assert check_tests.findings() == []


def test_every_module_has_a_test_about_it() -> None:
    assert check_tests.untested_modules() == []


def test_no_test_asserts_nothing() -> None:
    assert check_tests.silent_tests() == []


def test_the_suite_is_counted() -> None:
    files, tests = check_tests.counted()
    assert files > 50
    assert tests > 500


def test_a_command_module_is_matched_by_its_test_file_name() -> None:
    stems = check_tests._test_file_names()
    assert "test_zone_cli" in stems
    assert "test_dip_cli" in stems


def test_the_package_directories_are_left_out() -> None:
    assert "dipcount.model" in check_tests.EXEMPT
    assert "dipcount.clock" not in check_tests.EXEMPT


def test_a_test_that_only_raises_still_counts_as_asserting() -> None:
    import ast

    tree = ast.parse(
        "import pytest\n"
        "def test_one() -> None:\n"
        "    with pytest.raises(ValueError):\n"
        "        raise ValueError\n",
    )
    found = check_tests._tests_in(tree)
    assert check_tests._assertions(found[0]) == 1


def test_a_test_with_no_assertion_is_found() -> None:
    import ast

    tree = ast.parse("def test_one() -> None:\n    pass\n")
    found = check_tests._tests_in(tree)
    assert check_tests._assertions(found[0]) == 0


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_tests.main()
    assert raised.value.code == 0
