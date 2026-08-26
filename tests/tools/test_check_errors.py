from __future__ import annotations

from pathlib import Path

import pytest

from dipcount.rules import BY_NAME
from dipcount.tools import check_errors, source


def test_the_package_passes_its_own_check() -> None:
    assert check_errors.findings() == []


def test_nothing_raises_a_builtin() -> None:
    assert check_errors.raised_builtins() == []


def test_every_refusal_names_a_clause_the_rule_book_holds() -> None:
    assert check_errors.unknown_clauses() == []


def test_no_handler_catches_everything_in_silence() -> None:
    assert check_errors.broad_excepts() == []


def test_the_clause_names_are_read_off_the_refusals() -> None:
    path = source.package_root() / "service" / "larvicide.py"
    found = [name for name, _ in check_errors.clause_names(path)]
    assert "label.rate" in found
    assert "label.season" in found
    for name in found:
        assert name in BY_NAME


def test_the_four_clauses_the_check_found_missing_are_written_down() -> None:
    for name in ("pool.jar", "product.withdrawn", "trap.retired", "weather.station"):
        assert name in BY_NAME


def test_the_sheet_renderer_is_the_only_place_a_builtin_is_allowed() -> None:
    assert frozenset({"dipcount.report.sheet"}) == check_errors.ALLOWED_BUILTINS


def test_a_good_many_refusals_name_a_clause() -> None:
    assert check_errors.counted() > 40


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_errors.main()
    assert raised.value.code == 0


def test_a_raised_builtin_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\n\ndef go() -> None:\n    raise ValueError("no")\n')
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    monkeypatch.setattr(source, "dotted", lambda _: "dipcount.service.survey")
    assert [one.what for one in check_errors.raised_builtins()] == ["raises ValueError"]


def test_a_bare_raise_of_a_builtin_name_is_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\n\ndef go() -> None:\n    raise ValueError\n')
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    monkeypatch.setattr(source, "dotted", lambda _: "dipcount.service.survey")
    assert check_errors.raised_builtins()


def test_a_clause_that_is_not_in_the_rule_book_is_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\nRefusal("nothing.here", "no")\n')
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    monkeypatch.setattr(source, "dotted", lambda _: "dipcount.service.survey")
    found = check_errors.unknown_clauses()
    assert [one.what for one in found] == ["names the clause nothing.here"]


def test_a_bare_except_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\ntry:\n    pass\nexcept:\n    pass\n')
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    assert [one.what for one in check_errors.broad_excepts()] == ["catches everything"]


def test_a_silent_broad_except_is_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\ntry:\n    pass\nexcept Exception:\n    pass\n')
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    found = check_errors.broad_excepts()
    assert "without a reason" in found[0].what


def test_a_broad_except_with_a_reason_is_left_alone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "one.py"
    path.write_text(
        '"""A file."""\n\ntry:\n    pass\nexcept Exception:  # it raises three things\n    pass\n',
    )
    monkeypatch.setattr(source, "modules", lambda **_: [path])
    assert check_errors.broad_excepts() == []


def test_a_refusal_with_no_arguments_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\nRefusal()\n')
    assert check_errors.clause_names(path) == []
