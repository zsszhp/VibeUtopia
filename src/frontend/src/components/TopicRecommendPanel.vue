<template>
  <div class="topic-panel">
    <div class="panel-header">
      <h3 class="section-title">选题推荐</h3>
      <span v-if="styleProfile" class="style-badge">{{ styleProfile.style_summary || '风格已就绪' }}</span>
    </div>

    <!-- 博主信息 -->
    <div class="form-row">
      <input
        v-model="bloggerName"
        class="text-field"
        placeholder="博主名称（可选）"
      />
    </div>

    <!-- 历史文案 → 风格画像 -->
    <div class="form-block">
      <div class="form-label">历史文案（每行一条，用于生成风格画像）</div>
      <textarea
        v-model="historyText"
        class="history-input"
        rows="3"
        placeholder="粘贴 1-5 条历史文案，生成话题/语气/节奏/风险偏好/人设…"
      ></textarea>
      <div class="btn-row">
        <button class="btn-secondary" :disabled="styleLoading || !historyText.trim()" @click="buildStyle">
          {{ styleLoading ? '分析中…' : '生成风格画像' }}
        </button>
      </div>
    </div>

    <!-- 风格画像五维 -->
    <div v-if="styleProfile" class="style-grid">
      <div class="style-cell">
        <span class="cell-label">话题</span>
        <span class="cell-value">{{ topicLabel }}</span>
      </div>
      <div class="style-cell">
        <span class="cell-label">语气</span>
        <span class="cell-value">{{ styleProfile.expression?.tone_label || styleProfile.expression?.tone || '—' }}</span>
      </div>
      <div class="style-cell">
        <span class="cell-label">节奏</span>
        <span class="cell-value">{{ styleProfile.expression?.pacing || '—' }}</span>
      </div>
      <div class="style-cell">
        <span class="cell-label">风险偏好</span>
        <span class="cell-value" :class="toleranceClass">{{ styleProfile.risk?.risk_tolerance_label || styleProfile.risk?.risk_tolerance || '—' }}</span>
      </div>
      <div class="style-cell">
        <span class="cell-label">人设</span>
        <span class="cell-value">{{ styleProfile.persona?.role || '—' }}</span>
      </div>
      <div v-if="styleProfile.risk_impact" class="style-impact">
        <span class="cell-label">发布影响</span>
        <span class="impact-text">{{ styleProfile.risk_impact }}</span>
      </div>
    </div>

    <!-- 生成选题 -->
    <div class="btn-row">
      <button class="btn-primary" :disabled="topicLoading" @click="loadTopics">
        {{ topicLoading ? '生成中…' : '获取选题推荐' }}
      </button>
    </div>

    <p v-if="topicError" class="error-text">{{ topicError }}</p>

    <!-- 选题卡 -->
    <div v-if="recommendations.length" class="topic-cards">
      <div v-for="(rec, i) in recommendations" :key="i" class="topic-card" :class="'risk-' + rec.risk_level">
        <div class="card-head">
          <span class="card-index">选题 {{ i + 1 }}</span>
          <span class="safety-score" :class="safetyClass(rec.safety_score)">
            安全分 {{ rec.safety_score?.toFixed?.(0) ?? rec.safety_score }}
          </span>
          <span class="risk-tag" :class="'risk-' + rec.risk_level">{{ riskLabel(rec.risk_level) }}</span>
        </div>

        <div class="card-title">{{ rec.topic }}</div>

        <div class="card-row">
          <span class="row-label">切入点</span>
          <span class="row-value">{{ rec.angle }}</span>
        </div>
        <div class="card-row">
          <span class="row-label">预期效果</span>
          <span class="row-value">{{ rec.estimated_reach || '中等' }}</span>
        </div>
        <div class="card-row">
          <span class="row-label">风险预估</span>
          <span class="row-value">{{ rec.risk_note || riskLabel(rec.risk_level) }}</span>
        </div>
        <div class="card-row">
          <span class="row-label">推荐理由</span>
          <span class="row-value">{{ rec.reason }}</span>
        </div>
        <div v-if="rec.risk_impact" class="card-impact">
          <span class="row-label">发布判断</span>
          <span class="impact-text">{{ rec.risk_impact }}</span>
        </div>

        <div class="card-actions">
          <button class="btn-secondary btn-sm" @click="previewDraft(rec)">预审此选题草稿</button>
        </div>
      </div>
    </div>

    <p v-else-if="!topicLoading" class="empty-hint">
      点击「获取选题推荐」生成 3 张选题卡，每张含切入点、预期效果、风险预估与发布判断
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { bloggerApi } from '../api'
import { useReviewStore } from '../stores'

const props = defineProps<{
  styleProfileProp?: any
}>()

const emit = defineEmits<{
  (e: 'style-profile', profile: any): void
}>()

const reviewStore = useReviewStore()

const bloggerName = ref('')
const historyText = ref('')
const styleProfile = ref<any>(props.styleProfileProp || null)
const styleLoading = ref(false)
const recommendations = ref<any[]>([])
const topicLoading = ref(false)
const topicError = ref('')

const topicLabel = computed(() => {
  const topics = styleProfile.value?.topics?.primary_topics || []
  return topics.map((t: any) => t.topic || t).join('、') || '—'
})

const toleranceClass = computed(() => {
  const t = styleProfile.value?.risk?.risk_tolerance
  if (t === 'aggressive') return 'tol-aggressive'
  if (t === 'conservative') return 'tol-conservative'
  return 'tol-moderate'
})

function riskLabel(level: string) {
  const map: Record<string, string> = {
    safe: '安全', low: '较低', medium: '中等', high: '偏高', critical: '高危',
  }
  return map[level] || level || '待评估'
}

