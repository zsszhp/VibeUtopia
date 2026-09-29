/** 平台 ID ↔ 中文名共享字典，前后端 key 以英文 id 为准 */

export const PLATFORM_NAMES: Record<string, string> = {
  // P0
  bilibili: 'B站',
  xiaohongshu: '小红书',
  zhihu: '知乎',
  douyin: '抖音',
  weibo: '微博',
  // P1
  kuaishou: '快手',
  wechat_channels: '微信视频号',
  douban: '豆瓣',
  hupu: '虎扑',
  toutiao: '今日头条',
  tieba: '贴吧',
  taptap: 'TapTap',
  wechat_official: '公众号',
  shipinhao: '微信视频号',
  twitter: 'Twitter/X',
  facebook: 'Facebook',
  instagram: 'Instagram',
  youtube: 'YouTube',
  telegram: 'Telegram',
  reddit: 'Reddit',
  // P2
  tiktok_global: 'TikTok(国际)',
  linkedin: 'LinkedIn',
  nga: 'NGA',
  v2ex: 'V2EX',
  maimai: '脉脉',
  boss_zhilian: 'Boss直聘',
  smzdm: '什么值得买',
  zhihu_zhuanlan: '知乎专栏',
  jike: '即刻',
}

/** 平台展示名：英文 id → 中文；未知 id 原样返回 */
export function platformLabel(id?: string | null): string {
  if (!id) return '未知平台'
  return PLATFORM_NAMES[id] || id
}

/** 平台中文名 → 英文 id；未知名称返回 null */
export function platformIdByName(name: string): string | null {
  if (!name) return null
  if (name in PLATFORM_NAMES) return name
  for (const [id, label] of Object.entries(PLATFORM_NAMES)) {
    if (label === name) return id
  }
  return null
}

/** 热力图展示用平台 id 列表（与后端 platform_reactions 的 key 对齐） */
export const PLATFORM_IDS: string[] = [
  'douyin', 'weibo', 'xiaohongshu', 'bilibili', 'kuaishou', 'zhihu',
  'wechat_channels', 'toutiao', 'douban', 'tieba', 'hupu', 'wechat_official',
  'facebook', 'twitter', 'tiktok_global', 'instagram', 'youtube', 'reddit',
]
