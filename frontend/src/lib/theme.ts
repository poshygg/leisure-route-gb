import { Flower2, TentTree, Trees, Waves, Landmark, Building2, type LucideIcon } from 'lucide-react'
import type { ThemeKey, WaypointType } from '../data/mock'

export interface ThemeStyle {
  key: ThemeKey
  /** 라인/포인트 색 */
  color: string
  /** 연한 배경 */
  soft: string
  /** on-soft 텍스트 */
  ink: string
  emoji: string
}

export const THEME_STYLE: Record<ThemeKey, ThemeStyle> = {
  nature: { key: 'nature', color: '#17b26a', soft: '#e7f8ef', ink: '#0f7a48', emoji: '🌿' },
  heritage: { key: 'heritage', color: '#c47f2a', soft: '#fbf1e2', ink: '#8a561a', emoji: '🏛️' },
  fast: { key: 'fast', color: '#7a7f8a', soft: '#eef0f3', ink: '#4b505b', emoji: '⚡' },
}

export const WAYPOINT_ICON: Record<WaypointType, LucideIcon> = {
  tree: Trees,
  flower: Flower2,
  park: TentTree,
  water: Waves,
  heritage: Landmark,
  culture: Building2,
}

export const WAYPOINT_EMOJI: Record<WaypointType, string> = {
  tree: '🌳',
  flower: '🌸',
  park: '🏞️',
  water: '💧',
  heritage: '🏛️',
  culture: '🏘️',
}

export const WAYPOINT_LABEL: Record<WaypointType, string> = {
  tree: '가로수',
  flower: '꽃길',
  park: '공원',
  water: '수변',
  heritage: '문화유산',
  culture: '문화거리',
}
