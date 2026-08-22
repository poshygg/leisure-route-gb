import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Clock, Footprints, RotateCcw, Trash2, Undo2, X, Info, Navigation } from 'lucide-react'
import Shell from '../components/Shell'
import RouteMap from '../components/RouteMap'
import { LocateButton } from './Home'
import { useRoutes } from '../context/RouteContext'
import { metersToText, waypointPos, type Waypoint } from '../data/mock'
import { THEME_STYLE, WAYPOINT_ICON, WAYPOINT_LABEL, WAYPOINT_EMOJI } from '../lib/theme'

export default function RouteDetail() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const { endpoints, computeRoute, removeWaypoint, restoreWaypoint, resetRoute, isRemoved } = useRoutes()

  const route = useRoutes().routes.find((r) => r.id === id)
  const [popup, setPopup] = useState<Waypoint | null>(null)
  const [toast, setToast] = useState<{ w: Waypoint } | null>(null)

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3200)
    return () => clearTimeout(t)
  }, [toast])

  if (!route) {
    return (
      <div className="flex h-[100dvh] items-center justify-center">
        <button onClick={() => nav('/routes')} className="rounded-xl bg-[var(--color-brand)] px-4 py-2 font-bold text-white">
          경로 목록으로
        </button>
      </div>
    )
  }

  const st = THEME_STYLE[route.themeKey]
  const computed = computeRoute(id)!
  const removedWps = route.waypoints.filter((w) => isRemoved(id, w.id))

  function handleRemove(w: Waypoint) {
    removeWaypoint(id, w.id)
    setPopup(null)
    setToast({ w })
  }

  const map = (
    <RouteMap
      routes={[{ id: route.id, color: st.color, path: computed.path, selected: true }]}
      start={endpoints.start.pos}
      goal={endpoints.goal.pos}
      waypoints={computed.activeWaypoints
        .map((w) => {
          const pos = waypointPos(route, w.id)
          return pos
            ? { id: w.id, pos, emoji: WAYPOINT_EMOJI[w.type], color: st.color, active: popup?.id === w.id, onClick: () => setPopup(w) }
            : null
        })
        .filter((x): x is NonNullable<typeof x> => x !== null)}
      fitTo={route.path}
      fitKey={route.id}
      sheetFraction={0.7}
    />
  )

  const topBar = (
    <div className="flex items-center gap-2 rounded-full bg-white p-1.5 pr-4 shadow-[var(--shadow-card)] lg:m-4 lg:rounded-2xl lg:shadow-none lg:ring-1 lg:ring-black/5">
      <button
        onClick={() => nav('/routes')}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[var(--color-ink)] hover:bg-[#f4f5f7]"
        aria-label="뒤로"
      >
        <ArrowLeft size={22} />
      </button>
      <span className="text-[16px]">{st.emoji}</span>
      <span className="truncate text-[15px] font-extrabold">{route.name} 경로</span>
    </div>
  )

  const panel = (
    <div className="px-4 pb-6 pt-3 lg:px-5">
      {/* 요약 */}
      <div className="rounded-2xl p-4" style={{ background: st.soft }}>
        <div className="flex items-center gap-4">
          <span className="flex items-baseline gap-1">
            <Clock size={16} className="translate-y-0.5" style={{ color: st.ink }} />
            <b className="text-[22px] font-extrabold" style={{ color: st.ink }}>{computed.minutes}</b>
            <span className="text-[13px]" style={{ color: st.ink }}>분</span>
          </span>
          <span className="flex items-baseline gap-1" style={{ color: st.ink }}>
            <Footprints size={16} className="translate-y-0.5" />
            <b className="text-[18px] font-bold">{metersToText(computed.meters)}</b>
          </span>
          <span className="text-[13px]" style={{ color: st.ink }}>경유 {computed.activeWaypoints.length}곳</span>
        </div>
        {computed.removedCount > 0 && (
          <button
            onClick={() => resetRoute(id)}
            className="mt-3 flex items-center gap-1.5 rounded-lg bg-white/70 px-2.5 py-1.5 text-[12.5px] font-semibold"
            style={{ color: st.ink }}
          >
            <RotateCcw size={14} />
            경유지 {computed.removedCount}곳 제외됨 · 원래 경로로 복원
          </button>
        )}
      </div>

      {/* 안내 */}
      <div className="mt-4 mb-2 flex items-center gap-1.5 text-[12.5px] text-[var(--color-ink-3)]">
        <Info size={14} />
        원하지 않는 경유지를 삭제하면 경로가 다시 계산돼요.
      </div>

      {/* 경유지 목록 */}
      <h2 className="mb-2 mt-3 text-[15px] font-extrabold">경유지 {computed.activeWaypoints.length}</h2>
      <ul className="space-y-1.5">
        {computed.activeWaypoints.map((w, i) => {
          const Icon = WAYPOINT_ICON[w.type]
          return (
            <li
              key={w.id}
              className="flex items-center gap-3 rounded-xl border border-[#eceef1] bg-white p-2.5"
            >
              <button onClick={() => setPopup(w)} className="flex min-w-0 flex-1 items-center gap-3 text-left">
                <span className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: st.soft, color: st.color }}>
                  <Icon size={20} />
                  <span className="absolute -left-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-white text-[10px] font-bold shadow ring-1 ring-black/5" style={{ color: st.ink }}>
                    {i + 1}
                  </span>
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-[14.5px] font-bold">{w.name}</span>
                  <span className="block truncate text-[12px] text-[var(--color-ink-3)]">#{WAYPOINT_LABEL[w.type]}</span>
                </span>
              </button>
              <button
                onClick={() => handleRemove(w)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[var(--color-ink-3)] transition-colors hover:bg-[#fdeef1] hover:text-[var(--color-goal)]"
                aria-label={`${w.name} 삭제`}
              >
                <Trash2 size={18} />
              </button>
            </li>
          )
        })}
        {computed.activeWaypoints.length === 0 && (
          <li className="rounded-xl bg-[#f6f7f9] px-3 py-5 text-center text-[13px] text-[var(--color-ink-3)]">
            모든 경유지를 제외했어요. 최단 동선으로 안내해요.
          </li>
        )}
      </ul>

      {/* 삭제된 경유지 */}
      {removedWps.length > 0 && (
        <>
          <h2 className="mb-2 mt-6 text-[15px] font-extrabold text-[var(--color-ink-3)]">삭제한 경유지 {removedWps.length}</h2>
          <ul className="space-y-1.5">
            {removedWps.map((w) => {
              const Icon = WAYPOINT_ICON[w.type]
              return (
                <li key={w.id} className="flex items-center gap-3 rounded-xl border border-dashed border-[#e2e4e8] bg-[#fafbfc] p-2.5">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#eef0f3] text-[var(--color-ink-3)]">
                    <Icon size={20} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[14.5px] font-semibold text-[var(--color-ink-2)] line-through">{w.name}</span>
                    <span className="block truncate text-[12px] text-[var(--color-ink-3)]">#{WAYPOINT_LABEL[w.type]}</span>
                  </span>
                  <button
                    onClick={() => restoreWaypoint(id, w.id)}
                    className="flex shrink-0 items-center gap-1 rounded-lg bg-white px-2.5 py-2 text-[12.5px] font-bold text-[var(--color-brand)] ring-1 ring-[#e3e6ea]"
                  >
                    <Undo2 size={14} />
                    되돌리기
                  </button>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </div>
  )

  const footer = (
    <button
      onClick={() => nav(`/guide/${id}`)}
      className="flex w-full items-center justify-center gap-2 rounded-2xl py-4 text-[16px] font-bold text-white transition-transform active:scale-[0.99]"
      style={{ background: st.color }}
    >
      <Navigation size={19} />
      보행 시작
    </button>
  )

  return (
    <>
      <Shell map={map} topBar={topBar} panel={panel} footer={footer} floating={<LocateButton />} sheetMaxClass="max-h-[70%]" />

      {/* 경유지 상세 팝업 */}
      {popup && (
        <WaypointPopup
          w={popup}
          removed={isRemoved(id, popup.id)}
          themeColor={st.color}
          themeSoft={st.soft}
          themeInk={st.ink}
          onClose={() => setPopup(null)}
          onRemove={() => handleRemove(popup)}
          onRestore={() => {
            restoreWaypoint(id, popup.id)
            setPopup(null)
          }}
        />
      )}

      {/* 삭제 토스트 (되돌리기) */}
      {toast && (
        <div className="pointer-events-none fixed inset-x-0 bottom-24 z-50 flex justify-center px-4 lg:bottom-8 lg:left-[440px]">
          <div className="anim-pop pointer-events-auto flex items-center gap-3 rounded-full bg-[#17181c] px-4 py-2.5 text-white shadow-[var(--shadow-float)]">
            <span className="text-[13.5px] font-medium">‘{toast.w.name}’ 경유지를 삭제했어요</span>
            <button
              onClick={() => {
                restoreWaypoint(id, toast.w.id)
                setToast(null)
              }}
              className="flex items-center gap-1 text-[13.5px] font-bold text-[#8fc0ff]"
            >
              <Undo2 size={14} />
              되돌리기
            </button>
          </div>
        </div>
      )}
    </>
  )
}

function WaypointPopup({
  w,
  removed,
  themeColor,
  themeSoft,
  themeInk,
  onClose,
  onRemove,
  onRestore,
}: {
  w: Waypoint
  removed: boolean
  themeColor: string
  themeSoft: string
  themeInk: string
  onClose: () => void
  onRemove: () => void
  onRestore: () => void
}) {
  const Icon = WAYPOINT_ICON[w.type]
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center lg:items-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div
        onClick={(e) => e.stopPropagation()}
        className="anim-sheet relative w-full rounded-t-[24px] bg-white p-5 pb-8 shadow-[var(--shadow-float)] lg:mb-0 lg:max-w-[420px] lg:rounded-[24px]"
        style={{ paddingBottom: 'max(28px, env(safe-area-inset-bottom))' }}
      >
        <button onClick={onClose} className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-full text-[var(--color-ink-3)] hover:bg-[#f4f5f7]" aria-label="닫기">
          <X size={20} />
        </button>

        <div className="flex items-center gap-3">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl" style={{ background: themeSoft, color: themeColor }}>
            <Icon size={28} />
          </span>
          <div>
            <span className="rounded-md px-1.5 py-0.5 text-[11px] font-bold" style={{ background: themeSoft, color: themeInk }}>
              #{WAYPOINT_LABEL[w.type]}
            </span>
            <h3 className="mt-1 text-[19px] font-extrabold">{w.name}</h3>
          </div>
        </div>

        <div className="mt-4 rounded-2xl bg-[#f6f7f9] p-4">
          <p className="mb-1 flex items-center gap-1.5 text-[12.5px] font-bold text-[var(--color-ink-2)]">
            <Info size={14} />
            이 경로에 포함된 이유
          </p>
          <p className="text-[14px] leading-relaxed text-[var(--color-ink)]">{w.reason}</p>
          <p className="mt-3 text-[11.5px] text-[var(--color-ink-3)]">출처 · {w.source}</p>
        </div>

        {removed ? (
          <button
            onClick={onRestore}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-[var(--color-brand)] py-3.5 text-[15px] font-bold text-white"
          >
            <Undo2 size={18} />
            경유지 되돌리기
          </button>
        ) : (
          <button
            onClick={onRemove}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl border border-[#f2c9d3] bg-[#fdeef1] py-3.5 text-[15px] font-bold text-[var(--color-goal)]"
          >
            <Trash2 size={18} />
            이 경유지 삭제
          </button>
        )}
      </div>
    </div>
  )
}
