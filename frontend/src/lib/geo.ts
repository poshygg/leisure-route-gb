import { haversine, type LngLat } from '../data/mock'

/** 경로 노드들의 누적 거리(m) */
export function cumulativeMeters(path: LngLat[]): number[] {
  const cum = [0]
  for (let i = 1; i < path.length; i++) cum.push(cum[i - 1] + haversine(path[i - 1], path[i]))
  return cum
}

/** 시작점 기준 거리(m)에 해당하는 경로 위 좌표 */
export function pointAtMeters(path: LngLat[], dist: number): LngLat {
  if (path.length === 0) return { lng: 0, lat: 0 }
  const cum = cumulativeMeters(path)
  const total = cum[cum.length - 1]
  const d = Math.max(0, Math.min(dist, total))
  for (let i = 1; i < path.length; i++) {
    if (cum[i] >= d) {
      const seg = cum[i] - cum[i - 1] || 1
      const f = (d - cum[i - 1]) / seg
      return {
        lng: path[i - 1].lng + (path[i].lng - path[i - 1].lng) * f,
        lat: path[i - 1].lat + (path[i].lat - path[i - 1].lat) * f,
      }
    }
  }
  return path[path.length - 1]
}

/** 좌표 목록의 바운딩 박스 [[minLng,minLat],[maxLng,maxLat]] */
export function boundsOf(points: LngLat[]): [[number, number], [number, number]] {
  const lngs = points.map((p) => p.lng)
  const lats = points.map((p) => p.lat)
  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ]
}
