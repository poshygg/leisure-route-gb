import type { StyleSpecification } from 'maplibre-gl'

// 배경지도: CARTO Positron 래스터 (OSM 기반, API 키 불필요, 전 세계 커버).
// 원본 구조(피렌체 데모 PMTiles)는 한국 좌표에서 빈 화면이 되므로 교체했다.
// 자체 벡터 PMTiles 로 전환할 때는 buildStyle 만 다시 벡터 스타일로 바꾸면 된다.
// 출처표기(© OpenStreetMap © CARTO)는 필수라 attribution 으로 유지한다.

export const DEMO_CENTER: [number, number] = [129.2185, 35.8335] // 경주 대릉원~동궁과 월지 사이
export const DEMO_ORIGIN: [number, number] = [129.21, 35.838] // 대릉원 일원 (기본 출발점)
export const DEMO_ZOOM = 15

export function buildStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      carto: {
        type: 'raster',
        tiles: [
          'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
          'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
          'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
        ],
        tileSize: 256,
        maxzoom: 19,
        attribution: '© OpenStreetMap contributors © CARTO',
      },
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': '#e8e5db' } },
      { id: 'carto', type: 'raster', source: 'carto' },
    ],
  }
}
