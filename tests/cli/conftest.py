from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from dipcount.cli.main import cli

Run = Callable[..., Result]


@pytest.fixture
def runner() -> CliRunner:
    """A click runner that keeps stderr apart from stdout."""
    return CliRunner()


@pytest.fixture
def run(runner: CliRunner, tmp_path: Path) -> Run:
    """Run a command against a book of this test's own."""
    path = tmp_path / "district.sqlite3"

    def go(*args: str, actor: str = "office", expect: int = 0) -> Result:
        result = runner.invoke(
            cli,
            ["--book", str(path), "--actor", actor, *args],
            standalone_mode=False,
        )
        if expect == 0 and result.exit_code != 0:
            raise AssertionError(f"{args} failed: {result.output}\n{result.exception}")
        return result

    return go


@pytest.fixture
def started(run: Run) -> Run:
    """A book that has been initialised and has two zones in it."""
    run("book", "init")
    run("zone", "add", "north", "--supervisor", "R. Vandeburg")
    run("zone", "add", "south", "--supervisor", "T. Okwuosa")
    return run
