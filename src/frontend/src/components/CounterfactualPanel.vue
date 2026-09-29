<template>
  <div class="counterfactual-panel">
    <div class="panel-header">
      <h3 class="section-title">反事实改写预估</h3>
      <div class="disclaimer-badge">启发式预估，非全量仿真</div>
    </div>

    <!-- 修改策略选择 -->
    <div class="strategy-section">
      <div class="sub-title">修改策略</div>
      <div class="strategy-options">
        <div
          v-for="s in strategies"
          :key="s.value"
          class="strategy-option"
          :class="{ active: selectedStrategy === s.value }"
          @click="selectedStrategy = s.value"
        >
          <span class="strategy-name">{{ s.label }}</span>
          <span class="strategy-desc">{{ s.desc }}</span>
        </div>
      </div>
    </div>

    <!-- 执行预估按钮 -->
    <NButton
      type="primary"
      size="small"
      block
      :loading="simulating"
      :disabled="!canSimulate"
      @click="runSimulation"
    >
      运行改写预估
    </NButton>

    <!-- 预估/改写失败 -->
    <NAlert v-if="errorMsg" type="error" title="预估未完成" closable @close="errorMsg = ''">
      {{ errorMsg }}
    </NAlert>

    <!-- 预估结果 -->
    <div v-if="result" class="result-section">
      <!-- 修改前后对比 -->
      <div class="comparison-section">
        <div class="sub-title">修改对比</div>
        <div class="text-comparison">
          <div class="text-block before">
            <div class="block-label">修改前</div>
            <div class="block-content">{{ result.original_text?.slice(0, 200) }}</div>
            <div class="block-score">
              风险分: <span :class="scoreClass(result.before?.overall_risk_score || 0)">{{ result.before?.overall_risk_score }}</span>
            </div>
          </div>
          <div class="arrow-icon">→</div>
          <div class="text-block after">
            <div class="block-label">修改后</div>
            <div class="block-content">{{ result.modified_text?.slice(0, 200) }}</div>
            <div class="block-score">
              风险分: <span :class="scoreClass(result.after?.overall_risk_score || 0)">{{ result.after?.overall_risk_score }}</span>
              <span v-if="result.improvement_range" class="range-hint">
                （变化约 {{ result.improvement_range.low }} ~ {{ result.improvement_range.high }} 分，正值=风险下降）
              </span>
            </div>
          </div>
        </div>
        <div v-if="result.strategy?.rewrite_note" class="rewrite-note">
          改写说明：{{ result.strategy.rewrite_note }}
        </div>
      </div>

      <!-- 风险面方向性预估（不承诺必降） -->
      <div class="change-section">
        <div class="sub-title">风险面方向性预估</div>
        <div class="improvement-badge" :class="improvementClass">
          <span class="improvement-icon">{{ improvementIcon }}</span>
          <span class="improvement-value">{{ directionLabel }}</span>
        </div>
        <div v-if="result.comparisons?.length" class="dimension-changes">
          <div v-for="c in result.comparisons" :key="c.dimension" class="dim-change">
            <span class="dim-name">{{ c.dimension }}</span>
            <span class="dim-before">{{ c.before_score }}</span>
            <span class="dim-arrow" :class="c.change_direction">
              {{ c.change_direction === 'improved' ? '↓' : c.change_direction === 'worsened' ? '↑' : '→' }}
            </span>
            <span class="dim-after">{{ c.after_score }}</span>
            <span class="dim-change-val" :class="changeDirectionClass(c.change)">
              {{ c.change > 0 ? '+' : '' }}{{ c.change }}
            </span>
          </div>
        </div>
      </div>

      <!-- 建议 -->
      <div v-if="result.recommendation" class="recommendation-section">
        <div class="recommendation-text">{{ result.recommendation }}</div>
      </div>

      <div v-if="result.disclaimer" class="disclaimer-text">{{ result.disclaimer }}</div>
    </div>

    <!-- 空状态 -->
    <div v-if="!result && !simulating && !errorMsg" class="empty-state">
      <p>选择修改策略并运行改写预估，查看"如果修改了高风险句子，风险面可能怎样变化"</p>
      <p class="empty-note">启发式预估，非全量仿真；结果为区间与方向性参考，不代表真实舆论传播结果。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { NButton, NAlert } from 'naive-ui'
import { v3Api } from '../api'

const props = defineProps<{
  text?: string
  riskItems?: any[]
}>()

const selectedStrategy = ref('soften')
const simulating = ref(false)
const result = ref<any>(null)
const errorMsg = ref('')

const strategies = [
  { value: 'delete', label: '删除', desc: '直接删除高风险句子' },
  { value: 'replace', label: '替换', desc: '用中性表述替换' },
  { value: 'soften', label: '软化', desc: '降低措辞强度' },
  { value: 'rephrase', label: '重述', desc: '用安全表达重述' },
]

const canSimulate = computed(() => props.text && props.riskItems?.length)

const improvementClass = computed(() => {
  if (!result.value) return ''
  const hint = result.value.direction_hint
  if (hint === 'likely_down') return 'improved'
  if (hint === 'likely_up') return 'worsened'
  return 'neutral'
})

const improvementIcon = computed(() => {
  if (!result.value) return ''
  const hint = result.value.direction_hint
  if (hint === 'likely_down') return '↓'
  if (hint === 'likely_up') return '↑'
  return '—'
})

