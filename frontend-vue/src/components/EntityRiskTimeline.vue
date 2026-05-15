<template>
  <div class="entity-risk-timeline">
    <div v-if="!entities?.length" class="empty-state">
      <span>暂无实体风险链数据</span>
    </div>
    <NTimeline v-else size="small">
      <NTimelineItem
        v-for="entity in entities"
        :key="entity.id"
        :type="timelineType(entity.risk_level)"
        :title="entity.name"
      >
        <div class="entity-content">
          <div class="entity-row">
            <span class="entity-label">风险分数:</span>
            <span class="entity-score" :class="entity.risk_level">{{ entity.risk_score.toFixed(1) }}</span>
          </div>
          <div class="entity-row">
            <span class="entity-label">关联维度:</span>
            <div class="entity-dims">
              <NTag v-for="dim in entity.dimensions" :key="dim" size="tiny" :bordered="false" :type="dimTagType(entity.risk_level)">
                {{ dim }}
              </NTag>
            </div>
          </div>
          <div class="entity-row">
            <span class="entity-label">时间:</span>
            <span class="entity-time">{{ formatTime(entity.timestamp) }}</span>
          </div>
        </div>
      </NTimelineItem>
    </NTimeline>
  </div>
</template>

<script setup lang="ts">
import { NTimeline, NTimelineItem, NTag } from 'naive-ui'
import type { EntityChainItem } from '../api'

const props = defineProps<{
  entities?: EntityChainItem[]
}>()

function timelineType(level: string): 'default' | 'success' | 'warning' | 'error' {
  const map: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
    green: 'success',
    yellow: 'warning',
    orange: 'warning',
    red: 'error',
  }
  return map[level] || 'default'
}

function dimTagType(level: string): 'default' | 'success' | 'warning' | 'error' {
  const map: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
    green: 'success',
    yellow: 'warning',
    orange: 'warning',
    red: 'error',
  }
  return map[level] || 'default'
}

function formatTime(t: string) {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.entity-risk-timeline {
  width: 100%;
}

.entity-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.entity-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.entity-label {
  color: #888;
  min-width: 56px;
}

.entity-score {
  font-weight: 700;
  font-size: 13px;
}

.entity-score.green { color: #22c55e; }
.entity-score.yellow { color: #eab308; }
.entity-score.orange { color: #f97316; }
.entity-score.red { color: #ef4444; }

.entity-dims {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.entity-time {
  color: #666;
  font-size: 10px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 80px;
  color: #444;
  font-size: 12px;
  background: #0a0a0f;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
}
</style>
