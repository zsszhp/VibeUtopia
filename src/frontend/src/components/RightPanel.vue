<template>
  <div class="right-panel">
    <NTabs v-model:value="activeTab" type="line" size="small" class="right-tabs">
      <!-- ===== 风险详情 ===== -->
      <NTabPane name="detail" tab="风险详情">
        <!-- 分析完整度与不确定性 -->
        <section v-if="reviewStore.result?.confidence !== undefined" class="confidence-section">
          <h3 class="section-title">评估分析完整度</h3>
          <div class="confidence-row">
            <div class="conf-bar-lg">
              <div class="conf-fill-lg" :style="{ width: ((reviewStore.result.confidence ?? 0) * 100) + '%' }"></div>
            </div>
            <span class="conf-value">{{ ((reviewStore.result.confidence ?? 0) * 100).toFixed(0) }}%</span>
            <NTag :type="confidenceTagType" size="small" round class="conf-tag">
              {{ confidenceLabel }}
            </NTag>
          </div>

          <!-- 分析完整度原因标签 -->
          <div v-if="reviewStore.result?.confidence_breakdown?.reason_labels?.length" class="reason-labels">
            <NTag v-for="lab in reviewStore.result.confidence_breakdown.reason_labels" :key="lab" size="tiny" round class="reason-tag">
              {{ reasonLabelName(lab) }}
            </NTag>
          </div>

          <!-- 分析完整度详细分解 -->
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
                <span class="risk-score tabular-nums">{{ dim.score }}</span>
                <span class="severity-badge" :class="dim.severity">{{ severityLabel(dim.severity) }}</span>
              </div>
              <div v-if="expanded === dim.name" class="risk-body">
                <p class="evidence">{{ dim.evidence }}</p>
                <div class="confidence">
                  <span>分析完整度:</span>
                  <div class="conf-bar">
                    <div class="conf-fill" :style="{ width: ((dim.confidence ?? 0) * 100) + '%' }"></div>
                  </div>
                  <span class="tabular-nums">{{ ((dim.confidence ?? 0) * 100).toFixed(0) }}%</span>
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
              <span class="stat-value tabular-nums">{{ evidenceChains.length }}</span>
              <span class="stat-label">证据条目</span>
            </div>
            <div class="evidence-stat">
              <span class="stat-value tabular-nums">{{ crossValidatedCount }}</span>
              <span class="stat-label">交叉验证</span>
            </div>
            <div class="evidence-stat">
              <span class="stat-value tabular-nums">{{ avgConfidence.toFixed(0) }}%</span>
              <span class="stat-label">平均分析完整度</span>
            </div>
          </div>
          <div class="evidence-list">
            <details v-for="(ec, i) in evidenceChains.slice(0, 8)" :key="i" class="evidence-item">
              <summary>
                <span class="ec-dim">{{ (ec as any).dimension || ec.source || '未知维度' }}</span>
                <span class="ec-trigger">{{ ((ec as any).trigger || ec.content || '').slice(0, 28) }}</span>
              </summary>
              <div class="ec-body">
                <p v-if="(ec as any).trigger"><b>触发：</b>{{ (ec as any).trigger }}</p>
                <p v-if="(ec as any).context"><b>语境：</b>{{ (ec as any).context }}</p>
                <p v-if="(ec as any).mechanism"><b>机制：</b>{{ (ec as any).mechanism }}</p>
                <p v-if="(ec as any).impact"><b>影响：</b>{{ (ec as any).impact }}</p>
                <p v-if="ec.content"><b>内容：</b>{{ ec.content }}</p>
                <p v-if="ec.cross_validation?.length"><b>交叉验证：</b>{{ ec.cross_validation.length }} 条</p>
              </div>
            </details>
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

        <!-- 决策建议摘要 -->
        <section v-if="reviewStore.result" class="decision-summary-section">
          <h3 class="section-title">决策建议</h3>
          <div class="decision-summary-card" :class="decisionAdviceClass">
            <div class="decision-advice-label">{{ decisionAdviceLabel }}</div>
            <div class="decision-advice-reasoning">{{ decisionAdviceReasoning }}</div>
            <div v-if="decisionModCount > 0" class="decision-mod-count">
              需修改 {{ decisionModCount }} 项，预计风险降低 {{ decisionRiskReduction }} 分
            </div>
          </div>
        </section>
      </NTabPane>

      <!-- ===== 仿真与对比 ===== -->
      <NTabPane name="sim" tab="仿真对比">
        <!-- 历史对比 -->
        <section class="compare-section">
          <h3 class="section-title">历史对比</h3>
          <NSelect
            v-model:value="compareTaskId"
            :options="historyOptions"
            size="small"
            clearable
            placeholder="选择历史报告进行对比"
            class="compare-select"
          />
          <HistoryComparison
            :current-result="reviewStore.result"
            :history-result="compareResult"
          />
        </section>

        <!-- 反事实改写预估入口（启发式预估，非全量仿真） -->
        <section class="counterfactual-entry-section">
          <CounterfactualPanel
            :text="reviewStore.submittedText"
            :risk-items="counterfactualRiskItems"
          />
        </section>
      </NTabPane>

      <!-- ===== 扩展工具 ===== -->
      <NTabPane name="tools" tab="扩展工具">
        <!-- 分析流水线 -->
        <section class="tool-section">
          <h3 class="section-title">分析流水线</h3>
          <AnalysisPipeline :current-step="reviewStore.currentStep" :progress="reviewStore.progressPercent" />
        </section>

        <!-- 信号采集 -->
        <section class="tool-section">
          <SignalPanel />
          <BatchReviewPanel />
        </section>

        <!-- 博主画像 -->
        <section class="tool-section">
          <h3 class="section-title">博主画像</h3>
          <div class="blogger-id-row">
            <NInput
              v-model:value="bloggerId"
              size="small"
              placeholder="输入博主 ID 后加载画像"
              clearable
            />
          </div>
          <BloggerProfile v-if="bloggerId" :blogger-id="bloggerId" />
          <p v-else class="empty-hint">输入博主 ID 可查看画像、趋势与知识问答</p>
        </section>

        <!-- 知识图谱 -->
        <section class="tool-section">
          <KnowledgeGraph />
        </section>
      </NTabPane>
    </NTabs>

    <!-- 免责声明 -->
    <footer class="report-disclaimer">
      <p>本报告由自动化模型生成，风险提示仅供参考，不构成法律意见、平台最终审核意见或发布许可。</p>
      <p>内容仅用于本地分析；模型预测存在误判与漏判可能，高风险结论建议人工复核后使用。</p>
      <p>发布合法性责任由发布者自行承担。</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { NTag, NTooltip, NTabs, NTabPane, NSelect, NInput } from 'naive-ui'
