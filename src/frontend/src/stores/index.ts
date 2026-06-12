import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api'
import type { ReviewRequest, ReviewResult, ProgressResponse, HistoryItem, ModelsResponse } from '../api'

export const useReviewStore = defineStore('review', () => {
  const currentTaskId = ref('')
  const result = ref<ReviewResult | null>(null)
  const progress = ref<ProgressResponse | null>(null)
  const loading = ref(false)
  const currentStep = ref<'understanding' | 'assessment' | 'signal' | 'simulation' | 'report'>('understanding')
  const progressPercent = ref(0)

  // 错误状态管理
  const error = ref<string | null>(null)
  const errorTimestamp = ref<number | null>(null)

  // WebSocket 连接状态
  const wsConnected = ref(false)
  const wsFallbackPolling = ref(false)

  // 帧级进度
  const frameProgress = ref<{
    currentFrame: number
    totalFrames: number
    currentFrameUrl: string
    frameType: string
    deltaScore: number
    currentTask: string
  }>({
    currentFrame: 0,
    totalFrames: 0,
    currentFrameUrl: '',
    frameType: '',
    deltaScore: 0,
    currentTask: ''
  })

  // 序列描述
  const sequenceDescriptions = ref<Array<{
    segmentIndex: number
    description: string
    causalEvents: any[]
    actions: any[]
  }>>([])

  // 风险预警列表
  const riskAlerts = ref<Array<{
    dimension: string
    score: number
    frameIndex?: number
    detail: string
    severity: string
    timestamp: number
  }>>([])

  // 子任务列表
  const subTasks = ref<Array<{
    name: string
    status: 'completed' | 'in_progress' | 'pending'
  }>>([])

  function setError(msg: string | null) {
    error.value = msg
    errorTimestamp.value = msg ? Date.now() : null
  }

  function clearError() {
    error.value = null
    errorTimestamp.value = null
  }

  async function submitReview(req: ReviewRequest) {
    loading.value = true
    currentStep.value = 'understanding'
    progressPercent.value = 0
    result.value = null
    clearError()
    try {
      const resp = await api.submitReview(req)
      currentTaskId.value = resp.data.task_id
      return resp.data
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '提交预审失败'
      setError(msg)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchResult(taskId: string) {
    try {
      const resp = await api.getReviewResult(taskId)
      result.value = resp.data
      clearError()
      return resp.data
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '获取预审结果失败'
      setError(msg)
      return null
    }
  }

  async function fetchProgress(taskId: string) {
    try {
      const resp = await api.getReviewProgress(taskId)
      progress.value = resp.data
      currentStep.value = resp.data.current_step as any
      progressPercent.value = resp.data.progress * 100
      return resp.data
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '获取进度失败'
      setError(msg)
      return null
    }
  }

  // WebSocket 消息规范化处理
  function handleWsMessage(data: any) {
    switch (data.type) {
      case 'step_update':
        currentStep.value = data.step
        progressPercent.value = (data.progress || 0) * 100
        if (data.detail) {
          progress.value = {
            task_id: data.task_id,
            current_step: data.step,
            progress: data.progress || 0,
            detail: data.detail,
            completed_dimensions: data.completed_dimensions || [],
            remaining_dimensions: data.remaining_dimensions || [],
          }
        }
        break
      case 'frame_progress':
        frameProgress.value = {
          currentFrame: data.current_frame ?? 0,
          totalFrames: data.total_frames ?? 0,
          currentFrameUrl: data.current_frame_url ?? '',
          frameType: data.frame_type ?? '',
          deltaScore: data.delta_score ?? 0,
          currentTask: data.current_task ?? ''
        }
        break
      case 'sequence_update':
        sequenceDescriptions.value.push({
          segmentIndex: data.segment_index ?? 0,
          description: data.description ?? '',
          causalEvents: data.causal_events ?? [],
          actions: data.actions ?? []
        })
        break
      case 'risk_alert':
        riskAlerts.value.push({
          dimension: data.dimension ?? '',
          score: data.score ?? 0,
          frameIndex: data.frame_index,
          detail: data.detail ?? '',
          severity: data.severity ?? 'warning',
          timestamp: Date.now()
        })
        break
      case 'review_complete':
        fetchResult(data.task_id)
        progressPercent.value = 100
        currentStep.value = 'report'
        break
    }
  }

  // 重置/清理方法
  function reset() {
    currentTaskId.value = ''
    result.value = null
    progress.value = null
    loading.value = false
    currentStep.value = 'understanding'
    progressPercent.value = 0
    clearError()
    wsConnected.value = false
    wsFallbackPolling.value = false
    frameProgress.value = { currentFrame: 0, totalFrames: 0, currentFrameUrl: '', frameType: '', deltaScore: 0, currentTask: '' }
    sequenceDescriptions.value = []
    riskAlerts.value = []
    subTasks.value = []
  }

  function clearResult() {
    result.value = null
  }

  const riskLevel = computed(() => result.value?.risk_level ?? 'green')

  return {
    currentTaskId, result, progress, loading, currentStep, progressPercent, riskLevel,
    error, errorTimestamp, wsConnected, wsFallbackPolling,
    frameProgress, sequenceDescriptions, riskAlerts, subTasks,
    submitReview, fetchResult, fetchProgress,
    handleWsMessage, setError, clearError, reset, clearResult,
  }
})

export const useHistoryStore = defineStore('history', () => {
  const items = ref<HistoryItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 历史报告详情缓存
  const detailCache = ref<Record<string, ReviewResult>>({})

  async function fetchHistory(p: number = 1, perPage: number = 20, riskLevel?: string) {
    loading.value = true
    error.value = null
    try {
      const resp = await api.getHistory(p, perPage, riskLevel)
      items.value = resp.data.items
      total.value = resp.data.total
      page.value = p
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e?.message || '获取历史记录失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchHistoryDetail(taskId: string): Promise<ReviewResult | null> {
    if (detailCache.value[taskId]) return detailCache.value[taskId]
    try {
      const resp = await api.getHistoryDetail(taskId)
      detailCache.value[taskId] = resp.data
      return resp.data
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e?.message || '获取历史详情失败'
      return null
    }
  }

  function clearCache() {
    detailCache.value = {}
  }

  function reset() {
    items.value = []
    total.value = 0
    page.value = 1
    loading.value = false
    error.value = null
    clearCache()
  }

  return { items, total, page, loading, error, detailCache, fetchHistory, fetchHistoryDetail, clearCache, reset }
})

export const useModelsStore = defineStore('models', () => {
  const models = ref<ModelsResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchModels() {
    loading.value = true
    error.value = null
    try {
      const resp = await api.getModels()
      models.value = resp.data
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e?.message || '获取模型信息失败'
    } finally {
      loading.value = false
    }
  }

  const hardwareTier = computed(() => models.value?.hardware_tier ?? 'lite')

  function reset() {
    models.value = null
    loading.value = false
    error.value = null
  }

  return { models, loading, error, hardwareTier, fetchModels, reset }
})
