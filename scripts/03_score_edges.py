"""엣지 스코어링.

    python scripts/03_score_edges.py --region gyeongju --scorers river,comfort,heritage
"""
import geopandas as gpd
import typer

from leisure_route.config import INTERIM, MVP_SCORERS, PROCESSED
from leisure_route.scoring import get

app = typer.Typer(add_completion=False)


@app.command()
def main(region: str = "gyeongju", scorers: str = ",".join(MVP_SCORERS)):
    edges = gpd.read_file(INTERIM / f"{region}_edges.gpkg")
    for name in scorers.split(","):
        name = name.strip()
        s = get(name)
        edges[f"s_{name}"] = s(edges)
        col = edges[f"s_{name}"]
        typer.echo(f"  s_{name:<9} mean={col.mean():.3f}  nonzero={(col > 0).mean():.1%}")
    out = PROCESSED / f"{region}_scored.gpkg"
    edges.to_file(out, driver="GPKG")
    typer.echo(f"저장: {out}")


if __name__ == "__main__":
    app()
