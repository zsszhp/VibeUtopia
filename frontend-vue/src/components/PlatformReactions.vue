<template>
  <div class="platform-reactions">
    <h4 class="section-title">平台反应分布</h4>
    <div v-for="(data, platform) in reactions" :key="platform" class="platform-row">
      <span class="platform-name">{{ platformNameMap[platform] || platform }}</span>
      <div class="bar-group">
        <div class="bar positive" :style="{ width: (data.positive * 100) + '%' }"></div>
        <div class="bar neutral" :style="{ width: (data.neutral * 100) + '%' }"></div>
        <div class="bar negative" :style="{ width: (data.negative * 100) + '%' }"></div>
      </div>
      <div class="bar-labels">
        <span class="label-pos">{{ (data.positive * 100).toFixed(0) }}%</span>
        <span class="label-neg">{{ (data.negative * 100).toFixed(0) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  reactions: Record<string, { positive: number; neutral: number; negative: number }>
}>()

const platformNameMap: Record<string, string> = {
  bilibili: 'B站',
  xiaohongshu: '小红书',
  zhihu: '知乎',
  douyin: '抖音',
  weibo: '微博',
  kuaishou: '快手',
  wechat_channels: '微信视频号',
}
</script>

<style scoped>
.platform-reactions { padding: 8px 0; }
.section-title { font-size: 14px; color: #aaa; margin-bottom: 12px; }
.platform-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.platform-name { width: 72px; font-size: 12px; color: #888; flex-shrink: 0; }
.bar-group { flex: 1; display: flex; height: 18px; border-radius: 4px; overflow: hidden; background: #1e1e2e; }
.bar { height: 100%; transition: width 0.3s; min-width: 1px; }
.positive { background: #22c55e; }
.neutral { background: #eab308; }
.negative { background: #ef4444; }
.bar-labels { display: flex; gap: 4px; min-width: 60px; justify-content: space-between; }
.label-pos { font-size: 10px; color: #22c55e; }
.label-neg { font-size: 10px; color: #ef4444; }
</style>
