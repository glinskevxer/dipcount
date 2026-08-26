from __future__ import annotations

from pathlib import Path

import pytest

from dipcount.tools import check_design, source


def test_the_package_passes_its_own_check() -> None:
    assert check_design.findings() == []


def test_every_record_is_frozen() -> None:
    assert check_design.mutable_records() == []


def test_nothing_shares_a_mutable_default() -> None:
    assert check_design.shared_defaults() == []


def test_nothing_outside_the_book_uses_any() -> None:
    assert check_design.loose_typing() == []


def test_no_module_is_long_enough_to_be_two() -> None:
    assert check_design.long_modules() == []


def test_no_function_is_long_enough_to_be_two() -> None:
    assert check_design.long_functions() == []


def test_the_builder_is_the_only_record_allowed_to_change() -> None:
    assert frozenset({"Sheet"}) == check_design.BUILDERS


def test_the_row_values_are_the_only_place_any_belongs() -> None:
    assert frozenset({"dipcount.store.book"}) == check_design.ANY_ALLOWED


def test_the_caps_are_where_they_are() -> None:
    assert check_design.LONGEST_FUNCTION == 60
    assert check_design.LONGEST_MODULE == 700


def test_the_package_holds_a_good_many_records() -> None:
    assert check_design.counted() > 30


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_design.main()
    assert raised.value.code == 0


def test_a_dataclass_that_is_not_frozen_is_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "one.py"
    path.write_text(
        '"""A file."""\n\nfrom dataclasses import dataclass\n\n\n'
        "@dataclass\nclass Loose:\n    a: int\n",
    )
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    found = check_design.mutable_records()
    assert [one.what for one in found] == ["Loose is a dataclass that is not frozen"]


def test_a_mutable_default_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\n\ndef go(held: list[int] = []) -> None:\n    pass\n')
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    assert [one.what for one in check_design.shared_defaults()] == ["go has a mutable default"]


def test_a_use_of_any_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\nfrom typing import Any\n\nheld: Any = 1\n')
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    monkeypatch.setattr(source, "dotted", lambda _: "dipcount.service.survey")
    assert [one.what for one in check_design.loose_typing()] == ["uses Any"]


def test_a_long_module_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n' + "x = 1\n" * 900)
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    assert "lines long" in check_design.long_modules()[0].what


def test_a_long_function_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = "    x = 1\n" * 90
    path = tmp_path / "one.py"
    path.write_text(f'"""A file."""\n\n\ndef go() -> None:\n{body}')
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    assert "go is" in check_design.long_functions()[0].what


def test_a_long_command_is_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = "    x = 1\n" * 90
    path = tmp_path / "one.py"
    path.write_text(f'"""A file."""\n\n\n@click.command()\ndef go() -> None:\n{body}')
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    assert check_design.long_functions() == []
