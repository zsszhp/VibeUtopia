<template>
  <div class="left-panel">
    <!-- 上传区域 -->
    <section class="upload-section">
      <h3 class="section-title">内容输入</h3>

      <!-- 模式切换 -->
      <div class="mode-tabs">
        <button
          v-for="m in modes"
          :key="m.key"
          class="mode-tab"
          :class="{ active: inputMode === m.key }"
          @click="inputMode = m.key"
        >{{ m.label }}</button>
      </div>

      <!-- 本地输入错误 -->
      <NAlert v-if="localError" type="warning" closable class="local-error" @close="localError = ''">
        {{ localError }}
      </NAlert>

      <!-- 文本输入 -->
      <div v-if="inputMode === 'text'" class="input-area">
        <textarea
          v-model="textContent"
          placeholder="输入至少10个字符的文案内容..."
          rows="6"
          class="text-input"
          :disabled="isBusy"
        ></textarea>
        <div class="char-counter" :class="{ over: textContent.length > maxTextLength }">
          {{ textContent.length }} / {{ maxTextLength }} 字
        </div>
      </div>

      <!-- 视频上传 -->
      <div v-if="inputMode === 'video'" class="input-area">
        <div class="drop-zone" @dragover.prevent @drop.prevent="handleDrop">
          <p>拖拽视频文件到此处</p>
          <p class="hint">支持 mp4/mov/avi 格式，单文件 ≤ 100MB</p>
          <input type="file" accept=".mp4,.mov,.avi,video/mp4,video/quicktime,video/x-msvideo" multiple ref="fileInput" @change="handleFileSelect" class="file-input" />
          <button class="select-btn" :disabled="isBusy" @click="fileInput?.click()">选择文件</button>
        </div>
        <div v-if="videoFiles.length" class="file-list">
          <div v-for="(f, i) in videoFiles" :key="i" class="file-item">
            <span class="file-name">{{ f.name }} <small class="file-size">({{ formatSize(f.size) }})</small></span>
            <!-- 上传进度条 -->
            <div v-if="uploadProgress[f.name] !== undefined" class="upload-progress">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: uploadProgress[f.name] + '%' }"></div>
              </div>
              <span class="progress-text">{{ uploadProgress[f.name] }}%</span>
            </div>
            <button v-else class="remove-btn" @click="videoFiles.splice(i, 1)">x</button>
          </div>
        </div>
      </div>

      <!-- 混合模式 -->
      <div v-if="inputMode === 'mixed'" class="input-area">
        <textarea
          v-model="textContent"
          placeholder="文案内容..."
          rows="4"
          class="text-input"
          :disabled="isBusy"
        ></textarea>
        <div class="char-counter" :class="{ over: textContent.length > maxTextLength }">
          {{ textContent.length }} / {{ maxTextLength }} 字
        </div>
        <input type="file" accept=".mp4,.mov,.avi,video/mp4,video/quicktime,video/x-msvideo" multiple ref="fileInput" @change="handleFileSelect" class="file-input" />
        <button class="select-btn" :disabled="isBusy" @click="fileInput?.click()">添加视频</button>
        <div v-if="videoFiles.length" class="file-list">
          <div v-for="(f, i) in videoFiles" :key="i" class="file-item">
            <span class="file-name">{{ f.name }} <small class="file-size">({{ formatSize(f.size) }})</small></span>
            <button class="remove-btn" @click="videoFiles.splice(i, 1)">x</button>
          </div>
        </div>
      </div>

      <!-- 分析选项 -->
      <div class="options">
        <label class="option-label">分析深度</label>
        <select v-model="depth" class="depth-select" :disabled="isBusy">
          <option value="quick">快速 (60s)</option>
          <option value="standard">标准 (3min)</option>
          <option value="deep">深度 (10min)</option>
          <option value="large_scale">大规模 (30min)</option>
        </select>
      </div>

      <button
        class="submit-btn"
        :class="submitBtnClass"
        :disabled="!canSubmit || isBusy"
        @click="handleSubmit"
      >
        {{ submitBtnText }}
      </button>

      <p class="submit-disclaimer">
        风险提示由自动化模型生成，仅供参考，不构成法律意见；内容仅用于本地分析；预测结果存在不确定性。
      </p>
    </section>

    <!-- 历史记录 -->
    <section class="history-section">
      <h3 class="section-title">历史记录</h3>
      <div v-if="historyStore.items.length" class="history-list">
        <div
          v-for="item in historyStore.items"
          :key="item.task_id"
          class="history-item"
          :class="{ active: item.task_id === reviewStore.currentTaskId }"
          @click="loadHistory(item.task_id)"
        >
          <span class="history-risk" :class="item.risk_level">{{ riskLevelLabel(item.risk_level) }}</span>
          <span class="history-time">{{ formatTime(item.created_at) }}</span>
        </div>
      </div>
      <p v-else class="empty-hint">暂无历史记录</p>
    </section>

    <!-- 平台热力图 -->
    <section class="heatmap-section">
      <h3 class="section-title">平台覆盖</h3>
      <div class="platform-grid">
        <NTooltip v-for="p in platformHeatData" :key="p.id" trigger="hover">
          <template #trigger>
            <div
              class="platform-cell"
              :style="{ backgroundColor: p.color }"
            >{{ p.name }}</div>
          </template>
          <div class="platform-tooltip">
            <div class="pt-name">{{ p.name }}</div>
            <div class="pt-row">风险覆盖: <span class="pt-val">{{ (p.risk * 100).toFixed(0) }}%</span></div>
            <div class="pt-row">正向: <span class="pt-positive">{{ p.positive }}%</span></div>
            <div class="pt-row">中性: <span class="pt-neutral">{{ p.neutral }}%</span></div>
            <div class="pt-row">负向: <span class="pt-negative">{{ p.negative }}%</span></div>
          </div>
        </NTooltip>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { NTooltip, NAlert } from 'naive-ui'
