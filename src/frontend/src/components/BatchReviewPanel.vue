<template>
  <div class="batch-panel">
    <h3 class="section-title">批量快筛（MCN）</h3>
    <p class="hint">每行一条文案，最多 20 条；快速出等级，供人工复核排序。</p>
    <textarea
      v-model="raw"
      class="batch-input"
      rows="6"
      placeholder="文案1&#10;文案2&#10;..."
    />
    <button class="btn" :disabled="loading || !items.length" @click="runBatch">
      {{ loading ? '快筛中…' : `开始快筛（${items.length} 条）` }}
    </button>
    <p v-if="message" class="msg">{{ message }}</p>
    <div v-if="results.length" class="results">
      <div
        v-for="(r, i) in results"
        :key="i"
        class="row"
        :class="`lvl-${r.risk_level || 'error'}`"
      >
        <span class="lvl">{{ levelLabel(r.risk_level) }}</span>
        <span class="score">{{ r.overall_score ?? '—' }}</span>
        <span class="text">{{ r.text_preview }}</span>
        <span class="sug">{{ r.suggestion || r.error || '' }}</span>
      </div>
    </div>
    <p class="disclaimer">批量结果仅供合规参考，不构成法律意见，请人工复核。</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../api'
import { riskLevelLabel } from '../utils/labels'

const raw = ref('')
const loading = ref(false)
const message = ref('')
const results = ref<Array<{
  client_id: string
  risk_level?: string | null
  overall_score?: number | null
  suggestion?: string | null
  error?: string | null
  text_preview: string
}>>([])

const items = computed(() =>
  raw.value
    .split('\n')
    .map((t) => t.trim())
    .filter((t) => t.length >= 10)
    .slice(0, 20)
)

function levelLabel(l?: string | null) {
  return l ? riskLevelLabel(l) : '失败'
}

async function runBatch() {
  loading.value = true
  message.value = ''
  results.value = []
  try {
    const payload = items.value.map((t, i) => ({ client_id: `L${i + 1}`, text: t }))
    const r = await api.batchReview(payload)
    const map = new Map(payload.map((p) => [p.client_id, p.text]))
    results.value = (r.data.results || []).map((x: any) => ({
      ...x,
      text_preview: (map.get(x.client_id) || '').slice(0, 40),
    }))
    message.value = `完成：成功 ${r.data.ok} / 失败 ${r.data.failed}`
  } catch (e: any) {
    message.value = e?.response?.data?.detail || e?.message || '批量快筛失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.batch-panel {
  padding: 12px;
  background: var(--color-surface, #12121a);
  border: 1px solid var(--color-border, #1e1e2e);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.section-title {
  margin: 0;
  font-size: 13px;
  color: var(--color-text, #e0e0e0);
}
.hint {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-secondary, #888);
}
.batch-input {
  width: 100%;
  background: var(--color-bg, #0a0a0f);
  color: var(--color-text, #e0e0e0);
  border: 1px solid var(--color-border, #1e1e2e);
  border-radius: 6px;
  padding: 8px;
  font-size: 12px;
  resize: vertical;
}
.btn {
  background: var(--color-brand, #6366f1);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.msg {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-secondary, #aaa);
}
.results {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.row {
  display: grid;
  grid-template-columns: 56px 40px 1fr auto;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  padding: 6px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
}
.lvl {
  font-weight: 600;
}
.lvl-green .lvl { color: #22c55e; }
.lvl-yellow .lvl { color: #eab308; }
.lvl-orange .lvl { color: #f97316; }
.lvl-red .lvl { color: #ef4444; }
.score {
  font-variant-numeric: tabular-nums;
}
.text {
  color: var(--color-text-secondary, #aaa);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.disclaimer {
  margin: 0;
  font-size: 11px;
  color: var(--color-text-tertiary, #666);
}
</style>
