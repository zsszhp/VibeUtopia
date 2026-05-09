<template>
  <div class="right-panel">
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
                <div class="conf-fill" :style="{ width: (dim.confidence * 100) + '%' }"></div>
              </div>
              <span>{{ (dim.confidence * 100).toFixed(0) }}%</span>
            </div>
            <div v-if="dim.suggestion" class="suggestion">
              <span class="suggestion-label">建议:</span>
              <p>{{ dim.suggestion }}</p>
            </div>
          </div>
        </div>
      </div>
      <p v-else class="empty-hint">暂无风险数据</p>
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
import { ref } from 'vue'
import { useReviewStore } from '../stores'
import { computed } from 'vue'

const reviewStore = useReviewStore()
const expanded = ref('')

const dimensions = computed(() => reviewStore.result?.dimensions)
const suggestions = computed(() => reviewStore.result?.suggestions)
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