const directionLabel = computed(() => {
  if (!result.value) return ''
  const hint = result.value.direction_hint
  if (hint === 'likely_down') return '风险面可能下降'
  if (hint === 'likely_up') return '风险面可能升高'
  return '方向不确定'
})

function scoreClass(score: number) {
  if (score >= 80) return 'score-red'
  if (score >= 60) return 'score-orange'
  if (score >= 30) return 'score-yellow'
  return 'score-green'
}

function changeDirectionClass(change: number) {
  if (change < 0) return 'change-improved'
  if (change > 0) return 'change-worsened'
  return 'change-neutral'
}

async function runSimulation() {
  if (!canSimulate.value) return

  simulating.value = true
  result.value = null
  errorMsg.value = ''

  try {
    const resp = await v3Api.counterfactualSimulate({
      text: props.text!,
      risk_items: props.riskItems!,
      strategy_type: selectedStrategy.value,
    })
    const data = resp.data
    if (data?.error) {
      errorMsg.value = data.error
      result.value = null
    } else {
      result.value = data
    }
  } catch (e: any) {
    result.value = null
    errorMsg.value = e?.response?.data?.detail || e?.message || '改写预估失败，请稍后重试'
  } finally {
    simulating.value = false
  }
}
</script>

<style scoped>
.counterfactual-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 13px;
  color: #888;
  font-weight: 600;
  margin: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.disclaimer-badge {
  font-size: 10px;
  color: #b45309;
  background: rgba(180, 83, 9, 0.12);
  border: 1px solid rgba(180, 83, 9, 0.3);
  border-radius: 4px;
  padding: 2px 6px;
  white-space: nowrap;
}

.range-hint {
  color: #888;
  font-size: 10px;
}

.rewrite-note {
  margin-top: 6px;
  font-size: 10px;
  color: #888;
  line-height: 1.5;
}

.disclaimer-text {
  margin-top: 8px;
  font-size: 10px;
  color: #b45309;
  line-height: 1.5;
}

.empty-note {
  margin-top: 6px;
  font-size: 10px;
  color: #b45309;
}

.sub-title {
  font-size: 12px;
  color: #666;
  font-weight: 600;
  margin-bottom: 6px;
}

.strategy-section {
  margin-top: 4px;
}

.strategy-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.strategy-option {
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 6px;
  padding: 6px 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.strategy-option.active {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
}

.strategy-name {
  display: block;
  font-size: 12px;
  color: #ccc;
  font-weight: 600;
}

.strategy-desc {
  display: block;
  font-size: 10px;
  color: #666;
  margin-top: 2px;
}

.result-section {
  margin-top: 4px;
}

.comparison-section {
  margin-bottom: 12px;
}

.text-comparison {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.text-block {
  flex: 1;
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  padding: 8px;
}

.text-block.before {
  border-left: 3px solid #ef4444;
}

.text-block.after {
  border-left: 3px solid #22c55e;
}

.block-label {
  font-size: 10px;
  color: #666;
  margin-bottom: 4px;
  font-weight: 600;
}

.block-content {
  font-size: 11px;
  color: #aaa;
  line-height: 1.5;
  max-height: 80px;
  overflow-y: auto;
}

.block-score {
  font-size: 11px;
  color: #888;
  margin-top: 4px;
}

.arrow-icon {
  display: flex;
  align-items: center;
  color: #6366f1;
  font-size: 16px;
}

.score-green { color: #22c55e; font-weight: 700; }
.score-yellow { color: #eab308; font-weight: 700; }
.score-orange { color: #f97316; font-weight: 700; }
.score-red { color: #ef4444; font-weight: 700; }

.change-section {
  margin-bottom: 12px;
}

.improvement-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.improvement-badge.improved {
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.improvement-badge.worsened {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.improvement-badge.neutral {
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.improvement-icon {
  font-size: 16px;
}

.improvement-badge.improved .improvement-icon { color: #22c55e; }
.improvement-badge.worsened .improvement-icon { color: #ef4444; }
.improvement-badge.neutral .improvement-icon { color: #6366f1; }

.improvement-value {
  font-size: 16px;
  font-weight: 700;
}

.improvement-badge.improved .improvement-value { color: #22c55e; }
.improvement-badge.worsened .improvement-value { color: #ef4444; }
.improvement-badge.neutral .improvement-value { color: #6366f1; }

.dimension-changes {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dim-change {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  padding: 2px 6px;
  background: #1a1a2e;
  border-radius: 3px;
}

.dim-name {
  flex: 1;
  color: #aaa;
}

.dim-before, .dim-after {
  min-width: 30px;
  text-align: center;
  color: #888;
}

.dim-arrow {
  font-size: 12px;
}

.dim-arrow.improved { color: #22c55e; }
.dim-arrow.worsened { color: #ef4444; }

.dim-change-val {
  min-width: 40px;
  text-align: right;
  font-weight: 600;
}

.change-improved { color: #22c55e; }
.change-worsened { color: #ef4444; }
.change-neutral { color: #888; }

.recommendation-section {
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  padding: 8px;
}

.recommendation-text {
  font-size: 12px;
  color: #aaa;
  line-height: 1.5;
}

.empty-state {
  text-align: center;
  padding: 20px;
  color: #555;
  font-size: 12px;
  line-height: 1.6;
}
</style>
