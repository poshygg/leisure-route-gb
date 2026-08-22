import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  GOAL_PLACE,
  ROUTES,
  START_PLACE,
  pathMeters,
  walkMinutes,
  type Place,
  type RouteNode,
  type RouteTheme,
  type Waypoint,
} from '../data/mock'
import { planThemes } from '../services/api'

interface Endpoints {
  start: Place
  goal: Place
}

interface RouteContextValue {
  endpoints: Endpoints
  setEndpoints: (e: Endpoints) => void
  /** 현재 출발·도착 기준 백엔드 경로 3테마 (서버 없으면 내장 스냅샷) */
  routes: RouteTheme[]
  planning: boolean
  planError: string | null
  swapEndpoints: () => void
  /** 경로별 삭제된 경유 요소 id 집합 */
  removed: Record<string, string[]>
  removeWaypoint: (routeId: string, waypointId: string) => void
  restoreWaypoint: (routeId: string, waypointId: string) => void
  resetRoute: (routeId: string) => void
  isRemoved: (routeId: string, waypointId: string) => boolean
  /** 삭제 상태를 반영한 경로 정보 계산 */
  computeRoute: (routeId: string) => ComputedRoute | null
}

export interface ComputedRoute {
  id: string
  path: RouteNode[]
  activeWaypoints: Waypoint[]
  meters: number
  minutes: number
  removedCount: number
}

const RouteContext = createContext<RouteContextValue | null>(null)

export function RouteProvider({ children }: { children: ReactNode }) {
  const [endpoints, setEndpoints] = useState<Endpoints>({ start: START_PLACE, goal: GOAL_PLACE })
  const [removed, setRemoved] = useState<Record<string, string[]>>({})
  // 백엔드 라이브 경로. 초기값은 빌드에 내장된 스냅샷(plan.json) — 서버가 없어도 동작한다.
  const [routes, setRoutes] = useState<RouteTheme[]>(ROUTES)
  const [planning, setPlanning] = useState(false)
  const [planError, setPlanError] = useState<string | null>(null)
  const planRef = useRef<AbortController | null>(null)

  useEffect(() => {
    planRef.current?.abort()
    const ac = new AbortController()
    planRef.current = ac
    setPlanning(true)
    planThemes(endpoints.start.pos, endpoints.goal.pos, ac.signal)
      .then((themes) => {
        if (ac.signal.aborted) return
        setRoutes(themes)
        setPlanError(null)
        setRemoved({}) // 새 구간이면 삭제 상태 초기화
      })
      .catch((e: unknown) => {
        if (ac.signal.aborted) return
        setPlanError(e instanceof Error ? e.message : '경로 서버에 연결하지 못했습니다')
      })
      .finally(() => {
        if (!ac.signal.aborted) setPlanning(false)
      })
    return () => ac.abort()
  }, [endpoints.start.id, endpoints.goal.id, endpoints.start.pos, endpoints.goal.pos])

  const swapEndpoints = useCallback(() => {
    setEndpoints((e) => ({ start: e.goal, goal: e.start }))
  }, [])

  const removeWaypoint = useCallback((routeId: string, waypointId: string) => {
    setRemoved((prev) => {
      const cur = prev[routeId] ?? []
      if (cur.includes(waypointId)) return prev
      return { ...prev, [routeId]: [...cur, waypointId] }
    })
  }, [])

  const restoreWaypoint = useCallback((routeId: string, waypointId: string) => {
    setRemoved((prev) => {
      const cur = prev[routeId] ?? []
      return { ...prev, [routeId]: cur.filter((id) => id !== waypointId) }
    })
  }, [])

  const resetRoute = useCallback((routeId: string) => {
    setRemoved((prev) => ({ ...prev, [routeId]: [] }))
  }, [])

  const isRemoved = useCallback(
    (routeId: string, waypointId: string) => (removed[routeId] ?? []).includes(waypointId),
    [removed],
  )

  const computeRoute = useCallback(
    (routeId: string): ComputedRoute | null => {
      const route = routes.find((r) => r.id === routeId)
      if (!route) return null
      const removedIds = removed[routeId] ?? []
      // 삭제된 경유 노드를 제외하고 이웃 노드를 직접 연결(경로 재계산)
      const path = route.path.filter(
        (n) => !(n.waypointId && removedIds.includes(n.waypointId)),
      )
      const activeWaypoints = route.waypoints.filter((w) => !removedIds.includes(w.id))
      const meters = pathMeters(path)
      return {
        id: route.id,
        path,
        activeWaypoints,
        meters,
        minutes: walkMinutes(meters),
        removedCount: removedIds.length,
      }
    },
    [removed, routes],
  )

  const value = useMemo(
    () => ({
      endpoints,
      setEndpoints,
      routes,
      planning,
      planError,
      swapEndpoints,
      removed,
      removeWaypoint,
      restoreWaypoint,
      resetRoute,
      isRemoved,
      computeRoute,
    }),
    [endpoints, routes, planning, planError, swapEndpoints, removed, removeWaypoint, restoreWaypoint, resetRoute, isRemoved, computeRoute],
  )

  return <RouteContext.Provider value={value}>{children}</RouteContext.Provider>
}

export function useRoutes() {
  const ctx = useContext(RouteContext)
  if (!ctx) throw new Error('useRoutes must be used within RouteProvider')
  return ctx
}
