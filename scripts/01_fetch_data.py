"""데이터 수집. 원본은 커밋하지 않으므로 받는 방법을 여기 코드로 남깁니다.

수동 다운로드가 필요한 것 (API 없음):
  - 국가유산청_문화재 공간 정보 SHP : https://www.data.go.kr/data/3070426/openapi.do
      → data/raw/heritage/ 에 압축 해제
      → ★ .prj 확인 후 EPSG:4326 변환 (ADR-005)
      → ★ geometry 타입 분포 확인 (전부 폴리곤이 아닐 수 있음)
  - 국토지리정보원 DEM 5m        : 국토정보플랫폼 (회원가입 필요)
      → data/raw/dem/
  - OSM 한국 추출본              : https://download.geofabrik.de/asia/south-korea.html
      → data/raw/south-korea-latest.osm.pbf
"""
import typer

app = typer.Typer(add_completion=False)


@app.command()
def durunubi():
    """두루누비 284코스 GPX → data/raw/durunubi/  (학습 정답셋)"""
    raise NotImplementedError


@app.command()
def street_trees():
    """전국가로수길정보표준데이터 → data/raw/street_trees.csv"""
    raise NotImplementedError


if __name__ == "__main__":
    app()
