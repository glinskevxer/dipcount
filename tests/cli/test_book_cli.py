from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from dipcount import __version__
from dipcount.cli.main import cli, main
from tests.cli.conftest import Run


def test_init_makes_the_book(run: Run, tmp_path: Path) -> None:
    result = run("book", "init")
    assert "schema" in result.output
    assert (tmp_path / "district.sqlite3").exists()


def test_init_twice_says_so(run: Run) -> None:
    run("book", "init")
    result = run("book", "init")
    assert "already up to date" in result.output


def test_counts_lists_the_tables(started: Run) -> None:
    result = started("book", "counts")
    assert "zone" in result.output
    assert "site" in result.output


def test_check_reports_the_schema(started: Run) -> None:
    result = started("book", "check")
    assert "integrity" in result.output
    assert "ok" in result.output


def test_a_command_against_a_book_that_is_not_there(run: Run) -> None:
    result = run("zone", "list", expect=1)
    assert result.exit_code != 0


def test_a_command_against_an_unmigrated_book(run: Run, tmp_path: Path) -> None:
    (tmp_path / "district.sqlite3").write_bytes(b"")
    result = run("zone", "list", expect=1)
    assert result.exit_code != 0


def test_about_names_the_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["about"])
    assert __version__ in result.output


def test_the_version_flag_prints_the_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--version"])
    assert __version__ in result.output


def test_main_returns_zero_on_a_good_run(tmp_path: Path) -> None:
    path = tmp_path / "district.sqlite3"
    assert main(["--book", str(path), "book", "init"]) == 0


def test_main_returns_our_status_on_a_refusal(tmp_path: Path) -> None:
    path = tmp_path / "district.sqlite3"
    assert main(["--book", str(path), "zone", "list"]) != 0


def test_main_returns_the_click_status_on_a_bad_command(tmp_path: Path) -> None:
    path = tmp_path / "district.sqlite3"
    assert main(["--book", str(path), "nonsense"]) == 2


def test_the_glossary_prints_every_term(started: Run) -> None:
    result = started("book", "terms")
    assert "trap night" in result.output
    assert "reporting week" in result.output


def test_one_term_can_be_asked_for(started: Run) -> None:
    result = started("book", "terms", "--word", "vector index")
    assert "Abundance times infection rate" in result.output


def test_an_unknown_term_is_refused(started: Run) -> None:
    result = started("book", "terms", "--word", "swarm", expect=1)
    assert result.exit_code != 0


def test_a_backup_is_taken_and_verified(started: Run, tmp_path: Path) -> None:
    into = tmp_path / "backups"
    result = started("book", "backup", "--into", str(into))
    assert "sound" in result.output
    assert list(into.glob("*.sqlite3"))


def test_the_backups_are_listed(started: Run, tmp_path: Path) -> None:
    into = tmp_path / "backups"
    started("book", "backup", "--into", str(into))
    result = started("book", "backups", "--into", str(into))
    assert "1 row" in result.output
    assert "yes" in result.output


def test_a_rota_prunes_the_oldest(started: Run, tmp_path: Path) -> None:
    into = tmp_path / "backups"
    started("book", "backup", "--into", str(into))
    started("book", "backup", "--into", str(into))
    result = started("book", "backup", "--into", str(into), "--keep", "1")
    assert "pruned" in result.output or len(list(into.glob("*.sqlite3"))) <= 2
