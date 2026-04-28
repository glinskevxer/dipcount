from __future__ import annotations

import pytest

import dipcount
from dipcount.tools import check_package


def test_the_package_passes_its_own_check() -> None:
    assert check_package.findings() == []


def test_the_two_versions_agree() -> None:
    assert check_package.versions_agree() == []
    data = check_package.pyproject()
    project = data["project"]
    assert isinstance(project, dict)
    assert project["version"] == dipcount.__version__


def test_every_dependency_is_pinned_and_constrained() -> None:
    assert check_package.pins() == []


def test_every_re_export_exists() -> None:
    assert check_package.exports() == []


def test_the_console_script_points_at_something_importable() -> None:
    assert check_package.scripts() == []


def test_the_constraints_are_read_back_as_names_and_versions() -> None:
    held = check_package.constraints()
    assert held["click"] == "8.1.8"
    assert held["pytest"] == "8.3.4"


def test_the_stack_is_pinned_to_early_twenty_twenty_five() -> None:
    held = check_package.constraints()
    assert held["ruff"] == "0.9.2"
    assert held["mypy"] == "1.14.1"
    assert held["coverage"] == "7.6.10"


def test_a_pin_is_recognised_and_a_loose_name_is_not() -> None:
    assert check_package.PIN.match("click==8.1.8")
    assert not check_package.PIN.match("click>=8")
    assert not check_package.PIN.match("click")


def test_the_declared_dependencies_are_counted() -> None:
    assert len(check_package._declared()) == 6


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_package.main()
    assert raised.value.code == 0
