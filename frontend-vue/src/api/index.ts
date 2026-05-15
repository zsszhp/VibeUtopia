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
  affected_groups?: string[]
}

export interface SignalCorrelation {
  signal_id: string
  title: string
  platform: string
  correlation_score: number
  risk_boost: number
}

export interface CrossEffect {
  dimensions: string[]
  description: string
  combined_severity: string
}

export interface ConfidenceBreakdown {
  overall: number
  factors: {
    data_quality: number
    consistency: number
    evidence: number
    platform_validation: number
  }
}

export interface EvidenceChain {
  id: string
  source: string
  content: string
  confidence: number
  cross_validation: string[]
}

export interface SimulationNode {
  id: string
  name: string
  influence: number
  faction: 'support' | 'oppose' | 'neutral'
  details?: Record<string, any>
}

export interface SimulationEdge {
  source: string
  target: string
  strength: number
}

export interface SimulationData {
  nodes: SimulationNode[]
  edges: SimulationEdge[]
}

export interface PolarizationDataPoint {
  time: string
  polarization_index: number
  support_count: number
  oppose_count: number
  neutral_count: number
}

export interface PolarizationData {
  timeline: PolarizationDataPoint[]
  thresholds: {
    low: number
    medium: number
    high: number
  }
}

export interface EntityChainItem {
  id: string
  name: string
  risk_score: number
  risk_level: 'green' | 'yellow' | 'orange' | 'red'
  dimensions: string[]
  timestamp: string
  details?: Record<string, any>
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
  signal_correlations?: SignalCorrelation[]
  confidence?: number
  uncertainty_sources?: string[]
  cross_effects?: CrossEffect[]
  confidence_breakdown?: ConfidenceBreakdown
  evidence_chains?: EvidenceChain[]
  simulation_data?: SimulationData
  polarization_data?: PolarizationData
  entity_chains?: EntityChainItem[]
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

export interface UploadResponse {
  file_path: string
  file_name: string
  file_size: number
}

export const api = {
  /** 提交内容预审（统一入口） */
  submitReview: (req: ReviewRequest) =>
    axios.post<ReviewResponse>(`${API_BASE}/review`, req),

  /** 获取预审结果 */
  getReviewResult: (taskId: string) =>
    axios.get<ReviewResult>(`${API_BASE}/review/${taskId}`),

  /** 获取分析进度 */
  getReviewProgress: (taskId: string) =>
    axios.get<ProgressResponse>(`${API_BASE}/review/${taskId}/progress`),

  /** 历史记录 */
  getHistory: (page: number = 1, perPage: number = 20, riskLevel?: string) =>
    axios.get<HistoryResponse>(`${API_BASE}/history`, { params: { page, per_page: perPage, risk_level: riskLevel } }),

  /** 当前可用模型 */
  getModels: () =>
    axios.get<ModelsResponse>(`${API_BASE}/models`),

  /** 上传文件 */
  uploadFile: (file: File, onProgress?: (percent: number) => void) => {
    const formData = new FormData()
    formData.append('file', file)
    return axios.post<UploadResponse>(`${API_BASE}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percent)
        }
      }
    })
  },

  /** 获取历史报告详情 */
  getHistoryDetail: (taskId: string) =>
    axios.get<ReviewResult>(`${API_BASE}/history/${taskId}`),
}
