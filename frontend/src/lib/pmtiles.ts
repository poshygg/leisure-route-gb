import maplibregl from 'maplibre-gl'
import { Protocol } from 'pmtiles'

// pmtiles:// 프로토콜을 MapLibre 에 1회만 등록.
let registered = false
export function ensurePmtilesProtocol() {
  if (registered) return
  const protocol = new Protocol()
  maplibregl.addProtocol('pmtiles', protocol.tile)
  registered = true
}
