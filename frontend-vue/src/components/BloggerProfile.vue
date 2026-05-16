<template>
  <div class="blogger-profile">
    <div class="profile-header">
      <h3 class="section-title">博主画像</h3>
      <NTag v-if="profileData.risk_tolerance" :type="toleranceType" size="tiny" round>
        {{ toleranceLabel }}
      </NTag>
    </div>

    <!-- 风险趋势图 -->
    <div class="chart-section">
      <div class="sub-title">风险趋势</div>
      <div ref="trendChartEl" class="chart-container"></div>
    </div>

    <!-- 风险维度雷达图 -->
    <div class="chart-section">
      <div class="sub-title">风险维度</div>
      <div ref="radarChartEl" class="chart-container"></div>
    </div>

    <!-- 竞品对比表格 -->
    <div v-if="competitorData.dimension_comparisons?.length" class="competitor-section">
      <div class="sub-title">竞品对比</div>
      <div class="competitor-table">
        <div class="table-row header">
          <span class="col-dim">维度</span>
          <span class="col-score">博主</span>
          <span class="col-score">竞品</span>
          <span class="col-score">行业</span>
          <span class="col-pos">定位</span>
        </div>
        <div v-for="c in competitorData.dimension_comparisons" :key="c.dimension" class="table-row">
          <span class="col-dim">{{ c.dimension }}</span>
          <span class="col-score" :class="scoreClass(c.blogger_score)">{{ c.blogger_score }}</span>
          <span class="col-score">{{ c.competitor_score }}</span>
          <span class="col-score">{{ c.field_average }}</span>
          <span class="col-pos">
            <NTag size="tiny" :type="positionType(c.relative_position)" round>
              {{ positionLabel(c.relative_position) }}
            </NTag>
          </span>
        </div>
      </div>
    </div>

    <!-- 决策建议卡片 -->
    <div v-if="decisionAdvice" class="decision-section">
      <div class="sub-title">决策建议</div>
      <div class="decision-card" :class="decisionAdvice.advice_type">
        <div class="decision-label">{{ decisionAdvice.advice_label }}</div>
        <div class="decision-reasoning">{{ decisionAdvice.reasoning }}</div>
        <div v-if="decisionAdvice.modification_priorities?.length" class="mod-priorities">
          <div v-for="p in decisionAdvice.modification_priorities.slice(0, 3)" :key="p.dimension" class="mod-item">
            <span class="mod-priority">P{{ p.priority }}</span>
            <span class="mod-dim">{{ p.dimension }}</span>
            <span class="mod-action">{{ p.suggested_action }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 风险预测 -->
    <div v-if="profileData.prediction?.predicted_score !== undefined" class="prediction-section">
      <div class="sub-title">风险预测</div>
      <div class="prediction-card">
        <div class="prediction-score">
          <span class="pred-label">预测风险分</span>
          <span class="pred-value" :class="scoreClass(profileData.prediction.predicted_score)">
            {{ profileData.prediction.predicted_score }}
          </span>
          <NTag size="tiny" :type="riskLevelType(profileData.prediction.next_risk_level)" round>
            {{ profileData.prediction.next_risk_level }}
          </NTag>
        </div>
        <div v-if="profileData.prediction.risk_factors?.length" class="risk-factors">
          <div v-for="f in profileData.prediction.risk_factors" :key="f.dimension" class="risk-factor">
            {{ f.dimension }}: {{ f.reason }}
          </div>
        </div>
      </div>
    </div>

    <!-- 知识引擎面板 -->
    <div v-if="knowledgeData.primary_topics?.length" class="knowledge-section">
      <div class="sub-title">知识画像</div>

      <div v-if="knowledgeData.narrative_style" class="knowledge-item">
        <span class="ki-label">叙事风格</span>
        <span class="ki-value">{{ knowledgeData.narrative_style }}</span>
      </div>

      <div v-if="knowledgeData.expression_style" class="knowledge-item">
        <span class="ki-label">表达风格</span>
        <span class="ki-value">{{ knowledgeData.expression_style }}</span>
      </div>

      <div v-if="knowledgeData.primary_topics?.length" class="topics-section">
        <span class="ki-label">主要话题</span>
        <div class="topic-tags">
          <NTag v-for="t in knowledgeData.primary_topics.slice(0, 8)" :key="t" size="tiny" type="info" round>
            {{ t }}
          </NTag>
        </div>
      </div>

      <div v-if="knowledgeData.core_viewpoints?.length" class="viewpoints-section">
        <span class="ki-label">核心观点</span>
        <div v-for="vp in knowledgeData.core_viewpoints.slice(0, 5)" :key="vp.topic" class="viewpoint-item">
          <span class="vp-topic">{{ vp.topic }}</span>
          <span class="vp-content">{{ vp.viewpoint }}</span>
        </div>
      </div>
    </div>

    <!-- 知识问答 -->
    <div class="qa-section">
      <div class="sub-title">知识问答</div>
      <div class="qa-input-row">
        <input
          v-model="qaQuestion"
          class="qa-input"
          placeholder="输入问题，如：这个博主对AI的看法是什么？"
          @keyup.enter="askQuestion"
        />
        <button class="qa-btn" :disabled="qaLoading" @click="askQuestion">
          {{ qaLoading ? '思考中...' : '提问' }}
        </button>
      </div>
      <div v-if="qaAnswer" class="qa-answer">
        <div class="qa-answer-text">{{ qaAnswer.answer }}</div>
        <div v-if="qaAnswer.references?.length" class="qa-refs">
          <span class="qa-refs-label">引用：</span>
          <span v-for="(ref, i) in qaAnswer.references.slice(0, 3)" :key="i" class="qa-ref">
            {{ ref.video }} {{ ref.time }}
          </span>
        </div>
        <NTag v-if="qaAnswer.retrieval_mode" size="tiny" round>{{ qaAnswer.retrieval_mode }}</NTag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { NTag } from 'naive-ui'
import * as echarts from 'echarts'
import { v3Api, bloggerApi } from '../api'

const props = defineProps<{
  bloggerId?: string
}>()

const trendChartEl = ref<HTMLElement | null>(null)
const radarChartEl = ref<HTMLElement | null>(null)
let trendChart: echarts.ECharts | null = null
let radarChart: echarts.ECharts | null = null

const profileData = ref<any>({})
const competitorData = ref<any>({})
const decisionAdvice = ref<any>(null)
const knowledgeData = ref<any>({})
const qaQuestion = ref('')
const qaAnswer = ref<any>(null)
const qaLoading = ref(false)

const toleranceType = computed(() => {
  const t = profileData.value.risk_tolerance
  if (t === 'aggressive') return 'error' as const
  if (t === 'moderate') return 'warning' as const
  return 'success' as const
})

const toleranceLabel = computed(() => {
  const t = profileData.value.risk_tolerance
  if (t === 'aggressive') return '高风险偏好'
  if (t === 'moderate') return '中等风险'
  return '低风险偏好'
})

function scoreClass(score: number) {
  if (score >= 80) return 'score-red'
  if (score >= 60) return 'score-orange'
  if (score >= 40) return 'score-yellow'
  return 'score-green'
}

function positionType(pos: string) {
  if (pos === 'below_average') return 'success' as const
  if (pos === 'above_average') return 'error' as const
  return 'info' as const
}

function positionLabel(pos: string) {
  if (pos === 'below_average') return '优于均值'
  if (pos === 'above_average') return '高于均值'
  return '行业均值'
}

function riskLevelType(level: string) {
  if (level === 'red') return 'error' as const
  if (level === 'orange') return 'warning' as const
  if (level === 'yellow') return 'warning' as const
  return 'success' as const
}

async function fetchProfile() {
  if (!props.bloggerId) return
  try {
    const resp = await v3Api.getBloggerHistory(props.bloggerId)
    profileData.value = resp.data
    await nextTick()
    renderTrendChart()
    renderRadarChart()
  } catch {}
}

async function fetchCompetitor() {
  if (!props.bloggerId) return
}

async function fetchKnowledgeProfile() {
  if (!props.bloggerId) return
  try {
    const resp = await bloggerApi.getProfile(props.bloggerId)
    knowledgeData.value = resp.data
  } catch {}
}

async function askQuestion() {
  if (!props.bloggerId || !qaQuestion.value.trim()) return
  qaLoading.value = true
  qaAnswer.value = null
  try {
    const resp = await bloggerApi.ask(props.bloggerId, qaQuestion.value.trim())
    qaAnswer.value = resp.data
  } catch (e: any) {
    qaAnswer.value = { answer: '问答失败: ' + (e.message || '未知错误'), references: [] }
  } finally {
    qaLoading.value = false
  }
}

function renderTrendChart() {
  if (!trendChartEl.value) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartEl.value, 'dark')
  }

  const trendData = profileData.value.trend_data || []
  const dates = trendData.map((t: any) => t.date)
  const scores = trendData.map((t: any) => t.overall_score)

  trendChart.setOption({
    backgroundColor: 'transparent',
    grid: { top: 20, right: 20, bottom: 30, left: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 9, color: '#666' } },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { fontSize: 9, color: '#666' }, splitLine: { lineStyle: { color: '#1e1e2e' } } },
    series: [{
      type: 'line',
      data: scores,
      smooth: true,
      lineStyle: { color: '#6366f1', width: 2 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(99,102,241,0.3)' }, { offset: 1, color: 'rgba(99,102,241,0)' }] } },
      itemStyle: { color: '#6366f1' },
      symbolSize: 4,
    }],
    tooltip: { trigger: 'axis', backgroundColor: '#1a1a2e', borderColor: '#2a2a3e', textStyle: { color: '#ccc', fontSize: 11 } },
  })
}

