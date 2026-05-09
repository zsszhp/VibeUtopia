<template>
  <div class="platform-reactions">
    <h4 class="section-title">平台反应分布</h4>
    <div v-for="(data, platform) in reactions" :key="platform" class="platform-row">
      <span class="platform-name">{{ platform }}</span>
      <div class="bar-group">
        <div class="bar positive" :style="{ width: data.positive + '%' }"></div>
        <div class="bar neutral" :style="{ width: data.neutral + '%' }"></div>
        <div class="bar negative" :style="{ width: data.negative + '%' }"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  reactions: Record<string, { positive: number; neutral: number; negative: number }>
}>()
</script>

<style scoped>
.platform-reactions { padding: 8px 0; }
.section-title { font-size: 14px; color: #aaa; margin-bottom: 12px; }
.platform-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.platform-name { width: 60px; font-size: 12px; color: #888; flex-shrink: 0; }
.bar-group { flex: 1; display: flex; height: 16px; border-radius: 4px; overflow: hidden; background: #1e1e2e; }
.bar { height: 100%; transition: width 0.3s; }
.positive { background: #22c55e; }
.neutral { background: #eab308; }
.negative { background: #ef4444; }
</style>
