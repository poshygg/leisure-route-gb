// 여유길 데이터 모듈 — 백엔드 엔진 산출물(plan.json)을 그대로 노출한다.
// plan.json 은 scripts/40_export_frontend_plan.py 가 벨트 공공데이터 엔진으로
// 생성한 실데이터다 (경주 대릉원 → 동궁과 월지, 3개 테마 경로).
// 파일명이 mock.ts 인 것은 기존 페이지들의 import 경로를 유지하기 위함이며
// 내용은 더 이상 목업이 아니다. 좌표계: WGS84(EPSG:4326).

import plan from './plan.json'

export type LngLat = { lng: number; lat: number }

export type WaypointType = 'tree' | 'flower' | 'park' | 'water' | 'heritage' | 'culture'

export interface Waypoint {
  id: string
  name: string
  type: WaypointType
  /** 이 경유 요소가 경로에 포함된 이유 (공공데이터 근거) */
  reason: string
  /** 공공데이터 출처 */
  source: string
}

/** 경로를 구성하는 노드. 경유 요소(waypointId)이거나 단순 꺾임점(anchor). */
export interface RouteNode extends LngLat {
  waypointId?: string
}

export type ThemeKey = 'nature' | 'heritage' | 'fast'

export interface RouteTheme {
  id: string
  themeKey: ThemeKey
  name: string
  tagline: string
  /** 순서가 있는 경로 노드 목록 (출발 → … → 도착) */
  path: RouteNode[]
  waypoints: Waypoint[]
}

export interface Place {
  id: string
  name: string
  address: string
  pos: LngLat
}

export const START_PLACE: Place = plan.start as Place
export const GOAL_PLACE: Place = plan.goal as Place

export const ROUTES: RouteTheme[] = plan.routes as unknown as RouteTheme[]

export const RECENT_SEARCHES: { id: string; name: string; sub: string }[] =
  (plan.suggestions as Place[]).slice(0, 3).map((p) => ({
    id: 'recent-' + p.id,
    name: p.name,
    sub: p.address,
  }))

export const SEARCH_SUGGESTIONS: Place[] = [
  START_PLACE,
  GOAL_PLACE,
  ...(plan.suggestions as Place[]),
]

// ---- 거리/시간 계산 (WGS84 haversine) ----
const WALK_SPEED_M_PER_MIN = 67 // 약 4km/h

export function haversine(a: LngLat, b: LngLat): number {
  const R = 6371000
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const la1 = (a.lat * Math.PI) / 180
  const la2 = (b.lat * Math.PI) / 180
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)))
}

export function pathMeters(path: LngLat[]): number {
  let m = 0
  for (let i = 1; i < path.length; i++) m += haversine(path[i - 1], path[i])
  return m
}

export function metersToText(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${Math.round(m)}m`
}

export function walkMinutes(m: number): number {
  return Math.max(1, Math.round(m / WALK_SPEED_M_PER_MIN))
}

export function getRoute(id: string): RouteTheme | undefined {
  return ROUTES.find((r) => r.id === id)
}

export function waypointPos(route: RouteTheme, waypointId: string): LngLat | undefined {
  const node = route.path.find((n) => n.waypointId === waypointId)
  return node ? { lng: node.lng, lat: node.lat } : undefined
}

export function toTuples(path: LngLat[]): [number, number][] {
  return path.map((n) => [n.lng, n.lat])
}
