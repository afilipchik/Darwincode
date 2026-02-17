import click
from rich.console import Console

from darwincode.k8s.cluster import ClusterManager
from darwincode.k8s.images import ImageManager

console = Console()


@click.command()
@click.option("--cluster-name", default="darwincode", help="Kind cluster name")
@click.option("--skip-image", is_flag=True, help="Skip building the agent Docker image")
def init(cluster_name: str, skip_image: bool) -> None:
    """Initialize Kind cluster and build agent images."""
    cluster = ClusterManager(cluster_name)

    if cluster.exists():
        console.print(f"[yellow]Cluster '{cluster_name}' already exists.[/yellow]")
    else:
        console.print(f"[bold]Creating Kind cluster '{cluster_name}'...[/bold]")
        cluster.create()
        console.print("[green]Cluster created.[/green]")

    if not skip_image:
        console.print("[bold]Building agent Docker image...[/bold]")
        images = ImageManager(cluster_name)
        images.build_agent_image()
        images.load_into_kind()
        console.print("[green]Agent image loaded into cluster.[/green]")

    console.print("[bold green]Darwincode initialized.[/bold green]")
