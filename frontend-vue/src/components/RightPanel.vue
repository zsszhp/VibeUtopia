<template>
  <div class="right-panel">
    <!-- 置信度与不确定性 -->
    <section v-if="reviewStore.result?.confidence !== undefined" class="confidence-section">
      <h3 class="section-title">评估置信度</h3>
      <div class="confidence-row">
        <div class="conf-bar-lg">
          <div class="conf-fill-lg" :style="{ width: ((reviewStore.result.confidence ?? 0) * 100) + '%' }"></div>
        </div>
        <span class="conf-value">{{ ((reviewStore.result.confidence ?? 0) * 100).toFixed(0) }}%</span>
        <NTag :type="confidenceTagType" size="small" round class="conf-tag">
          {{ confidenceLabel }}
        </NTag>
      </div>

      <!-- 置信度详细分解 -->
      <div v-if="reviewStore.result.confidence_breakdown" class="confidence-breakdown">
        <div class="breakdown-item">
          <span class="breakdown-label">数据质量</span>
          <div class="breakdown-bar">
            <div class="breakdown-fill" :style="{ width: (reviewStore.result.confidence_breakdown.factors?.data_quality * 100) + '%' }"></div>
          </div>
          <span class="breakdown-value">{{ (reviewStore.result.confidence_breakdown.factors?.data_quality * 100).toFixed(0) }}%</span>
        </div>
        <div class="breakdown-item">
          <span class="breakdown-label">评估一致性</span>
          <div class="breakdown-bar">
            <div class="breakdown-fill" :style="{ width: (reviewStore.result.confidence_breakdown.factors?.consistency * 100) + '%' }"></div>
          </div>
          <span class="breakdown-value">{{ (reviewStore.result.confidence_breakdown.factors?.consistency * 100).toFixed(0) }}%</span>
        </div>
        <div class="breakdown-item">
          <span class="breakdown-label">证据充分性</span>
          <div class="breakdown-bar">
            <div class="breakdown-fill" :style="{ width: (reviewStore.result.confidence_breakdown.factors?.evidence * 100) + '%' }"></div>
          </div>
          <span class="breakdown-value">{{ (reviewStore.result.confidence_breakdown.factors?.evidence * 100).toFixed(0) }}%</span>
        </div>
        <div class="breakdown-item">
          <span class="breakdown-label">平台验证</span>
          <div class="breakdown-bar">
            <div class="breakdown-fill" :style="{ width: (reviewStore.result.confidence_breakdown.factors?.platform_validation * 100) + '%' }"></div>
          </div>
          <span class="breakdown-value">{{ (reviewStore.result.confidence_breakdown.factors?.platform_validation * 100).toFixed(0) }}%</span>
        </div>
      </div>

      <!-- 不确定性来源 Tooltip -->
      <div v-if="reviewStore.result.uncertainty_sources?.length" class="uncertainty-list">
        <NTooltip v-for="src in reviewStore.result.uncertainty_sources" :key="src" trigger="hover">
          <template #trigger>
            <span class="uncertainty-tag">{{ src }}</span>
          </template>
          不确定性来源: {{ src }}
        </NTooltip>
      </div>
    </section>

    <!-- 风险详情 -->
    <section class="risk-detail-section">
      <h3 class="section-title">风险详情</h3>
      <div v-if="dimensions && dimensions.length">
        <div
          v-for="dim in dimensions"
          :key="dim.name"
          class="risk-item"
          :class="dim.severity"
          @click="expanded = expanded === dim.name ? '' : dim.name"
        >
          <div class="risk-header">
            <span class="risk-name">{{ dim.name }}</span>
            <span class="risk-score">{{ dim.score }}</span>
            <span class="severity-badge" :class="dim.severity">{{ dim.severity }}</span>
          </div>
          <div v-if="expanded === dim.name" class="risk-body">
            <p class="evidence">{{ dim.evidence }}</p>
            <div class="confidence">
              <span>置信度:</span>
              <div class="conf-bar">
                <div class="conf-fill" :style="{ width: ((dim.confidence ?? 0) * 100) + '%' }"></div>
              </div>
              <span>{{ ((dim.confidence ?? 0) * 100).toFixed(0) }}%</span>
            </div>
            <div v-if="dim.suggestion" class="suggestion">
              <span class="suggestion-label">建议:</span>
              <p>{{ dim.suggestion }}</p>
            </div>
            <!-- 受影响群体 -->
            <div v-if="dim.affected_groups?.length" class="affected-groups">
              <span class="ag-label">影响群体:</span>
              <span v-for="g in dim.affected_groups" :key="g" class="ag-tag">{{ g }}</span>
            </div>
          </div>
        </div>
      </div>
      <p v-else class="empty-hint">暂无风险数据</p>
    </section>

    <!-- 证据链摘要 -->
    <section v-if="evidenceChains?.length" class="evidence-section">
      <h3 class="section-title">证据链</h3>
      <div class="evidence-summary">
        <div class="evidence-stat">
          <span class="stat-value">{{ evidenceChains.length }}</span>
          <span class="stat-label">证据条目</span>
        </div>
        <div class="evidence-stat">
          <span class="stat-value">{{ crossValidatedCount }}</span>
          <span class="stat-label">交叉验证</span>
        </div>
        <div class="evidence-stat">
          <span class="stat-value">{{ avgConfidence.toFixed(0) }}%</span>
          <span class="stat-label">平均置信度</span>
        </div>
      </div>
    </section>

    <!-- 传播推演可视化 -->
    <section class="propagation-section">
      <h3 class="section-title">传播推演</h3>
      <PropagationGraph :simulation-data="reviewStore.result?.simulation_data" />
    </section>

    <!-- 极化趋势 -->
    <section class="polarization-section">
      <h3 class="section-title">极化趋势</h3>
      <PolarizationChart :polarization-data="reviewStore.result?.polarization_data" />
    </section>

    <!-- 热点关联列表 -->
    <section class="hotspot-section">
      <h3 class="section-title">热点关联</h3>
      <HotspotList :hotspots="signalCorrelations" />
    </section>

    <!-- 实体风险链时间线 -->
    <section class="entity-chain-section">
      <h3 class="section-title">实体风险链</h3>
      <EntityRiskTimeline :entities="reviewStore.result?.entity_chains" />
    </section>

    <!-- 交叉效应 -->
    <section v-if="crossEffects?.length" class="cross-effects-section">
      <h3 class="section-title">交叉风险</h3>
      <div v-for="(ce, i) in crossEffects" :key="i" class="cross-effect-item">
        <div class="ce-dims">{{ ce.dimensions?.join(' × ') }}</div>
        <p class="ce-desc">{{ ce.description }}</p>
      </div>
    </section>

    <!-- 修改建议 -->
    <section v-if="suggestions && suggestions.length" class="suggestions-section">
      <h3 class="section-title">修改建议</h3>
      <div v-for="(s, i) in suggestions" :key="i" class="suggestion-card">
        <div class="original-text">{{ s.original }}</div>
        <div class="arrow">↓</div>
        <div class="suggested-text">{{ s.suggestion }}</div>
        <span class="dim-tag">{{ s.dimension }}</span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { NTag, NTooltip } from 'naive-ui'