import { useReviewStore, useHistoryStore } from '../stores'
import { api } from '../api'
import { riskLevelLabel } from '../utils/labels'
import { PLATFORM_IDS, platformLabel } from '../utils/platforms'
import { loadSettings } from '../utils/settings'

const reviewStore = useReviewStore()
const historyStore = useHistoryStore()
const settings = loadSettings()

const inputMode = ref<'text' | 'video' | 'mixed'>('text')
const textContent = ref('')
const videoFiles = ref<File[]>([])
const depth = ref<'quick' | 'standard' | 'deep' | 'large_scale'>(settings.defaultDepth)
const uploadProgress = ref<Record<string, number>>({})
const isUploading = ref(false)
const localError = ref('')
const fileInput = ref<HTMLInputElement>()

const maxTextLength = 2000
const maxFileSize = 100 * 1024 * 1024
const allowedExtensions = ['mp4', 'mov', 'avi']

const modes = [
  { key: 'text' as const, label: '文本' },
  { key: 'video' as const, label: '视频' },
  { key: 'mixed' as const, label: '混合' },
]

const isBusy = computed(() =>
  isUploading.value ||
  reviewStore.status === 'submitting' ||
  reviewStore.status === 'analyzing'
)

const canSubmit = computed(() => {
  if (textContent.value.length > maxTextLength) return false
  if (inputMode.value === 'text') return textContent.value.trim().length >= 10
  if (inputMode.value === 'video') return videoFiles.value.length > 0
  return textContent.value.trim().length >= 10 || videoFiles.value.length > 0
})

const submitBtnText = computed(() => {
  if (isUploading.value || reviewStore.status === 'submitting') return '上传中...'
  if (reviewStore.status === 'analyzing') return `分析中 ${Math.round(reviewStore.progressPercent)}%`
  if (reviewStore.status === 'done') return '完成'
  if (reviewStore.status === 'error') return '失败，点击重试'
  return '开始预审'
})

const submitBtnClass = computed(() => ({
  'is-uploading': isUploading.value || reviewStore.status === 'submitting',
  'is-analyzing': reviewStore.status === 'analyzing',
  'is-done': reviewStore.status === 'done',
  'is-error': reviewStore.status === 'error',
}))

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(0) + 'KB'
  return bytes + 'B'
}

