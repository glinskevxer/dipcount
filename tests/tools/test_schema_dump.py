from __future__ import annotations

import pytest

from dipcount import glossary
from dipcount.store.migrations import MIGRATIONS, latest
from dipcount.tools import build_glossary, schema_dump


def test_the_document_matches_the_schema_the_migrations_build() -> None:
    assert schema_dump.matches()


def test_the_document_names_every_table() -> None:
    text = schema_dump.document()
    for table in schema_dump.tables():
        assert f"### {table}" in text


def test_the_document_names_every_step() -> None:
    text = schema_dump.document()
    for step in MIGRATIONS:
        assert step.name in text
    assert f"Schema version {latest()}" in text


def test_the_tables_are_the_ones_the_book_holds() -> None:
    found = schema_dump.tables()
    for name in ("site", "trap", "pool", "treatment", "run", "bioassay", "request"):
        assert name in found


def test_the_foreign_keys_are_written_down() -> None:
    text = schema_dump.document()
    assert "Points at: zone to zone" in text
    assert "Indexed:" in text


def test_the_document_can_be_written_back() -> None:
    made = schema_dump.write()
    assert made.read_text() == schema_dump.document()


def test_the_dump_checks_rather_than_writes_when_asked() -> None:
    with pytest.raises(SystemExit) as raised:
        schema_dump.main(["--check"])
    assert raised.value.code == 0


def test_the_glossary_document_matches_the_term_table() -> None:
    assert build_glossary.matches()


def test_the_glossary_document_names_every_term() -> None:
    text = build_glossary.document()
    for one in glossary.TERMS:
        assert one.word in text
        assert one.owner in text


def test_the_glossary_can_be_written_back() -> None:
    made = build_glossary.write()
    assert made.read_text() == build_glossary.document()


def test_the_glossary_checks_rather_than_writes_when_asked() -> None:
    with pytest.raises(SystemExit) as raised:
        build_glossary.main(["--check"])
    assert raised.value.code == 0
