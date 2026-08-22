"""스코어러 레지스트리."""
from .artwork import ArtworkScorer
from .base import NotImplementedScorer, Scorer
from .building import BuildingScorer
from .comfort import ComfortScorer
from .flower import FlowerScorer
from .heritage import HeritageScorer
from .quiet import QuietScorer
from .river import RiverScorer
from .sky import SkyScorer
from .street import StreetScorer
from .tree import TreeScorer

#: 이름 → 클래스. config.SCORE_COLS 의 s_<name> 과 대응합니다.
REGISTRY: dict[str, type[Scorer]] = {
    "river": RiverScorer,
    "comfort": ComfortScorer,
    "heritage": HeritageScorer,
    "tree": TreeScorer,
    "flower": FlowerScorer,
    "sky": SkyScorer,
    "artwork": ArtworkScorer,
    "street": StreetScorer,
    "quiet": QuietScorer,
    "building": BuildingScorer,
}


def get(name: str) -> Scorer:
    if name not in REGISTRY:
        raise KeyError(f"unknown scorer: {name!r}. 사용 가능: {sorted(REGISTRY)}")
    return REGISTRY[name]()


__all__ = ["Scorer", "NotImplementedScorer", "REGISTRY", "get"]
