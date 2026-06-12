<template>
  <div class="workbench">
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

    <!-- 热点关联摘要 -->
    <div v-if="reviewStore.result?.signal_correlations?.length" class="signal-summary">
      <h3 class="summary-title">热点关联摘要</h3>
      <div class="signal-chips">
        <span v-for="sc in reviewStore.result.signal_correlations.slice(0, 5)" :key="sc.signal_id" class="signal-chip">
          {{ sc.title }} <small>({{ (sc.correlation_score * 100).toFixed(0) }}%)</small>
        </span>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!reviewStore.result && !reviewStore.loading" class="empty-state">
      <p>在左侧输入文案或上传视频开始预审</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useReviewStore } from '../stores'
import AnalysisDashboard from '../components/AnalysisDashboard.vue'
import RiskGauge from '../components/RiskGauge.vue'
import DimensionRadar from '../components/DimensionRadar.vue'
import PlatformReactions from '../components/PlatformReactions.vue'

const reviewStore = useReviewStore()
</script>

<style scoped>
.workbench {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 200px 1fr 1fr;
  gap: 16px;
}

.signal-summary {
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 8px;
  padding: 12px 16px;
}

.summary-title {
  font-size: 13px;
  color: #888;
  margin-bottom: 8px;
  font-weight: 600;
}

.signal-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.signal-chip {
  font-size: 12px;
  padding: 4px 10px;
  background: rgba(249,115,22,0.1);
  border: 1px solid rgba(249,115,22,0.3);
  border-radius: 12px;
  color: #f97316;
}

.signal-chip small {
  color: #888;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #555;
  font-size: 14px;
}
</style>