function renderRadarChart() {
  if (!radarChartEl.value) return
  if (!radarChart) {
    radarChart = echarts.init(radarChartEl.value, 'dark')
  }

  const trendData = profileData.value.trend_data || []
  const latestPoint = trendData[trendData.length - 1]
  const dimData = latestPoint?.dimensions || {}

  const dims = Object.keys(dimData)
  if (!dims.length) return

  const maxScore = Math.max(...Object.values(dimData) as number[], 50) * 1.2

  radarChart.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: dims.map(d => ({ name: d, max: maxScore })),
      axisName: { color: '#888', fontSize: 9 },
      splitArea: { areaStyle: { color: ['rgba(99,102,241,0.02)', 'rgba(99,102,241,0.05)'] } },
      splitLine: { lineStyle: { color: '#1e1e2e' } },
      axisLine: { lineStyle: { color: '#1e1e2e' } },
    },
    series: [{
      type: 'radar',
      data: [{ value: Object.values(dimData), name: '风险维度', areaStyle: { color: 'rgba(99,102,241,0.2)' }, lineStyle: { color: '#6366f1' }, itemStyle: { color: '#6366f1' } }],
    }],
  })
}

onMounted(() => {
  fetchProfile()
  fetchKnowledgeProfile()
})

onUnmounted(() => {
  trendChart?.dispose()
  radarChart?.dispose()
})

