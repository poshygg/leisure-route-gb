// Google/OSRM Encoded Polyline Algorithm Format.
// OSRM 은 기본적으로 정밀도 5(polyline) 또는 6(polyline6)을 사용한다.
// 여기서는 정밀도 5를 기본값으로 encode/decode 를 모두 제공한다.
// 좌표 표기: [lat, lng] (OSRM/Google 스펙과 동일). 지도용 GeoJSON 은 [lng, lat] 이므로 변환 필요.

export type LatLngTuple = [number, number] // [lat, lng]

/** OSRM encoded polyline 문자열을 [lat, lng] 배열로 디코딩 */
export function decodePolyline(str: string, precision = 5): LatLngTuple[] {
  let index = 0
  let lat = 0
  let lng = 0
  const coordinates: LatLngTuple[] = []
  const factor = Math.pow(10, precision)

  while (index < str.length) {
    let result = 1
    let shift = 0
    let b: number
    do {
      b = str.charCodeAt(index++) - 63 - 1
      result += b << shift
      shift += 5
    } while (b >= 0x1f)
    lat += result & 1 ? ~(result >> 1) : result >> 1

    result = 1
    shift = 0
    do {
      b = str.charCodeAt(index++) - 63 - 1
      result += b << shift
      shift += 5
    } while (b >= 0x1f)
    lng += result & 1 ? ~(result >> 1) : result >> 1

    coordinates.push([lat / factor, lng / factor])
  }
  return coordinates
}

function encodeNumber(num: number): string {
  let sgnNum = num < 0 ? ~(num << 1) : num << 1
  let output = ''
  while (sgnNum >= 0x20) {
    output += String.fromCharCode((0x20 | (sgnNum & 0x1f)) + 63)
    sgnNum >>= 5
  }
  output += String.fromCharCode(sgnNum + 63)
  return output
}

/** [lat, lng] 배열을 OSRM encoded polyline 문자열로 인코딩 */
export function encodePolyline(coordinates: LatLngTuple[], precision = 5): string {
  if (coordinates.length === 0) return ''
  const factor = Math.pow(10, precision)
  let output = ''
  let prevLat = 0
  let prevLng = 0
  for (const [lat, lng] of coordinates) {
    const rLat = Math.round(lat * factor)
    const rLng = Math.round(lng * factor)
    output += encodeNumber(rLat - prevLat)
    output += encodeNumber(rLng - prevLng)
    prevLat = rLat
    prevLng = rLng
  }
  return output
}

/** OSRM([lat,lng]) → GeoJSON([lng,lat]) 좌표 변환 */
export function toLngLat(coords: LatLngTuple[]): [number, number][] {
  return coords.map(([lat, lng]) => [lng, lat])
}