function safetyClass(score: number) {
  if (score >= 80) return 'safety-high'
  if (score >= 55) return 'safety-mid'
  return 'safety-low'
}

async function buildStyle() {
  const lines = historyText.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!lines.length) return
  styleLoading.value = true
  try {
    const resp = await bloggerApi.getStyleProfile({
      blogger_name: bloggerName.value || undefined,
      contents: lines,
    })
    styleProfile.value = resp.data
    emit('style-profile', resp.data)
  } catch (e: any) {
    styleProfile.value = null
    topicError.value = '风格画像生成失败：' + (e?.message || '未知错误')
  } finally {
    styleLoading.value = false
  }
}

async function loadTopics() {
  topicLoading.value = true
  topicError.value = ''
  try {
    const resp = await bloggerApi.recommendTopics({
      blogger_profile: styleProfile.value || {},
      blogger_name: bloggerName.value || undefined,
    })
    recommendations.value = resp.data.recommendations || []
    if (!recommendations.value.length) {
      topicError.value = resp.data.error || '暂无可用热点数据，可稍后重试'
    }
  } catch (e: any) {
    recommendations.value = []
    topicError.value = '选题推荐失败：' + (e?.message || '未知错误')
  } finally {
    topicLoading.value = false
  }
}

function previewDraft(rec: any) {
  const draft = `${rec.topic}\n\n${rec.brief || rec.angle || ''}\n\n【切入点】${rec.angle || ''}`.trim()
  reviewStore.applyDraft(draft)
}
</script>

<style scoped>
.topic-panel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.section-title {
  font-size: var(--fs-md);
  color: var(--text-tertiary);
  font-weight: 600;
  margin: 0;
}

.style-badge {
  font-size: var(--fs-2xs);
  color: var(--brand-400);
  background: var(--brand-soft);
  padding: 2px 8px;
  border-radius: var(--r-full);
}

.form-block {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.form-label {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.text-field,
.history-input {
  width: 100%;
  background: var(--bg-inset);
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  padding: 6px 8px;
  color: var(--text-primary);
  font-size: var(--fs-sm);
  outline: none;
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
}

.text-field:focus,
.history-input:focus {
  border-color: var(--brand-600);
}

.btn-row {
  display: flex;
  gap: var(--sp-2);
}

.btn-primary,
.btn-secondary {
  border: none;
  border-radius: var(--r-sm);
  padding: 6px 12px;
  font-size: var(--fs-sm);
  cursor: pointer;
  transition: opacity var(--dur-fast);
}

.btn-primary {
  background: var(--brand-600);
  color: #fff;
}

.btn-secondary {
  background: var(--bg-overlay);
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
}

.btn-sm {
  padding: 4px 10px;
  font-size: var(--fs-xs);
}

.btn-primary:disabled,
.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.style-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-2);
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
  padding: var(--sp-3);
}

.style-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cell-label {
  font-size: var(--fs-2xs);
  color: var(--text-tertiary);
}

.cell-value {
  font-size: var(--fs-sm);
  color: var(--text-primary);
}

.tol-aggressive { color: var(--risk-high); }
.tol-moderate { color: var(--risk-warn); }
.tol-conservative { color: var(--risk-safe); }

.style-impact {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: var(--sp-1);
  border-top: 1px solid var(--border-subtle);
}

.impact-text {
  font-size: var(--fs-xs);
  color: var(--text-secondary);
  line-height: 1.5;
}

.topic-cards {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.topic-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-left: 3px solid var(--brand-600);
  border-radius: var(--r-md);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.topic-card.risk-safe { border-left-color: var(--risk-safe); }
.topic-card.risk-low { border-left-color: var(--risk-safe); }
.topic-card.risk-medium { border-left-color: var(--risk-warn); }
.topic-card.risk-high { border-left-color: var(--risk-high); }
.topic-card.risk-critical { border-left-color: var(--risk-critical); }

.card-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.card-index {
  font-size: var(--fs-2xs);
  color: var(--text-tertiary);
}

.safety-score {
  font-size: var(--fs-xs);
  font-weight: 700;
  margin-left: auto;
}

.safety-high { color: var(--risk-safe); }
.safety-mid { color: var(--risk-warn); }
.safety-low { color: var(--risk-critical); }

.risk-tag {
  font-size: var(--fs-2xs);
  padding: 1px 6px;
  border-radius: var(--r-full);
}

.risk-tag.risk-safe,
.risk-tag.risk-low { background: var(--risk-safe-soft); color: var(--risk-safe); }
.risk-tag.risk-medium { background: var(--risk-warn-soft); color: var(--risk-warn); }
.risk-tag.risk-high { background: var(--risk-high-soft); color: var(--risk-high); }
.risk-tag.risk-critical { background: var(--risk-critical-soft); color: var(--risk-critical); }

.card-title {
  font-size: var(--fs-lg);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.4;
}

.card-row,
.card-impact {
  display: flex;
  gap: var(--sp-2);
  font-size: var(--fs-xs);
  line-height: 1.5;
}

.card-impact {
  background: var(--bg-inset);
  border-radius: var(--r-sm);
  padding: var(--sp-2);
  margin-top: var(--sp-1);
}

.row-label {
  color: var(--brand-400);
  min-width: 52px;
  flex-shrink: 0;
  font-weight: 600;
}

.row-value {
  color: var(--text-secondary);
  flex: 1;
}

.card-actions {
  margin-top: var(--sp-2);
  display: flex;
  justify-content: flex-end;
}

.error-text {
  font-size: var(--fs-xs);
  color: var(--risk-critical);
  margin: 0;
}

.empty-hint {
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  margin: 0;
}
</style>
