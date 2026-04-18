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
