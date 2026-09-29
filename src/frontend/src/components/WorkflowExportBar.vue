<template>
  <div v-if="taskId" class="workflow-export">
    <div class="row">
      <span class="label">审核状态</span>
      <select v-model="status" class="status-select" @change="onStatusChange">
        <option value="draft">草稿</option>
        <option value="pending_review">待复核</option>
        <option value="approved">通过</option>
        <option value="rejected">驳回</option>
      </select>
      <button class="btn" :disabled="loading" @click="applyStatus">更新状态</button>
    </div>
    <div class="row">
      <span class="label">导出报告</span>
      <button class="btn" @click="exportAs('md')">导出 Markdown</button>
      <button class="btn ghost" @click="exportAs('json')">导出 JSON</button>
    </div>
    <p v-if="message" class="msg">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useReviewStore } from '../stores'
import { api } from '../api'
import { storeToRefs } from 'pinia'

const reviewStore = useReviewStore()
const { currentTaskId: taskId, result } = storeToRefs(reviewStore)

const status = ref('draft')
const loading = ref(false)
const message = ref('')

watch(
  () => result.value,
  (r) => {
    const ws = (r as any)?.workflow_status
    if (ws) status.value = ws
  },
  { immediate: true }
)

async function applyStatus() {
  if (!taskId.value) return
  loading.value = true
  message.value = ''
  try {
    await api.updateWorkflow(taskId.value, status.value)
    message.value = `状态已更新为「${statusLabel(status.value)}」`
  } catch (e: any) {
    message.value = e?.response?.data?.detail || e?.message || '更新失败'
  } finally {
    loading.value = false
  }
}

function onStatusChange() {
  message.value = ''
}

async function exportAs(format: 'md' | 'json') {
  if (!taskId.value) return
  message.value = ''
  try {
    const resp = await api.exportReview(taskId.value, format)
    const blob = new Blob([resp.data as BlobPart], {
      type: format === 'md' ? 'text/markdown;charset=utf-8' : 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `vibeutopia-report-${taskId.value}.${format}`
    a.click()
    URL.revokeObjectURL(url)
    message.value = '报告已导出'
  } catch (e: any) {
    message.value = e?.response?.data?.detail || e?.message || '导出失败'
  }
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    pending_review: '待复核',
    approved: '通过',
    rejected: '驳回',
  }
  return map[s] || s
}
</script>

<style scoped>
.workflow-export {
  margin-top: 12px;
  padding: 12px;
  background: var(--color-surface, #12121a);
  border: 1px solid var(--color-border, #1e1e2e);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.label {
  font-size: 12px;
  color: var(--color-text-secondary, #888);
  min-width: 64px;
}
.status-select {
  background: var(--color-bg, #0a0a0f);
  color: var(--color-text, #e0e0e0);
  border: 1px solid var(--color-border, #1e1e2e);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
}
.btn {
  background: var(--color-brand, #6366f1);
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.ghost {
  background: transparent;
  border: 1px solid var(--color-border, #1e1e2e);
  color: var(--color-text, #e0e0e0);
}
.msg {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-secondary, #aaa);
}
</style>