function validateAndAppend(files: File[]) {
  localError.value = ''
  const problems: string[] = []
  for (const file of files) {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    if (!allowedExtensions.includes(ext)) {
      problems.push(`「${file.name}」格式不支持，仅支持 mp4/mov/avi`)
      continue
    }
    if (file.size > maxFileSize) {
      problems.push(`「${file.name}」超过 100MB 上限`)
      continue
    }
    if (videoFiles.value.some(f => f.name === file.name && f.size === file.size)) {
      problems.push(`「${file.name}」已在列表中`)
      continue
    }
    videoFiles.value.push(file)
  }
  if (problems.length) {
    localError.value = problems.join('；')
  }
}

function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files) validateAndAppend(Array.from(target.files))
  target.value = ''
}

function handleDrop(e: DragEvent) {
  if (e.dataTransfer?.files) validateAndAppend(Array.from(e.dataTransfer.files))
}

async function uploadVideoFiles(): Promise<string[]> {
  if (videoFiles.value.length === 0) return []

  isUploading.value = true
  localError.value = ''
  const uploadedPaths: string[] = []

  try {
    for (const file of videoFiles.value) {
      const resp = await api.uploadFile(file, (percent) => {
        uploadProgress.value[file.name] = percent
      })
      uploadedPaths.push(resp.data.file_path)
    }
    return uploadedPaths
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '视频上传失败'
    localError.value = `上传失败：${msg}`
    throw e
  } finally {
    isUploading.value = false
    uploadProgress.value = {}
  }
}

async function handleSubmit() {
  if (isBusy.value || !canSubmit.value) return

  localError.value = ''
  try {
    // 先上传视频文件
    let videoPaths: string[] = []
    if (videoFiles.value.length > 0) {
      videoPaths = await uploadVideoFiles()
    }

    const texts = textContent.value.trim()
      ? [{ type: 'text', content: textContent.value.trim() }]
      : []

    await reviewStore.submitReview({
      mode: inputMode.value,
      video_files: videoPaths,
      texts,
      options: { depth: depth.value },
    })
  } catch (e: any) {
    // uploadVideoFiles 已写 localError；提交错误由 store.error 全局提示
    if (!localError.value && !reviewStore.error) {
      localError.value = e?.message || '提交失败，请稍后重试'
    }
  }
}

function loadHistory(taskId: string) {
  // 切换历史报告前清空进行中视图，避免旧进度残留
  reviewStore.reset()
  reviewStore.fetchResult(taskId)
}

function formatTime(t: string | null) {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

interface PlatformHeatItem {
  id: string
  name: string
  risk: number
  positive: number
  neutral: number
  negative: number
  color: string
}

function riskToColor(risk: number): string {
  if (risk >= 0.75) return 'rgba(239,68,68,0.6)'
  if (risk >= 0.5) return 'rgba(249,115,22,0.5)'
  if (risk >= 0.25) return 'rgba(234,179,8,0.35)'
  return 'rgba(99,102,241,0.2)'
}

// platform_reactions 的 key 是英文平台 id（douyin/weibo/...），必须用 id 查表
const platformHeatData = computed<PlatformHeatItem[]>(() => {
  const reactions = reviewStore.result?.platform_reactions
  return PLATFORM_IDS.map(id => {
    const r = reactions?.[id]
    if (r) {
      const total = r.positive + r.neutral + r.negative
      const risk = total > 0 ? r.negative / total : 0
      return {
        id,
        name: platformLabel(id),
        risk,
        positive: total > 0 ? Math.round((r.positive / total) * 100) : 0,
        neutral: total > 0 ? Math.round((r.neutral / total) * 100) : 0,
        negative: total > 0 ? Math.round((r.negative / total) * 100) : 0,
        color: riskToColor(risk),
      }
    }
    return { id, name: platformLabel(id), risk: 0, positive: 0, neutral: 0, negative: 0, color: riskToColor(0) }
  })
})

historyStore.fetchHistory()
</script>

<style scoped>
.left-panel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding: var(--sp-3);
}

.section-title {
  font-size: var(--fs-md);
  color: var(--text-tertiary);
  margin-bottom: var(--sp-2);
  font-weight: 600;
}

.mode-tabs {
  display: flex;
  gap: var(--sp-1);
  margin-bottom: var(--sp-2);
}

.mode-tab {
  flex: 1;
  padding: 6px 0;
  font-size: var(--fs-sm);
  background: var(--bg-inset);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--dur-base);
}

.mode-tab.active {
  background: var(--brand-600);
  border-color: var(--brand-600);
  color: #fff;
}

