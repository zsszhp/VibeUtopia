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
      reviewStore.wsConnected = true
      reviewStore.wsFallbackPolling = false
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        reviewStore.handleWsMessage(data)
      } catch (e) {
        console.warn('[WS] 解析消息失败:', e)
      }
    }

    ws.onclose = () => {
      console.log('[WS] 连接关闭')
      ws = null
      reviewStore.wsConnected = false
      startPolling(taskId)
      scheduleReconnect(taskId)
    }

    ws.onerror = () => {
      console.warn('[WS] 连接错误')
      ws?.close()
    }
  } catch {
    reviewStore.wsConnected = false
    startPolling(taskId)
  }
}

function disconnect() {
  if (ws) { ws.close(); ws = null }
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  reviewStore.wsConnected = false
  reviewStore.wsFallbackPolling = false
}

function startPolling(taskId: string) {
  if (pollTimer) return
  reviewStore.wsFallbackPolling = true
  pollTimer = setInterval(async () => {
    if (reviewStore.currentStep === 'report') {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
      reviewStore.wsFallbackPolling = false
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

watch(() => reviewStore.currentTaskId, (newId) => {
  if (newId) connect(newId)
  else disconnect()
})

onUnmounted(disconnect)
</script>
