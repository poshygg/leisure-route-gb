// 여유길 백엔드(server/app.py) 어댑터.
// vite dev 프록시(/api → :8010)를 타므로 베이스 URL 이 필요 없다.
// 서버가 없으면 호출부가 정적 plan.json 데이터(mock.ts)로 폴백한다.

import type { LngLat, Place, RouteNode, RouteTheme, Waypoint, WaypointType } from '../data/mock'

interface PlanPoi {
  axis: string
  name: string
  lat: number
  lon: number
}

interface PlanRoute {
  rank: number
  km: number
  min: number
  detour: number
  score: number
  axis_means: Record<string, number>
  segments: { c: [number, number][]; a: string | null }[]
  pois: PlanPoi[]
}

interface PlanPayload {
  routes: PlanRoute[]
  axes: Record<string, { label: string; color: string }>
}

const WP_TYPE: Record<string, WaypointType> = {
  heritage: 'heritage',
  parks: 'park',
  coast: 'water',
  trees: 'tree',
}
const SOURCE: Record<string, string> = {
  heritage: '국가유산청 국가유산 공간정보',
  parks: '전국도시공원정보표준데이터',
  coast: '국립해양조사원 해안선',
}
const NAMES: Record<string, [string, string]> = {
  heritage: ['문화재 여유길', '문화유산 곁을 지나는 길'],
  nature: ['자연 여유길', '물가와 공원, 조용한 골목으로 도는 길'],
  fast: ['빠른 길', '우회 없이 곧장 가는 기준선'],
}

function toTheme(r: PlanRoute, themeKey: 'nature' | 'heritage' | 'fast', labels: PlanPayload['axes']): RouteTheme {
  const path: RouteNode[] = []
  r.segments.forEach((seg, i) => {
    const coords = i === 0 ? seg.c : seg.c.slice(1)
    for (const [lat, lng] of coords) path.push({ lng, lat })
  })

  const used = new Set<number>()
  const waypoints: Waypoint[] = []
  r.pois.forEach((p, j) => {
    let best = -1
    let bestD = Infinity
    path.forEach((n, ni) => {
      const d = (n.lng - p.lon) ** 2 + (n.lat - p.lat) ** 2
      if (d < bestD) {
        bestD = d
        best = ni
      }
    })
    if (best < 0 || used.has(best)) return
    used.add(best)
    const wid = `w-${themeKey}-${j}`
    path[best] = { ...path[best], waypointId: wid }
    waypoints.push({
      id: wid,
      name: p.name,
      type: WP_TYPE[p.axis] ?? 'culture',
      reason: `${labels[p.axis]?.label ?? p.axis} 축 인접 — 경로 점수에 기여`,
      source: SOURCE[p.axis] ?? '공공데이터',
    })
  })

  const [name, tagline] = NAMES[themeKey]
  return {
    id: `r-${themeKey}`,
    themeKey,
    name,
    tagline: `${tagline} · ${r.km}km · ${r.min}분`,
    path,
    waypoints,
  }
}

/** 출발·도착으로 백엔드 경로 계획 → 프론트 3테마. 실패 시 throw. */
export async function planThemes(
  start: LngLat,
  goal: LngLat,
  signal?: AbortSignal,
  exclude: LngLat[] = [],
): Promise<RouteTheme[]> {
  let qs = `from=${start.lat},${start.lng}&to=${goal.lat},${goal.lng}&k=3`
  if (exclude.length) {
    qs += `&exclude=${exclude.map((p) => `${p.lat},${p.lng}`).join(';')}`
  }
  const res = await fetch(`/api/plan?${qs}`, { signal })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `경로 계획 실패 (${res.status})`)
  }
  const payload = (await res.json()) as PlanPayload
  const routes = payload.routes
  if (!routes.length) throw new Error('경로를 찾지 못했습니다.')

  const idx = routes.map((_, i) => i)
  const fastI = idx.reduce((a, b) => (routes[b].detour < routes[a].detour ? b : a))
  const rest = idx.filter((i) => i !== fastI)
  const herI = rest.length
    ? rest.reduce((a, b) =>
        (routes[b].axis_means.heritage ?? 0) > (routes[a].axis_means.heritage ?? 0) ? b : a)
    : fastI
  const natI = rest.find((i) => i !== herI) ?? herI

  return [
    toTheme(routes[natI], 'nature', payload.axes),
    toTheme(routes[herI], 'heritage', payload.axes),
    toTheme(routes[fastI], 'fast', payload.axes),
  ]
}

/** 장소 검색 (벨트 전역 654곳 — 국가유산·도시공원). */
export async function searchPlaces(q: string, signal?: AbortSignal): Promise<Place[]> {
  const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=12`, { signal })
  if (!res.ok) throw new Error(`검색 실패 (${res.status})`)
  return (await res.json()) as Place[]
}
