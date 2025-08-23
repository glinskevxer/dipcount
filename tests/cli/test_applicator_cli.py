from __future__ import annotations

from tests.cli.conftest import Run


def test_the_register_lists_everybody(crewed: Run) -> None:
    result = crewed("crew", "list")
    assert "AP-001" in result.output
    assert "K. Brennaman" in result.output
    assert "2 rows" in result.output


def test_the_register_narrows_by_grade(crewed: Run) -> None:
    result = crewed("crew", "list", "--grade", "technician")
    assert "1 row" in result.output
    assert "D. Uzoma" in result.output


def test_a_licence_number_is_not_reused(crewed: Run) -> None:
    result = crewed(
        "crew",
        "add",
        "Somebody",
        "PA-44192",
        "--grade",
        "certified",
        "--category",
        "core",
        "--certified",
        "2024-03-01",
        "--expires",
        "2027-03-01",
        expect=1,
    )
    assert result.exit_code != 0


def test_a_technician_needs_a_supervisor(crewed: Run) -> None:
    result = crewed(
        "crew",
        "add",
        "R. Salcedo",
        "PA-44194",
        "--grade",
        "technician",
        "--category",
        "core",
        "--certified",
        "2024-03-01",
        "--expires",
        "2027-03-01",
        expect=1,
    )
    assert result.exit_code != 0


def test_a_holder_shows_their_standing(crewed: Run) -> None:
    result = crewed("crew", "show", "AP-001", "--on", "2025-06-04")
    assert "aquatic" in result.output
    assert "hours needed" in result.output
    assert "no" in result.output


def test_credits_bring_somebody_up_to_renewable(crewed: Run) -> None:
    crewed(
        "crew",
        "credit",
        "AP-002",
        "core review day",
        "--on",
        "2025-02-12",
        "--category",
        "core",
        "--hours",
        "9",
    )
    result = crewed("crew", "show", "AP-002", "--on", "2025-06-04")
    assert "core review day" in result.output
    assert "renewable" in result.output


def test_the_same_course_on_the_same_day_twice(crewed: Run) -> None:
    crewed(
        "crew",
        "credit",
        "AP-002",
        "core review day",
        "--on",
        "2025-02-12",
        "--category",
        "core",
        "--hours",
        "9",
    )
    result = crewed(
        "crew",
        "credit",
        "AP-002",
        "core review day",
        "--on",
        "2025-02-12",
        "--category",
        "core",
        "--hours",
        "9",
        expect=1,
    )
    assert result.exit_code != 0


def test_a_licence_is_renewed_forwards(crewed: Run) -> None:
    result = crewed(
        "crew",
        "renew",
        "AP-001",
        "--certified",
        "2027-03-01",
        "--expires",
        "2030-03-01",
    )
    assert "2030-03-01" in result.output


def test_a_renewal_backwards_is_refused(crewed: Run) -> None:
    result = crewed(
        "crew",
        "renew",
        "AP-001",
        "--certified",
        "2024-03-01",
        "--expires",
        "2026-03-01",
        expect=1,
    )
    assert result.exit_code != 0


def test_somebody_leaving_drops_off_the_in_date_list(crewed: Run) -> None:
    crewed("crew", "leave", "AP-002", "--on", "2025-08-01")
    result = crewed("crew", "list", "--on", "2025-09-01")
    assert "1 row" in result.output


def test_the_licences_running_out_are_listed(crewed: Run) -> None:
    result = crewed("crew", "expiring", "--on", "2027-01-01", "--days", "90")
    assert "2 rows" in result.output
    assert "no" in result.output


def test_nobody_is_expiring_this_summer(crewed: Run) -> None:
    result = crewed("crew", "expiring", "--on", "2025-06-04", "--days", "90")
    assert "0 rows" in result.output


def test_the_crew_for_a_job_names_the_category(crewed: Run) -> None:
    crewed("product", "stock", "--on", "2025-01-15")
    crewed(
        "site",
        "add",
        "north",
        "Sawyer marsh",
        "--habitat",
        "cattail_marsh",
        "--extent",
        "6 acre",
        "--on",
        "2025-03-01",
    )
    result = crewed("crew", "for", "SI-0001", "Bactilore G", "--on", "2025-06-04")
    assert "aquatic category" in result.output
    assert "K. Brennaman" in result.output
    assert "D. Uzoma" not in result.output