import { useReviewStore, useHistoryStore } from '../stores'
import { severityLabel } from '../utils/labels'
import type { ReviewResult } from '../api'
import PropagationGraph from './PropagationGraph.vue'
import PolarizationChart from './PolarizationChart.vue'
import HotspotList from './HotspotList.vue'
import EntityRiskTimeline from './EntityRiskTimeline.vue'
import CounterfactualPanel from './CounterfactualPanel.vue'
import HistoryComparison from './HistoryComparison.vue'
import AnalysisPipeline from './AnalysisPipeline.vue'
import SignalPanel from './SignalPanel.vue'
import BatchReviewPanel from './BatchReviewPanel.vue'
import BloggerProfile from './BloggerProfile.vue'
import KnowledgeGraph from './KnowledgeGraph.vue'

const reviewStore = useReviewStore()
const historyStore = useHistoryStore()
const expanded = ref('')
const activeTab = ref<'detail' | 'sim' | 'tools'>('detail')
const compareTaskId = ref<string | null>(null)
const compareResult = ref<ReviewResult | null>(null)
const bloggerId = ref('')

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

const confidenceTagType = computed(() => {
  const level = reviewStore.result?.confidence_breakdown?.confidence_level
  if (level === 'very_high' || level === 'high') return 'success' as const
  if (level === 'medium') return 'warning' as const
  if (level === 'low') return 'error' as const
  const c = reviewStore.result?.confidence ?? 0
  if (c >= 0.8) return 'success' as const
  if (c >= 0.6) return 'warning' as const
  return 'error' as const
})

const confidenceLabel = computed(() => {
  const level = reviewStore.result?.confidence_breakdown?.confidence_level
  const levelMap: Record<string, string> = {
    very_high: '极高置信',
    high: '高置信',
    medium: '中置信',
    low: '低置信',
  }
  if (level && levelMap[level]) return levelMap[level]
  const c = reviewStore.result?.confidence ?? 0
  if (c >= 0.8) return '高置信'
  if (c >= 0.6) return '中置信'
  return '低置信'
})

const reasonLabelName = (lab: string) => {
  const map: Record<string, string> = {
    consistency: '评估一致',
    low_consistency: '评估分歧',
    cross_validation: '交叉验证',
    no_cross_validation: '无交叉验证',
    data_quality: '数据质量好',
    low_data_quality: '数据质量低',
    platform_validation: '平台验证',
    weak_platform_validation: '平台验证弱',
    full_coverage: '维度完整',
    partial_coverage: '维度不全',
  }
  return map[lab] ?? lab
}

const decisionAdviceClass = computed(() => {
  const score = reviewStore.result?.overall_risk ?? 0
  if (score >= 80) return 'advice-do-not-publish'
  if (score >= 60) return 'advice-postpone'
  if (score >= 30) return 'advice-modify'
  return 'advice-publish'
})

