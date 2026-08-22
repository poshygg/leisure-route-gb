import type { ReactNode } from 'react'

interface ShellProps {
  /** 지도 배경 (전체를 채움, 데스크톱에서는 사이드바 오른쪽) */
  map: ReactNode
  /** 상단 검색/헤더 바 */
  topBar?: ReactNode
  /** 패널 본문 (모바일=바텀시트 / 데스크톱=좌측 사이드바) */
  panel: ReactNode
  /** 지도 위 플로팅 컨트롤 */
  floating?: ReactNode
  /** 패널 하단 고정 푸터 (CTA 등) */
  footer?: ReactNode
  /** 모바일 바텀시트 최대 높이 클래스 (기본 74%) */
  sheetMaxClass?: string
}

export default function Shell({ map, topBar, panel, floating, footer, sheetMaxClass = 'max-h-[74%]' }: ShellProps) {
  return (
    <div className="relative mx-auto h-[100dvh] w-full max-w-[1440px] overflow-hidden bg-[#e9eef4]">
      {/* 지도 레이어 */}
      <div className="absolute inset-0 lg:left-[440px]">{map}</div>

      {/* 사이드바(데스크톱) / 바텀시트(모바일) */}
      <aside
        className={`absolute z-20 flex flex-col bg-white ${sheetMaxClass} inset-x-0 bottom-0 rounded-t-[26px] shadow-[var(--shadow-sheet)] lg:inset-y-0 lg:left-0 lg:right-auto lg:w-[440px] lg:max-h-none lg:rounded-none lg:shadow-[var(--shadow-float)]`}
      >
        {/* 모바일 그랩 핸들 */}
        <div className="flex shrink-0 justify-center pt-2.5 lg:hidden">
          <span className="h-1.5 w-11 rounded-full bg-[#dcdee3]" />
        </div>

        {topBar && <div className="hidden shrink-0 lg:block">{topBar}</div>}

        <div className="no-scrollbar flex-1 overflow-y-auto overscroll-contain">{panel}</div>

        {footer && (
          <div
            className="shrink-0 border-t border-[#f0f1f3] bg-white px-4 pt-3"
            style={{ paddingBottom: 'max(14px, env(safe-area-inset-bottom))' }}
          >
            {footer}
          </div>
        )}
      </aside>

      {/* 모바일 상단 플로팅 바 */}
      {topBar && (
        <div className="absolute inset-x-0 top-0 z-30 p-3 lg:hidden" style={{ paddingTop: 'max(12px, env(safe-area-inset-top))' }}>
          {topBar}
        </div>
      )}

      {/* 지도 플로팅 컨트롤 */}
      {floating && (
        <div className="absolute right-4 top-24 z-30 flex flex-col gap-2 lg:right-6 lg:top-auto lg:bottom-6">
          {floating}
        </div>
      )}
    </div>
  )
}
