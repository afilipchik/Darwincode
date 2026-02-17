import click
from rich.console import Console

from darwincode.k8s.cluster import ClusterManager

console = Console()


@click.command()
@click.option("--cluster-name", default="darwincode", help="Kind cluster name")
@click.confirmation_option(prompt="This will delete the Kind cluster. Continue?")
def destroy(cluster_name: str) -> None:
    """Tear down the Kind cluster."""
    cluster = ClusterManager(cluster_name)

    if not cluster.exists():
        console.print(f"[yellow]Cluster '{cluster_name}' does not exist.[/yellow]")
        return

    console.print(f"[bold]Deleting Kind cluster '{cluster_name}'...[/bold]")
    cluster.delete()
    console.print("[green]Cluster deleted.[/green]")
