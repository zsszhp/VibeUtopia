import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

const API_BASE = '/api/v1'

export const useAnalysisStore = defineStore('analysis', () => {
  const currentTaskId = ref('')
  const analysisResult = ref<any>(null)
  const v2Result = ref<any>(null)
  const loading = ref(false)
  const mode = ref<'quick' | 'deep'>('quick')

  async function submitText(text: string, analysisMode: 'quick' | 'deep') {
    loading.value = true
    mode.value = analysisMode
    try {
      const resp = await axios.post(`${API_BASE}/analyze/v2`, { text, mode: analysisMode })
      currentTaskId.value = resp.data.task_id
      analysisResult.value = null
      v2Result.value = null
      return resp.data
    } finally {
      loading.value = false
    }
  }

  async function fetchResult(taskId: string) {
    try {
      const resp = await axios.get(`${API_BASE}/analyze/v2/${taskId}`)
      if (resp.data.status === 'completed') {
        analysisResult.value = resp.data.mvp_result
        v2Result.value = resp.data.v2_result
      }
      return resp.data
    } catch (e) {
      console.error('获取结果失败', e)
      return null
    }
  }

  return { currentTaskId, analysisResult, v2Result, loading, mode, submitText, fetchResult }
})

export const useVideoStore = defineStore('video', () => {
  const videoTaskId = ref('')
  const videoResult = ref<any>(null)
  const loading = ref(false)

  async function submitVideo(url: string, videoPath: string, mode: string, maxFrames: number) {
    loading.value = true
    try {
      const resp = await axios.post(`${API_BASE}/analyze-video/v2`, {
        url, video_path: videoPath, mode, max_frames: maxFrames,
      })
      videoTaskId.value = resp.data.task_id
      videoResult.value = null
      return resp.data
    } finally {
      loading.value = false
    }
  }

  async function fetchFrameResults(taskId: string) {
    try {
      const resp = await axios.get(`${API_BASE}/frames/${taskId}`)
      if (resp.data.status === 'completed') {
        videoResult.value = resp.data
      }
      return resp.data
    } catch (e) {
      console.error('获取帧结果失败', e)
      return null
    }
  }

  return { videoTaskId, videoResult, loading, submitVideo, fetchFrameResults }
})

export const useSimulationStore = defineStore('simulation', () => {
  const simulations = ref<any[]>([])
  const activeSimId = ref('')
  const simStatus = ref<any>(null)
  const wsConnected = ref(false)
  let ws: WebSocket | null = null

  async function createSimulation(text: string, totalTicks: number = 24) {
    const resp = await axios.post(`${API_BASE}/simulation/create`, {
      seed_content: text,
      total_ticks: totalTicks,
      mode: 'lightweight',
    })
    activeSimId.value = resp.data.sim_id
    return resp.data
  }

  async function fetchSimStatus(simId: string) {
    const resp = await axios.get(`${API_BASE}/simulation/${simId}/status`)
    simStatus.value = resp.data
    return resp.data
  }

  function connectWebSocket(simId: string) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/simulation/${simId}`)

    ws.onopen = () => { wsConnected.value = true }
    ws.onclose = () => { wsConnected.value = false }
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      simStatus.value = data
    }
  }

  function disconnectWebSocket() {
    if (ws) {
      ws.close()
      ws = null
    }
  }

  return { simulations, activeSimId, simStatus, wsConnected, createSimulation, fetchSimStatus, connectWebSocket, disconnectWebSocket }
})
