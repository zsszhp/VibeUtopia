<template>
  <div class="analysis-dashboard">
    <!-- Section 1: Pipeline Overview -->
    <div class="pipeline-section">
      <div class="section-header">
        <span class="section-icon">⬡</span>
        <span class="section-title">分析流水线</span>
        <span class="pipeline-status-badge" :class="pipelineStatusClass">{{ pipelineStatusText }}</span>
      </div>
      <div class="pipeline-track">
        <div
          v-for="(step, idx) in steps"
          :key="step.key"
          class="pipeline-step"
          :class="{
            'step-done': stepIndex > idx,
            'step-active': step.key === currentStep,
            'step-pending': stepIndex < idx,
          }"
        >
          <div class="step-connector" v-if="idx > 0">
            <div class="connector-line" :class="{ filled: stepIndex >= idx }"></div>
            <div class="connector-flow" v-if="stepIndex >= idx"></div>
          </div>
          <div class="step-node">
            <div class="node-ring">
              <div class="node-core">
                <svg v-if="stepIndex > idx" class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span v-else-if="step.key === currentStep" class="node-number">{{ idx + 1 }}</span>
                <span v-else class="node-number dim">{{ idx + 1 }}</span>
              </div>
            </div>
            <div class="step-label">{{ step.label }}</div>
            <div v-if="step.key === currentStep" class="step-progress">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: `${Math.round(progress * 100)}%` }"></div>
              </div>
              <span class="progress-text">{{ Math.round(progress * 100) }}%</span>
            </div>
            <div v-else-if="stepIndex > idx" class="step-done-badge">已完成</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 2: Real-time Detail Panel -->
    <div class="detail-section">
      <!-- Left Column: Module Info -->
      <div class="detail-left">
        <div class="panel-card">
          <div class="card-header">
            <span class="card-icon">◈</span>
            <span class="card-title">当前模块</span>
          </div>
          <div class="module-info">
            <div class="module-name-row">
              <span class="module-name">{{ currentStepLabel }}</span>
              <span class="module-pct">{{ Math.round(progress * 100) }}%</span>
            </div>
            <div class="module-progress-bar">
              <div class="module-progress-fill" :style="{ width: `${Math.round(progress * 100)}%` }"></div>
            </div>
            <p v-if="detail" class="module-detail">{{ detail }}</p>
          </div>
        </div>

        <div class="panel-card">
          <div class="card-header">
            <span class="card-icon">◉</span>
            <span class="card-title">维度进度</span>
          </div>
          <div class="dimensions-grid">
            <div class="dim-column">
              <div class="dim-column-title completed">已完成</div>
              <div v-if="completedDimensions?.length" class="dim-list">
                <div v-for="dim in completedDimensions" :key="dim" class="dim-item completed">
                  <span class="dim-check">✓</span>
                  <span>{{ dim }}</span>
                </div>
              </div>
              <div v-else class="dim-empty">暂无</div>
            </div>
            <div class="dim-column">
              <div class="dim-column-title remaining">待处理</div>
              <div v-if="remainingDimensions?.length" class="dim-list">
                <div v-for="dim in remainingDimensions" :key="dim" class="dim-item remaining">
                  <span class="dim-dot"></span>
                  <span>{{ dim }}</span>
                </div>
              </div>
              <div v-else class="dim-empty">全部完成</div>
            </div>
          </div>
        </div>

        <div v-if="subTasks?.length" class="panel-card">
          <div class="card-header">
            <span class="card-icon">☰</span>
            <span class="card-title">子任务</span>
          </div>
          <div class="subtask-list">
            <div
              v-for="task in subTasks"
              :key="task.name"
              class="subtask-item"
              :class="task.status"
            >
              <span class="subtask-indicator"></span>
              <span class="subtask-name">{{ task.name }}</span>
              <span class="subtask-badge">{{ subTaskStatusLabel(task.status) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Frame Analysis -->
      <div class="detail-right">
        <div v-if="frameProgress" class="panel-card">
          <div class="card-header">
            <span class="card-icon">▦</span>
            <span class="card-title">帧分析预览</span>
            <span class="frame-counter">{{ frameProgress.currentFrame }} / {{ frameProgress.totalFrames }}</span>
          </div>
          <div class="frame-preview-area">
            <div class="frame-main">
              <img
                v-if="frameProgress.currentFrameUrl"
                :src="frameProgress.currentFrameUrl"
                class="frame-thumbnail current"
                alt="当前帧"
              />
              <div v-else class="frame-placeholder current">
                <span>帧 {{ frameProgress.currentFrame }}</span>
              </div>
              <div class="frame-meta">
                <span class="frame-type-badge">{{ frameProgress.frameType }}</span>
                <span class="delta-score" :class="deltaScoreClass">
                  Δ {{ frameProgress.deltaScore >= 0 ? '+' : '' }}{{ frameProgress.deltaScore.toFixed(2) }}
                </span>
              </div>
            </div>
            <div class="frame-task-label">{{ frameProgress.currentTask }}</div>
          </div>
        </div>

        <div v-if="sequenceDescriptions?.length" class="panel-card">
          <div class="card-header">
            <span class="card-icon">⟿</span>
            <span class="card-title">序列描述</span>
          </div>
          <div class="sequence-list">
            <div
              v-for="seq in sequenceDescriptions"
              :key="seq.segmentIndex"
              class="sequence-item"
            >
              <div class="seq-header">
                <span class="seq-index">片段 {{ seq.segmentIndex }}</span>
              </div>
              <p class="seq-description">{{ seq.description }}</p>

              <!-- Causal Chain -->
              <div v-if="seq.causalEvents?.length" class="causal-chain">
                <span class="chain-label">因果链</span>
                <div class="chain-nodes">
                  <template v-for="(event, eIdx) in seq.causalEvents" :key="eIdx">
                    <div class="chain-node">
                      <span class="chain-event">{{ typeof event === 'string' ? event : event.description || event.name || JSON.stringify(event) }}</span>
                    </div>
                    <svg v-if="eIdx < seq.causalEvents.length - 1" class="chain-arrow" viewBox="0 0 20 12" fill="none">
                      <path d="M0 6H14M14 6L9 1M14 6L9 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </template>
                </div>
              </div>

              <!-- Actions -->
              <div v-if="seq.actions?.length" class="action-list">
                <span class="action-label">行为检测</span>
                <div class="action-items">
                  <span
                    v-for="(action, aIdx) in seq.actions"
                    :key="aIdx"
                    class="action-tag"
                  >
                    {{ typeof action === 'string' ? action : action.name || action.type || JSON.stringify(action) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 3: Risk Alert Stream -->
    <div v-if="riskAlerts?.length" class="alert-section">
      <div class="section-header">
        <span class="section-icon">⚠</span>
        <span class="section-title">风险预警流</span>
        <span class="alert-count">{{ riskAlerts.length }} 条预警</span>
      </div>
      <div class="alert-stream">
        <TransitionGroup name="alert-slide">
          <div
            v-for="alert in riskAlerts"
            :key="`${alert.dimension}-${alert.timestamp}`"
            class="alert-item"
            :class="`severity-${alert.severity}`"
          >
            <div class="alert-severity-bar"></div>
            <div class="alert-body">
              <div class="alert-top-row">
                <span class="alert-dimension">{{ alert.dimension }}</span>
                <span class="alert-score">{{ alert.score }}</span>
                <span class="alert-severity-tag">{{ severityLabel(alert.severity) }}</span>
              </div>
              <p class="alert-detail">{{ alert.detail }}</p>
              <div class="alert-meta">
                <span v-if="alert.frameIndex !== undefined" class="alert-frame">帧 #{{ alert.frameIndex }}</span>
                <span class="alert-time">{{ formatTime(alert.timestamp) }}</span>
              </div>
            </div>
          </div>
        </TransitionGroup>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface FrameProgress {
  currentFrame: number
  totalFrames: number
  currentFrameUrl: string
  frameType: string
  deltaScore: number
  currentTask: string
}

interface SequenceDescription {
  segmentIndex: number
  description: string
  causalEvents: any[]
  actions: any[]
}

interface RiskAlert {
  dimension: string
  score: number
  frameIndex?: number
  detail: string
  severity: string
  timestamp: number
}

interface SubTask {
  name: string
  status: 'completed' | 'in_progress' | 'pending'
}

interface Props {
  currentStep: string
  progress: number
  detail?: string
  completedDimensions?: string[]
  remainingDimensions?: string[]
  frameProgress?: FrameProgress
  sequenceDescriptions?: SequenceDescription[]
  riskAlerts?: RiskAlert[]
  subTasks?: SubTask[]
}

const props = withDefaults(defineProps<Props>(), {
  detail: '',
  completedDimensions: () => [],
  remainingDimensions: () => [],
  frameProgress: undefined,
  sequenceDescriptions: () => [],
  riskAlerts: () => [],
  subTasks: () => [],
})

const steps = [
  { key: 'understanding', label: '内容理解' },
  { key: 'assessment', label: '风险评估' },
  { key: 'signal', label: '信号采集' },
  { key: 'simulation', label: '仿真推演' },
  { key: 'report', label: '报告生成' },
]

const stepIndex = computed(() => steps.findIndex(s => s.key === props.currentStep))
const currentStepLabel = computed(() => {
  const found = steps.find(s => s.key === props.currentStep)
  return found ? found.label : props.currentStep
})

const pipelineStatusClass = computed(() => {
  if (stepIndex.value < 0) return 'status-idle'
  if (stepIndex.value >= steps.length - 1 && props.progress >= 1) return 'status-complete'
  return 'status-running'
})

const pipelineStatusText = computed(() => {
  if (stepIndex.value < 0) return '待启动'
  if (stepIndex.value >= steps.length - 1 && props.progress >= 1) return '已完成'
  return '运行中'
})

const deltaScoreClass = computed(() => {
  if (!props.frameProgress) return ''
  return props.frameProgress.deltaScore >= 0 ? 'delta-positive' : 'delta-negative'
})

function subTaskStatusLabel(status: string): string {
  const map: Record<string, string> = {
    completed: '已完成',
    in_progress: '进行中',
    pending: '待处理',
  }
  return map[status] || status
}

function severityLabel(severity: string): string {
  const map: Record<string, string> = {
    critical: '严重',
    high: '高危',
    medium: '中危',
    low: '低危',
  }
  return map[severity] || severity
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}
</script>

<style scoped>
/* ===== Root Container ===== */
.analysis-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: linear-gradient(145deg, #0a0a14 0%, #0d0d1a 50%, #0a0e1a 100%);
  border-radius: 12px;
  border: 1px solid rgba(99, 102, 241, 0.12);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: #c8c8d4;
  min-width: 0;
}

/* ===== Section Header ===== */
.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.section-icon {
  font-size: 14px;
  color: #6366f1;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e0ec;
  letter-spacing: 0.5px;
}

/* ===== Pipeline Section ===== */
.pipeline-section {
  background: rgba(15, 15, 28, 0.7);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(99, 102, 241, 0.1);
  border-radius: 10px;
  padding: 16px;
}

.pipeline-status-badge {
  margin-left: auto;
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 500;
}

.pipeline-status-badge.status-running {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.pipeline-status-badge.status-complete {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.pipeline-status-badge.status-idle {
  background: rgba(100, 100, 120, 0.15);
  color: #888;
  border: 1px solid rgba(100, 100, 120, 0.2);
}

.pipeline-track {
  display: flex;
  align-items: flex-start;
  gap: 0;
  overflow-x: auto;
  padding: 8px 0;
}

.pipeline-step {
  display: flex;
  align-items: flex-start;
  flex-shrink: 0;
}

.step-connector {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 2px;
  position: relative;
}

.connector-line {
  width: 32px;
  height: 2px;
  background: rgba(40, 40, 60, 0.8);
  border-radius: 1px;
  position: relative;
  overflow: hidden;
}

.connector-line.filled {
  background: rgba(99, 102, 241, 0.3);
}

.connector-flow {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, #6366f1, transparent);
  animation: flowRight 2s infinite;
}

@keyframes flowRight {
  0% { left: -100%; }
  100% { left: 100%; }
}

.step-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.node-ring {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #28283e;
  background: rgba(15, 15, 28, 0.9);
  transition: all 0.4s ease;
}

.step-active .node-ring {
  border-color: #6366f1;
  box-shadow: 0 0 16px rgba(99, 102, 241, 0.4), inset 0 0 8px rgba(99, 102, 241, 0.1);
  animation: nodePulse 2s ease-in-out infinite;
}

.step-done .node-ring {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.2);
}

@keyframes nodePulse {
  0%, 100% {
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.3), inset 0 0 6px rgba(99, 102, 241, 0.08);
  }
  50% {
    box-shadow: 0 0 24px rgba(99, 102, 241, 0.55), inset 0 0 12px rgba(99, 102, 241, 0.15);
  }
}

.node-core {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.check-icon {
  width: 18px;
  height: 18px;
  color: #22c55e;
}

.node-number {
  font-size: 14px;
  font-weight: 700;
  color: #818cf8;
}

.node-number.dim {
  color: #444460;
}

.step-label {
  font-size: 11px;
  color: #555570;
  white-space: nowrap;
  transition: color 0.3s;
}

.step-active .step-label {
  color: #c7d2fe;
  font-weight: 600;
}

.step-done .step-label {
  color: #86efac;
}

.step-progress {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}

.progress-bar {
  width: 48px;
  height: 3px;
  background: rgba(40, 40, 60, 0.6);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #818cf8);
  border-radius: 2px;
  transition: width 0.5s ease;
}

.progress-text {
  font-size: 10px;
  color: #818cf8;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.step-done-badge {
  font-size: 9px;
  color: #4ade80;
  background: rgba(34, 197, 94, 0.1);
  padding: 1px 6px;
  border-radius: 4px;
  margin-top: 2px;
}

/* ===== Detail Section ===== */
.detail-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

@media (max-width: 768px) {
  .detail-section {
    grid-template-columns: 1fr;
  }
}

.detail-left,
.detail-right {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ===== Panel Card ===== */
.panel-card {
  background: rgba(15, 15, 28, 0.6);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(99, 102, 241, 0.08);
  border-radius: 10px;
  padding: 14px;
  transition: border-color 0.3s;
}

.panel-card:hover {
  border-color: rgba(99, 102, 241, 0.18);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.card-icon {
  font-size: 12px;
  color: #6366f1;
}

.card-title {
  font-size: 12px;
  font-weight: 600;
  color: #a0a0b8;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.frame-counter {
  margin-left: auto;
  font-size: 11px;
  color: #6366f1;
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

/* ===== Module Info ===== */
.module-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.module-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.module-name {
  font-size: 16px;
  font-weight: 700;
  color: #e0e0ec;
}

.module-pct {
  font-size: 20px;
  font-weight: 800;
  color: #818cf8;
  font-variant-numeric: tabular-nums;
}

.module-progress-bar {
  height: 4px;
  background: rgba(40, 40, 60, 0.6);
  border-radius: 2px;
  overflow: hidden;
}

.module-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #a78bfa);
  border-radius: 2px;
  transition: width 0.5s ease;
}

.module-detail {
  font-size: 12px;
  color: #8888a0;
  line-height: 1.5;
  margin: 0;
}

/* ===== Dimensions ===== */
.dimensions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.dim-column-title {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 8px;
}

.dim-column-title.completed {
  color: #4ade80;
}

.dim-column-title.remaining {
  color: #f59e0b;
}

.dim-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dim-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 3px 0;
}

.dim-item.completed {
  color: #86efac;
}

.dim-item.remaining {
  color: #a0a0b8;
}

.dim-check {
  font-size: 10px;
  color: #22c55e;
  font-weight: 700;
}

.dim-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #f59e0b;
  flex-shrink: 0;
}

.dim-empty {
  font-size: 11px;
  color: #555;
  font-style: italic;
}

/* ===== Sub Tasks ===== */
.subtask-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.subtask-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(20, 20, 36, 0.5);
  font-size: 12px;
  transition: background 0.2s;
}

.subtask-item:hover {
  background: rgba(30, 30, 50, 0.7);
}

.subtask-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.subtask-item.completed .subtask-indicator {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.4);
}

.subtask-item.in_progress .subtask-indicator {
  background: #6366f1;
  box-shadow: 0 0 6px rgba(99, 102, 241, 0.4);
  animation: subtaskPulse 1.5s infinite;
}

.subtask-item.pending .subtask-indicator {
  background: #444;
}

@keyframes subtaskPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.subtask-name {
  flex: 1;
  color: #c0c0d0;
}

.subtask-item.completed .subtask-name {
  color: #86efac;
}

.subtask-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.subtask-item.completed .subtask-badge {
  background: rgba(34, 197, 94, 0.12);
  color: #4ade80;
}

.subtask-item.in_progress .subtask-badge {
  background: rgba(99, 102, 241, 0.12);
  color: #818cf8;
}

.subtask-item.pending .subtask-badge {
  background: rgba(100, 100, 120, 0.12);
  color: #666;
}

/* ===== Frame Preview ===== */
.frame-preview-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.frame-main {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.frame-thumbnail {
  width: 48px;
  height: 36px;
  border-radius: 4px;
  object-fit: cover;
  border: 1px solid rgba(99, 102, 241, 0.3);
  flex-shrink: 0;
}

.frame-thumbnail.current {
  border-color: #6366f1;
  box-shadow: 0 0 8px rgba(99, 102, 241, 0.25);
}

.frame-placeholder {
  width: 48px;
  height: 36px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #555;
  background: rgba(20, 20, 36, 0.8);
  border: 1px dashed #333;
  flex-shrink: 0;
}

.frame-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.frame-type-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(99, 102, 241, 0.12);
  color: #818cf8;
  display: inline-block;
  width: fit-content;
}

.delta-score {
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.delta-positive {
  color: #f59e0b;
}

.delta-negative {
  color: #22c55e;
}

.frame-task-label {
  font-size: 11px;
  color: #777;
  padding: 4px 8px;
  background: rgba(20, 20, 36, 0.5);
  border-radius: 4px;
}

/* ===== Sequence Descriptions ===== */
.sequence-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sequence-item {
  padding: 10px;
  background: rgba(20, 20, 36, 0.4);
  border-radius: 8px;
  border-left: 2px solid rgba(99, 102, 241, 0.3);
}

.seq-header {
  margin-bottom: 4px;
}

.seq-index {
  font-size: 11px;
  font-weight: 600;
  color: #818cf8;
}

.seq-description {
  font-size: 12px;
  color: #b0b0c4;
  line-height: 1.5;
  margin: 0 0 8px;
}

/* ===== Causal Chain ===== */
.causal-chain {
  margin-bottom: 8px;
}

.chain-label,
.action-label {
  font-size: 10px;
  font-weight: 600;
  color: #6366f1;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
  display: block;
}

.chain-nodes {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.chain-node {
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 4px;
  padding: 2px 8px;
}

.chain-event {
  font-size: 11px;
  color: #a5b4fc;
}

.chain-arrow {
  width: 16px;
  height: 10px;
  color: #6366f1;
  flex-shrink: 0;
}

/* ===== Actions ===== */
.action-list {
  margin-top: 4px;
}

.action-items {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.action-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(168, 85, 247, 0.1);
  color: #c084fc;
  border: 1px solid rgba(168, 85, 247, 0.15);
}

/* ===== Risk Alert Section ===== */
.alert-section {
  background: rgba(15, 15, 28, 0.5);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(239, 68, 68, 0.1);
  border-radius: 10px;
  padding: 14px;
}

.alert-count {
  margin-left: auto;
  font-size: 11px;
  color: #ef4444;
  font-weight: 500;
}

.alert-stream {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
}

.alert-stream::-webkit-scrollbar {
  width: 4px;
}

.alert-stream::-webkit-scrollbar-track {
  background: transparent;
}

.alert-stream::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.2);
  border-radius: 2px;
}

.alert-item {
  display: flex;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(20, 20, 36, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.03);
  transition: all 0.2s;
}

.alert-item:hover {
  background: rgba(25, 25, 42, 0.7);
}

.alert-severity-bar {
  width: 3px;
  border-radius: 2px;
  flex-shrink: 0;
}

.severity-critical .alert-severity-bar {
  background: #ef4444;
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
}

.severity-high .alert-severity-bar {
  background: #f97316;
  box-shadow: 0 0 6px rgba(249, 115, 22, 0.3);
}

.severity-medium .alert-severity-bar {
  background: #eab308;
}

.severity-low .alert-severity-bar {
  background: #6366f1;
}

.alert-body {
  flex: 1;
  min-width: 0;
}

.alert-top-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
}

.alert-dimension {
  font-size: 12px;
  font-weight: 600;
  color: #e0e0ec;
}

.alert-score {
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.severity-critical .alert-score {
  color: #ef4444;
}

.severity-high .alert-score {
  color: #f97316;
}

.severity-medium .alert-score {
  color: #eab308;
}

.severity-low .alert-score {
  color: #818cf8;
}

.alert-severity-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: auto;
}

.severity-critical .alert-severity-tag {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.severity-high .alert-severity-tag {
  background: rgba(249, 115, 22, 0.15);
  color: #fb923c;
}

.severity-medium .alert-severity-tag {
  background: rgba(234, 179, 8, 0.15);
  color: #facc15;
}

.severity-low .alert-severity-tag {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
}

.alert-detail {
  font-size: 11px;
  color: #8888a0;
  line-height: 1.4;
  margin: 0;
}

.alert-meta {
  display: flex;
  gap: 10px;
  margin-top: 4px;
  font-size: 10px;
  color: #555;
}

/* ===== Alert Transition ===== */
.alert-slide-enter-active {
  transition: all 0.4s ease-out;
}

.alert-slide-leave-active {
  transition: all 0.3s ease-in;
}

.alert-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.alert-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

.alert-slide-move {
  transition: transform 0.3s ease;
}
</style>
