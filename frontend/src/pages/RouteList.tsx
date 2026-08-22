import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRightLeft, Clock, Footprints, ChevronRight } from 'lucide-react'
import Shell from '../components/Shell'
import RouteMap from '../components/RouteMap'
import { LocateButton } from './Home'
import { useRoutes } from '../context/RouteContext'
import { metersToText, waypointPos, type ThemeKey } from '../data/mock'
import { THEME_STYLE, WAYPOINT_ICON, WAYPOINT_EMOJI } from '../lib/theme'

export default function RouteList() {
  const nav = useNavigate()
  const { endpoints, swapEndpoints, computeRoute, routes } = useRoutes()
  const [selectedId, setSelectedId] = useState(routes[0].id)

  const selected = computeRoute(selectedId)!
  const selectedRoute = routes.find((r) => r.id === selectedId) ?? routes[0]

  const map = (
    <RouteMap
      routes={routes.map((r) => ({
        id: r.id,
        color: THEME_STYLE[r.themeKey].color,
        path: computeRoute(r.id)!.path,
        selected: r.id === selectedId,
        faded: r.id !== selectedId,
      }))}
      start={endpoints.start.pos}
      goal={endpoints.goal.pos}
      waypoints={selected.activeWaypoints
        .map((w) => {
          const pos = waypointPos(selectedRoute, w.id)
          return pos ? { id: w.id, pos, emoji: WAYPOINT_EMOJI[w.type], color: THEME_STYLE[selectedRoute.themeKey].color } : null
        })
        .filter((x): x is NonNullable<typeof x> => x !== null)}
      fitTo={selected.path}
      fitKey={selectedId}
      sheetFraction={0.68}
    />
  )

  const topBar = (
    <div className="flex items-center gap-2 rounded-full bg-white p-1.5 shadow-[var(--shadow-card)] lg:m-4 lg:rounded-2xl lg:shadow-none lg:ring-1 lg:ring-black/5">
      <button
        onClick={() => nav('/search')}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[var(--color-ink)] hover:bg-[#f4f5f7]"
        aria-label="뒤로"
      >
        <ArrowLeft size={22} />
      </button>
      <button onClick={() => nav('/search')} className="min-w-0 flex-1 truncate rounded-full px-2 py-1.5 text-left text-[15px] font-bold hover:bg-[#f6f7f9]">
        {endpoints.start.name}
      </button>
      <button onClick={swapEndpoints} className="shrink-0 text-[var(--color-brand)]" aria-label="전환">
        <ArrowRightLeft size={18} />
      </button>
      <button onClick={() => nav('/search')} className="min-w-0 flex-1 truncate rounded-full px-2 py-1.5 text-left text-[15px] font-bold hover:bg-[#f6f7f9]">
        {endpoints.goal.name}
      </button>
    </div>
  )

  const panel = (
    <div className="px-4 pb-8 pt-3 lg:px-5">
      <div className="mb-3 flex items-center gap-2">
        <h1 className="text-[18px] font-extrabold">여유 경로 {routes.length}개를 찾았어요</h1>
      </div>
      <p className="mb-4 text-[13.5px] text-[var(--color-ink-2)]">
        테마를 눌러 지도에서 비교하고, 경유지를 편집해 보세요.
      </p>

      <div className="space-y-3">
        {routes.map((r) => {
          const c = computeRoute(r.id)!
          const st = THEME_STYLE[r.themeKey]
          const isSel = r.id === selectedId
          return (
            <div
              key={r.id}
              onClick={() => setSelectedId(r.id)}
              className={`cursor-pointer rounded-2xl border bg-white p-4 transition-all ${
                isSel ? 'border-transparent shadow-[var(--shadow-card)] ring-2' : 'border-[#eceef1] hover:border-[#dcdfe4]'
              }`}
              style={isSel ? ({ '--tw-ring-color': st.color } as React.CSSProperties) : undefined}
            >
              <div className="flex items-start gap-3">
                <span
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-[20px]"
                  style={{ background: st.soft }}
                >
                  {st.emoji}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-[16px] font-extrabold">{r.name}</h3>
                    <ThemeTag themeKey={r.themeKey} />
                  </div>
                  <p className="mt-0.5 truncate text-[13px] text-[var(--color-ink-2)]">{r.tagline}</p>
                </div>
              </div>

              <div className="mt-3 flex items-center gap-4">
                <span className="flex items-baseline gap-1">
                  <Clock size={15} className="translate-y-0.5 text-[var(--color-ink-3)]" />
                  <b className="text-[18px] font-extrabold">{c.minutes}</b>
                  <span className="text-[13px] text-[var(--color-ink-2)]">분</span>
                </span>
                <span className="flex items-baseline gap-1">
                  <Footprints size={15} className="translate-y-0.5 text-[var(--color-ink-3)]" />
                  <b className="text-[16px] font-bold">{metersToText(c.meters)}</b>
                </span>
                {c.activeWaypoints.length > 0 && (
                  <span className="text-[13px] text-[var(--color-ink-3)]">경유 {c.activeWaypoints.length}곳</span>
                )}
              </div>

              {c.activeWaypoints.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {c.activeWaypoints.map((w) => {
                    const Icon = WAYPOINT_ICON[w.type]
                    return (
                      <span
                        key={w.id}
                        className="flex items-center gap-1 rounded-full px-2.5 py-1 text-[12.5px] font-semibold"
                        style={{ background: st.soft, color: st.ink }}
                      >
                        <Icon size={13} />
                        {w.name}
                      </span>
                    )
                  })}
                </div>
              )}

              {isSel && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    nav(`/routes/${r.id}`)
                  }}
                  className="mt-4 flex w-full items-center justify-center gap-1 rounded-xl py-3 text-[15px] font-bold text-white transition-transform active:scale-[0.99]"
                  style={{ background: st.color }}
                >
                  이 경로로 걷기 · 경유지 편집
                  <ChevronRight size={18} />
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )

  return <Shell map={map} topBar={topBar} panel={panel} floating={<LocateButton />} sheetMaxClass="max-h-[68%]" />
}

function ThemeTag({ themeKey }: { themeKey: ThemeKey }) {
  const st = THEME_STYLE[themeKey]
  return (
    <span className="rounded-md px-1.5 py-0.5 text-[11px] font-bold" style={{ background: st.soft, color: st.ink }}>
      추천
    </span>
  )
}
