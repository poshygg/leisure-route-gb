import type { GeocodingAdapter, LngLat, ReverseGeocodeResult } from './types'

// 실제 역지오코딩 서버가 없으므로 mock 구현.
// 응답 형태는 실제 스펙(ReverseGeocodeResult)과 동일하며,
// 나중에 HttpGeocodingAdapter 로 교체해도 호출부는 바뀌지 않는다.

const AREA = ['물빛동', '삼동', '중대동', '햇살동', '문화동', '늘푸른동']
const ROAD = ['물빛공원로', '느티나무길', '벚꽃로', '한옥마을길', '문화의길', '실개천로', '성곽길']

function hash(pos: LngLat): number {
  // 좌표를 정수화해 결정적 해시 생성 (좌표가 바뀌면 결과도 바뀜)
  const a = Math.round(pos.lng * 1e5)
  const b = Math.round(pos.lat * 1e5)
  let h = (a ^ (b << 1)) >>> 0
  h = (h * 2654435761) >>> 0
  return h
}

export class MockGeocodingAdapter implements GeocodingAdapter {
  /** mock 네트워크 지연(ms) */
  constructor(private readonly latencyMs = 220) {}

  reverseGeocode(pos: LngLat, signal?: AbortSignal): Promise<ReverseGeocodeResult> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        const h = hash(pos)
        const area = AREA[h % AREA.length]
        const road = ROAD[Math.floor(h / 8) % ROAD.length]
        const bldg = (h % 180) + 1
        const jibun = ((Math.floor(h / 32) % 900) + 100)
        resolve({
          placeName: `${area} ${road} 일대`,
          roadAddress: `경상북도 ${area} ${road} ${bldg}`,
          jibunAddress: `경상북도 ${area} ${jibun}`,
          position: pos,
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
// export class HttpGeocodingAdapter implements GeocodingAdapter {
//   constructor(private baseUrl: string) {}
//   async reverseGeocode(pos: LngLat, signal?: AbortSignal): Promise<ReverseGeocodeResult> {
//     const res = await fetch(`${this.baseUrl}/reverse?lon=${pos.lng}&lat=${pos.lat}`, { signal })
//     const j = await res.json()
//     return { placeName: j.name, roadAddress: j.road, jibunAddress: j.jibun, position: pos }
//   }
// }

export const geocoding: GeocodingAdapter = new MockGeocodingAdapter()
