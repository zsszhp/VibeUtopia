<template>
  <div class="hotspot-list">
    <div v-if="!hotspots?.length" class="empty-state">
      <span>暂无关联热点</span>
    </div>
    <NList v-else bordered size="small" class="hotspot-nlist">
      <NListItem v-for="item in hotspots" :key="item.signal_id">
        <div class="hotspot-item" @click="toggleExpand(item.signal_id)">
          <div class="hotspot-header">
            <span class="hotspot-title">{{ item.title }}</span>
            <NTag :type="riskTagType(item.risk_boost)" size="small" round>
              +{{ (item.risk_boost * 100).toFixed(0) }}%
            </NTag>
          </div>
          <div class="hotspot-meta">
            <NTag size="tiny" :bordered="false" type="info">{{ item.platform }}</NTag>
            <span class="correlation-score">关联度: {{ (item.correlation_score * 100).toFixed(0) }}%</span>
          </div>
          <div v-if="expandedId === item.signal_id" class="hotspot-detail">
            <div class="detail-row">
              <span class="detail-label">信号ID:</span>
              <span class="detail-value">{{ item.signal_id }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">关联度:</span>
              <span class="detail-value">{{ (item.correlation_score * 100).toFixed(1) }}%</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">风险提升:</span>
              <span class="detail-value risk-boost">+{{ (item.risk_boost * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </NListItem>
    </NList>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NList, NListItem, NTag } from 'naive-ui'
import type { SignalCorrelation } from '../api'

const props = defineProps<{
  hotspots?: SignalCorrelation[]
}>()

const expandedId = ref('')

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? '' : id
}

function riskTagType(boost: number): 'default' | 'warning' | 'error' {
  if (boost >= 0.3) return 'error'
  if (boost >= 0.15) return 'warning'
  return 'default'
}
</script>

<style scoped>
.hotspot-list {
  width: 100%;
}

.hotspot-nlist {
  background: transparent;
}

.hotspot-item {
  cursor: pointer;
  width: 100%;
}

.hotspot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.hotspot-title {
  font-size: 12px;
  color: #ccc;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotspot-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.correlation-score {
  font-size: 10px;
  color: #6366f1;
}

.hotspot-detail {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #1e1e2e;
}

.detail-row {
  display: flex;
  gap: 6px;
  font-size: 11px;
  margin-bottom: 2px;
}

.detail-label {
  color: #888;
  min-width: 50px;
}

.detail-value {
  color: #ccc;
}

.risk-boost {
  color: #ef4444;
  font-weight: 600;
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