import { useReviewStore } from '../stores'
import PropagationGraph from './PropagationGraph.vue'
import PolarizationChart from './PolarizationChart.vue'
import HotspotList from './HotspotList.vue'
import EntityRiskTimeline from './EntityRiskTimeline.vue'

const reviewStore = useReviewStore()
const expanded = ref('')

const dimensions = computed(() => reviewStore.result?.dimensions)
const suggestions = computed(() => reviewStore.result?.suggestions)
const signalCorrelations = computed(() => reviewStore.result?.signal_correlations)
const crossEffects = computed(() => reviewStore.result?.cross_effects)

const evidenceChains = computed(() => reviewStore.result?.evidence_chains || [])
const crossValidatedCount = computed(() => {
  if (!evidenceChains.value) return 0
  return evidenceChains.value.filter((ec: any) => ec.cross_validation?.length > 0).length
})
const avgConfidence = computed(() => {
  if (!evidenceChains.value || evidenceChains.value.length === 0) return 0
  const total = evidenceChains.value.reduce((sum: number, ec: any) => sum + (ec.confidence || 0), 0)
  return (total / evidenceChains.value.length) * 100
})

// 置信度标签
const confidenceTagType = computed(() => {
  const c = reviewStore.result?.confidence ?? 0
  if (c >= 0.8) return 'success' as const
  if (c >= 0.6) return 'warning' as const
  return 'error' as const
})

const confidenceLabel = computed(() => {
  const c = reviewStore.result?.confidence ?? 0
  if (c >= 0.8) return '高置信'
  if (c >= 0.6) return '中置信'
  return '低置信'
})
</script>

