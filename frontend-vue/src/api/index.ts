import axios from 'axios'

const API_BASE = '/api/v1'

// ─── TypeScript 接口定义 ─────────────────────────────────────────

export interface ReviewRequest {
  mode: 'text' | 'video' | 'mixed'
  video_files?: string[]
  texts?: { type: string; content: string }[]
  options?: {
    depth?: 'quick' | 'standard' | 'deep' | 'large_scale'
    platforms?: string[]
    enable_simulation?: boolean
  }
}

export interface ReviewResponse {
  task_id: string
  status: string
  estimated_depth: string
  estimated_duration_seconds: number
}

export interface ProgressResponse {
  task_id: string
  current_step: 'understanding' | 'assessment' | 'signal' | 'simulation' | 'report'
  progress: number
  detail: string
  completed_dimensions: string[]
  remaining_dimensions: string[]
}

export interface RiskDimension {
  name: string
  score: number
  severity: 'green' | 'yellow' | 'orange' | 'red'
  evidence: string
  evidence_source: { type: string; content: string; location: string }
  confidence: number
  suggestion: string
}

export interface ReviewResult {
  task_id: string
  status: string
  overall_risk?: number
  risk_level?: 'green' | 'yellow' | 'orange' | 'red'
  method?: string
  dimensions?: RiskDimension[]
  platform_reactions?: Record<string, { positive: number; neutral: number; negative: number }>
  suggestions?: { original: string; suggestion: string; dimension: string }[]
  error?: string
}

export interface HistoryItem {
  task_id: string
  status: string
  created_at: string | null
  overall_risk?: number
  risk_level?: 'green' | 'yellow' | 'orange' | 'red'
}

export interface HistoryResponse {
  total: number
  items: HistoryItem[]
}

export interface ModelsResponse {
  hardware_tier: 'lite' | 'standard' | 'pro' | 'ultra'
  models: Record<string, { primary: string; fallback: string }>
}

// ─── 5个核心API ─────────────────────────────────────────────────

export const api = {
  /** 提交内容预审（统一入口） */
  submitReview: (req: ReviewRequest) =>
    axios.post<ReviewResponse>(`${API_BASE}/api/review`, req),

  /** 获取预审结果 */
  getReviewResult: (taskId: string) =>
    axios.get<ReviewResult>(`${API_BASE}/api/review/${taskId}`),

  /** 获取分析进度 */
  getReviewProgress: (taskId: string) =>
    axios.get<ProgressResponse>(`${API_BASE}/api/review/${taskId}/progress`),

  /** 历史记录 */
  getHistory: (page: number = 1, perPage: number = 20, riskLevel?: string) =>
    axios.get<HistoryResponse>(`${API_BASE}/api/history`, { params: { page, per_page: perPage, risk_level: riskLevel } }),

  /** 当前可用模型 */
  getModels: () =>
    axios.get<ModelsResponse>(`${API_BASE}/api/models`),
}
