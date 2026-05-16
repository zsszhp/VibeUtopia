<template>
  <div class="history-comparison">
    <div v-if="!currentResult && !historyResult" class="empty-state">
      <span>请选择历史记录进行对比</span>
    </div>
    <template v-else>
      <div class="comparison-header">
        <div class="comparison-col current">
          <span class="col-label">当前报告</span>
          <NTag v-if="currentResult?.risk_level" :type="riskTagType(currentResult.risk_level)" size="small" round>
            {{ currentResult.risk_level.toUpperCase() }}
          </NTag>
        </div>
        <div class="comparison-col history">
          <span class="col-label">历史报告</span>
          <NTag v-if="historyResult?.risk_level" :type="riskTagType(historyResult.risk_level)" size="small" round>
            {{ historyResult.risk_level.toUpperCase() }}
          </NTag>
        </div>
      </div>

      <div class="comparison-body">
        <!-- 总体风险对比 -->
        <div class="compare-section">
          <div class="compare-row">
            <div class="compare-cell current">
              <span class="compare-value" :class="currentResult?.risk_level">
                {{ currentResult?.overall_risk?.toFixed(1) ?? '-' }}
              </span>
            </div>
            <div class="compare-divider">
              <span class="compare-label">总体风险</span>
            </div>
            <div class="compare-cell history">
              <span class="compare-value" :class="historyResult?.risk_level">
                {{ historyResult?.overall_risk?.toFixed(1) ?? '-' }}
              </span>
            </div>
          </div>
          <div v-if="riskDiff !== null" class="diff-indicator" :class="riskDiff > 0 ? 'diff-up' : riskDiff < 0 ? 'diff-down' : ''">
            {{ riskDiff > 0 ? '↑' : riskDiff < 0 ? '↓' : '=' }} {{ Math.abs(riskDiff).toFixed(1) }}
          </div>
        </div>

        <!-- 置信度对比 -->
        <div class="compare-section">
          <div class="compare-row">
            <div class="compare-cell current">
              <span class="compare-value">{{ currentResult?.confidence !== undefined ? (currentResult.confidence * 100).toFixed(0) + '%' : '-' }}</span>
            </div>
            <div class="compare-divider">
              <span class="compare-label">置信度</span>
            </div>
            <div class="compare-cell history">
              <span class="compare-value">{{ historyResult?.confidence !== undefined ? (historyResult.confidence * 100).toFixed(0) + '%' : '-' }}</span>
            </div>
          </div>
        </div>

        <!-- 维度对比 -->
        <div v-if="mergedDimensions.length" class="compare-section">
          <h4 class="sub-title">维度对比</h4>
          <div v-for="dim in mergedDimensions" :key="dim.name" class="compare-row dim-row">
            <div class="compare-cell current">
              <span class="compare-value" :class="dim.currentLevel">{{ dim.currentScore ?? '-' }}</span>
            </div>
            <div class="compare-divider">
              <span class="compare-label">{{ dim.name }}</span>
            </div>
            <div class="compare-cell history">
              <span class="compare-value" :class="dim.historyLevel">{{ dim.historyScore ?? '-' }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NTag } from 'naive-ui'
import type { ReviewResult } from '../api'

const props = defineProps<{
  currentResult?: ReviewResult | null
  historyResult?: ReviewResult | null
}>()

const riskDiff = computed(() => {
  if (props.currentResult?.overall_risk != null && props.historyResult?.overall_risk != null) {
    return props.currentResult.overall_risk - props.historyResult.overall_risk
  }
  return null
})

const mergedDimensions = computed(() => {
  const currentDims = props.currentResult?.dimensions || []
  const historyDims = props.historyResult?.dimensions || []
  const dimMap = new Map<string, { name: string; currentScore: number | null; currentLevel: string; historyScore: number | null; historyLevel: string }>()

  for (const d of currentDims) {
    dimMap.set(d.name, { name: d.name, currentScore: d.score, currentLevel: d.severity, historyScore: null, historyLevel: '' })
  }
  for (const d of historyDims) {
    const existing = dimMap.get(d.name)
    if (existing) {
      existing.historyScore = d.score
      existing.historyLevel = d.severity
    } else {
      dimMap.set(d.name, { name: d.name, currentScore: null, currentLevel: '', historyScore: d.score, historyLevel: d.severity })
    }
  }
  return Array.from(dimMap.values())
})

function riskTagType(level: string): 'default' | 'success' | 'warning' | 'error' {
  const map: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
    green: 'success',
    yellow: 'warning',
    orange: 'warning',
    red: 'error',
  }
  return map[level] || 'default'
}
</script>

<style scoped>
.history-comparison {
  width: 100%;
}

.comparison-header {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 12px;
}

.comparison-col {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px;
  background: #1a1a2e;
  border-radius: 6px;
}

.col-label {
  font-size: 12px;
  color: #888;
  font-weight: 600;
}

.comparison-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.compare-section {
  position: relative;
}

.compare-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
}

.compare-cell {
  padding: 4px 8px;
  text-align: center;
}

.compare-cell.current {
  text-align: right;
}

.compare-cell.history {
  text-align: left;
}

.compare-value {
  font-size: 14px;
  font-weight: 700;
  color: #e0e0e0;
}

.compare-value.green { color: #22c55e; }
.compare-value.yellow { color: #eab308; }
.compare-value.orange { color: #f97316; }
.compare-value.red { color: #ef4444; }

.compare-divider {
  padding: 0 8px;
  text-align: center;
}

.compare-label {
  font-size: 10px;
  color: #666;
  white-space: nowrap;
}

.diff-indicator {
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  margin-top: 2px;
}

.diff-up { color: #ef4444; }
.diff-down { color: #22c55e; }

.sub-title {
  font-size: 11px;
  color: #888;
  margin-bottom: 6px;
  font-weight: 600;
}

.dim-row {
  margin-bottom: 2px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 120px;
  color: #444;
  font-size: 12px;
  background: #0a0a0f;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
}
</style>
