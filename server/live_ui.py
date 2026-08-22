# -*- coding: utf-8 -*-
"""MVP UI(romantic_route/ui.py `_TEMPLATE`)를 '살아있는' 페이지로 바꾸는 패처.

원칙: **MVP UI 를 다시 쓰지 않는다.** 원본 템플릿을 그대로 읽어와서
정확히 정해진 앵커 몇 군데만 바꾸고, 조작 패널과 fetch 레이어를 뒤에 덧붙인다.
CSS·카드·게이트·범례·지배축 채색은 전부 원본 그대로다.

앵커가 하나라도 안 맞으면 기동 시점에 바로 죽는다 (조용히 깨진 UI 를 내보내지 않기 위해).
MVP 쪽 ui.py 를 고쳤다면 여기 PATCHES 도 같이 고쳐야 한다.
"""

from __future__ import annotations

# engine 이 romantic_route 를 sys.path 에 올리고 ui 를 다시 내보낸다.
# 여기서 romantic_route 를 직접 import 하면 import 순서에 따라 깨지므로 engine 을 거친다.
from engine import ui

# (설명, 찾을 문자열, 바꿀 문자열)
PATCHES = [
    (
        "payload 를 상수 → 교체 가능한 변수로",
        "const D = __PAYLOAD__;",
        "let D = null;",
    ),
    (
        "사이드패널 구축 블록을 재호출 가능한 함수로",
        "/* ---- 사이드패널 ---- */",
        "function render(){\n  sel = 0;",
    ),
    (
        "게이트 컨테이너를 매 렌더마다 비우기",
        'const gates = document.getElementById("gates");',
        'const gates = document.getElementById("gates");\ngates.innerHTML = "";',
    ),
    (
        "카드 컨테이너를 매 렌더마다 비우기",
        'const cards = document.getElementById("cards");',
        'const cards = document.getElementById("cards");\ncards.innerHTML = "";',
    ),
    (
        "최초 draw/fitBounds 를 render() 안으로 닫기",
        "draw();\nmap.fitBounds(L.polyline(fullCoords(D.routes[0])).getBounds(), {padding:[46,46]});\n</script>",
        "draw();\nmap.fitBounds(L.polyline(fullCoords(D.routes[0])).getBounds(), {padding:[46,46]});\n}\n</script>",
    ),
    (
        "조작 패널을 사이드바 맨 위에 삽입",
        "<h1>낭만 경로</h1>",
        "<h1>여유길</h1>\n__CONTROLS__",
    ),
    (
        "탭 제목도 저장소 이름에 맞춤",
        "<title>낭만 경로</title>",
        "<title>여유길 — 경북 여유로운 보행 경로</title>",
    ),
]

CONTROLS = """
<div id="ctl">
  <div class="ctl-row">
    <button class="pick" id="pick-o" data-slot="o"><i class="mk o"></i><span id="lab-o">출발지를 지정하세요</span></button>
    <button class="swap" id="swap" title="출발↔도착">⇅</button>
  </div>
  <div class="ctl-row">
    <button class="pick" id="pick-d" data-slot="d"><i class="mk d"></i><span id="lab-d">도착지를 지정하세요</span></button>
    <button class="swap" id="gps" title="현재 위치를 출발지로">◎</button>
  </div>
  <div class="hint" id="hint">칸을 누른 뒤 지도를 클릭하면 지정됩니다.</div>
  <input id="q" class="q-in" placeholder="장소 검색 (예: 감은사지, 호미곶)" autocomplete="off">
  <div id="q-res"></div>
  <div class="ax-wrap" id="ax"></div>
  <div class="ctl-row">
    <select id="strength" title="여유로움을 얼마나 강하게 밀어붙일지">
      <option value="1.0">부드럽게</option>
      <option value="2.0" selected>보통</option>
      <option value="3.5">강하게</option>
    </select>
    <select id="k" title="후보 경로 수">
      <option value="2">후보 2</option>
      <option value="3" selected>후보 3</option>
      <option value="4">후보 4</option>
    </select>
  </div>
  <button id="go" class="go">여유 경로 탐색</button>
  <div id="status"></div>
  <div id="drop-wrap"></div>
  <button id="guide" class="go alt">보행 안내 시작</button>
</div>

<div id="nav">
  <div class="nav-top">
    <span class="nav-next" id="nav-next">—</span>
    <button id="nav-stop">종료</button>
  </div>
  <div class="nav-track"><span id="nav-fill"></span></div>
  <div class="nav-meta" id="nav-meta"></div>
</div>
"""

