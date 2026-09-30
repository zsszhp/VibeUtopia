<template>
  <div class="workbench">
    <!-- Verdict Banner：结论前置，3 秒内看清能不能发 -->
    <div
      v-if="reviewStore.result"
      class="verdict-banner"
      :class="`verdict-${verdict.level}`"
    >
      <div class="verdict-left">
        <div class="verdict-label">{{ verdict.label }}</div>
        <div class="verdict-sub">
          <span v-if="highRiskCount > 0">{{ highRiskCount }} 项需处理</span>
          <span v-else>无高风险项</span>
          <span v-if="confidenceText" class="verdict-conf">分析完整度 {{ confidenceText }}</span>
        </div>
        <p class="verdict-advice">{{ verdict.advice }}</p>
      </div>
      <div class="verdict-score-wrap">
        <div class="verdict-score tabular-nums">{{ scoreDisplay }}</div>
        <div class="verdict-score-caption">综合风险 / 100</div>
        <div class="threshold-bar" aria-hidden="true">
          <div
            v-for="seg in thresholdSegments"
            :key="seg.key"
            class="threshold-seg"
            :class="{ active: seg.active }"
            :style="{ background: seg.color }"
          ></div>
        </div>
        <div class="threshold-labels">
          <span>0</span><span>30</span><span>60</span><span>80</span><span>100</span>
        </div>
      </div>
    </div>

    <!-- 分析流水线 - 使用增强版 AnalysisDashboard -->
    <AnalysisDashboard
      :current-step="reviewStore.currentStep"
      :progress="reviewStore.progressPercent"
      :detail="reviewStore.progress?.detail"
      :completed-dimensions="reviewStore.progress?.completed_dimensions"
      :remaining-dimensions="reviewStore.progress?.remaining_dimensions"
      :frame-progress="reviewStore.frameProgress"
      :sequence-descriptions="reviewStore.sequenceDescriptions"
      :risk-alerts="reviewStore.riskAlerts"
      :sub-tasks="reviewStore.subTasks"
    />

    <!-- 风险仪表盘 -->
    <div v-if="reviewStore.result" class="dashboard-grid">
      <RiskGauge :score="reviewStore.result.overall_risk ?? 0" :level="reviewStore.result.risk_level ?? 'green'" />
      <DimensionRadar v-if="reviewStore.result.dimensions" :dimensions="reviewStore.result.dimensions" />
      <PlatformReactions v-if="reviewStore.result.platform_reactions" :reactions="reviewStore.result.platform_reactions" />
    </div>

    <!-- 审核工作流与报告导出 -->
    <WorkflowExportBar v-if="reviewStore.result" />

    <!-- 热点关联摘要 -->
    <div v-if="reviewStore.result?.signal_correlations?.length" class="signal-summary">
      <h3 class="summary-title">热点关联摘要</h3>
      <div class="signal-chips">
        <span v-for="sc in reviewStore.result.signal_correlations.slice(0, 5)" :key="sc.signal_id" class="signal-chip">
          {{ sc.title }} <small class="tabular-nums">({{ (sc.correlation_score * 100).toFixed(0) }}%)</small>
        </span>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!reviewStore.result && !reviewStore.loading" class="empty-state">
      <p>在左侧输入文案或上传视频开始预审</p>
      <button class="example-btn" @click="loadExample">
        填入示例文案
      </button>
      <p class="empty-hint">发布前 3 分钟自查：能不能发、哪里改、怎么改</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useReviewStore } from '../stores'
import { scoreVerdict, RISK_THRESHOLDS } from '../utils/labels'

const EXAMPLE_TEXT =
  '好一个为人民服务，真是优秀，懂的都懂。所谓的英雄事迹都是编出来的，历史书上的内容都是胜利者写的。某地区的习俗实在太落后了，我们应该用先进的方式去改造他们。我有内部消息某只股票下周会暴涨，赶紧全仓买入！'

function loadExample() {
  reviewStore.applyDraft(EXAMPLE_TEXT)
}
import AnalysisDashboard from '../components/AnalysisDashboard.vue'
import RiskGauge from '../components/RiskGauge.vue'
import DimensionRadar from '../components/DimensionRadar.vue'
import PlatformReactions from '../components/PlatformReactions.vue'
import WorkflowExportBar from '../components/WorkflowExportBar.vue'

const reviewStore = useReviewStore()

