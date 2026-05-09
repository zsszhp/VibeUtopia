import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api'
import type { ReviewRequest, ReviewResult, ProgressResponse, HistoryItem, ModelsResponse } from '../api'

export const useReviewStore = defineStore('review', () => {
  // ─── 状态 ─────────────────────────────────────────────
  const currentTaskId = ref('')
  const result = ref<ReviewResult | null>(null)
  const progress = ref<ProgressResponse | null>(null)
  const loading = ref(false)
  const currentStep = ref<'understanding' | 'assessment' | 'signal' | 'simulation' | 'report'>('understanding')
  const progressPercent = ref(0)

  // ─── 操作 ─────────────────────────────────────────────
  async function submitReview(req: ReviewRequest) {
    loading.value = true
    currentStep.value = 'understanding'
    progressPercent.value = 0
    result.value = null
    try {
      const resp = await api.submitReview(req)
      currentTaskId.value = resp.data.task_id
      return resp.data
    } finally {
      loading.value = false
    }
  }

  async function fetchResult(taskId: string) {
    try {
      const resp = await api.getReviewResult(taskId)
      result.value = resp.data
      return resp.data
    } catch (e) {
      console.error('获取预审结果失败', e)
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
    } catch (e) {
      console.error('获取进度失败', e)
      return null
    }
  }

  const riskLevel = computed(() => result.value?.risk_level ?? 'green')

  return {
    currentTaskId, result, progress, loading, currentStep, progressPercent, riskLevel,
    submitReview, fetchResult, fetchProgress,
  }
})

export const useHistoryStore = defineStore('history', () => {
  const items = ref<HistoryItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)

  async function fetchHistory(p: number = 1, perPage: number = 20, riskLevel?: string) {
    loading.value = true
    try {
      const resp = await api.getHistory(p, perPage, riskLevel)
      items.value = resp.data.items
      total.value = resp.data.total
      page.value = p
    } finally {
      loading.value = false
    }
  }

  return { items, total, page, loading, fetchHistory }
})

export const useModelsStore = defineStore('models', () => {
  const models = ref<ModelsResponse | null>(null)
  const loading = ref(false)

  async function fetchModels() {
    loading.value = true
    try {
      const resp = await api.getModels()
      models.value = resp.data
    } finally {
      loading.value = false
    }
  }

  const hardwareTier = computed(() => models.value?.hardware_tier ?? 'lite')

  return { models, loading, hardwareTier, fetchModels }
})
