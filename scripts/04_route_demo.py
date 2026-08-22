"""라우팅 데모 — 3단계 "눈으로 검증" 게이트용.

    python scripts/04_route_demo.py --region gyeongju \
        --from-latlon 35.8562,129.2247 --to-latlon 35.8348,129.2194

결과를 folium 지도로 뽑아 실제로 보세요. "오 이 길 좋네"가 안 나오면
데이터를 더 넣지 말고 멈추세요 (ADR-004).
"""
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    region: str = "gyeongju",
    from_latlon: str = typer.Option(..., "--from-latlon"),
    to_latlon: str = typer.Option(..., "--to-latlon"),
):
    raise NotImplementedError("scripts/04_route_demo.py — 그래프 로딩 후 Router.options() 호출")


if __name__ == "__main__":
    app()