EXTRA_CSS = """
<style>
#ctl{margin-top:12px; display:grid; gap:7px}
.ctl-row{display:flex; gap:6px; align-items:stretch}
.pick{
  flex:1; min-width:0; display:flex; align-items:center; gap:8px; text-align:left;
  font:inherit; font-size:12.5px; color:var(--ink); background:var(--surface);
  border:1px solid var(--line); border-radius:9px; padding:9px 11px; cursor:pointer;
}
.pick:hover{border-color:#c9c8c2}
.pick.armed{border-color:var(--ink); box-shadow:0 0 0 2px rgba(0,0,0,.05)}
.pick span{overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.mk{width:9px; height:9px; border-radius:50%; flex:none; border:2px solid #fff;
    box-shadow:0 0 0 1px rgba(0,0,0,.25)}
.mk.o{background:#0b0b0b} .mk.d{background:#e34948}
.swap{font:inherit; font-size:14px; line-height:1; color:var(--ink-2); background:var(--surface);
  border:1px solid var(--line); border-radius:9px; width:38px; cursor:pointer}
.swap:hover{border-color:#c9c8c2}
.hint{font-size:11px; color:var(--ink-3); line-height:1.5}
.q-in{
  font:inherit; font-size:12.5px; color:var(--ink); background:var(--panel);
  border:1px solid var(--line); border-radius:9px; padding:9px 11px; width:100%;
}
.q-in:focus{outline:none; border-color:var(--ink)}
#q-res{display:none; border:1px solid var(--line); border-radius:9px; overflow:hidden}
#q-res.on{display:block}
.q-hit{display:block; width:100%; text-align:left; font:inherit; font-size:12px;
  padding:8px 11px; background:var(--panel); border:0; border-top:1px solid var(--line);
  cursor:pointer; color:var(--ink)}
#q-res .q-hit:first-child{border-top:0}
.q-hit:hover{background:var(--surface)}
.q-hit small{display:block; color:var(--ink-3); font-size:10.5px; margin-top:1px}
.ax-wrap{display:flex; flex-wrap:wrap; gap:5px}
.ax{font-size:11.5px; color:var(--ink-2); border:1px solid var(--line); background:var(--surface);
  border-radius:999px; padding:4px 10px; cursor:pointer; display:inline-flex;
  align-items:center; gap:5px; user-select:none}
.ax.on{color:var(--ink); border-color:var(--ink)}
.ax .dot{opacity:.28}
.ax.on .dot{opacity:1}
#ctl select{font:inherit; font-size:12px; color:var(--ink); background:var(--surface);
  border:1px solid var(--line); border-radius:9px; padding:8px 9px; flex:1; cursor:pointer}
.go{
  font:inherit; font-size:13px; font-weight:650; color:#fff; background:var(--ink);
  border:0; border-radius:9px; padding:11px; cursor:pointer; width:100%;
}
.go:disabled{background:#c9c8c2; cursor:default}
.go.alt{background:var(--panel); color:var(--ink); border:1px solid var(--ink)}
.go.alt:disabled{background:var(--panel); color:var(--ink-3); border-color:var(--line)}
#status{font-size:11.5px; line-height:1.5; color:var(--ink-3); min-height:1px}
#status.err{color:#c0392b}

/* 제외한 경유 요소 */
#drop-wrap:empty{display:none}
.drop-head{font-size:11px; font-weight:700; color:var(--ink-3); letter-spacing:.08em; margin:4px 0 6px}
.drop{display:flex; align-items:center; gap:7px; font-size:11.5px; color:var(--ink-2);
  border:1px dashed var(--line); border-radius:8px; padding:6px 9px; margin-bottom:5px}
.drop span{flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  text-decoration:line-through}
.drop button{font:inherit; font-size:11px; font-weight:650; color:var(--ink); background:var(--panel);
  border:1px solid var(--line); border-radius:6px; padding:3px 8px; cursor:pointer}
.drop button:hover{border-color:var(--ink)}

/* 경유 요소 칩에 붙는 삭제 버튼 (MVP 카드의 .poi 를 후처리) */
.poi .x{margin-left:2px; color:var(--ink-3); cursor:pointer; font-weight:700; padding:0 1px}
.poi .x:hover{color:#c0392b}

/* 보행 안내 */
/* JS 가 #map 안으로 옮긴다 (지도 위에 뜨도록) */
#nav{display:none; position:absolute; left:50%; transform:translateX(-50%); bottom:18px;
  width:min(420px, calc(100% - 32px)); z-index:1000;
  background:var(--panel); border:1px solid var(--line); border-radius:13px;
  box-shadow:0 4px 18px rgba(0,0,0,.14); padding:12px 14px}
#nav.on{display:block}
.nav-top{display:flex; align-items:center; gap:10px}
.nav-next{flex:1; min-width:0; font-size:14px; font-weight:650; overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap}
#nav-stop{font:inherit; font-size:11.5px; color:var(--ink-2); background:var(--surface);
  border:1px solid var(--line); border-radius:7px; padding:5px 10px; cursor:pointer}
.nav-track{height:6px; background:var(--track); border-radius:4px; overflow:hidden; margin:9px 0 7px}
#nav-fill{display:block; height:100%; width:0%; background:var(--ink); border-radius:4px;
  transition:width .3s}
.nav-meta{font-size:11.5px; color:var(--ink-2); display:flex; gap:12px; flex-wrap:wrap}
.me{width:14px; height:14px; border-radius:50%; background:#2a78d6;
  border:3px solid #fff; box-shadow:0 1px 5px rgba(0,0,0,.4)}
</style>
"""