<style scoped>
.right-panel {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  font-size: 13px;
  color: #888;
  margin-bottom: 8px;
  font-weight: 600;
}

.confidence-section { margin-bottom: 4px; }

.confidence-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.conf-bar-lg {
  flex: 1;
  height: 8px;
  background: #1e1e2e;
  border-radius: 4px;
  overflow: hidden;
}

.conf-fill-lg {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 4px;
  transition: width 0.3s;
}

.conf-value {
  font-size: 14px;
  font-weight: 700;
  color: #8b5cf6;
  min-width: 36px;
  text-align: right;
}

.conf-tag {
  flex-shrink: 0;
}

.confidence-breakdown {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.breakdown-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.breakdown-label {
  color: #888;
  min-width: 60px;
}

.breakdown-bar {
  flex: 1;
  height: 4px;
  background: #2a2a3e;
  border-radius: 2px;
  overflow: hidden;
}

.breakdown-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 2px;
  transition: width 0.3s;
}

.breakdown-value {
  color: #8b5cf6;
  font-weight: 600;
  min-width: 30px;
  text-align: right;
}

.uncertainty-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.uncertainty-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(234,179,8,0.15);
  color: #eab308;
  cursor: default;
}

.risk-item {
  padding: 8px;
  border-radius: 6px;
  margin-bottom: 6px;
  background: #1a1a2e;
  border-left: 3px solid #333;
  cursor: pointer;
  transition: all 0.2s;
}

.risk-item.green { border-left-color: #22c55e; }
.risk-item.yellow { border-left-color: #eab308; }
.risk-item.orange { border-left-color: #f97316; }
.risk-item.red { border-left-color: #ef4444; }

.risk-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.risk-name { font-size: 13px; color: #ccc; flex: 1; }
.risk-score { font-size: 16px; font-weight: 700; color: #e0e0e0; }

.severity-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  font-weight: 600;
}

.severity-badge.green { background: rgba(34,197,94,0.2); color: #22c55e; }
.severity-badge.yellow { background: rgba(234,179,8,0.2); color: #eab308; }
.severity-badge.orange { background: rgba(249,115,22,0.2); color: #f97316; }
.severity-badge.red { background: rgba(239,68,68,0.2); color: #ef4444; }

.risk-body { margin-top: 8px; padding-top: 8px; border-top: 1px solid #2a2a3e; }

.evidence { font-size: 12px; color: #aaa; line-height: 1.5; margin-bottom: 6px; }

.confidence {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #888;
}

.conf-bar {
  flex: 1;
  height: 4px;
  background: #2a2a3e;
  border-radius: 2px;
  overflow: hidden;
}

.conf-fill {
  height: 100%;
  background: #6366f1;
  border-radius: 2px;
}

.suggestion { margin-top: 6px; }
.suggestion-label { font-size: 11px; color: #6366f1; }
.suggestion p { font-size: 12px; color: #aaa; margin-top: 2px; }

.affected-groups {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.ag-label {
  font-size: 11px;
  color: #888;
}

.ag-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(99,102,241,0.15);
  color: #6366f1;
}

.evidence-section { margin-top: 4px; }

.evidence-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 12px;
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 8px;
}

.evidence-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #6366f1;
  line-height: 1;
}

.stat-label {
  font-size: 10px;
  color: #888;
  margin-top: 4px;
}

.propagation-section { margin-top: 4px; }
.polarization-section { margin-top: 4px; }
.hotspot-section { margin-top: 4px; }
.entity-chain-section { margin-top: 4px; }

.cross-effects-section { margin-top: 4px; }

.cross-effect-item {
  padding: 6px 8px;
  background: #1a1a2e;
  border-radius: 4px;
  margin-bottom: 4px;
  border-left: 2px solid #ef4444;
}

.ce-dims { font-size: 11px; color: #ef4444; font-weight: 600; margin-bottom: 2px; }
.ce-desc { font-size: 11px; color: #aaa; line-height: 1.4; }

.suggestion-card {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}

.original-text {
  font-size: 12px;
  color: #ef4444;
  text-decoration: line-through;
  opacity: 0.8;
}

.arrow { text-align: center; color: #6366f1; font-size: 14px; }

.suggested-text { font-size: 12px; color: #22c55e; }

.dim-tag {
  display: inline-block;
  margin-top: 4px;
  font-size: 10px;
  color: #888;
  background: #2a2a3e;
  padding: 2px 6px;
  border-radius: 3px;
}

.empty-hint { font-size: 12px; color: #444; }
</style>
