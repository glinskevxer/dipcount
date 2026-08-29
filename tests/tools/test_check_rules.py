from __future__ import annotations

from decimal import Decimal

import pytest

from dipcount import rules
from dipcount.service.trapping import Index
from dipcount.tools import build_rules, check_rules


def test_the_rule_book_passes_its_own_check() -> None:
    assert check_rules.findings() == []


def test_every_clause_is_used_somewhere() -> None:
    assert check_rules.unused_clauses() == []


def test_every_clause_has_a_heading_and_a_sentence() -> None:
    assert check_rules.clause_shape() == []


def test_the_documented_only_list_is_all_real_clauses() -> None:
    assert check_rules.documented_only_exists() == []
    for name in check_rules.DOCUMENTED_ONLY:
        assert name in rules.BY_NAME


def test_the_generated_document_matches_the_clause_table() -> None:
    assert build_rules.matches()


def test_the_document_names_every_clause() -> None:
    text = build_rules.document()
    for clause in rules.CLAUSES:
        assert clause.name in text
        assert clause.heading in text


def test_the_document_carries_the_figures() -> None:
    text = build_rules.document()
    assert "wind band" in text
    assert "1 to 10 mph" in text
    assert "response ladder" in text


def test_every_figure_has_a_value() -> None:
    for name, value in build_rules.figures().items():
        assert name
        assert value


def test_the_document_can_be_written_back() -> None:
    made = build_rules.write()
    assert made.read_text() == build_rules.document()


def test_the_generator_checks_rather_than_writes_when_asked() -> None:
    with pytest.raises(SystemExit) as raised:
        build_rules.main(["--check"])
    assert raised.value.code == 0


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_rules.main()
    assert raised.value.code == 0


def test_the_adult_clauses_are_named_by_the_index() -> None:
    made = Index(2025, 23, "gravid", 40, Decimal(1), 1, dropped=1)
    assert "adult.threshold" in made.reasons
    assert "adult.broken" in made.reasons


def test_a_full_week_names_only_the_threshold_clause() -> None:
    made = Index(2025, 23, "gravid", 40, Decimal(1), 1)
    assert made.reasons == ("adult.threshold",)


def test_a_clause_with_no_heading_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    thin = rules.Clause("larval.thin", "", "a" * 80)
    monkeypatch.setattr("dipcount.rules.CLAUSES", (thin,))
    found = check_rules.clause_shape()
    assert any("no heading" in one.what for one in found)


def test_a_clause_that_says_almost_nothing_is_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thin = rules.Clause("larval.thin", "a heading", "too short")
    monkeypatch.setattr("dipcount.rules.CLAUSES", (thin,))
    assert any("almost nothing" in one.what for one in check_rules.clause_shape())


def test_a_clause_name_without_an_area_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    odd = rules.Clause("thin", "a heading", "a" * 80)
    monkeypatch.setattr("dipcount.rules.CLAUSES", (odd,))
    assert any("is not area.name" in one.what for one in check_rules.clause_shape())


def test_a_documented_name_that_is_not_a_clause_is_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check_rules, "DOCUMENTED_ONLY", frozenset({"nothing.here"}))
    found = check_rules.documented_only_exists()
    assert [one.what for one in found] == [
        "nothing.here is on the documented list and is not a clause",
    ]


def test_a_stale_rule_book_stops_the_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_rules, "matches", lambda: False)
    with pytest.raises(SystemExit) as raised:
        build_rules.main(["--check"])
    assert raised.value.code == 1


def test_the_rule_book_is_written_when_no_check_is_asked_for(
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_rules.main([])
    assert "wrote" in capsys.readouterr().out
