import { useEffect, useRef, useState } from 'react'
import maplibregl, { type StyleSpecification } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { ensurePmtilesProtocol } from '../lib/pmtiles'
import { buildStyle, DEMO_CENTER } from '../lib/mapStyle'
import { boundsOf } from '../lib/geo'
import { toTuples, type LngLat } from '../data/mock'

export interface RouteMapRoute {
  id: string
  color: string
  path: LngLat[]
  selected?: boolean
  faded?: boolean
}

export interface RouteMapWaypoint {
  id: string
  pos: LngLat
  emoji: string
  color: string
  active?: boolean
  onClick?: () => void
}

interface RouteMapProps {
  routes: RouteMapRoute[]
  start?: LngLat
  goal?: LngLat
  waypoints?: RouteMapWaypoint[]
  current?: LngLat | null
  /** 이 좌표들이 모두 보이도록 뷰를 맞춤 */
  fitTo?: LngLat[]
  /** 값이 바뀔 때만 fit 재적용 (선택 경로 변경 등) */
  fitKey?: string
  interactive?: boolean
  /** 모바일 바텀시트가 덮는 화면 비율 (fit 하단 여백 계산용) */
  sheetFraction?: number
}

export default function RouteMap({
  routes,
  start,
  goal,
  waypoints = [],
  current,
  fitTo,
  fitKey,
  interactive = true,
  sheetFraction = 0.64,
}: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])
  const currentMarkerRef = useRef<maplibregl.Marker | null>(null)
  const [ready, setReady] = useState(false)

  // 지도 초기화(1회)
  useEffect(() => {
    if (!containerRef.current) return
    ensurePmtilesProtocol()
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: buildStyle() as StyleSpecification,
      center: DEMO_CENTER,
      zoom: 14,
      attributionControl: false,
      preserveDrawingBuffer: true,
      interactive,
    })
    mapRef.current = map
    map.dragRotate.disable()
    map.touchZoomRotate.disableRotation()
    if (interactive) map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')

    map.on('load', () => {
      map.resize()
      map.addSource('routes', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addLayer({
        id: 'routes-casing',
        type: 'line',
        source: 'routes',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#ffffff',
          'line-width': ['case', ['get', 'selected'], 11, 7],
          'line-opacity': ['case', ['get', 'faded'], 0, 1],
        },
      })
      map.addLayer({
        id: 'routes-line',
        type: 'line',
        source: 'routes',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['case', ['get', 'selected'], 7, 4.5],
          'line-opacity': ['case', ['get', 'faded'], 0.35, 1],
        },
      })
      setReady(true)
    })

    return () => {
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = []
      currentMarkerRef.current?.remove()
      currentMarkerRef.current = null
      map.remove()
      mapRef.current = null
      setReady(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 경로 라인 갱신
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const src = map.getSource('routes') as maplibregl.GeoJSONSource | undefined
    if (!src) return
    const ordered = [...routes].sort((a, b) => Number(!!a.selected) - Number(!!b.selected)) // 선택 경로를 마지막(위)에
    const fc: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: ordered.map((r) => ({
        type: 'Feature',
        properties: { color: r.color, selected: !!r.selected, faded: !!r.faded },
        geometry: { type: 'LineString', coordinates: toTuples(r.path) },
      })),
    }
    src.setData(fc)
  }, [routes, ready])

  // 정적 마커(출발/도착/경유지) — 변경 시에만 재구성
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    markersRef.current.forEach((m) => m.remove())
    markersRef.current = []
    if (start) markersRef.current.push(addPin(map, start, '출발', '#2f6bff'))
    if (goal) markersRef.current.push(addPin(map, goal, '도착', '#ff375f'))
    for (const w of waypoints) markersRef.current.push(addWaypoint(map, w))
  }, [start, goal, waypoints, ready])

  // 현재 위치 마커 — 매 프레임 위치만 갱신(재생성 X)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    if (current) {
      if (currentMarkerRef.current) currentMarkerRef.current.setLngLat([current.lng, current.lat])
      else currentMarkerRef.current = addCurrent(map, current)
    } else {
      currentMarkerRef.current?.remove()
      currentMarkerRef.current = null
    }
  }, [current, ready])

  // 뷰 맞춤
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !fitTo || fitTo.length === 0) return
    const h = map.getContainer().clientHeight || 800
    const isMobile = window.innerWidth < 1024
    // 데스크톱은 지도가 사이드바 오른쪽 별도 영역이라 겹침 없음.
    // 모바일은 바텀시트가 덮는 만큼 하단 여백을 크게 줘서 경로 전체가 보이게 함.
    const padding = {
      top: isMobile ? 108 : 90,
      left: isMobile ? 44 : 60,
      right: isMobile ? 44 : 60,
      bottom: isMobile ? Math.round(h * sheetFraction) + 20 : 120,
    }
    map.fitBounds(boundsOf(fitTo), { padding, duration: 600, maxZoom: 16.5 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, fitKey ?? JSON.stringify(fitTo)])

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
    </div>
  )
}

// ---- 마커 엘리먼트 ----
function addPin(map: maplibregl.Map, pos: LngLat, label: string, color: string) {
  const el = document.createElement('div')
  el.style.cssText = 'display:flex;flex-direction:column;align-items:center;'
  el.innerHTML = `
    <div style="background:${color};color:#fff;font:800 13px Pretendard,system-ui,sans-serif;padding:4px 10px;border-radius:12px;white-space:nowrap;box-shadow:0 2px 6px rgba(20,22,30,.25)">${label}</div>
    <div style="width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:6px solid ${color};margin-top:-1px"></div>
    <div style="width:9px;height:9px;border-radius:50%;background:${color};border:2px solid #fff;margin-top:-1px;box-shadow:0 1px 3px rgba(0,0,0,.3)"></div>`
  return new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat([pos.lng, pos.lat]).addTo(map)
}

function addWaypoint(map: maplibregl.Map, w: RouteMapWaypoint) {
  const el = document.createElement('button')
  el.type = 'button'
  const size = w.active ? 38 : 32
  el.style.cssText = `width:${size}px;height:${size}px;border-radius:50%;background:#fff;border:${
    w.active ? 4 : 3
  }px solid ${w.color};display:flex;align-items:center;justify-content:center;font-size:${
    w.active ? 18 : 15
  }px;cursor:${w.onClick ? 'pointer' : 'default'};padding:0;line-height:1;box-shadow:0 1px 5px rgba(20,22,30,.28)`
  el.textContent = w.emoji
  if (w.onClick)
    el.addEventListener('click', (e) => {
      e.stopPropagation()
      w.onClick!()
    })
  return new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([w.pos.lng, w.pos.lat]).addTo(map)
}

function addCurrent(map: maplibregl.Map, pos: LngLat) {
  const el = document.createElement('div')
  el.style.cssText = 'position:relative;width:22px;height:22px;'
  el.innerHTML = `
    <span style="position:absolute;left:50%;top:50%;width:22px;height:22px;transform:translate(-50%,-50%);border-radius:50%;background:#2f6bff;opacity:.25;animation:pulse-ring 1.6s ease-out infinite"></span>
    <span style="position:absolute;left:50%;top:50%;width:16px;height:16px;transform:translate(-50%,-50%);border-radius:50%;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.3)"></span>
    <span style="position:absolute;left:50%;top:50%;width:11px;height:11px;transform:translate(-50%,-50%);border-radius:50%;background:#2f6bff"></span>`
  return new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([pos.lng, pos.lat]).addTo(map)
}
