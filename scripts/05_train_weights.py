"""두루누비 GPX로 가중치 학습 (ADR-003).

    python scripts/05_train_weights.py --region gyeongju

절차:
  1. 두루누비 GPX → 맵매칭 → positive epath
  2. 같은 OD의 최단경로 → negative epath
  3. fit_weights(pairs) → w
  4. pairwise_accuracy 와 엣지 Jaccard 재현율 보고
"""
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(region: str = "gyeongju"):
    raise NotImplementedError("scripts/05_train_weights.py — graph/match.py 완성 후")


if __name__ == "__main__":
    app()