const score = computed(() => reviewStore.result?.overall_risk ?? 0)
const verdict = computed(() => scoreVerdict(score.value))
const scoreDisplay = computed(() => Math.round(score.value))

const confidenceText = computed(() => {
  const c = reviewStore.result?.confidence
  return c === undefined ? '' : `${Math.round(c * 100)}%`
})

const highRiskCount = computed(() => {
  const dims = reviewStore.result?.dimensions || []
  return dims.filter((d: any) => d.severity === 'orange' || d.severity === 'red').length
})

// 四段阈值条：0-29 / 30-59 / 60-79 / 80-100
const thresholdSegments = computed(() => {
  const s = score.value
  return [
    { key: 'safe', color: 'var(--risk-safe)', active: s < RISK_THRESHOLDS.warn },
    { key: 'warn', color: 'var(--risk-warn)', active: s >= RISK_THRESHOLDS.warn && s < RISK_THRESHOLDS.high },
    { key: 'high', color: 'var(--risk-high)', active: s >= RISK_THRESHOLDS.high && s < RISK_THRESHOLDS.critical },
    { key: 'critical', color: 'var(--risk-critical)', active: s >= RISK_THRESHOLDS.critical },
  ]
})
</script>

<style scoped>
.workbench {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.verdict-banner {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: var(--sp-6);
  min-height: 96px;
  padding: var(--sp-4) var(--sp-5);
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-left: 4px solid var(--border-default);
  border-radius: var(--r-md);
}

.verdict-banner.verdict-green { border-left-color: var(--risk-safe); background: var(--risk-safe-soft); }
.verdict-banner.verdict-yellow { border-left-color: var(--risk-warn); background: var(--risk-warn-soft); }
.verdict-banner.verdict-orange { border-left-color: var(--risk-high); background: var(--risk-high-soft); }
.verdict-banner.verdict-red { border-left-color: var(--risk-critical); background: var(--risk-critical-soft); }

.verdict-left {
  flex: 1;
  min-width: 0;
}

.verdict-label {
  font-size: var(--fs-2xl);
  font-weight: 700;
  line-height: 1.2;
  color: var(--text-primary);
}

.verdict-green .verdict-label { color: var(--risk-safe); }
.verdict-yellow .verdict-label { color: var(--risk-warn); }
.verdict-orange .verdict-label { color: var(--risk-high); }
.verdict-red .verdict-label { color: var(--risk-critical); }

.verdict-sub {
  display: flex;
  gap: var(--sp-3);
  margin-top: var(--sp-1);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.verdict-conf {
  color: var(--text-tertiary);
}

.verdict-advice {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-md);
  color: var(--text-secondary);
  line-height: 1.5;
}

.verdict-score-wrap {
  flex-shrink: 0;
  width: 180px;
  text-align: right;
}

.verdict-score {
  font-family: var(--font-numeric);
  font-size: 48px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
}

.verdict-green .verdict-score { color: var(--risk-safe); }
.verdict-yellow .verdict-score { color: var(--risk-warn); }
.verdict-orange .verdict-score { color: var(--risk-high); }
.verdict-red .verdict-score { color: var(--risk-critical); }

.verdict-score-caption {
  margin-top: var(--sp-1);
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.threshold-bar {
  display: flex;
  gap: 2px;
  margin-top: var(--sp-2);
  height: 6px;
}

.threshold-seg {
  flex: 1;
  border-radius: 2px;
  opacity: 0.25;
  transition: opacity var(--dur-base);
}

.threshold-seg.active {
  opacity: 1;
}

.threshold-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 2px;
  font-size: var(--fs-2xs);
  color: var(--text-disabled);
  font-variant-numeric: tabular-nums;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 200px 1fr 1fr;
  gap: var(--sp-4);
}

.signal-summary {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
  padding: var(--sp-3) var(--sp-4);
}

.summary-title {
  font-size: var(--fs-md);
  color: var(--text-tertiary);
  margin-bottom: var(--sp-2);
  font-weight: 600;
}

.signal-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.signal-chip {
  font-size: var(--fs-sm);
  padding: var(--sp-1) 10px;
  background: var(--risk-high-soft);
  border: 1px solid rgba(249, 115, 22, 0.3);
  border-radius: var(--r-full);
  color: var(--risk-high);
}

.signal-chip small {
  color: var(--text-tertiary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 300px;
  color: var(--text-tertiary);
  font-size: var(--fs-lg);
}

.example-btn {
  background: var(--color-brand, #6366f1);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
}

.empty-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}
</style>
