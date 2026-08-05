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


def test_a_version_that_does_not_agree_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dipcount, "__version__", "9.9.9")
    found = check_package.versions_agree()
    assert found
    assert "9.9.9" in found[0].what


def test_a_loose_dependency_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_package, "_declared", lambda: ["click>=8"])
    found = check_package.pins()
    assert [one.what for one in found] == ["click>=8 is not pinned"]


def test_a_pin_the_constraints_do_not_carry_is_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check_package, "_declared", lambda: ["nothing==1.0"])
    found = check_package.pins()
    assert [one.what for one in found] == ["does not carry nothing"]


def test_a_pin_at_the_wrong_version_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_package, "_declared", lambda: ["click==7.0"])
    found = check_package.pins()
    assert "pins click at 8.1.8" in found[0].what


def test_a_console_script_pointing_nowhere_is_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        check_package,
        "pyproject",
        lambda: {"project": {"scripts": {"dipcount": "nothing.at.all:main"}}},
    )
    found = check_package.scripts()
    assert "points at nothing.at.all" in found[0].what


def test_a_console_script_wanting_a_missing_attribute_is_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        check_package,
        "pyproject",
        lambda: {"project": {"scripts": {"dipcount": "dipcount.clock:nothing"}}},
    )
    found = check_package.scripts()
    assert "wants dipcount.clock:nothing" in found[0].what
