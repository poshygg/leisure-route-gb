import { encodePolyline, type LatLngTuple } from '../lib/polyline'
import type { LngLat, OsrmResponse, RoutingAdapter } from './types'

// 실제 OSRM 서버가 없으므로 mock 구현.
// OSRM /route/v1/foot/{coords}?geometries=polyline&overview=full 과 동일한 형태의 응답을 만든다.
// geometry 는 정밀도 5 encoded polyline 이므로, 호출부는 실제 OSRM 과 동일하게 디코딩하면 된다.

const WALK_SPEED_M_PER_S = 1.25 // 약 4.5km/h

function haversine(a: LngLat, b: LngLat): number {
  const R = 6371000
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const la1 = (a.lat * Math.PI) / 180
  const la2 = (b.lat * Math.PI) / 180
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** 두 점 사이에 살짝 꺾인 중간점들을 만들어 도로를 따라가는 듯한 경로를 생성 */
function buildSegment(a: LngLat, b: LngLat, seed: number): LatLngTuple[] {
  const steps = 8
  const pts: LatLngTuple[] = []
  const dx = b.lng - a.lng
  const dy = b.lat - a.lat
  // 진행 방향에 수직인 벡터(지그재그 오프셋용)
  const nx = -dy
  const ny = dx
  for (let i = 0; i <= steps; i++) {
    const t = i / steps
    // 경로를 자연스럽게 흔들어 직선이 아닌 형태로 (양끝은 오프셋 0)
    const wobble = Math.sin(t * Math.PI) * Math.sin((seed + i) * 1.7) * 0.18
    const lng = a.lng + dx * t + nx * wobble
    const lat = a.lat + dy * t + ny * wobble
    pts.push([lat, lng])
  }
  return pts
}

export class MockRoutingAdapter implements RoutingAdapter {
  constructor(private readonly latencyMs = 260) {}

  route(coordinates: LngLat[], signal?: AbortSignal): Promise<OsrmResponse> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        if (coordinates.length < 2) {
          resolve({ code: 'Ok', routes: [], waypoints: [] })
          return
        }

        const full: LatLngTuple[] = []
        let distance = 0
        for (let i = 0; i < coordinates.length - 1; i++) {
          const a = coordinates[i]
          const b = coordinates[i + 1]
          distance += haversine(a, b)
          const seg = buildSegment(a, b, i + 1)
          if (i > 0) seg.shift() // 세그먼트 경계 중복 제거
          full.push(...seg)
        }
        // 흔들림으로 늘어난 실제 길이를 반영해 거리 보정
        distance = distance * 1.08

        const geometry = encodePolyline(full, 5)
        resolve({
          code: 'Ok',
          routes: [
            {
              geometry,
              distance: Math.round(distance),
              duration: Math.round(distance / WALK_SPEED_M_PER_S),
              weight: Math.round(distance / WALK_SPEED_M_PER_S),
              weight_name: 'routability',
            },
          ],
          waypoints: coordinates.map((c, i) => ({
            location: [c.lng, c.lat],
            name: i === 0 ? '출발지' : i === coordinates.length - 1 ? '도착지' : `경유 ${i}`,
          })),
        })
      }, this.latencyMs)

      signal?.addEventListener('abort', () => {
        clearTimeout(timer)
        reject(new DOMException('Aborted', 'AbortError'))
      })
    })
  }
}

// 실제 API 교체 예시(참고용, 미사용):
// export class HttpRoutingAdapter implements RoutingAdapter {
//   constructor(private baseUrl = 'https://router.project-osrm.org') {}
//   async route(coordinates: LngLat[], signal?: AbortSignal): Promise<OsrmResponse> {
//     const path = coordinates.map((c) => `${c.lng},${c.lat}`).join(';')
//     const url = `${this.baseUrl}/route/v1/foot/${path}?geometries=polyline&overview=full`
//     const res = await fetch(url, { signal })
//     return (await res.json()) as OsrmResponse
//   }
// }

export const routing: RoutingAdapter = new MockRoutingAdapter()