const decisionAdviceLabel = computed(() => {
  const score = reviewStore.result?.overall_risk ?? 0
  if (score >= 80) return '不建议发布'
  if (score >= 60) return '建议暂缓发布'
  if (score >= 30) return '建议修改后发布'
  return '可发布'
})

const decisionAdviceReasoning = computed(() => {
  const score = reviewStore.result?.overall_risk ?? 0
  const dimCount = reviewStore.result?.dimensions?.length || 0
  return `综合风险评分 ${score} 分，共 ${dimCount} 个风险维度`
})

const decisionModCount = computed(() => {
  const dims = reviewStore.result?.dimensions || []
  return dims.filter((d: any) => d.severity === 'orange' || d.severity === 'red').length
})

const decisionRiskReduction = computed(() => {
  const dims = reviewStore.result?.dimensions || []
  const highRisk = dims.filter((d: any) => d.severity === 'orange' || d.severity === 'red')
  return highRisk.reduce((sum: number, d: any) => sum + (d.score || 0) * 0.3, 0).toFixed(0)
})

const counterfactualRiskItems = computed(() => {
  const dims = reviewStore.result?.dimensions || []
  return dims.map((d: any) => ({
    dimension: d.name,
    severity: d.severity,
    evidence: d.evidence,
    score: d.score,
  }))
})

const historyOptions = computed(() =>
  historyStore.items.map(item => ({
    label: `${item.overall_risk ?? '-'} 分 · ${item.created_at ? new Date(item.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : item.task_id.slice(0, 8)}`,
    value: item.task_id,
  }))
)

watch(compareTaskId, async (taskId) => {
  if (!taskId) {
    compareResult.value = null
    return
  }
  compareResult.value = await historyStore.fetchHistoryDetail(taskId)
})
</script>

