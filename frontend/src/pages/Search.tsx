import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowUpDown, ChevronRight, Clock, Home as HomeIcon, MapPin, TreePine, X } from 'lucide-react'
import RouteMap from '../components/RouteMap'
import { useRoutes } from '../context/RouteContext'
import {
  RECENT_SEARCHES,
  SEARCH_SUGGESTIONS,
  GOAL_PLACE,
  START_PLACE,
  type Place,
} from '../data/mock'
import { THEME_STYLE } from '../lib/theme'
import { searchPlaces } from '../services/api'

type Field = 'start' | 'goal'

export default function Search() {
  const nav = useNavigate()
  const { setEndpoints, routes } = useRoutes()

  const [start, setStart] = useState<Place | null>(START_PLACE)
  const [goal, setGoal] = useState<Place | null>(GOAL_PLACE)
  const [startText, setStartText] = useState(START_PLACE.name)
  const [goalText, setGoalText] = useState(GOAL_PLACE.name)
  const [active, setActive] = useState<Field | null>(null)
  const [error, setError] = useState<string | null>(null)

  const query = active === 'start' ? startText : active === 'goal' ? goalText : ''
  // 라이브 검색 — 백엔드 /api/search (벨트 전역 국가유산·공원).
  // 서버가 없거나 실패하면 내장 목록으로 폴백한다.
  const [apiHits, setApiHits] = useState<Place[] | null>(null)
  useEffect(() => {
    const q = query.trim()
    if (!active || !q) {
      setApiHits(null)
      return
    }
    const ac = new AbortController()
    const timer = setTimeout(() => {
      searchPlaces(q, ac.signal)
        .then((hits) => setApiHits(hits))
        .catch(() => setApiHits(null))
    }, 200)
    return () => {
      clearTimeout(timer)
      ac.abort()
    }
  }, [active, query])
  const suggestions = useMemo(() => {
    if (!active) return []
    const q = query.trim()
    if (q && apiHits) return apiHits
    const list = q
      ? SEARCH_SUGGESTIONS.filter((p) => p.name.includes(q) || p.address.includes(q))
      : SEARCH_SUGGESTIONS
    return list
  }, [active, query, apiHits])

  function pick(p: Place) {
    if (active === 'start') {
      setStart(p)
      setStartText(p.name)
    } else if (active === 'goal') {
      setGoal(p)
      setGoalText(p.name)
    }
    setActive(null)
    setError(null)
  }

  function swap() {
    setStart(goal)
    setGoal(start)
    setStartText(goalText)
    setGoalText(startText)
  }

  function submit() {
    if (!start || !goal || !startText.trim() || !goalText.trim()) {
      setError('출발지와 목적지를 모두 설정해 주세요.')
      return
    }
    if (start.id === goal.id) {
      setError('출발지와 목적지가 같아요. 다른 목적지를 선택해 주세요.')
      return
    }
    setEndpoints({ start, goal })
    nav('/routes')
  }

  const canSubmit = !!(start && goal && startText.trim() && goalText.trim())

  return (
    <div className="relative flex h-[100dvh] w-full bg-white">
      {/* 검색 컬럼 */}
      <div className="relative flex w-full flex-col lg:w-[440px] lg:shrink-0 lg:border-r lg:border-[#eef0f2]">
        {/* 헤더 + 입력 */}
        <div
          className="shrink-0 px-4 pb-4 pt-3"
          style={{ paddingTop: 'max(12px, env(safe-area-inset-top))' }}
        >
          <button
            onClick={() => nav(-1)}
            className="mb-2 flex h-10 w-10 items-center justify-center rounded-full text-[var(--color-ink)] transition-colors hover:bg-[#f4f5f7]"
            aria-label="뒤로"
          >
            <ArrowLeft size={24} />
          </button>

          <div className="flex items-center gap-2">
            <div className="flex-1 rounded-2xl bg-[#f4f5f7] px-4 py-1">
              <FieldRow
                dotColor="var(--color-start)"
                placeholder="출발지 검색"
                value={startText}
                onFocus={() => setActive('start')}
                onChange={(v) => {
                  setStartText(v)
                  setStart(null)
                }}
                onClear={() => {
                  setStartText('')
                  setStart(null)
                  setActive('start')
                }}
                active={active === 'start'}
              />
              <div className="h-px bg-[#e3e5e9]" />
              <FieldRow
                dotColor="var(--color-goal)"
                placeholder="도착지 검색"
                value={goalText}
                onFocus={() => setActive('goal')}
                onChange={(v) => {
                  setGoalText(v)
                  setGoal(null)
                }}
                onClear={() => {
                  setGoalText('')
                  setGoal(null)
                  setActive('goal')
                }}
                active={active === 'goal'}
              />
            </div>
            <button
              onClick={swap}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-[#e6e8ec] bg-white text-[var(--color-ink-2)] shadow-sm transition-transform active:scale-90"
              aria-label="출발지·도착지 전환"
            >
              <ArrowUpDown size={18} />
            </button>
          </div>

          {error && (
            <p className="mt-3 rounded-xl bg-[#fdeef1] px-3 py-2 text-[13px] font-medium text-[var(--color-goal)]">
              {error}
            </p>
          )}
        </div>

        {/* 본문: 제안 목록 / 최근기록 */}
        <div className="no-scrollbar relative flex-1 overflow-y-auto px-4">
          {active ? (
            <ul className="pb-4">
              {suggestions.length === 0 && (
                <li className="py-16 text-center text-[14px] text-[var(--color-ink-3)]">
                  검색 결과가 없어요.
                </li>
              )}
              {suggestions.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => pick(p)}
                    className="flex w-full items-center gap-3 rounded-xl px-2 py-3 text-left transition-colors hover:bg-[#f6f7f9]"
                  >
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#eef1f4] text-[var(--color-ink-2)]">
                      <MapPin size={17} />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-[15px] font-semibold">{p.name}</span>
                      <span className="block truncate text-[12.5px] text-[var(--color-ink-3)]">{p.address}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <>
              <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1 pt-1">
                <Chip icon={<HomeIcon size={15} />} label="집" />
                <Chip icon={<TreePine size={15} />} label="산책코스 🚶" />
                <Chip icon={<ChevronRight size={15} />} label="" round />
              </div>

              <h2 className="mb-1 mt-5 text-[16px] font-extrabold">최근기록</h2>
              {RECENT_SEARCHES.length === 0 ? (
                <div className="flex flex-col items-center py-24 text-center">
                  <p className="text-[14px] text-[var(--color-ink-3)]">최근 검색 기록이 없어요.</p>
                </div>
              ) : (
                <ul className="pb-4">
                  {RECENT_SEARCHES.map((r) => (
                    <li key={r.id}>
                      <button
                        onClick={() => {
                          const p = SEARCH_SUGGESTIONS.find((s) => s.name === r.name)
                          if (p) {
                            setGoal(p)
                            setGoalText(p.name)
                          }
                        }}
                        className="flex w-full items-center gap-3 rounded-xl px-2 py-3 text-left transition-colors hover:bg-[#f6f7f9]"
                      >
                        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#eef1f4] text-[var(--color-ink-3)]">
                          <Clock size={16} />
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-[15px] font-semibold">{r.name}</span>
                          <span className="block truncate text-[12.5px] text-[var(--color-ink-3)]">{r.sub}</span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>

        {/* 하단 CTA */}
        <div
          className="shrink-0 border-t border-[#f0f1f3] bg-white px-4 pt-3"
          style={{ paddingBottom: 'max(14px, env(safe-area-inset-bottom))' }}
        >
          <div className="mb-2 flex justify-center">
            <button
              onClick={() => nav('/map')}
              className="flex items-center gap-1.5 text-[14px] font-semibold text-[var(--color-ink-2)]"
            >
              <MapPin size={17} className="text-[var(--color-goal)]" />
              지도에서 선택
            </button>
          </div>
          <button
            onClick={submit}
            disabled={!canSubmit}
            className={`w-full rounded-2xl py-4 text-[16px] font-bold text-white transition-colors ${
              canSubmit ? 'bg-[var(--color-brand)] hover:bg-[var(--color-brand-dark)]' : 'bg-[#c8ccd2]'
            }`}
          >
            여유 경로 탐색
          </button>
        </div>
      </div>

      {/* 지도 미리보기 (데스크톱) */}
      <div className="hidden lg:block lg:flex-1">
        <RouteMap
          routes={[{ id: routes[0].id, color: THEME_STYLE.nature.color, path: routes[0].path, faded: true }]}
          start={start?.pos ?? START_PLACE.pos}
          goal={goal?.pos ?? GOAL_PLACE.pos}
          fitTo={routes[0].path}
          fitKey="search"
          interactive={false}
        />
      </div>
    </div>
  )
}

function FieldRow({
  dotColor,
  placeholder,
  value,
  onFocus,
  onChange,
  onClear,
  active,
}: {
  dotColor: string
  placeholder: string
  value: string
  onFocus: () => void
  onChange: (v: string) => void
  onClear: () => void
  active: boolean
}) {
  return (
    <div className="flex items-center gap-3 py-2.5">
      <span
        className="h-3.5 w-3.5 shrink-0 rounded-full border-[3px]"
        style={{ borderColor: dotColor }}
      />
      <input
        value={value}
        placeholder={placeholder}
        onFocus={onFocus}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-0 flex-1 bg-transparent text-[16px] font-medium text-[var(--color-ink)] placeholder:font-normal placeholder:text-[var(--color-ink-3)] focus:outline-none"
      />
      {active && value && (
        <button onClick={onClear} className="text-[var(--color-ink-3)]" aria-label="지우기">
          <X size={17} />
        </button>
      )}
    </div>
  )
}

function Chip({ icon, label, round }: { icon: React.ReactNode; label: string; round?: boolean }) {
  return (
    <button
      className={`flex shrink-0 items-center gap-1.5 border border-[#e6e8ec] bg-white font-semibold text-[var(--color-ink)] shadow-sm transition-colors hover:bg-[#f6f7f9] ${
        round ? 'h-10 w-10 justify-center rounded-full' : 'rounded-full px-4 py-2 text-[14px]'
      }`}
    >
      <span className="text-[var(--color-ink-2)]">{icon}</span>
      {label}
    </button>
  )
}
