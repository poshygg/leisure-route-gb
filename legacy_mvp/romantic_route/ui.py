# -*- coding: utf-8 -*-
"""인터랙티브 경로 UI — 사이드패널(경로 카드·축 바·게이트 리포트) + 지배축 채색 지도.

folium(explain.make_map)의 후속. 후보 경로를 카드로 전환하며 보고,
선택된 경로는 간선마다 '지배 축' 색으로 칠한다. 축 색은 dataviz 검증기를
통과한 고정 배정이다 (색은 축을 따라가고, 실행마다 바뀌지 않는다).
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

import numpy as np
import pyproj

from .config import AXES
from .routing import RouteStats, route_edges

# 축 -> 색 고정 배정 (dataviz validate_palette.js 통과 세트)
#  - {조용함, 나무, 문화재}, {조용함, 나무, 꽃}, {조용함, 물가, 나무} all-pairs PASS
#  - WARN(저대비/CVD 6-8 밴드)은 모든 바 직접 라벨 + 범례 + 툴팁으로 보완
AXIS_COLORS: Dict[str, str] = {
    "quiet":    "#2a78d6",   # 파랑
    "trees":    "#1baf7a",   # 청록
    "heritage": "#eda100",   # 황금
    "flower":   "#e34948",   # 적색
    "water":    "#4a3aa7",   # 보라
    "art":      "#eb6834",   # 주황
    "gentle":   "#008300",   # 녹색
    "skyview":  "#d55181",   # 분홍 (파생 축, 동시 표시 드묾)
    "snow":     "#8a8a85",   # 중립 회색 (휴리스틱 축임을 색으로도 드러냄)
}
FALLBACK_COLOR = "#8a8a85"


def _transformer(crs):
    return pyproj.Transformer.from_crs(crs, 4326, always_xy=True)


def _edge_coords(Gp, u, v, d, tf) -> List[List[float]]:
    if d.get("geometry") is not None:
        xs, ys = zip(*d["geometry"].coords)
    else:
        xs = (Gp.nodes[u]["x"], Gp.nodes[v]["x"])
        ys = (Gp.nodes[u]["y"], Gp.nodes[v]["y"])
    lons, lats = tf.transform(xs, ys)
    return [[round(la, 6), round(lo, 6)] for la, lo in zip(lats, lons)]


def _route_segments(Gp, st: RouteStats, weights: Dict[str, float], tf):
    """간선별 [좌표열, 지배축, 축점수] — 연속 동일 지배축은 병합해 용량을 줄인다."""
    segs = []
    for u, v, key, d in route_edges(Gp, st.nodes):
        s = d.get("axis_scores") or {}
        dom = (max(s, key=lambda k: s[k] * weights.get(k, 0.0)) if s else None)
        coords = _edge_coords(Gp, u, v, d, tf)
        if segs and segs[-1]["a"] == dom:
            segs[-1]["c"] += coords[1:]
            n = segs[-1]["n"] + 1
            segs[-1]["s"] = {k: round((segs[-1]["s"].get(k, 0) * (n - 1) + s.get(k, 0)) / n, 3)
                             for k in s}
            segs[-1]["n"] = n
        else:
            segs.append({"c": coords, "a": dom,
                         "s": {k: round(v_, 3) for k, v_ in s.items()}, "n": 1})
    for sg in segs:
        sg.pop("n", None)
    return segs


def _route_pois(Gp, st: RouteStats, feats: Dict[str, dict], keys: List[str],
                crs, tf, radius: float = 120.0, limit: int = 12):
    """경로 주변의 이름 있는 피처 -> 지도에 찍을 점 목록."""
    from .explain import route_geometry
    geom = route_geometry(Gp, st.nodes)
    buf = geom.buffer(radius)
    out, seen = [], set()
    for k in keys:
        f = feats.get(k)
        if not f:
            continue
        for gdf in (f.get("points"), f.get("areas")):
            if gdf is None or gdf.empty or "name" not in gdf.columns:
                continue
            sel = gdf[gdf.geometry.intersects(buf) & gdf["name"].notna()]
            if sel.empty:
                continue
            pts = sel.geometry.representative_point()
            for name, p in zip(sel["name"], pts):
                if not name or (k, name) in seen:
                    continue
                seen.add((k, name))
                lon, lat = tf.transform(p.x, p.y)
                out.append({"axis": k, "name": str(name),
                            "lat": round(lat, 6), "lon": round(lon, 6)})
    # 축별로 골고루 남기기
    by_axis: Dict[str, list] = {}
    for p in out:
        by_axis.setdefault(p["axis"], []).append(p)
    trimmed = []
    per = max(1, limit // max(len(by_axis), 1))
    for k, ps in by_axis.items():
        trimmed += ps[:per]
    return trimmed[:limit]


def build_payload(Gp, stats: List[RouteStats], weights: Dict[str, float],
                  feats: Dict[str, dict], crs,
                  query: str = "", summary: str = "",
                  baseline_nodes: Optional[List[int]] = None,
                  excluded: Optional[List[dict]] = None) -> dict:
    tf = _transformer(crs)
    keys = list(weights)

    routes = []
    for i, st in enumerate(stats, 1):
        routes.append({
            "rank": i,
            "km": round(st.length_m / 1000, 2),
            "min": int(round(st.minutes)),
            "detour": round(st.detour, 2),
            "score": round(st.score, 3),
            "variety": round(st.variety, 2),
            "axis_means": {k: round(v, 3) for k, v in st.axis_means.items()
                           if np.isfinite(v)},
            "segments": _route_segments(Gp, st, weights, tf),
            "pois": _route_pois(Gp, st, feats, keys, crs, tf),
        })

    baseline = None
    if baseline_nodes:
        coords = []
        for u, v, key, d in route_edges(Gp, baseline_nodes):
            cs = _edge_coords(Gp, u, v, d, tf)
            coords += cs if not coords else cs[1:]
        baseline = coords

    return {
        "query": query, "summary": summary,
        "weights": {k: round(v, 3) for k, v in weights.items()},
        "axes": {k: {"label": AXES[k].label,
                     "color": AXIS_COLORS.get(k, FALLBACK_COLOR)}
                 for k in keys},
        "excluded": excluded or [],
        "routes": routes,
        "baseline": baseline,
    }


def make_ui_map(Gp, stats, crs, out_path: str, feats=None, weights=None,
                query: str = "", summary: str = "",
                baseline_nodes=None, excluded=None) -> str:
    payload = build_payload(Gp, stats, weights or {}, feats or {}, crs,
                            query, summary, baseline_nodes, excluded)
    html = _TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>낭만 경로</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{
  --surface:#fcfcfb; --panel:#ffffff; --line:#e8e7e3;
  --ink:#0b0b0b; --ink-2:#52514e; --ink-3:#8a8a85;
  --track:#efeeea; --accent:#2a78d6;
}
*{box-sizing:border-box; margin:0}
html,body{height:100%}
body{
  font-family:"Pretendard Variable",Pretendard,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  background:var(--surface); color:var(--ink); display:flex; overflow:hidden;
}
#side{
  width:352px; min-width:352px; height:100%; overflow-y:auto;
  background:var(--panel); border-right:1px solid var(--line); padding:20px 18px 28px;
}
#map{flex:1; height:100%; background:#eef0ee}
h1{font-size:17px; font-weight:700; letter-spacing:-.2px}
.sub{font-size:12.5px; color:var(--ink-2); margin-top:6px; line-height:1.5}
.query{
  margin-top:10px; padding:9px 12px; background:var(--surface);
  border:1px solid var(--line); border-radius:9px;
  font-size:13px; color:var(--ink-2); line-height:1.45;
}
.query b{color:var(--ink); font-weight:600}
.sect{font-size:11px; font-weight:700; color:var(--ink-3);
  letter-spacing:.08em; margin:20px 0 8px}
.gate{
  border:1px solid var(--line); border-left:3px solid var(--ink-3);
  border-radius:8px; padding:9px 11px; font-size:12px;
  color:var(--ink-2); line-height:1.5; margin-bottom:8px; background:var(--surface);
}
.gate b{color:var(--ink)}
.card{
  border:1px solid var(--line); border-radius:12px; padding:13px 14px;
  margin-bottom:10px; cursor:pointer; background:var(--panel);
  transition:border-color .12s, box-shadow .12s;
}
.card:hover{border-color:#c9c8c2}
.card.on{border-color:var(--ink); box-shadow:0 1px 6px rgba(0,0,0,.07)}
.card-top{display:flex; align-items:baseline; gap:8px}
.rank{
  font-size:11px; font-weight:700; color:var(--ink-2);
  border:1px solid var(--line); border-radius:999px; padding:2px 8px;
}
.card.on .rank{background:var(--ink); color:#fff; border-color:var(--ink)}
.stats{font-size:13.5px; font-weight:650}
.stats .dim{color:var(--ink-3); font-weight:400; margin:0 1px}
.score{margin-left:auto; font-size:13px; font-weight:700}
.score .lbl{font-size:10.5px; font-weight:500; color:var(--ink-3); margin-right:3px}
.bars{margin-top:11px; display:grid; gap:7px}
.bar-row{display:grid; grid-template-columns:70px 1fr 40px; gap:8px; align-items:center}
.bar-lbl{font-size:11.5px; color:var(--ink-2); display:flex; align-items:center; gap:5px}
.dot{width:8px; height:8px; border-radius:50%; flex:none}
.track{display:block; height:6px; background:var(--track); border-radius:4px; overflow:hidden}
.fill{display:block; height:100%; border-radius:4px}
.bar-val{font-size:11px; color:var(--ink-2); text-align:right;
  font-variant-numeric:tabular-nums}
.meta-row{margin-top:10px; display:flex; gap:6px; flex-wrap:wrap}
.chip{font-size:10.5px; color:var(--ink-2); border:1px solid var(--line);
  border-radius:999px; padding:2.5px 8px; background:var(--surface)}
.pois{margin-top:10px; border-top:1px dashed var(--line); padding-top:9px;
  display:none; flex-wrap:wrap; gap:5px}
.card.on .pois{display:flex}
.poi{font-size:11px; color:var(--ink-2); display:inline-flex; align-items:center;
  gap:5px; border:1px solid var(--line); border-radius:7px; padding:3px 8px}
.legend-box{display:grid; gap:6px; font-size:12px; color:var(--ink-2)}
.legend-box .row{display:flex; align-items:center; gap:8px}
.swatch{width:18px; height:5px; border-radius:3px; flex:none}
.dash{width:18px; border-top:2px dashed var(--ink-3); flex:none}
.foot{margin-top:22px; font-size:11px; color:var(--ink-3); line-height:1.6}
.leaflet-tooltip.seg-tip{
  font-family:inherit; font-size:12px; line-height:1.5;
  border:1px solid var(--line); box-shadow:0 2px 8px rgba(0,0,0,.09);
  border-radius:8px; padding:7px 10px;
}
.seg-tip b{font-size:12px}
.seg-tip .r{display:flex; align-items:center; gap:6px; margin-top:3px; color:var(--ink-2)}
.pin{
  width:12px; height:12px; border-radius:50%;
  border:2.5px solid #fff; box-shadow:0 1px 4px rgba(0,0,0,.35);
}
.ep{
  font-size:11px; font-weight:700; color:#fff; background:var(--ink);
  border-radius:999px; padding:3px 9px; white-space:nowrap;
  box-shadow:0 1px 5px rgba(0,0,0,.3); transform:translate(-50%,-50%);
  display:inline-block;
}
@media (max-width:760px){
  body{flex-direction:column}
  #side{width:100%; min-width:0; height:46%; order:2; border-right:0;
    border-top:1px solid var(--line)}
  #map{height:54%}
}
</style>
</head>
<body>
<div id="side">
  <h1>낭만 경로</h1>
  <div class="sub" id="sub"></div>
  <div class="query" id="query"></div>
  <div id="gates"></div>
  <div class="sect">추천 경로</div>
  <div id="cards"></div>
  <div class="sect">범례</div>
  <div class="legend-box" id="legend"></div>
  <div class="foot">간선을 지배 축 색으로 칠했다 — 그 구간에서 무엇이 가장 좋은지가 색이다.<br>
  점수는 간선 길이 가중 평균(0~1). 회색 점선은 최단경로 기준선.</div>
</div>
<div id="map"></div>
<script>
const D = __PAYLOAD__;
const GRAY = "#b7b6b0";

const map = L.map("map", {zoomControl:true});
L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  {attribution:"&copy; OpenStreetMap &copy; CARTO", maxZoom:19}).addTo(map);

const layers = {baseline:L.layerGroup().addTo(map),
                others:L.layerGroup().addTo(map),
                casing:L.layerGroup().addTo(map),
                segs:L.layerGroup().addTo(map),
                pois:L.layerGroup().addTo(map),
                ends:L.layerGroup().addTo(map)};
let sel = 0;

function axColor(k){ return (D.axes[k]||{}).color || GRAY; }
function axLabel(k){ return (D.axes[k]||{}).label || k; }
function fullCoords(r){ return r.segments.flatMap((s,i)=> i? s.c.slice(1): s.c); }

function segTip(seg){
  let h = "<b>"+ (seg.a? axLabel(seg.a): "—") +" 구간</b>";
  const ks = Object.keys(seg.s||{}).sort((a,b)=>seg.s[b]-seg.s[a]);
  for(const k of ks){
    h += '<div class="r"><span class="dot" style="background:'+axColor(k)+'"></span>'
       + axLabel(k) + " " + Math.round(seg.s[k]*100) + "%</div>";
  }
  return h;
}

function draw(){
  for(const k in layers) layers[k].clearLayers();
  const r = D.routes[sel];

  if(D.baseline){
    L.polyline(D.baseline, {color:"#52514e", weight:2, opacity:.65,
      dashArray:"5 7", interactive:false}).addTo(layers.baseline);
  }
  D.routes.forEach((o,i)=>{
    if(i===sel) return;
    L.polyline(fullCoords(o), {color:GRAY, weight:4, opacity:.55})
      .on("click", ()=>select(i))
      .bindTooltip("경로 "+o.rank+" · "+o.km+"km · 점수 "+o.score,
                   {sticky:true, className:"seg-tip"})
      .addTo(layers.others);
  });
  L.polyline(fullCoords(r), {color:"#ffffff", weight:10, opacity:.9,
    interactive:false}).addTo(layers.casing);
  r.segments.forEach(seg=>{
    L.polyline(seg.c, {color: seg.a? axColor(seg.a): GRAY, weight:6, opacity:.95})
      .bindTooltip(segTip(seg), {sticky:true, className:"seg-tip"})
      .addTo(layers.segs);
  });
  r.pois.forEach(p=>{
    L.marker([p.lat,p.lon], {icon:L.divIcon({className:"", iconSize:[12,12],
        html:'<div class="pin" style="background:'+axColor(p.axis)+'"></div>'})})
      .bindTooltip(axLabel(p.axis)+" · "+p.name, {className:"seg-tip", direction:"top"})
      .addTo(layers.pois);
  });
  const cs = fullCoords(r);
  const mk = (ll,txt)=> L.marker(ll,{icon:L.divIcon({className:"",iconSize:[0,0],
      html:'<span class="ep">'+txt+'</span>'}), interactive:false}).addTo(layers.ends);
  mk(cs[0],"출발"); mk(cs[cs.length-1],"도착");
}

function select(i){
  sel = i;
  document.querySelectorAll(".card").forEach((el,j)=>el.classList.toggle("on", j===i));
  draw();
  map.fitBounds(L.polyline(fullCoords(D.routes[i])).getBounds(), {padding:[46,46]});
}

/* ---- 사이드패널 ---- */
document.getElementById("sub").textContent =
  "후보 " + D.routes.length + "개 · 활성 축 " + Object.keys(D.axes).length + "개";
document.getElementById("query").innerHTML =
  (D.query? "“<b>"+D.query+"</b>”": "") +
  (D.summary? '<div style="margin-top:4px">해석: '+D.summary+"</div>": "");

const gates = document.getElementById("gates");
if(D.excluded.length){
  const g = document.createElement("div");
  g.innerHTML = '<div class="sect">데이터 게이트</div>' + D.excluded.map(e=>
    '<div class="gate"><b>'+e.label+'</b> 축 제외 — '+e.reason+'</div>').join("");
  gates.appendChild(g);
}

const cards = document.getElementById("cards");
D.routes.forEach((r,i)=>{
  const el = document.createElement("div");
  el.className = "card" + (i===0? " on":"");
  const ks = Object.keys(r.axis_means).sort((a,b)=>(D.weights[b]||0)-(D.weights[a]||0));
  el.innerHTML =
    '<div class="card-top"><span class="rank">'+r.rank+'위</span>'
    + '<span class="stats">'+r.km+'<span class="dim">km</span> · '
    + r.min+'<span class="dim">분</span> · '
    + '<span class="dim">우회</span> '+r.detour+'x</span>'
    + '<span class="score"><span class="lbl">종합</span>'+r.score.toFixed(3)+'</span></div>'
    + '<div class="bars">' + ks.map(k=>{
        const v = r.axis_means[k];
        return '<div class="bar-row"><span class="bar-lbl">'
          + '<span class="dot" style="background:'+axColor(k)+'"></span>'+axLabel(k)+'</span>'
          + '<span class="track"><span class="fill" style="width:'+Math.round(v*100)
          + '%;background:'+axColor(k)+'"></span></span>'
          + '<span class="bar-val">'+Math.round(v*100)+'%</span></div>';
      }).join("") + '</div>'
    + '<div class="meta-row"><span class="chip">변화도 '+r.variety.toFixed(2)+'</span>'
    + ks.map(k=>'<span class="chip">'+axLabel(k)+' 가중치 '
        + Math.round((D.weights[k]||0)*100)+'%</span>').join("") + '</div>'
    + (r.pois.length?
        '<div class="pois">'+ r.pois.map(p=>
          '<span class="poi"><span class="dot" style="background:'+axColor(p.axis)
          +'"></span>'+p.name+'</span>').join("") + '</div>' : "");
  el.addEventListener("click", ()=>select(i));
  cards.appendChild(el);
});

const legend = document.getElementById("legend");
legend.innerHTML = Object.keys(D.axes).map(k=>
  '<div class="row"><span class="swatch" style="background:'+axColor(k)+'"></span>'
  + axLabel(k)+' 구간</div>').join("")
  + '<div class="row"><span class="swatch" style="background:'+GRAY+'"></span>다른 후보 경로</div>'
  + (D.baseline? '<div class="row"><span class="dash"></span>최단경로 기준선</div>': "");

draw();
map.fitBounds(L.polyline(fullCoords(D.routes[0])).getBounds(), {padding:[46,46]});
</script>
</body>
</html>
"""