<style scoped>
.right-panel {
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.right-tabs :deep(.n-tabs-nav) {
  margin-bottom: var(--sp-2);
}

.section-title {
  font-size: var(--fs-md);
  color: var(--text-tertiary);
  margin-bottom: var(--sp-2);
  font-weight: 600;
}

.confidence-section { margin-bottom: var(--sp-1); }

.confidence-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.conf-bar-lg {
  flex: 1;
  height: 8px;
  background: var(--bg-overlay);
  border-radius: var(--r-sm);
  overflow: hidden;
}

.conf-fill-lg {
  height: 100%;
  background: var(--brand-600);
  border-radius: var(--r-sm);
  transition: width var(--dur-base);
}

.conf-value {
  font-size: var(--fs-lg);
  font-weight: 700;
  color: var(--brand-400);
  min-width: 36px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.conf-tag {
  flex-shrink: 0;
}

.reason-labels { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
.reason-tag { opacity: 0.85; }
.confidence-breakdown {
  margin-top: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.breakdown-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-xs);
}

.breakdown-label {
  color: var(--text-tertiary);
  min-width: 60px;
}

.breakdown-bar {
  flex: 1;
  height: 4px;
  background: var(--border-default);
  border-radius: 2px;
  overflow: hidden;
}

.breakdown-fill {
  height: 100%;
  background: var(--brand-600);
  border-radius: 2px;
  transition: width var(--dur-base);
}

.breakdown-value {
  color: var(--brand-400);
  font-weight: 600;
  min-width: 30px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.uncertainty-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
  margin-top: 6px;
}

.uncertainty-tag {
  font-size: var(--fs-2xs);
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--risk-warn-soft);
  color: var(--risk-warn);
  cursor: default;
}

.risk-item {
  padding: var(--sp-2);
  border-radius: 6px;
  margin-bottom: 6px;
  background: var(--bg-inset);
  border-left: 3px solid var(--border-default);
  cursor: pointer;
  transition: all var(--dur-base);
}

.risk-item.green { border-left-color: var(--risk-safe); }
.risk-item.yellow { border-left-color: var(--risk-warn); }
.risk-item.orange { border-left-color: var(--risk-high); }
.risk-item.red { border-left-color: var(--risk-critical); }

.risk-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.risk-name { font-size: var(--fs-md); color: var(--text-secondary); flex: 1; }
.risk-score { font-size: var(--fs-xl); font-weight: 700; color: var(--text-primary); }

.severity-badge {
  font-size: var(--fs-2xs);
  padding: 2px 6px;
  border-radius: 3px;
  font-weight: 600;
}

.severity-badge.green { background: var(--risk-safe-soft); color: var(--risk-safe); }
.severity-badge.yellow { background: var(--risk-warn-soft); color: var(--risk-warn); }
.severity-badge.orange { background: var(--risk-high-soft); color: var(--risk-high); }
.severity-badge.red { background: var(--risk-critical-soft); color: var(--risk-critical); }

.risk-body { margin-top: var(--sp-2); padding-top: var(--sp-2); border-top: 1px solid var(--border-default); }

.evidence { font-size: var(--fs-sm); color: var(--text-secondary); line-height: 1.5; margin-bottom: 6px; }

.confidence {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.conf-bar {
  flex: 1;
  height: 4px;
  background: var(--border-default);
  border-radius: 2px;
  overflow: hidden;
}

.conf-fill {
  height: 100%;
  background: var(--brand-600);
  border-radius: 2px;
}

.suggestion { margin-top: 6px; }
.suggestion-label { font-size: var(--fs-xs); color: var(--brand-400); }
.suggestion p { font-size: var(--fs-sm); color: var(--text-secondary); margin-top: 2px; }

.affected-groups {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
  align-items: center;
}

.ag-label {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.ag-tag {
  font-size: var(--fs-2xs);
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--brand-soft);
  color: var(--brand-400);
}

.evidence-section { margin-top: var(--sp-1); }

.evidence-list { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.evidence-item { background: rgba(255,255,255,0.03); border-radius: 4px; padding: 4px 8px; }
.evidence-item summary { cursor: pointer; font-size: 11px; display: flex; gap: 8px; }
.ec-dim { color: var(--color-brand, #6366f1); font-weight: 600; }
.ec-trigger { color: var(--color-text-secondary, #888); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ec-body { font-size: 11px; color: var(--color-text-secondary, #aaa); padding: 6px 0 2px; line-height: 1.55; }
.ec-body p { margin: 2px 0; }


.evidence-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-2);
  padding: var(--sp-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
}

.evidence-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.stat-value {
  font-size: var(--fs-xl);
  font-weight: 700;
  color: var(--brand-400);
  line-height: 1;
}

.stat-label {
  font-size: var(--fs-2xs);
  color: var(--text-tertiary);
  margin-top: var(--sp-1);
}

.propagation-section,
.polarization-section,
.hotspot-section,
.entity-chain-section,
.cross-effects-section,
.decision-summary-section,
.compare-section,
.counterfactual-entry-section,
.tool-section {
  margin-top: var(--sp-1);
}

.tool-section + .tool-section {
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--border-subtle);
}

.compare-select {
  margin-bottom: var(--sp-2);
}

.blogger-id-row {
  margin-bottom: var(--sp-2);
}

.cross-effect-item {
  padding: 6px var(--sp-2);
  background: var(--bg-inset);
  border-radius: var(--r-sm);
  margin-bottom: var(--sp-1);
  border-left: 2px solid var(--risk-critical);
}

.ce-dims { font-size: var(--fs-xs); color: var(--risk-critical); font-weight: 600; margin-bottom: 2px; }
.ce-desc { font-size: var(--fs-xs); color: var(--text-secondary); line-height: 1.4; }

.suggestion-card {
  background: var(--bg-inset);
  border-radius: 6px;
  padding: var(--sp-2);
  margin-bottom: var(--sp-2);
}

.original-text {
  font-size: var(--fs-sm);
  color: var(--risk-critical);
  text-decoration: line-through;
  opacity: 0.8;
}

.arrow { text-align: center; color: var(--brand-400); font-size: var(--fs-lg); }

.suggested-text { font-size: var(--fs-sm); color: var(--risk-safe); }

.dim-tag {
  display: inline-block;
  margin-top: var(--sp-1);
  font-size: var(--fs-2xs);
  color: var(--text-tertiary);
  background: var(--border-default);
  padding: 2px 6px;
  border-radius: 3px;
}

.empty-hint { font-size: var(--fs-sm); color: var(--text-tertiary); }

.decision-summary-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 10px;
  border-left: 3px solid var(--brand-600);
}

.decision-summary-card.advice-publish { border-left-color: var(--risk-safe); }
.decision-summary-card.advice-modify { border-left-color: var(--risk-warn); }
.decision-summary-card.advice-postpone { border-left-color: var(--risk-high); }
.decision-summary-card.advice-do-not-publish { border-left-color: var(--risk-critical); }

.decision-advice-label {
  font-size: var(--fs-lg);
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--sp-1);
}

.decision-advice-reasoning {
  font-size: var(--fs-xs);
  color: var(--text-secondary);
  line-height: 1.5;
}

.decision-mod-count {
  font-size: var(--fs-xs);
  color: var(--brand-400);
  margin-top: var(--sp-1);
}

.report-disclaimer {
  margin-top: var(--sp-4);
  padding: var(--sp-2) var(--sp-3);
  border-top: 1px solid var(--border-subtle);
  font-size: var(--fs-xs);
  line-height: 1.6;
  color: var(--text-tertiary);
}

.report-disclaimer p {
  margin: 2px 0;
}
</style>