watch(() => props.bloggerId, () => {
  fetchProfile()
  fetchKnowledgeProfile()
  qaAnswer.value = null
})
</script>

<style scoped>
.blogger-profile {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title {
  font-size: 13px;
  color: #888;
  font-weight: 600;
  margin: 0;
}

.sub-title {
  font-size: 12px;
  color: #666;
  font-weight: 600;
  margin-bottom: 6px;
}

.chart-section {
  margin-top: 4px;
}

.chart-container {
  width: 100%;
  height: 180px;
  background: #0a0a0f;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
}

.competitor-section {
  margin-top: 4px;
}

.competitor-table {
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  overflow: hidden;
}

.table-row {
  display: flex;
  align-items: center;
  padding: 4px 8px;
  font-size: 11px;
  border-bottom: 1px solid #1e1e2e;
}

.table-row.header {
  color: #666;
  font-weight: 600;
  background: #0a0a0f;
}

.col-dim { flex: 2; color: #aaa; }
.col-score { flex: 1; text-align: center; color: #888; }
.col-pos { flex: 1; text-align: center; }

.score-green { color: #22c55e; }
.score-yellow { color: #eab308; }
.score-orange { color: #f97316; }
.score-red { color: #ef4444; }

.decision-section {
  margin-top: 4px;
}

.decision-card {
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  padding: 10px;
  border-left: 3px solid #6366f1;
}

.decision-card.publish { border-left-color: #22c55e; }
.decision-card.publish_with_modification { border-left-color: #eab308; }
.decision-card.postpone { border-left-color: #f97316; }
.decision-card.do_not_publish { border-left-color: #ef4444; }

.decision-label {
  font-size: 14px;
  font-weight: 700;
  color: #e0e0e0;
  margin-bottom: 4px;
}

.decision-reasoning {
  font-size: 11px;
  color: #aaa;
  line-height: 1.5;
  margin-bottom: 6px;
}

.mod-priorities {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mod-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 11px;
}

.mod-priority {
  color: #f97316;
  font-weight: 600;
  min-width: 20px;
}

.mod-dim {
  color: #6366f1;
  min-width: 60px;
}

.mod-action {
  color: #aaa;
  flex: 1;
}

.prediction-section {
  margin-top: 4px;
}

.prediction-card {
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  padding: 10px;
}

.prediction-score {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.pred-label {
  font-size: 11px;
  color: #888;
}

.pred-value {
  font-size: 18px;
  font-weight: 700;
}

.risk-factors {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.risk-factor {
  font-size: 11px;
  color: #aaa;
}

.knowledge-section {
  margin-top: 4px;
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  padding: 10px;
}

.knowledge-item {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 11px;
}

.ki-label {
  color: #6366f1;
  font-weight: 600;
  min-width: 56px;
}

.ki-value {
  color: #ccc;
  flex: 1;
}

.topics-section {
  margin-bottom: 8px;
}

.topic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.viewpoints-section {
  margin-top: 4px;
}

.viewpoint-item {
  display: flex;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 11px;
}

.vp-topic {
  color: #6366f1;
  font-weight: 600;
  min-width: 60px;
}

.vp-content {
  color: #aaa;
  flex: 1;
}

.qa-section {
  margin-top: 4px;
}

.qa-input-row {
  display: flex;
  gap: 6px;
}

.qa-input {
  flex: 1;
  background: #0a0a0f;
  border: 1px solid #1e1e2e;
  border-radius: 4px;
  padding: 6px 8px;
  color: #ccc;
  font-size: 12px;
  outline: none;
}

.qa-input:focus {
  border-color: #6366f1;
}

.qa-btn {
  background: #6366f1;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.qa-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.qa-answer {
  margin-top: 8px;
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  padding: 10px;
}

.qa-answer-text {
  font-size: 12px;
  color: #ddd;
  line-height: 1.6;
  margin-bottom: 6px;
}

.qa-refs {
  font-size: 10px;
  color: #888;
  margin-bottom: 4px;
}

.qa-refs-label {
  color: #6366f1;
}

.qa-ref {
  margin-right: 8px;
}
</style>
