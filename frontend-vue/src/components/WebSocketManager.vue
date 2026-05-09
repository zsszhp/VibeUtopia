<template>
  <div></div>
</template>

<script setup lang="ts">
import { watch, onUnmounted } from 'vue'
import { useReviewStore } from '../stores'

const reviewStore = useReviewStore()
let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

function connect(taskId: string) {
  if (!taskId) return
  disconnect()

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${window.location.host}/ws/review/${taskId}`

  try {
    ws = new WebSocket(url)

    ws.onopen = () => {
      console.log('[WS] 已连接:', taskId)
      // 停止轮询
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleMessage(data)
      } catch (e) {
        console.warn('[WS] 解析消息失败:', e)
      }
    }

    ws.onclose = () => {
      console.log('[WS] 连接关闭')
      ws = null
      // 降级为轮询
      startPolling(taskId)
      // 自动重连
      scheduleReconnect(taskId)
    }

    ws.onerror = () => {
      console.warn('[WS] 连接错误')
      ws?.close()
    }
  } catch {
    // WebSocket不可用，降级为轮询
    startPolling(taskId)
  }
}

function disconnect() {
  if (ws) { ws.close(); ws = null }
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

function handleMessage(data: any) {
  switch (data.type) {
    case 'step_update':
      reviewStore.currentStep = data.step
      reviewStore.progressPercent = (data.progress || 0) * 100
      if (data.detail) {
        reviewStore.progress = {
          task_id: data.task_id,
          current_step: data.step,
          progress: data.progress || 0,
          detail: data.detail,
          completed_dimensions: data.completed_dimensions || [],
          remaining_dimensions: data.remaining_dimensions || [],
        }
      }
      break
    case 'risk_alert':
      // 风险预警 - 可后续扩展弹窗
      console.warn('[WS] 风险预警:', data.dimension, data.score)
      break
    case 'review_complete':
      reviewStore.fetchResult(data.task_id)
      reviewStore.progressPercent = 100
      reviewStore.currentStep = 'report'
      break
  }
}

function startPolling(taskId: string) {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    if (reviewStore.currentStep === 'report') {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
      return
    }
    await reviewStore.fetchProgress(taskId)
  }, 3000)
}

function scheduleReconnect(taskId: string) {
  if (reconnectTimer) return
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    if (reviewStore.currentTaskId === taskId && reviewStore.currentStep !== 'report') {
      connect(taskId)
    }
  }, 5000)
}

// 监听taskId变化自动连接
watch(() => reviewStore.currentTaskId, (newId) => {
  if (newId) connect(newId)
  else disconnect()
})

onUnmounted(disconnect)
</script>
