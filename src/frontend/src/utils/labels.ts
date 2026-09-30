/** 风险 / 严重度中文词典与阈值口径（30/60/80），禁止在组件内散落 map */

export type RiskLevelKey = 'green' | 'yellow' | 'orange' | 'red'

/** 风险等级中文：green→安全 yellow→注意 orange→较高 red→高危 */
export function riskLevelLabel(level?: string | null): string {
  const map: Record<string, string> = {
    green: '安全',
    yellow: '注意',
    orange: '较高',
    red: '高危',
  }
  return map[level ?? ''] || '未知'
}

/** 预警严重度中文：兼容 color 词与 critical/high/medium/low 两套取值 */
export function severityLabel(severity?: string | null): string {
  const map: Record<string, string> = {
    green: '安全',
    yellow: '注意',
    orange: '较高',
    red: '高危',
    critical: '严重',
    high: '高危',
    medium: '中危',
    low: '低危',
    warning: '注意',
    info: '提示',
  }
  return map[severity ?? ''] || '未知'
}

/** 风险分四档阈值：30/60/80 */
export const RISK_THRESHOLDS = { warn: 30, high: 60, critical: 80 } as const

export interface Verdict {
  /** 结论词 */
  label: string
  /** 语义色 key，对应 tokens.css 的 risk-* */
  level: RiskLevelKey
  /** 一句话建议 */
  advice: string
}

export function scoreVerdict(score: number, topDims?: string[]): Verdict {
  const focus = topDims?.length ? `优先处理：${topDims.slice(0, 2).join('、')}。` : ''
  if (score >= RISK_THRESHOLDS.critical) {
    return { label: '不建议发布', level: 'red', advice: `${focus}存在严重风险，发布后大概率引发负面舆情，建议重做或仅限内部流转。` }
  }
  if (score >= RISK_THRESHOLDS.high) {
    return { label: '建议暂缓发布', level: 'orange', advice: `${focus}风险较高，建议先处理高危问题并复验后再发布。` }
  }
  if (score >= RISK_THRESHOLDS.warn) {
    return { label: '建议修改后发布', level: 'yellow', advice: `${focus}存在可改进风险点，按修改建议调整后可发布。` }
  }
  return { label: '可发布', level: 'green', advice: `${focus}整体风险可控，可按计划发布并持续关注反馈。` }
}

/** 分数 → 语义色 class 后缀（green/yellow/orange/red） */
export function scoreLevel(score: number): RiskLevelKey {
  return scoreVerdict(score).level
}


/** 维度简要说明（tooltip） */
export const DIMENSION_HINTS: Record<string, string> = {
  政治敏感: '涉政人物、领土主权、外交红线',
  法律合规: '广告法、侵权、虚假宣传',
  民族宗教: '民族歧视、宗教冒犯',
  事实错误: '谣言、伪科学、虚假信息',
  平台禁区: '规避审核、黑灰产',
  性别议题: '性别对立、物化歧视',
  群体冒犯: '地域/职业/年龄歧视',
  道德伦理: '公序良俗、道德绑架',
  时事踩雷: '蹭热点、关联翻车事件',
  情绪极化: '煽动对立、极端言论',
  价值观倾向: '历史虚无、拜金、反社会',
  未成年人保护: '诱导未成年人、过度曝光儿童',
  隐私侵犯: '人肉、偷拍、泄露隐私',
  知识产权: '抄袭洗稿、假冒、未授权',
}
