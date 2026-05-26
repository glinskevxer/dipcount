from __future__ import annotations

import pytest

from dipcount import __version__
from dipcount.tools import release_check, source


def test_the_package_passes_the_last_gate() -> None:
    assert release_check.findings() == []


def test_every_other_check_is_clean() -> None:
    assert release_check.every_check() == []


def test_nothing_is_left_over_from_debugging() -> None:
    assert release_check.leftovers() == []


def test_nothing_outside_the_checks_prints() -> None:
    assert release_check.printing() == []


def test_the_generated_documents_are_current() -> None:
    assert release_check.documents() == []


def test_the_changelog_names_this_version() -> None:
    assert release_check.changelog() == []
    path = source.project_root() / "CHANGELOG.md"
    assert f"## {__version__}" in path.read_text()


def test_every_check_the_package_has_is_on_the_list() -> None:
    modules = {
        source.dotted(one).rsplit(".", 1)[1]
        for one in source.modules(under="tools")
        if one.stem.startswith("check_")
    }
    listed = {one.__name__.rsplit(".", 1)[1] for one in release_check.CHECKS}
    assert modules == listed


def test_the_checks_are_the_only_place_that_prints() -> None:
    assert frozenset({"dipcount.tools"}) == release_check.PRINTING_ALLOWED


def test_the_leftover_words_are_the_ones_worth_refusing() -> None:
    for word in ("TODO", "FIXME", "breakpoint("):
        assert word in release_check.LEFTOVERS


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        release_check.main()
    assert raised.value.code == 0
