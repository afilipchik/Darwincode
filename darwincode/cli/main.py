import click

from darwincode.cli.commands.destroy import destroy
from darwincode.cli.commands.init import init
from darwincode.cli.commands.logs import logs
from darwincode.cli.commands.results import results
from darwincode.cli.commands.run import run
from darwincode.cli.commands.status import status


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Darwincode — Evolutionary code generation."""


cli.add_command(init)
cli.add_command(run)
cli.add_command(status)
cli.add_command(logs)
cli.add_command(results)
cli.add_command(destroy)
