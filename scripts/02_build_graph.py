"""OSM 보행 그래프 구축 + 연결성 점검.

    python scripts/02_build_graph.py --region gyeongju
"""
import typer

from leisure_route.config import REGIONS
from leisure_route.graph import build_pedestrian_graph

app = typer.Typer(add_completion=False)


@app.command()
def main(region: str = "gyeongju"):
    meta = REGIONS[region]
    typer.echo(f"[{region}] {meta['name']} 보행 그래프 구축")
    G = build_pedestrian_graph(f"{meta['name']}, 경상북도, South Korea")
    typer.echo(f"  nodes={G.number_of_nodes()}  edges={G.number_of_edges()}")
    typer.echo("  ★ 3단계 게이트 실패의 주원인은 OSM 보행로 누락입니다. 연결성을 먼저 보세요.")
    # TODO: DEM 부착 → edges['grade'],  data/interim/{region}_edges.gpkg 저장


if __name__ == "__main__":
    app()
