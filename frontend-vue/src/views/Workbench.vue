<template>
  <div class="workbench">
    <!-- 分析流水线 -->
    <AnalysisPipeline :current-step="reviewStore.currentStep" :progress="reviewStore.progressPercent" />

    <!-- 风险仪表盘 -->
    <div v-if="reviewStore.result" class="dashboard-grid">
      <RiskGauge :score="reviewStore.result.overall_risk ?? 0" :level="reviewStore.result.risk_level ?? 'green'" />
      <DimensionRadar v-if="reviewStore.result.dimensions" :dimensions="reviewStore.result.dimensions" />
      <PlatformReactions v-if="reviewStore.result.platform_reactions" :reactions="reviewStore.result.platform_reactions" />
    </div>

    <!-- 空状态 -->
    <div v-if="!reviewStore.result && !reviewStore.loading" class="empty-state">
      <p>在左侧输入文案或上传视频开始预审</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useReviewStore } from '../stores'
import AnalysisPipeline from '../components/AnalysisPipeline.vue'
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

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #555;
  font-size: 14px;
}
</style>
