<template>
  <div class="polarization-chart">
    <div v-if="!polarizationData?.timeline?.length" class="empty-state">
      <span>暂无极化趋势数据</span>
    </div>
    <div v-else ref="chartRef" style="width: 100%; height: 260px"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { PolarizationData } from '../api'

const props = defineProps<{
  polarizationData?: PolarizationData
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function handleResize() { chart?.resize() }

function render() {
  if (!chartRef.value || !props.polarizationData?.timeline?.length) return

  if (!chart) {
    chart = echarts.init(chartRef.value, 'dark')
    window.addEventListener('resize', handleResize)
  }

  const timeline = props.polarizationData.timeline
  const thresholds = props.polarizationData.thresholds

  const markLines: any[] = []
  if (thresholds) {
    const thresholdLabels: Record<string, string> = { low: '低极化', medium: '中极化', high: '高极化' }
    const thresholdColors: Record<string, string> = { low: '#22c55e', medium: '#eab308', high: '#ef4444' }
    for (const [key, val] of Object.entries(thresholds)) {
      markLines.push({
        yAxis: val,
        lineStyle: { color: thresholdColors[key] || '#888', type: 'dashed', width: 1 },
        label: {
          formatter: thresholdLabels[key] || key,
          position: 'insideEndTop',
          color: thresholdColors[key] || '#888',
          fontSize: 10,
        },
      })
    }
  }

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a1a2e',
      borderColor: '#2a2a3e',
      textStyle: { color: '#e0e0e0', fontSize: 11 },
    },
    legend: {
      data: ['极化指数', '支持', '反对', '中立'],
      textStyle: { color: '#888', fontSize: 10 },
      top: 0,
      itemWidth: 12,
      itemHeight: 8,
    },
    grid: {
      left: 40,
      right: 40,
      top: 36,
      bottom: 24,
    },
    xAxis: {
      type: 'category',
      data: timeline.map(d => d.time),
      axisLine: { lineStyle: { color: '#2a2a3e' } },
      axisLabel: { color: '#666', fontSize: 9, interval: Math.max(0, Math.floor(timeline.length / 6) - 1) },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '极化指数',
        nameTextStyle: { color: '#888', fontSize: 10 },
        min: 0,
        max: 1,
        splitLine: { lineStyle: { color: '#1e1e2e' } },
        axisLabel: { color: '#666', fontSize: 10 },
      },
      {
        type: 'value',
        name: '人数',
        nameTextStyle: { color: '#888', fontSize: 10 },
        splitLine: { show: false },
        axisLabel: { color: '#666', fontSize: 10 },
      },
    ],
    series: [
      {
        name: '极化指数',
        type: 'line',
        data: timeline.map(d => d.polarization_index),
        smooth: true,
        lineStyle: { color: '#6366f1', width: 2 },
        itemStyle: { color: '#6366f1' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(99,102,241,0.3)' },
          { offset: 1, color: 'rgba(99,102,241,0.02)' },
        ]) },
        markLine: { silent: true, data: markLines, symbol: 'none' },
      },
      {
        name: '支持',
        type: 'line',
        yAxisIndex: 1,
        data: timeline.map(d => d.support_count),
        smooth: true,
        lineStyle: { color: '#6366f1', width: 1, type: 'dashed' },
        itemStyle: { color: '#6366f1' },
        symbol: 'none',
      },
      {
        name: '反对',
        type: 'line',
        yAxisIndex: 1,
        data: timeline.map(d => d.oppose_count),
        smooth: true,
        lineStyle: { color: '#ef4444', width: 1, type: 'dashed' },
        itemStyle: { color: '#ef4444' },
        symbol: 'none',
      },
      {
        name: '中立',
        type: 'line',
        yAxisIndex: 1,
        data: timeline.map(d => d.neutral_count),
        smooth: true,
        lineStyle: { color: '#888', width: 1, type: 'dashed' },
        itemStyle: { color: '#888' },
        symbol: 'none',
      },
    ],
  }, true)
}

onMounted(() => nextTick(render))
watch(() => props.polarizationData, () => nextTick(render), { deep: true })
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.polarization-chart {
  width: 100%;
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
