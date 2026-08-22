import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import maplibregl, { type StyleSpecification } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { ArrowLeft, Check, MapPin, Route as RouteIcon } from 'lucide-react'
import { ensurePmtilesProtocol } from '../lib/pmtiles'
import { buildStyle, DEMO_CENTER, DEMO_ORIGIN, DEMO_ZOOM } from '../lib/mapStyle'
import { decodePolyline, toLngLat } from '../lib/polyline'
import { geocoding } from '../services/geocoding'
import { routing } from '../services/routing'
import type { ReverseGeocodeResult } from '../services/types'

const EMPTY_FC: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }

export default function MapScreen() {
  const nav = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const geoAbortRef = useRef<AbortController | null>(null)
  const routeAbortRef = useRef<AbortController | null>(null)

  const [geo, setGeo] = useState<ReverseGeocodeResult | null>(null)
  const [geoLoading, setGeoLoading] = useState(true)
  const [routeInfo, setRouteInfo] = useState<{ distance: number; duration: number } | null>(null)
  const [confirmed, setConfirmed] = useState(false)

  // ---- 역지오코딩(중앙 좌표) ----
  function runReverse() {
    const map = mapRef.current
    if (!map) return
    geoAbortRef.current?.abort()
    const ac = new AbortController()
    geoAbortRef.current = ac
    const c = map.getCenter()
    setGeoLoading(true)
    geocoding
      .reverseGeocode({ lng: c.lng, lat: c.lat }, ac.signal)
      .then((r) => {
        setGeo(r)
        setGeoLoading(false)
      })
      .catch((e) => {
        if (e?.name !== 'AbortError') setGeoLoading(false)
      })
  }

  // 이동 종료 → 300ms 디바운스 → 역지오코딩
  function scheduleReverse() {
    setConfirmed(false)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(runReverse, 300)
  }

  // ---- 라우팅(OSRM mock) → polyline 디코딩 → 라인 그리기 ----
  function drawRoute(destLng: number, destLat: number) {
    const map = mapRef.current
    if (!map) return
    routeAbortRef.current?.abort()
    const ac = new AbortController()
    routeAbortRef.current = ac
    routing
      .route(
        [
          { lng: DEMO_ORIGIN[0], lat: DEMO_ORIGIN[1] },
          { lng: destLng, lat: destLat },
        ],
        ac.signal,
      )
      .then((res) => {
        const r = res.routes[0]
        if (!r) return
        const line = toLngLat(decodePolyline(r.geometry, 5)) // 정밀도 5 디코딩
        const src = map.getSource('route') as maplibregl.GeoJSONSource | undefined
        src?.setData({
          type: 'FeatureCollection',
          features: [{ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: line } }],
        } as GeoJSON.FeatureCollection)
        setRouteInfo({ distance: r.distance, duration: r.duration })
      })
      .catch((e) => {
        if (e?.name !== 'AbortError') console.warn('route failed', e)
      })
  }

  function handleConfirm() {
    const map = mapRef.current
    if (!map) return
    const c = map.getCenter()
    setConfirmed(true)
    drawRoute(c.lng, c.lat)
  }

  // 초기 중앙 좌표 역지오코딩(지도 렌더와 무관하게 즉시 주소 표시)
  useEffect(() => {
    const ac = new AbortController()
    geocoding
      .reverseGeocode({ lng: DEMO_CENTER[0], lat: DEMO_CENTER[1] }, ac.signal)
      .then((r) => {
        setGeo(r)
        setGeoLoading(false)
      })
      .catch(() => {})
    return () => ac.abort()
  }, [])

  // ---- 지도 초기화(1회) ----
  useEffect(() => {
    if (!containerRef.current) return
    ensurePmtilesProtocol()

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: buildStyle() as StyleSpecification,
      center: DEMO_CENTER,
      zoom: DEMO_ZOOM,
      attributionControl: false,
      preserveDrawingBuffer: true, // 렌더 검증용 픽셀 샘플링 허용
    })
    mapRef.current = map
    ;(window as unknown as { __map?: maplibregl.Map }).__map = map

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')

    map.on('load', () => {
      map.resize() // 컨테이너 크기 확정 후 캔버스 재측정
      map.addSource('route', { type: 'geojson', data: EMPTY_FC })
      map.addLayer({
        id: 'route-casing',
        type: 'line',
        source: 'route',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#ffffff', 'line-width': 10 },
      })
      map.addLayer({
        id: 'route-line',
        type: 'line',
        source: 'route',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#2f6bff', 'line-width': 6 },
      })
      drawRoute(DEMO_CENTER[0], DEMO_CENTER[1]) // 데모 경로 즉시 표시
    })

    map.on('moveend', scheduleReverse)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      geoAbortRef.current?.abort()
      routeAbortRef.current?.abort()
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-[#eef1ec]">
      {/* 지도 — MapLibre 가 컨테이너에 position:relative 를 강제하므로 인라인 style 로 절대배치를 고정 */}
      <div ref={containerRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />

      {/* 상단 헤더 */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-center gap-2 p-3"
        style={{ paddingTop: 'max(12px, env(safe-area-inset-top))' }}
      >
        <button
          onClick={() => nav('/')}
          className="pointer-events-auto flex h-11 w-11 items-center justify-center rounded-full bg-white text-[var(--color-ink)] shadow-[var(--shadow-float)] transition-transform active:scale-95"
          aria-label="뒤로"
        >
          <ArrowLeft size={22} />
        </button>
        <div className="pointer-events-auto rounded-full bg-white px-4 py-2.5 text-[14px] font-bold shadow-[var(--shadow-float)]">
          지도에서 위치 선택
        </div>
      </div>

      {/* 중앙 고정 마커 (DOM 오버레이 → 지도를 움직여도 항상 중앙) */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-full" aria-hidden>
        <div className="flex flex-col items-center" style={{ transform: 'translateY(6px)' }}>
          <MapPin size={40} className="text-[var(--color-goal)] drop-shadow-md" fill="var(--color-goal)" stroke="#fff" strokeWidth={1.5} />
        </div>
      </div>
      {/* 마커 지면 그림자 점 */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2">
        <span className="block h-2 w-2 rounded-full bg-black/30" />
      </div>

      {/* 하단 바텀시트 */}
      <div className="absolute inset-x-0 bottom-0 z-20 p-3" style={{ paddingBottom: 'max(12px, env(safe-area-inset-bottom))' }}>
        <div className="mx-auto max-w-[520px] rounded-[22px] bg-white p-4 shadow-[var(--shadow-sheet)]">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#eef3ff] text-[var(--color-brand)]">
              <MapPin size={20} />
            </span>
            <div className="min-w-0 flex-1">
              {geoLoading && !geo ? (
                <>
                  <div className="h-5 w-40 animate-pulse rounded bg-[#eef0f3]" />
                  <div className="mt-2 h-4 w-56 animate-pulse rounded bg-[#f2f4f6]" />
                </>
              ) : (
                <>
                  <p className="truncate text-[17px] font-extrabold">
                    {geo?.placeName ?? '위치를 확인하는 중'}
                    {geoLoading && <span className="ml-1 text-[12px] font-medium text-[var(--color-ink-3)]">갱신 중…</span>}
                  </p>
                  <p className="mt-0.5 truncate text-[13.5px] text-[var(--color-ink-2)]">{geo?.roadAddress ?? '—'}</p>
                  {geo?.jibunAddress && (
                    <p className="mt-0.5 truncate text-[12px] text-[var(--color-ink-3)]">지번 · {geo.jibunAddress}</p>
                  )}
                </>
              )}
            </div>
          </div>

          {routeInfo && (
            <div className="mt-3 flex items-center gap-2 rounded-xl bg-[#eef3ff] px-3 py-2 text-[13px] font-semibold text-[var(--color-brand-dark)]">
              <RouteIcon size={15} />
              출발지에서 여기까지 {formatDistance(routeInfo.distance)} · 약 {Math.round(routeInfo.duration / 60)}분
            </div>
          )}

          <button
            onClick={handleConfirm}
            disabled={!geo}
            className={`mt-3 flex w-full items-center justify-center gap-1.5 rounded-2xl py-3.5 text-[16px] font-bold text-white transition-colors ${
              geo ? 'bg-[var(--color-brand)] hover:bg-[var(--color-brand-dark)]' : 'bg-[#c8ccd2]'
            }`}
          >
            <Check size={19} />
            {confirmed ? '이 위치로 경로 표시됨' : '확인'}
          </button>
        </div>
      </div>
    </div>
  )
}

function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${Math.round(m)}m`
}
