# 여유길 — 여유를 즐기는 보행 경로 서비스 (프론트엔드)

최단 시간이 아닌 **풍경과 주변 장소**를 기준으로 보행 경로를 제안하는 웹 서비스의 프론트엔드입니다.
사용자는 자연 친화 · 문화재 등 여유 테마 경로를 비교하고, 원하지 않는 경유지를 삭제하며
경로의 성격을 직접 조정(협상형 경로 탐색)합니다.

## 실행

```bash
npm install
npm run dev
```

`http://localhost:5174` 접속. 프로덕션 빌드는 `npm run build` → `npm run preview`.

## 기술 스택

- Vite + React 18 + TypeScript
- Tailwind CSS v4 (`@tailwindcss/vite`)
- React Router v7
- lucide-react (아이콘)
- **지도: MapLibre GL JS + PMTiles (전 화면 공통)** — 렌더링은 MapLibre, 타일은 PMTiles(개발용 공개 데모: protomaps Firenze). API 키 불필요
- **라우팅: 외부 OSRM HTTP API 규격** — 지도 코드와 완전 분리된 어댑터(현재 mock)
- 좌표계: 저장·전송 전부 WGS84(EPSG:4326)
- 홈·경로 비교·경유지 편집·보행 안내·`/map` 모두 동일한 MapLibre 지도를 사용한다(공유 컴포넌트 `src/components/RouteMap.tsx`).

### 지도 화면(`/map`) — 확정 스택으로 구현

`src/pages/MapScreen.tsx` 한 파일에 지도 UI, `src/services/*` 에 교체 가능한 어댑터를 분리했다.

- 전체화면 MapLibre 지도 + 확대/축소/드래그
- 화면 중앙 고정 마커(DOM 오버레이) — 지도를 움직여도 항상 중앙
- 지도 이동이 멈추면 **300ms 디바운스** 후 중앙 좌표를 역지오코딩 → 하단 바텀시트에 장소명·도로명주소·`확인` 표시
- `확인` 시 OSRM 규격 응답의 **encoded polyline(정밀도 5)** 을 디코딩해 경로 라인을 지도에 렌더

#### 어댑터 교체 지점 (mock → 실제 API)

| 파일 | 인터페이스 | 실제 전환 |
|---|---|---|
| `src/services/geocoding.ts` | `GeocodingAdapter` | `MockGeocodingAdapter` → `HttpGeocodingAdapter`(예시 주석 포함) |
| `src/services/routing.ts` | `RoutingAdapter` | `MockRoutingAdapter` → OSRM `/route/v1/foot/...`(예시 주석 포함) |
| `src/lib/mapStyle.ts` | `DEMO_PMTILES_URL` | 데모 PMTiles → 자체 PMTiles URL |

mock 응답은 실제 스펙과 동일한 형태(`ReverseGeocodeResult`, OSRM `code/routes[].geometry/distance/duration`)라 호출부 변경 없이 교체된다.
polyline 인코딩/디코딩은 `src/lib/polyline.ts`(정밀도 파라미터화).

## 반응형

- **모바일**: 지도 위 바텀시트 UI (첨부 시안 대응)
- **데스크톱(≥1024px)**: 좌측 440px 사이드바 + 우측 전체 지도 (네이버/구글 지도 데스크톱 패턴)

한 벌의 컴포넌트(`Shell`)가 화면 폭에 따라 바텀시트 ↔ 사이드바로 전환됩니다.

## 화면 구성 (기능명세 대응)

| 경로 | 화면 | 명세 대응 |
|---|---|---|
| `/` | 홈 — 지도 · 검색 진입 · 주변 여유 장소 | 1 |
| `/search` | 출발지·목적지 검색 (전환·제안·입력 검증) | 1.1 |
| `/map` | MapLibre+PMTiles 지도에서 위치 선택 · 역지오코딩 · OSRM 경로 | 1.1 |
| `/routes` | 여유 테마 경로 비교 추천 (자연친화·문화재·최단) | 2, 2.1 |
| `/routes/:id` | 선택 경로 상세 · 경유 요소 정보/삭제/복원 | 3.1, 4.1 |
| `/guide/:id` | 보행 안내 (현재 위치·다음 경유지·남은 경로 요약) | 5.1 |

## 핵심 상호작용

- **여유 테마 비교**: 지도에서 선택 경로는 진하게, 나머지는 연하게 표시. 카드로 시간·거리·경유 요소 비교.
- **경유 요소 근거**: 경유지 마커/목록 선택 → 포함 이유 + 공공데이터 출처 팝업. 팝업에서 바로 삭제 가능.
- **협상형 조정**: 경유지 삭제 → 경로·거리·시간 재계산. 토스트/목록/복원 버튼으로 되돌리기, 원래 경로 복원.
- **보행 안내**: 경로를 따라 현재 위치가 진행, 다음 경유지까지 거리·남은 시간·진행률, 남은 경로 요약 시트.

## 데이터

백엔드 없이 `src/data/mock.ts`의 목업으로 동작합니다.
경로는 WGS84 노드 배열(`RouteNode[]`)로 표현하며, 경유 요소 삭제 시 해당 노드를 제외해 경로를 재계산합니다.
거리는 haversine 으로 실제 미터를 계산합니다. 실제 API 연동 시 좌표만 서비스 지역으로 바꾸고
동일 스키마(`RouteTheme`, `Waypoint`, `Place`)를 응답으로 사용할 수 있도록 설계했습니다.

## 구조

```
src/
  data/mock.ts          경로·경유지·장소 목업(WGS84) + haversine 거리/시간
  context/RouteContext  출발/도착·경유지 삭제 상태(전 화면 공유)
  services/             GeocodingAdapter · RoutingAdapter(OSRM 규격) + mock
  lib/                  mapStyle(PMTiles), polyline(정밀도5), geo(진행/바운즈),
                        pmtiles(프로토콜), theme(색·아이콘·이모지)
  components/           RouteMap(공유 MapLibre 지도), Shell(반응형 셸)
  pages/                Home · Search · MapScreen(/map) · RouteList · RouteDetail · Guide
```
