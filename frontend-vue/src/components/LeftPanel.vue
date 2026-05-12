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

      <!-- 文本输入 -->
      <div v-if="inputMode === 'text'" class="input-area">
        <textarea
          v-model="textContent"
          placeholder="输入至少10个字符的文案内容..."
          rows="6"
          class="text-input"
        ></textarea>
      </div>

      <!-- 视频上传 -->
      <div v-if="inputMode === 'video'" class="input-area">
        <div class="drop-zone" @dragover.prevent @drop.prevent="handleDrop">
          <p>拖拽视频文件到此处</p>
          <p class="hint">支持 mp4/mov/avi 格式</p>
          <input type="file" accept="video/*" multiple ref="fileInput" @change="handleFileSelect" class="file-input" />
          <button class="select-btn" @click="fileInput?.click()">选择文件</button>
        </div>
        <div v-if="videoFiles.length" class="file-list">
          <div v-for="(f, i) in videoFiles" :key="i" class="file-item">
            <span>{{ f.name }}</span>
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
        ></textarea>
        <input type="file" accept="video/*" multiple ref="fileInput" @change="handleFileSelect" class="file-input" />
        <button class="select-btn" @click="fileInput?.click()">添加视频</button>
      </div>

      <!-- 分析选项 -->
      <div class="options">
        <label class="option-label">分析深度</label>
        <select v-model="depth" class="depth-select">
          <option value="quick">快速 (60s)</option>
          <option value="standard">标准 (3min)</option>
          <option value="deep">深度 (10min)</option>
          <option value="large_scale">大规模 (30min)</option>
        </select>
      </div>

      <button
        class="submit-btn"
        :disabled="!canSubmit || reviewStore.loading || isUploading"
        @click="handleSubmit"
      >
        {{ isUploading ? '上传中...' : reviewStore.loading ? '分析中...' : '开始预审' }}
      </button>
    </section>

    <!-- 历史记录 -->
    <section class="history-section">
      <h3 class="section-title">历史记录</h3>
      <div v-if="historyStore.items.length" class="history-list">
        <div
          v-for="item in historyStore.items"
          :key="item.task_id"
          class="history-item"
          @click="loadHistory(item.task_id)"
        >
          <span class="history-risk" :class="item.risk_level">{{ item.risk_level?.toUpperCase() || '?' }}</span>
          <span class="history-time">{{ formatTime(item.created_at) }}</span>
        </div>
      </div>
      <p v-else class="empty-hint">暂无历史记录</p>
    </section>

    <!-- 平台热力图 -->
    <section class="heatmap-section">
      <h3 class="section-title">平台覆盖</h3>
      <div class="platform-grid">
        <div
          v-for="p in platforms"
          :key="p"
          class="platform-cell"
        >{{ p }}</div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useReviewStore, useHistoryStore } from '../stores'
import { api } from '../api'

const reviewStore = useReviewStore()
const historyStore = useHistoryStore()

const inputMode = ref<'text' | 'video' | 'mixed'>('text')
const textContent = ref('')
const videoFiles = ref<File[]>([])
const depth = ref<'quick' | 'standard' | 'deep' | 'large_scale'>('standard')
const uploadProgress = ref<Record<string, number>>({})
const isUploading = ref(false)
const fileInput = ref<HTMLInputElement>()

const modes = [
  { key: 'text' as const, label: '文本' },
  { key: 'video' as const, label: '视频' },
  { key: 'mixed' as const, label: '混合' },
]

const canSubmit = computed(() => {
  if (inputMode.value === 'text') return textContent.value.trim().length >= 10
  if (inputMode.value === 'video') return videoFiles.value.length > 0
  return textContent.value.trim().length >= 10 || videoFiles.value.length > 0
})

function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files) videoFiles.value.push(...Array.from(target.files))
}

function handleDrop(e: DragEvent) {
  if (e.dataTransfer?.files) videoFiles.value.push(...Array.from(e.dataTransfer.files))
}

async function uploadVideoFiles(): Promise<string[]> {
  if (videoFiles.value.length === 0) return []

  isUploading.value = true
  const uploadedPaths: string[] = []

  try {
    for (const file of videoFiles.value) {
      const resp = await api.uploadFile(file, (percent) => {
        uploadProgress.value[file.name] = percent
      })
      uploadedPaths.push(resp.data.file_path)
    }
  } finally {
    isUploading.value = false
    uploadProgress.value = {}
  }

  return uploadedPaths
}

async function handleSubmit() {
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
}

function loadHistory(taskId: string) {
  reviewStore.fetchResult(taskId)
}

function formatTime(t: string | null) {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const platforms = [
  '抖音', '微博', '小红书', 'B站', '快手', '知乎', '微信视频号',
  '今日头条', '豆瓣', '贴吧', '虎扑', '公众号',
  'Facebook', 'Twitter', 'TikTok', 'Instagram', 'YouTube', 'Reddit',
]

historyStore.fetchHistory()
</script>

<style scoped>
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px;
}

.section-title {
  font-size: 13px;
  color: #888;
  margin-bottom: 8px;
  font-weight: 600;
}

.mode-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}

.mode-tab {
  flex: 1;
  padding: 6px 0;
  font-size: 12px;
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 4px;
  color: #888;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-tab.active {
  background: #6366f1;
  border-color: #6366f1;
  color: #fff;
}

.text-input {
  width: 100%;
  padding: 8px;
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 13px;
  resize: vertical;
  font-family: inherit;
}

.drop-zone {
  border: 2px dashed #2a2a3e;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  color: #666;
  font-size: 12px;
}

.hint { font-size: 11px; color: #444; margin-top: 4px; }

.file-input { display: none; }

.select-btn {
  margin-top: 8px;
  padding: 4px 12px;
  font-size: 12px;
  background: #1e1e2e;
  border: 1px solid #2a2a3e;
  border-radius: 4px;
  color: #aaa;
  cursor: pointer;
}

.file-list { margin-top: 8px; }

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  background: #1a1a2e;
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 12px;
  color: #aaa;
}

.remove-btn {
  background: none;
  border: none;
  color: #ef4444;
  cursor: pointer;
  font-size: 12px;
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
  background: #2a2a3e;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 2px;
  transition: width 0.3s;
}

.progress-text {
  font-size: 10px;
  color: #888;
  min-width: 28px;
  text-align: right;
}

.options {
  margin-top: 8px;
}

.option-label {
  font-size: 12px;
  color: #888;
  display: block;
  margin-bottom: 4px;
}

.depth-select {
  width: 100%;
  padding: 6px;
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 12px;
}

.submit-btn {
  width: 100%;
  margin-top: 12px;
  padding: 8px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.history-list { max-height: 200px; overflow-y: auto; }

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: #888;
  transition: background 0.2s;
}

.history-item:hover { background: #1a1a2e; }

.history-risk {
  font-weight: 700;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
}

.history-risk.green { background: rgba(34,197,94,0.2); color: #22c55e; }
.history-risk.yellow { background: rgba(234,179,8,0.2); color: #eab308; }
.history-risk.orange { background: rgba(249,115,22,0.2); color: #f97316; }
.history-risk.red { background: rgba(239,68,68,0.2); color: #ef4444; }

.history-time { color: #555; }

.empty-hint { font-size: 12px; color: #444; }

.platform-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
}

.platform-cell {
  padding: 4px 2px;
  text-align: center;
  font-size: 10px;
  color: #666;
  background: #1a1a2e;
  border-radius: 3px;
  cursor: default;
}
</style>
