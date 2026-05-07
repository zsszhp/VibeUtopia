import axios from 'axios'

const API_BASE = '/api'

export const api = {
  // 文字风控
  analyzeText: (text: string, mode: string = 'quick') =>
    axios.post(`${API_BASE}/analyze/v2`, { text, mode }),

  getAnalysisResult: (taskId: string) =>
    axios.get(`${API_BASE}/analyze/v2/${taskId}`),

  // 视频风控
  extractVideo: (url: string) =>
    axios.post(`${API_BASE}/extract-video`, { url }),

  analyzeVideoV2: (url: string, videoPath: string, mode: string, maxFrames: number) =>
    axios.post(`${API_BASE}/analyze-video/v2`, { url, video_path: videoPath, mode, max_frames: maxFrames }),

  getFrameResults: (taskId: string) =>
    axios.get(`${API_BASE}/frames/${taskId}`),

  analyzeFrames: (videoPath: string, maxFrames: number, enableOcr: boolean, enableRisk: boolean) =>
    axios.post(`${API_BASE}/analyze-frames`, { video_path: videoPath, max_frames: maxFrames, enable_ocr: enableOcr, enable_risk: enableRisk }),

  transcribeAudio: (videoPath: string, enableSentiment: boolean) =>
    axios.post(`${API_BASE}/audio/transcribe`, { video_path: videoPath, enable_sentiment: enableSentiment }),

  getCrossModalRisk: (taskId: string) =>
    axios.get(`${API_BASE}/cross-modal/${taskId}`),

  // 信号采集
  fetchSignals: (mode: string = 'standard') =>
    axios.post(`${API_BASE}/signal/fetch`, { mode }),

  getSignals: (limit: number = 50) =>
    axios.get(`${API_BASE}/signal/list`, { params: { limit } }),

  // 知识图谱
  queryEntity: (name: string) =>
    axios.get(`${API_BASE}/graph/entity/${encodeURIComponent(name)}`),

  getEntityRiskChain: (name: string) =>
    axios.get(`${API_BASE}/entities/${encodeURIComponent(name)}/risk-chain`),

  // 仿真
  createSimulation: (text: string, totalTicks: number = 24, mode: string = 'lightweight') =>
    axios.post(`${API_BASE}/simulation/create`, { seed_content: text, total_ticks: totalTicks, mode }),

  getSimStatus: (simId: string) =>
    axios.get(`${API_BASE}/simulation/${simId}/status`),

  getSimSnapshot: (simId: string) =>
    axios.get(`${API_BASE}/simulation/${simId}/snapshot`),

  // 报告
  generateReport: (type: string, taskId: string) =>
    axios.post(`${API_BASE}/report/${type}`, { task_id: taskId }),

  getReports: (type?: string) =>
    axios.get(`${API_BASE}/report/list`, { params: { type } }),

  // 趋势预测
  predictTrend: (taskId: string) =>
    axios.post(`${API_BASE}/prediction/trend`, { task_id: taskId }),

  // 回测
  runBacktest: () =>
    axios.post(`${API_BASE}/backtest/run`),

  getBacktestResults: () =>
    axios.get(`${API_BASE}/backtest/results`),

  // 一致性
  checkConsistency: (text: string, runCount: number = 3) =>
    axios.post(`${API_BASE}/consistency/check`, { text, run_count: runCount }),

  // 系统
  getDbStatus: () =>
    axios.get(`${API_BASE}/system/db-status`),
}