.local-error {
  margin-bottom: var(--sp-2);
  font-size: var(--fs-sm);
}

.input-area {
  margin-bottom: var(--sp-1);
}

.text-input {
  width: 100%;
  padding: var(--sp-2);
  background: var(--bg-inset);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  color: var(--text-primary);
  font-size: var(--fs-md);
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
}

.char-counter {
  margin-top: var(--sp-1);
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.char-counter.over {
  color: var(--risk-critical);
}

.drop-zone {
  border: 2px dashed var(--border-default);
  border-radius: var(--r-md);
  padding: var(--sp-4);
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.hint { font-size: var(--fs-xs); color: var(--text-tertiary); margin-top: var(--sp-1); }

.file-input { display: none; }

.select-btn {
  margin-top: var(--sp-2);
  padding: var(--sp-1) var(--sp-3);
  font-size: var(--fs-sm);
  background: var(--bg-overlay);
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  cursor: pointer;
}

.select-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-list { margin-top: var(--sp-2); }

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-1) var(--sp-2);
  background: var(--bg-inset);
  border-radius: var(--r-sm);
  margin-bottom: var(--sp-1);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size { color: var(--text-tertiary); }

.remove-btn {
  background: none;
  border: none;
  color: var(--risk-critical);
  cursor: pointer;
  font-size: var(--fs-sm);
}

.upload-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: var(--border-default);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--brand-600);
  border-radius: 2px;
  transition: width var(--dur-base);
}

.progress-text {
  font-size: var(--fs-2xs);
  color: var(--text-tertiary);
  min-width: 28px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.options {
  margin-top: var(--sp-2);
}

.option-label {
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  display: block;
  margin-bottom: var(--sp-1);
}

.depth-select {
  width: 100%;
  padding: 6px;
  background: var(--bg-inset);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  color: var(--text-primary);
  font-size: var(--fs-sm);
}

.submit-btn {
  width: 100%;
  margin-top: var(--sp-3);
  padding: var(--sp-2);
  background: var(--brand-600);
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: var(--fs-lg);
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--dur-base);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.submit-btn.is-done {
  background: var(--risk-safe);
}

.submit-btn.is-error {
  background: var(--risk-critical);
}

.submit-disclaimer {
  margin-top: var(--sp-2);
  padding: var(--sp-1) var(--sp-2);
  font-size: var(--fs-xs);
  line-height: 1.5;
  color: var(--text-tertiary);
  border-left: 2px solid var(--border-subtle);
}

.submit-btn.is-analyzing,
.submit-btn.is-uploading {
  background: var(--brand-400);
}

.history-list { max-height: 200px; overflow-y: auto; }

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px var(--sp-2);
  border-radius: var(--r-sm);
  cursor: pointer;
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  transition: background var(--dur-base);
}

.history-item:hover { background: var(--bg-inset); }
.history-item.active { background: var(--brand-soft); }

.history-risk {
  font-weight: 700;
  font-size: var(--fs-xs);
  padding: 2px 6px;
  border-radius: 3px;
}

.history-risk.green { background: var(--risk-safe-soft); color: var(--risk-safe); }
.history-risk.yellow { background: var(--risk-warn-soft); color: var(--risk-warn); }
.history-risk.orange { background: var(--risk-high-soft); color: var(--risk-high); }
.history-risk.red { background: var(--risk-critical-soft); color: var(--risk-critical); }

.history-time { color: var(--text-disabled); }

.empty-hint { font-size: var(--fs-sm); color: var(--text-tertiary); }

.platform-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-1);
}

.platform-cell {
  padding: var(--sp-1) 2px;
  text-align: center;
  font-size: var(--fs-2xs);
  color: var(--text-primary);
  border-radius: 3px;
  cursor: pointer;
  transition: all var(--dur-base);
}

.platform-cell:hover {
  transform: scale(1.05);
}

.platform-tooltip {
  font-size: var(--fs-xs);
}

.pt-name {
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--sp-1);
}

.pt-row {
  color: var(--text-secondary);
  margin-top: 2px;
}

.pt-val { color: var(--brand-400); font-weight: 600; }
.pt-positive { color: var(--risk-safe); }
.pt-neutral { color: var(--text-tertiary); }
.pt-negative { color: var(--risk-critical); }
</style>