LIVE_JS = """
<script>
/* ---- 라이브 레이어 (MVP UI 위에 얹는 조작·통신 부분) ----------------- */
const AXES_META = __AXES_META__;
const DEFAULT_O = __DEFAULT_O__;
const DEFAULT_D = __DEFAULT_D__;

const S = {o: null, d: null, armed: null, axes: AXES_META.map(a => a.key), drops: []};
const marks = L.layerGroup().addTo(map);
map.setView([(DEFAULT_O[0] + DEFAULT_D[0]) / 2, (DEFAULT_O[1] + DEFAULT_D[1]) / 2], 13);

const $ = (id) => document.getElementById(id);
const fmt = (p) => p.name || (p.lat.toFixed(5) + ", " + p.lng.toFixed(5));

function setStatus(msg, isErr) {
  const el = $("status");
  el.textContent = msg || "";
  el.className = isErr ? "err" : "";
}

function drawMarks() {
  marks.clearLayers();
  for (const slot of ["o", "d"]) {
    const p = S[slot];
    if (!p) continue;
    L.marker([p.lat, p.lng], {icon: L.divIcon({className: "", iconSize: [12, 12],
      html: '<div class="pin" style="background:' + (slot === "o" ? "#0b0b0b" : "#e34948") + '"></div>'})})
      .addTo(marks);
  }
}

function setPoint(slot, p) {
  S[slot] = p;
  $("lab-" + slot).textContent = fmt(p);
  drawMarks();
  arm(null);
  if (!p.name) {
    fetch("/api/reverse?lng=" + p.lng + "&lat=" + p.lat)
      .then(r => r.json())
      .then(j => { if (S[slot] === p) { p.name = j.placeName; $("lab-" + slot).textContent = fmt(p); } })
      .catch(() => {});
  }
}

function arm(slot) {
  S.armed = slot;
  $("pick-o").classList.toggle("armed", slot === "o");
  $("pick-d").classList.toggle("armed", slot === "d");
  $("hint").textContent = slot
    ? (slot === "o" ? "지도를 클릭해 출발지를 찍으세요." : "지도를 클릭해 도착지를 찍으세요.")
    : "칸을 누른 뒤 지도를 클릭하면 지정됩니다.";
}

$("pick-o").onclick = () => arm(S.armed === "o" ? null : "o");
$("pick-d").onclick = () => arm(S.armed === "d" ? null : "d");
$("swap").onclick = () => {
  const a = S.o, b = S.d;
  if (a) setPoint("d", a); if (b) setPoint("o", b);
};
map.on("click", (e) => {
  if (!S.armed) return;
  setPoint(S.armed, {lat: +e.latlng.lat.toFixed(6), lng: +e.latlng.lng.toFixed(6), name: null});
});

/* 축 토글 */
const axWrap = $("ax");
AXES_META.forEach(a => {
  const b = document.createElement("button");
  b.className = "ax on";
  b.innerHTML = '<span class="dot" style="background:' + a.color + '"></span>' + a.label;
  b.onclick = () => {
    const i = S.axes.indexOf(a.key);
    if (i >= 0 && S.axes.length === 1) return;   // 최소 1개는 남긴다
    if (i >= 0) S.axes.splice(i, 1); else S.axes.push(a.key);
    b.classList.toggle("on", i < 0);
  };
  axWrap.appendChild(b);
});

/* 장소 검색 */
let qTimer = null;
$("q").addEventListener("input", (e) => {
  const q = e.target.value.trim();
  clearTimeout(qTimer);
  if (q.length < 2) { $("q-res").className = ""; $("q-res").innerHTML = ""; return; }
  qTimer = setTimeout(() => {
    fetch("/api/search?q=" + encodeURIComponent(q))
      .then(r => r.json())
      .then(hits => {
        const box = $("q-res");
        box.innerHTML = "";
        if (!hits.length) { box.className = ""; return; }
        hits.forEach(h => {
          const b = document.createElement("button");
          b.className = "q-hit";
          b.innerHTML = h.name + "<small>" + (h.addr || h.reason || "") + "</small>";
          b.onclick = () => {
            const slot = S.armed || (!S.o ? "o" : "d");
            setPoint(slot, {lat: h.lat, lng: h.lng, name: h.name});
            map.setView([h.lat, h.lng], 15);
            box.className = ""; box.innerHTML = ""; $("q").value = "";
          };
          box.appendChild(b);
        });
        box.className = "on";
      })
      .catch(() => {});
  }, 250);
});

/* 탐색 */
let busy = false;
function plan() {
  if (busy) return;
  if (!S.o || !S.d) { setStatus("출발지와 도착지를 모두 지정해 주세요.", true); return; }
  busy = true;
  $("go").disabled = true;
  setStatus("경로를 찾는 중…");
  const ex = S.drops.map(p => p.lat + "," + p.lng).join(";");
  const u = "/api/plan?from=" + S.o.lat + "," + S.o.lng + "&to=" + S.d.lat + "," + S.d.lng
          + "&axes=" + S.axes.join(",") + "&k=" + $("k").value + "&strength=" + $("strength").value
          + (ex ? "&exclude=" + encodeURIComponent(ex) : "");
  fetch(u)
    .then(async r => {
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "탐색에 실패했습니다.");
      return j;
    })
    .then(j => {
      D = j;
      render();
      afterRender();
      drawMarks();
      const m = j.meta || {};
      setStatus("보행망 " + (m.graph ? m.graph.nodes.toLocaleString() + "노드" : "")
        + " · 기준선 " + (m.baselineKm || "?") + "km"
        + (m.diversityFeasible === false ? " · 대안 경로가 거의 없는 구간입니다" : "")
        + (S.drops.length ? " · 경유지 " + S.drops.length + "곳 제외" : ""));
    })
    .catch(e => setStatus(e.message, true))
    .finally(() => { busy = false; $("go").disabled = false; });
}
$("go").onclick = plan;

/* ---- 현재 위치 (GPS) --------------------------------------------- */
let meMark = null;
function gpsOnce(slot) {
  if (!navigator.geolocation) { setStatus("이 브라우저는 위치 기능을 지원하지 않습니다.", true); return; }
  setStatus("현재 위치를 확인하는 중…");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const p = {lat: +pos.coords.latitude.toFixed(6), lng: +pos.coords.longitude.toFixed(6), name: null};
      setPoint(slot, p);
      map.setView([p.lat, p.lng], 15);
      setStatus("현재 위치를 " + (slot === "o" ? "출발지" : "도착지") + "로 잡았습니다.");
    },
    (err) => setStatus(gpsMsg(err), true),
    {enableHighAccuracy: true, timeout: 10000, maximumAge: 30000}
  );
}
function gpsMsg(err) {
  if (err && err.code === 1) return "위치 권한이 거부됐습니다. 브라우저 주소창의 자물쇠에서 허용해 주세요.";
  if (err && err.code === 3) return "위치 확인이 시간 내에 끝나지 않았습니다.";
  if (!window.isSecureContext) return "http 접속에서는 브라우저가 위치를 막습니다 (localhost 또는 https 필요).";
  return "현재 위치를 가져오지 못했습니다.";
}
$("gps").onclick = () => gpsOnce(S.armed || "o");

/* ---- 경유 요소 제외 · 복원 ---------------------------------------- */
function poiKey(p) { return p.lat.toFixed(5) + "," + p.lng.toFixed(5); }

function dropPoi(p) {
  if (S.drops.some(q => poiKey(q) === poiKey(p))) return;
  S.drops.push(p);
  plan();
}
function restorePoi(key) {
  S.drops = S.drops.filter(q => poiKey(q) !== key);
  plan();
}

function renderDrops() {
  const box = $("drop-wrap");
  box.innerHTML = "";
  if (!S.drops.length) return;
  const h = document.createElement("div");
  h.className = "drop-head";
  h.textContent = "제외한 경유 요소 " + S.drops.length;
  box.appendChild(h);
  S.drops.forEach(p => {
    const row = document.createElement("div");
    row.className = "drop";
    const s = document.createElement("span");
    s.textContent = p.name;
    const b = document.createElement("button");
    b.textContent = "되돌리기";
    b.onclick = () => restorePoi(poiKey(p));
    row.appendChild(s); row.appendChild(b);
    box.appendChild(row);
  });
}

/** MVP 카드가 그린 .poi 칩에 삭제 버튼만 덧붙인다 (원본 렌더 코드는 건드리지 않는다) */
function decoratePois() {
  D.routes.forEach((r, ri) => {
    const card = document.querySelectorAll(".card")[ri];
    if (!card) return;
    const chips = card.querySelectorAll(".poi");
    r.pois.forEach((p, pi) => {
      const chip = chips[pi];
      if (!chip || chip.querySelector(".x")) return;
      const x = document.createElement("span");
      x.className = "x";
      x.textContent = "×";
      x.title = p.name + " 빼고 다시 찾기";
      x.onclick = (e) => {
        e.stopPropagation();
        dropPoi({lat: p.lat, lng: p.lon, name: p.name});
      };
      chip.appendChild(x);
    });
  });
}

function afterRender() {
  decoratePois();
  renderDrops();
  $("guide").disabled = !(D && D.routes && D.routes.length);
  if (NAV.on) navStop();
}

/* ---- 보행 안내 ----------------------------------------------------- */
const NAV = {on: false, watch: null, line: null, cum: null, pois: null};
const navEl = $("nav");
document.getElementById("map").appendChild(navEl);   // 지도 위로 옮긴다

function hav(a, b) {
  const R = 6371000, rad = Math.PI / 180;
  const dLat = (b[0] - a[0]) * rad, dLng = (b[1] - a[1]) * rad;
  const la1 = a[0] * rad, la2 = b[0] * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}
function cumulative(line) {
  const c = [0];
  for (let i = 1; i < line.length; i++) c.push(c[i - 1] + hav(line[i - 1], line[i]));
  return c;
}
/** 점을 경로 위로 투영 → {along: 시작점부터의 거리(m), off: 경로에서 벗어난 거리(m)} */
function projectOn(line, cum, p) {
  let best = {along: 0, off: Infinity};
  const kx = Math.cos(p[0] * Math.PI / 180) * 111320, ky = 110540;
  const px = p[1] * kx, py = p[0] * ky;
  for (let i = 1; i < line.length; i++) {
    const ax = line[i - 1][1] * kx, ay = line[i - 1][0] * ky;
    const bx = line[i][1] * kx, by = line[i][0] * ky;
    const dx = bx - ax, dy = by - ay;
    const L2 = dx * dx + dy * dy;
    let t = L2 ? ((px - ax) * dx + (py - ay) * dy) / L2 : 0;
    t = Math.max(0, Math.min(1, t));
    const qx = ax + dx * t, qy = ay + dy * t;
    const off = Math.hypot(px - qx, py - qy);
    if (off < best.off) best = {along: cum[i - 1] + Math.hypot(qx - ax, qy - ay), off: off};
  }
  return best;
}
function metersText(m) { return m >= 1000 ? (m / 1000).toFixed(1) + "km" : Math.round(m / 10) * 10 + "m"; }

function navStart() {
  if (!D || !D.routes[sel]) return;
  if (!navigator.geolocation) { setStatus("이 브라우저는 위치 기능을 지원하지 않습니다.", true); return; }
  NAV.line = fullCoords(D.routes[sel]);
  NAV.cum = cumulative(NAV.line);
  const total = NAV.cum[NAV.cum.length - 1];
  NAV.pois = (D.routes[sel].pois || []).map(p => {
    const pr = projectOn(NAV.line, NAV.cum, [p.lat, p.lon]);
    return {name: p.name, axis: p.axis, along: pr.along};
  }).sort((a, b) => a.along - b.along);

  NAV.on = true;
  navEl.classList.add("on");
  $("guide").textContent = "보행 안내 종료";
  setStatus("위치를 따라 안내합니다.");

  NAV.watch = navigator.geolocation.watchPosition(
    (pos) => navTick([pos.coords.latitude, pos.coords.longitude], total, pos.coords.accuracy),
    (err) => { setStatus(gpsMsg(err), true); navStop(); },
    {enableHighAccuracy: true, timeout: 15000, maximumAge: 2000}
  );
}

function navTick(here, total, acc) {
  const pr = projectOn(NAV.line, NAV.cum, here);
  const done = Math.max(0, Math.min(total, pr.along));
  const remain = total - done;
  const pct = total ? (done / total) * 100 : 0;

  if (!meMark) {
    meMark = L.marker(here, {icon: L.divIcon({className: "", iconSize: [14, 14],
      html: '<div class="me"></div>'})}).addTo(map);
  } else meMark.setLatLng(here);
  map.panTo(here, {animate: true, duration: .4});

  const next = NAV.pois.find(p => p.along > done + 5);
  $("nav-next").textContent = next
    ? (axLabel(next.axis) + " · " + next.name + " " + metersText(next.along - done))
    : "도착지까지 " + metersText(remain);
  $("nav-fill").style.width = pct.toFixed(1) + "%";
  $("nav-meta").innerHTML =
    "<span>남은 " + metersText(remain) + "</span>"
    + "<span>약 " + Math.max(1, Math.round(remain / 67)) + "분</span>"
    + "<span>" + Math.round(pct) + "%</span>"
    + (pr.off > 40 ? '<span style="color:#c0392b">경로에서 ' + metersText(pr.off) + " 벗어남</span>" : "")
    + (acc && acc > 50 ? '<span style="color:var(--ink-3)">위치 정확도 ±' + Math.round(acc) + "m</span>" : "");

  if (remain < 25) {
    $("nav-next").textContent = "목적지에 도착했습니다";
    navStop(true);
  }
}

function navStop(arrived) {
  if (NAV.watch !== null) navigator.geolocation.clearWatch(NAV.watch);
  NAV.watch = null;
  NAV.on = false;
  $("guide").textContent = "보행 안내 시작";
  if (!arrived) navEl.classList.remove("on");
}

$("guide").onclick = () => NAV.on ? navStop() : navStart();
$("nav-stop").onclick = () => { navStop(); navEl.classList.remove("on"); };

$("guide").disabled = true;

/* 첫 진입 — 기본 구간으로 한 번 그려 준다 */
setPoint("o", {lat: DEFAULT_O[0], lng: DEFAULT_O[1], name: null});
setPoint("d", {lat: DEFAULT_D[0], lng: DEFAULT_D[1], name: null});
plan();
</script>
"""


def build_live_html(axes_meta: list, default_o: tuple, default_d: tuple) -> str:
    """원본 MVP 템플릿 + 조작 패널 + fetch 레이어."""
    html = ui._TEMPLATE
    for label, old, new in PATCHES:
        if html.count(old) != 1:
            raise RuntimeError(
                f"MVP 템플릿 패치 실패 [{label}] — 앵커가 {html.count(old)}번 발견됨 (1이어야 함).\n"
                f"romantic_route/ui.py 의 _TEMPLATE 이 바뀌었습니다. live_ui.PATCHES 를 맞춰 주세요.\n"
                f"앵커: {old[:70]!r}"
            )
        html = html.replace(old, new, 1)

    html = html.replace("__CONTROLS__", CONTROLS, 1)
    html = html.replace("</head>", EXTRA_CSS + "</head>", 1)

    import json
    live = (LIVE_JS
            .replace("__AXES_META__", json.dumps(axes_meta, ensure_ascii=False))
            .replace("__DEFAULT_O__", json.dumps(list(default_o)))
            .replace("__DEFAULT_D__", json.dumps(list(default_d))))
    html = html.replace("</body>", live + "</body>", 1)
    return html
