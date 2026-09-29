<template>
  <div class="platform-reactions">
    <h4 class="section-title">平台反应分布</h4>
    <div v-for="(data, platform) in reactions" :key="platform" class="platform-row">
      <span class="platform-name">{{ platformLabel(platform) }}</span>
      <div class="bar-group">
        <div class="bar positive" :style="{ width: (data.positive * 100) + '%' }"></div>
        <div class="bar neutral" :style="{ width: (data.neutral * 100) + '%' }"></div>
        <div class="bar negative" :style="{ width: (data.negative * 100) + '%' }"></div>
      </div>
      <div class="bar-labels">
        <span class="label-pos tabular-nums">{{ (data.positive * 100).toFixed(0) }}%</span>
        <span class="label-neg tabular-nums">{{ (data.negative * 100).toFixed(0) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { platformLabel } from '../utils/platforms'

defineProps<{
  reactions: Record<string, { positive: number; neutral: number; negative: number }>
}>()
</script>

<style scoped>
.platform-reactions { padding: var(--sp-2) 0; }
.section-title { font-size: var(--fs-lg); color: var(--text-secondary); margin-bottom: var(--sp-3); }
.platform-row { display: flex; align-items: center; gap: var(--sp-2); margin-bottom: var(--sp-2); }
.platform-name { width: 72px; font-size: var(--fs-sm); color: var(--text-tertiary); flex-shrink: 0; }
.bar-group { flex: 1; display: flex; height: 18px; border-radius: var(--r-sm); overflow: hidden; background: var(--bg-overlay); }
.bar { height: 100%; transition: width var(--dur-base); min-width: 1px; }
.positive { background: var(--risk-safe); }
.neutral { background: var(--risk-warn); }
.negative { background: var(--risk-critical); }
.bar-labels { display: flex; gap: var(--sp-1); min-width: 60px; justify-content: space-between; }
.label-pos { font-size: var(--fs-2xs); color: var(--risk-safe); }
.label-neg { font-size: var(--fs-2xs); color: var(--risk-critical); }
</style>
