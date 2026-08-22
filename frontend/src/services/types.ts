// 외부 서비스 어댑터 공통 타입.
// 모든 좌표는 WGS84(EPSG:4326). 저장·전송 전부 이 좌표계를 사용한다.

export interface LngLat {
  lng: number
  lat: number
}

// ---- 역지오코딩(Reverse Geocoding) ----
// 실제 API(Nominatim/네이버 reverse geocoding 등)와 동일한 형태의 결과.
export interface ReverseGeocodeResult {
  /** 장소명 또는 지역명 */
  placeName: string
  /** 도로명주소 */
  roadAddress: string
  /** 지번주소 (선택) */
  jibunAddress?: string
  /** 질의한 WGS84 좌표 */
  position: LngLat
}

export interface GeocodingAdapter {
  reverseGeocode(pos: LngLat, signal?: AbortSignal): Promise<ReverseGeocodeResult>
}

// ---- 라우팅(OSRM HTTP API) ----
// OSRM /route/v1/{profile}/{coords}?geometries=polyline&overview=full 응답과 동일한 형태.
export interface OsrmRoute {
  /** encoded polyline (정밀도 5) */
  geometry: string
  /** 미터 */
  distance: number
  /** 초 */
  duration: number
  weight?: number
  weight_name?: string
}

export interface OsrmWaypoint {
  /** [lng, lat] */
  location: [number, number]
  name: string
}

export interface OsrmResponse {
  code: string
  routes: OsrmRoute[]
  waypoints: OsrmWaypoint[]
}

export interface RoutingAdapter {
  /** 경유 좌표(WGS84) 목록으로 보행 경로를 요청 */
  route(coordinates: LngLat[], signal?: AbortSignal): Promise<OsrmResponse>
}
