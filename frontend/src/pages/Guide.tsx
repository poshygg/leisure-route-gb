import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, CornerUpRight, Flag, Home, MapPin, Pause, Play, ListTree, X } from 'lucide-react'
import Shell from '../components/Shell'
import RouteMap from '../components/RouteMap'
import { LocateButton } from './Home'
import { useRoutes } from '../context/RouteContext'
import { metersToText, pathMeters, walkMinutes, waypointPos, type RouteNode } from '../data/mock'
import { THEME_STYLE, WAYPOINT_ICON, WAYPOINT_EMOJI } from '../lib/theme'
import { cumulativeMeters, pointAtMeters } from '../lib/geo'

const EMPTY_PATH: RouteNode[] = []

export default function Guide() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const { endpoints, computeRoute } = useRoutes()

  const route = useRoutes().routes.find((r) => r.id === id)
  const computed = useMemo(() => computeRoute(id), [id, computeRoute])
  const [progress, setProgress] = useState(0) // 0..1
  const [playing, setPlaying] = useState(true)
  const [showSummary, setShowSummary] = useState(false)
  const raf = useRef<number>()

  const path: RouteNode[] = computed?.path ?? EMPTY_PATH
  const totalM = useMemo(() => pathMeters(path), [path])
  const cum = useMemo(() => cumulativeMeters(path), [path])

  // 지도에 전달하는 배열은 애니메이션 프레임마다 재생성되지 않도록 메모이즈
  const routesProp = useMemo(
    () => (route && computed ? [{ id: route.id, color: THEME_STYLE[route.themeKey].color, path: computed.path, selected: true }] : []),
    [route, computed],
  )
  const waypointsProp = useMemo(
    () =>
      route && computed
        ? computed.activeWaypoints
            .map((w) => {
              const pos = waypointPos(route, w.id)
              return pos ? { id: w.id, pos, emoji: WAYPOINT_EMOJI[w.type], color: THEME_STYLE[route.themeKey].color } : null
            })
            .filter((x): x is NonNullable<typeof x> => x !== null)
        : [],
    [route, computed],
  )

  useEffect(() => {
    if (!playing || totalM === 0) return
    let last = performance.now()
    const durationSec = 40 // 약 40초에 완주(시연용)
    const tick = (now: number) => {
      const dt = (now - last) / 1000
      last = now
      setProgress((p) => {
        const np = p + dt / durationSec
        return np >= 1 ? 1 : np
      })
      raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current)
    }
  }, [playing, totalM])

  useEffect(() => {
    if (progress >= 1) setPlaying(false)
  }, [progress])

  if (!route || !computed) {
    return (
      <div className="flex h-[100dvh] items-center justify-center">
        <button onClick={() => nav('/routes')} className="rounded-xl bg-[var(--color-brand)] px-4 py-2 font-bold text-white">
          경로 목록으로
        </button>
      </div>
    )
  }

  const st = THEME_STYLE[route.themeKey]
  const curDist = totalM * progress
  const cur = pointAtMeters(path, curDist)
  const remainingM = totalM * (1 - progress)
  const remMin = walkMinutes(remainingM)
  const arrived = progress >= 1

  // 다음 경유 요소
  const nextNodeIdx = path.findIndex((n, i) => n.waypointId && cum[i] > curDist + 1)
  const nextNode = nextNodeIdx >= 0 ? path[nextNodeIdx] : null
  const nextWp = nextNode?.waypointId ? computed.activeWaypoints.find((w) => w.id === nextNode.waypointId) : null
  const nextDistM = nextNode ? cum[nextNodeIdx] - curDist : remainingM

  const NextIcon = nextWp ? WAYPOINT_ICON[nextWp.type] : Flag

  const map = (
    <RouteMap
      routes={routesProp}
      start={endpoints.start.pos}
      goal={endpoints.goal.pos}
      waypoints={waypointsProp}
      current={arrived ? null : cur}
      fitTo={route.path}
      fitKey={route.id}
    />
  )

  const topBar = (
    <div className="flex items-center gap-3 rounded-2xl bg-white p-3 shadow-[var(--shadow-card)] lg:m-4 lg:shadow-none lg:ring-1 lg:ring-black/5">
      <button
        onClick={() => nav(`/routes/${id}`)}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[var(--color-ink)] hover:bg-[#f4f5f7]"
        aria-label="뒤로"
      >
        <ArrowLeft size={22} />
      </button>
      <div className="min-w-0 flex-1">
        <p className="text-[12px] font-semibold text-[var(--color-ink-3)]">도착지</p>
        <p className="truncate text-[15px] font-extrabold">{endpoints.goal.name}</p>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-[12px] font-semibold text-[var(--color-ink-3)]">남은 거리</p>
        <p className="text-[15px] font-extrabold" style={{ color: st.color }}>{metersToText(remainingM)}</p>
      </div>
    </div>
  )

  const panel = (
    <div className="px-4 pb-6 pt-4 lg:px-5">
      {arrived ? (
        <div className="flex flex-col items-center py-6 text-center">
          <span className="flex h-16 w-16 items-center justify-center rounded-full" style={{ background: st.soft, color: st.color }}>
            <Flag size={30} />
          </span>
          <h2 className="mt-3 text-[20px] font-extrabold">목적지에 도착했어요</h2>
          <p className="mt-1 text-[14px] text-[var(--color-ink-2)]">{route.name} 경로로 여유롭게 걸었어요 🌿</p>
        </div>
      ) : (
        <>
          {/* 다음 안내 카드 */}
          <div className="flex items-center gap-3 rounded-2xl border border-[#eceef1] bg-white p-4">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl" style={{ background: st.soft, color: st.color }}>
              {nextWp ? <NextIcon size={24} /> : <CornerUpRight size={24} />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold text-[var(--color-ink-3)]">
                {nextWp ? '다음 경유지' : '목적지 방면'}
              </p>
              <p className="truncate text-[17px] font-extrabold">{nextWp ? nextWp.name : endpoints.goal.name}</p>
            </div>
            <span className="shrink-0 text-[16px] font-extrabold" style={{ color: st.color }}>
              {metersToText(nextDistM)}
            </span>
          </div>

          {/* 진행바 */}
          <div className="mt-4">
            <div className="mb-1.5 flex justify-between text-[12.5px] font-semibold text-[var(--color-ink-2)]">
              <span>남은 시간 약 {remMin}분</span>
              <span>{Math.round(progress * 100)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[#eef0f3]">
              <div className="h-full rounded-full transition-[width] duration-200" style={{ width: `${progress * 100}%`, background: st.color }} />
            </div>
          </div>

          {/* 컨트롤 */}
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => setPlaying((p) => !p)}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-[#e6e8ec] bg-white py-3 text-[14px] font-bold text-[var(--color-ink)]"
            >
              {playing ? <Pause size={17} /> : <Play size={17} />}
              {playing ? '일시정지' : '이어 걷기'}
            </button>
            <button
              onClick={() => setShowSummary(true)}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-[#e6e8ec] bg-white py-3 text-[14px] font-bold text-[var(--color-ink)]"
            >
              <ListTree size={17} />
              경로 요약
            </button>
          </div>
        </>
      )}
    </div>
  )

  const footer = (
    <button
      onClick={() => nav('/')}
      className="flex w-full items-center justify-center gap-2 rounded-2xl bg-[var(--color-brand)] py-4 text-[16px] font-bold text-white transition-colors hover:bg-[var(--color-brand-dark)]"
    >
      <Home size={19} />
      홈으로
    </button>
  )

  return (
    <>
      <Shell map={map} topBar={topBar} panel={panel} footer={footer} floating={<LocateButton />} sheetMaxClass="max-h-[64%]" />

      {/* 경로 요약 시트 */}
      {showSummary && (
        <div className="fixed inset-0 z-50 flex items-end justify-center lg:items-center" onClick={() => setShowSummary(false)}>
          <div className="absolute inset-0 bg-black/30" />
          <div
            onClick={(e) => e.stopPropagation()}
            className="anim-sheet relative max-h-[76%] w-full overflow-y-auto no-scrollbar rounded-t-[24px] bg-white p-5 shadow-[var(--shadow-float)] lg:max-w-[420px] lg:rounded-[24px]"
            style={{ paddingBottom: 'max(28px, env(safe-area-inset-bottom))' }}
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-[18px] font-extrabold">남은 경로 요약</h3>
              <button onClick={() => setShowSummary(false)} className="flex h-9 w-9 items-center justify-center rounded-full text-[var(--color-ink-3)] hover:bg-[#f4f5f7]" aria-label="닫기">
                <X size={20} />
              </button>
            </div>

            <div className="mb-4 flex items-center gap-4 rounded-2xl p-3.5" style={{ background: st.soft, color: st.ink }}>
              <span className="text-[13px] font-semibold">남은 거리 <b className="text-[15px]">{metersToText(remainingM)}</b></span>
              <span className="text-[13px] font-semibold">약 <b className="text-[15px]">{remMin}분</b></span>
            </div>

            <ol className="relative space-y-4 pl-1">
              <Step icon={<MapPin size={16} />} title="현재 위치" sub={`${Math.round(progress * 100)}% 지점`} color={st.color} soft={st.soft} />
              {computed.activeWaypoints
                .filter((w) => {
                  const idx = path.findIndex((n) => n.waypointId === w.id)
                  return idx >= 0 && cum[idx] > curDist
                })
                .map((w) => {
                  const Icon = WAYPOINT_ICON[w.type]
                  return <Step key={w.id} icon={<Icon size={16} />} title={w.name} sub="경유지" color={st.color} soft={st.soft} />
                })}
              <Step icon={<Flag size={16} />} title={endpoints.goal.name} sub="도착" color="var(--color-goal)" soft="#fde8ee" last />
            </ol>
          </div>
        </div>
      )}
    </>
  )
}

function Step({
  icon,
  title,
  sub,
  color,
  soft,
  last,
}: {
  icon: React.ReactNode
  title: string
  sub: string
  color: string
  soft: string
  last?: boolean
}) {
  return (
    <li className="relative flex items-center gap-3">
      {!last && <span className="absolute left-[18px] top-9 h-[calc(100%-4px)] w-0.5 -translate-x-1/2 bg-[#e8eaee]" />}
      <span className="z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full" style={{ background: soft, color }}>
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-[15px] font-bold">{title}</span>
        <span className="block text-[12px] text-[var(--color-ink-3)]">{sub}</span>
      </span>
    </li>
  )
}
