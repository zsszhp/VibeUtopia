/** 应用设置持久化：localStorage 读写，供 LeftPanel / App / api 共用 */

export interface AppSettings {
  apiBase: string
  defaultDepth: 'quick' | 'standard' | 'deep' | 'large_scale'
  /** 当前版本仅支持暗色主题 */
  theme: 'dark'
  model: string
}

export const SETTINGS_KEY = 'vibeutopia_settings'

export const DEFAULT_SETTINGS: AppSettings = {
  apiBase: '',
  defaultDepth: 'standard',
  theme: 'dark',
  model: 'auto',
}

export function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (!raw) return { ...DEFAULT_SETTINGS }
    const saved = JSON.parse(raw) as Partial<AppSettings>
    const merged = { ...DEFAULT_SETTINGS, ...saved }
    // 主题仅支持暗色，历史配置中的 light 回退为 dark
    merged.theme = 'dark'
    const depths = ['quick', 'standard', 'deep', 'large_scale']
    if (!depths.includes(merged.defaultDepth)) merged.defaultDepth = 'standard'
    return merged
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

export function saveSettings(settings: Partial<AppSettings>): AppSettings {
  const next = { ...loadSettings(), ...settings, theme: 'dark' as const }
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(next))
  return next
}

export function resetSettings(): void {
  localStorage.removeItem(SETTINGS_KEY)
}
