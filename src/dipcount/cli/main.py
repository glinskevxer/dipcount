"""The entry point, the global options, and where errors turn into statuses."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from dipcount import __version__, clock
from dipcount.cli import applicator as applicator_commands
from dipcount.cli import bioassay as bioassay_commands
from dipcount.cli import block as block_commands
from dipcount.cli import book as book_commands
from dipcount.cli import dip as dip_commands
from dipcount.cli import equipment as equipment_commands
from dipcount.cli import lot as lot_commands
from dipcount.cli import pool as pool_commands
from dipcount.cli import product as product_commands
from dipcount.cli import report as report_commands
from dipcount.cli import request as request_commands
from dipcount.cli import site as site_commands
from dipcount.cli import spray as spray_commands
from dipcount.cli import trap as trap_commands
from dipcount.cli import treat as treat_commands
from dipcount.cli import virus as virus_commands
from dipcount.cli import weather as weather_commands
from dipcount.cli import zone as zone_commands
from dipcount.cli.options import Desk
from dipcount.errors import DipcountError, describe, status_for


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="dipcount")
@click.option(
    "--book",
    "book_path",
    default="district.sqlite3",
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="The district book to work against.",
)
@click.option(
    "--actor",
    default="office",
    show_default=True,
    help="Whose name goes on the audit trail.",
)
@click.option(
    "--zone",
    "zone_name",
    default=clock.DEFAULT_ZONE,
    show_default=True,
    help="The time zone the district works in.",
)
@click.pass_context
def cli(ctx: click.Context, book_path: Path, actor: str, zone_name: str) -> None:
    """Records for a mosquito abatement district."""
    ctx.obj = Desk(path=book_path, actor=actor, zone_name=zone_name)


cli.add_command(book_commands.book)
cli.add_command(zone_commands.zone)
cli.add_command(site_commands.site)
cli.add_command(dip_commands.dip)
cli.add_command(trap_commands.trap)
cli.add_command(pool_commands.pool)
cli.add_command(virus_commands.arbo)
cli.add_command(product_commands.product)
cli.add_command(lot_commands.lot)
cli.add_command(treat_commands.treat)
cli.add_command(applicator_commands.crew)
cli.add_command(block_commands.block)
cli.add_command(block_commands.register)
cli.add_command(spray_commands.spray)
cli.add_command(equipment_commands.shop)
cli.add_command(request_commands.call)
cli.add_command(bioassay_commands.assay)
cli.add_command(report_commands.report)
cli.add_command(weather_commands.wx)


@cli.command()
def about() -> None:
    """What this program is and what version it is."""
    click.echo(f"dipcount {__version__}")
    click.echo("surveillance, treatment records and use reporting for a mosquito district")


def main(argv: list[str] | None = None) -> int:
    """Run the command line and turn our errors into exit statuses."""
    try:
        cli.main(args=argv, standalone_mode=False)
    except DipcountError as error:
        click.echo(describe(error), err=True)
        return status_for(error)
    except click.ClickException as error:
        error.show()
        return error.exit_code
    except click.Abort:
        click.echo("stopped", err=True)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
