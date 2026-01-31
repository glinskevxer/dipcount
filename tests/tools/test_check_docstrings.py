from __future__ import annotations

from pathlib import Path

import pytest

from dipcount.tools import check_docstrings


def test_the_package_passes_its_own_check() -> None:
    assert check_docstrings.findings() == []


def test_a_missing_docstring_is_found(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\n\ndef go() -> None:\n    pass\n')
    found = check_docstrings._findings_for(path)
    assert [one.what for one in found] == ["go has no docstring"]


def test_a_private_helper_may_go_without(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\n\ndef _go() -> None:\n    pass\n')
    assert check_docstrings._findings_for(path) == []


def test_a_module_without_a_docstring_is_found(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('def go() -> None:\n    """Do the thing."""\n')
    found = check_docstrings._findings_for(path)
    assert any("module has no docstring" in one.what for one in found)


def test_a_docstring_that_does_not_end_a_sentence(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\n\ndef go() -> None:\n    """Does the thing"""\n')
    found = check_docstrings._findings_for(path)
    assert any("does not end a sentence" in one.what for one in found)


def test_a_docstring_that_only_restates_the_name(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text('"""A file."""\n\n\ndef week_start() -> None:\n    """Week start."""\n')
    found = check_docstrings._findings_for(path)
    assert any("only restates the name" in one.what for one in found)


@pytest.mark.parametrize("text", ["The week start.", "A week start."])
def test_the_articles_do_not_rescue_a_restatement(tmp_path: Path, text: str) -> None:
    path = tmp_path / "one.py"
    path.write_text(f'"""A file."""\n\n\ndef week_start() -> None:\n    """{text}"""\n')
    found = check_docstrings._findings_for(path)
    assert any("only restates the name" in one.what for one in found)


def test_a_real_sentence_passes(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    path.write_text(
        '"""A file."""\n\n\ndef week_start() -> None:\n'
        '    """The Sunday a reporting week opens on."""\n',
    )
    assert check_docstrings._findings_for(path) == []


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_docstrings.main()
    assert raised.value.code == 0
