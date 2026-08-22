import { useNavigate } from 'react-router-dom'
import { Search as SearchIcon, Locate, Sparkles, Home as HomeIcon, Star, TreePine, Landmark } from 'lucide-react'
import Shell from '../components/Shell'
import RouteMap from '../components/RouteMap'
import { START_PLACE, GOAL_PLACE, waypointPos } from '../data/mock'
import { useRoutes } from '../context/RouteContext'
import { WAYPOINT_ICON, THEME_STYLE, WAYPOINT_LABEL, WAYPOINT_EMOJI } from '../lib/theme'

export default function Home() {
  const nav = useNavigate()
  const { routes } = useRoutes()

  const nature = routes[0]
  const map = (
    <RouteMap
      routes={[{ id: nature.id, color: THEME_STYLE.nature.color, path: nature.path, selected: true }]}
      start={START_PLACE.pos}
      goal={GOAL_PLACE.pos}
      waypoints={nature.waypoints
        .map((w) => {
          const pos = waypointPos(nature, w.id)
          return pos ? { id: w.id, pos, emoji: WAYPOINT_EMOJI[w.type], color: THEME_STYLE.nature.color } : null
        })
        .filter((x): x is NonNullable<typeof x> => x !== null)}
      fitTo={nature.path}
      fitKey="home"
      sheetFraction={0.62}
    />
  )

  const topBar = (
    <div className="lg:p-5">
      <div className="mb-3 hidden items-center gap-2 lg:flex">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--color-brand)] text-white">
          <TreePine size={18} />
        </div>
        <span className="text-[19px] font-extrabold tracking-tight">여유길</span>
      </div>
      <button
        onClick={() => nav('/search')}
        className="flex w-full items-center gap-3 rounded-2xl border border-black/5 bg-white px-4 py-3.5 text-left shadow-[var(--shadow-card)] lg:border-[#eceef1] lg:shadow-none lg:ring-1 lg:ring-black/5"
      >
        <SearchIcon size={20} className="text-[var(--color-ink-3)]" />
        <span className="text-[15px] text-[var(--color-ink-3)]">어디로 걸어볼까요?</span>
      </button>
    </div>
  )

  const panel = (
    <div className="px-4 pb-8 pt-3 lg:px-5">
      {/* 빠른 진입 */}
      <div className="mb-5 flex gap-2 overflow-x-auto no-scrollbar">
        <QuickChip icon={<HomeIcon size={15} />} label="집" onClick={() => nav('/search')} />
        <QuickChip icon={<Star size={15} />} label="즐겨찾기" onClick={() => nav('/search')} />
        <QuickChip icon={<TreePine size={15} />} label="산책코스" onClick={() => nav('/routes')} />
        <QuickChip icon={<Landmark size={15} />} label="문화코스" onClick={() => nav('/routes')} />
      </div>

      {/* 추천 배너 */}
      <button
        onClick={() => nav('/routes')}
        className="mb-6 flex w-full items-center gap-3 rounded-2xl bg-gradient-to-br from-[#eaf3ff] to-[#e7f8ef] p-4 text-left"
      >
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-[var(--color-brand)] shadow-sm">
          <Sparkles size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-bold">여유로운 보행 경로를 찾아드려요</p>
          <p className="mt-0.5 text-[13px] text-[var(--color-ink-2)]">자연 친화 · 문화재 테마로 비교해 보세요</p>
        </div>
      </button>

      {/* 주변 여유 장소 */}
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-[17px] font-extrabold">지금 주변 여유 장소</h2>
        <span className="text-[12px] text-[var(--color-ink-3)]">12분 전 업데이트</span>
      </div>
      <ul className="space-y-1">
        {routes[0].waypoints.concat(routes[1]?.waypoints ?? []).slice(0, 5).map((w, i) => {
          const Icon = WAYPOINT_ICON[w.type]
          return (
            <li key={w.id}>
              <button
                onClick={() => nav('/routes')}
                className="flex w-full items-center gap-3 rounded-xl px-2 py-2.5 text-left transition-colors hover:bg-[#f6f7f9]"
              >
                <span className="w-5 text-center text-[15px] font-extrabold text-[var(--color-ink-3)]">{i + 1}</span>
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f2f4f6] text-[var(--color-ink-2)]">
                  <Icon size={19} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[15px] font-semibold">{w.name}</span>
                  <span className="block truncate text-[12.5px] text-[var(--color-ink-3)]">
                    #{WAYPOINT_LABEL[w.type]} · 도보 추천 코스
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )

  const floating = <LocateButton />

  return <Shell map={map} topBar={topBar} panel={panel} floating={floating} sheetMaxClass="max-h-[62%]" />
}

function QuickChip({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex shrink-0 items-center gap-1.5 rounded-full border border-[#eceef1] bg-white px-3.5 py-2 text-[13.5px] font-semibold text-[var(--color-ink)] shadow-sm transition-colors hover:bg-[#f6f7f9]"
    >
      <span className="text-[var(--color-ink-2)]">{icon}</span>
      {label}
    </button>
  )
}

export function LocateButton() {
  return (
    <button
      className="flex h-11 w-11 items-center justify-center rounded-full bg-white text-[var(--color-brand)] shadow-[var(--shadow-float)] transition-transform active:scale-95"
      aria-label="현재 위치"
    >
      <Locate size={20} />
    </button>
  )
}
