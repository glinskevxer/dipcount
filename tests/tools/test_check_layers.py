from __future__ import annotations

import pytest

from dipcount.tools import check_layers, source


def test_the_package_passes_its_own_check() -> None:
    assert check_layers.findings() == []


def test_every_module_is_in_the_layer_table() -> None:
    assert check_layers.unknown_layers() == []


def test_the_layers_run_in_the_order_they_are_written() -> None:
    ranks = check_layers.RANKS
    assert ranks["errors"] < ranks["model"] < ranks["store"] < ranks["service"]
    assert ranks["service"] < ranks["report"] < ranks["cli"]


def test_a_dotted_name_finds_its_layer() -> None:
    assert check_layers.layer_of("dipcount.store.book") == check_layers.RANKS["store"]
    assert check_layers.layer_of("dipcount.clock") == check_layers.RANKS["clock"]


def test_something_outside_the_package_has_no_layer() -> None:
    assert check_layers.layer_of("sqlite3") is None
    assert check_layers.layer_of("click") is None
    assert check_layers.layer_of("dipcount") is None


def test_a_model_importing_a_service_is_found() -> None:
    found = check_layers.findings_in(
        "dipcount.model.site",
        '"""A file."""\n\nfrom dipcount.service import survey\n',
        "model/site.py",
    )
    assert len(found) == 1
    assert "a layer above" in found[0].what


def test_a_service_importing_a_store_is_fine() -> None:
    found = check_layers.findings_in(
        "dipcount.service.survey",
        '"""A file."""\n\nfrom dipcount.store import sites\n',
        "service/survey.py",
    )
    assert found == []


def test_a_plain_import_statement_is_read_too() -> None:
    found = check_layers.findings_in(
        "dipcount.model.site",
        '"""A file."""\n\nimport dipcount.cli.main\n',
        "model/site.py",
    )
    assert len(found) == 1


def test_something_outside_the_package_is_left_alone() -> None:
    found = check_layers.findings_in(
        "dipcount.model.site",
        '"""A file."""\n\nimport sqlite3\n',
        "model/site.py",
    )
    assert found == []


def test_a_model_reaching_into_the_store_is_found() -> None:
    path = source.package_root() / "model" / "site.py"
    text = path.read_text()
    assert "from dipcount.store" not in text
    assert "from dipcount.rows import Row" in text


def test_every_model_reads_its_rows_from_the_leaf_module() -> None:
    for path in source.modules(under="model"):
        text = path.read_text()
        if "Row" in text and "from dipcount" in text:
            assert "from dipcount.store.book import Row" not in text


def test_the_store_still_offers_the_row_type() -> None:
    from dipcount import rows
    from dipcount.store import book

    assert book.Row is rows.Row


def test_the_check_runs_as_a_module() -> None:
    with pytest.raises(SystemExit) as raised:
        check_layers.main()
    assert raised.value.code == 0
