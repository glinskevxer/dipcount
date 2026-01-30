from __future__ import annotations

import importlib

import pytest

from dipcount import glossary
from dipcount.errors import NotFound


def test_every_term_is_lower_case_and_unique() -> None:
    for one in glossary.TERMS:
        assert one.word == one.word.lower()
    assert len(glossary.words()) == len(glossary.TERMS)


def test_every_term_says_something() -> None:
    for one in glossary.TERMS:
        assert len(one.meaning) > 40
        assert one.meaning.endswith(".")


def test_a_term_is_found_either_case() -> None:
    assert glossary.term("trap night").owner == "dipcount.model.trap"
    assert glossary.term("Trap Night").word == "trap night"


def test_an_unknown_term_is_not_found() -> None:
    with pytest.raises(NotFound):
        glossary.term("swarm")


def test_every_owner_is_a_module_that_exists() -> None:
    for owner in glossary.owners():
        assert importlib.import_module(owner)


def test_the_areas_gather_the_terms() -> None:
    assert glossary.in_area("model")
    assert glossary.in_area("rules")
    counted = sum(len(glossary.in_area(one)) for one in {term.area for term in glossary.TERMS})
    assert counted == len(glossary.TERMS)


def test_the_words_that_matter_most_are_all_in_there() -> None:
    for word in ("reporting week", "trap night", "index", "label", "season cap"):
        assert word in glossary.words()


def test_the_glossary_prints_one_line_a_term() -> None:
    lines = glossary.as_lines()
    assert len(lines) == len(glossary.TERMS)
    assert lines[0].startswith("**")
