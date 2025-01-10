from __future__ import annotations

import pytest

from dipcount.errors import (
    BookError,
    DipcountError,
    Duplicate,
    LabelViolation,
    MigrationError,
    NotFound,
    RuleViolation,
    UsageError,
    describe,
    status_for,
)


def test_everything_descends_from_the_base() -> None:
    for kind in (UsageError, NotFound, Duplicate, RuleViolation, LabelViolation, BookError):
        assert issubclass(kind, DipcountError)


def test_not_found_names_the_kind_and_the_key() -> None:
    error = NotFound("trap", "TR-0004")
    assert error.kind == "trap"
    assert error.key == "TR-0004"
    assert str(error) == "no trap named TR-0004"


def test_duplicate_reads_as_a_sentence() -> None:
    error = Duplicate("site", "SI-0012")
    assert str(error) == "site SI-0012 is already on the books"
    assert error.kind == "site"


def test_rule_violation_carries_the_clause_name() -> None:
    error = RuleViolation("larval.threshold", "one larva per dip is under the threshold")
    assert error.rule == "larval.threshold"
    assert "under the threshold" in str(error)


def test_a_label_violation_is_not_an_ordinary_rule_violation() -> None:
    error = LabelViolation("label.rate", "8 oz per acre is over the labelled maximum")
    assert isinstance(error, RuleViolation)
    assert error.exit_status != RuleViolation.exit_status


def test_migration_error_is_a_book_error() -> None:
    assert issubclass(MigrationError, BookError)


def test_exit_statuses_are_distinct() -> None:
    kinds: list[type[DipcountError]] = [
        DipcountError,
        UsageError,
        NotFound,
        Duplicate,
        RuleViolation,
        LabelViolation,
        BookError,
        MigrationError,
    ]
    statuses = [kind.exit_status for kind in kinds]
    assert len(set(statuses)) == len(statuses)


def test_describe_puts_the_clause_in_the_line() -> None:
    line = describe(RuleViolation("spray.wind", "wind is 12 mph"))
    assert line == "RuleViolation [spray.wind]: wind is 12 mph"


def test_describe_handles_a_plain_error() -> None:
    assert describe(NotFound("pool", "PL-1")) == "NotFound: no pool named PL-1"


def test_status_for_falls_back_to_one() -> None:
    assert status_for(ValueError("not ours")) == 1
    assert status_for(NotFound("zone", "west")) == NotFound.exit_status


def test_raising_and_catching_by_the_base() -> None:
    with pytest.raises(DipcountError):
        raise LabelViolation("label.site", "a labelled site this is not")
