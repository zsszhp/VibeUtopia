<template>
  <div ref="radarRef" style="width: 100%; height: 300px"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import type * as ECharts from 'echarts'
import type { RiskDimension } from '../api'

const props = defineProps<{ dimensions: RiskDimension[] }>()
const radarRef = ref<HTMLElement>()
let chart: ECharts.ECharts | null = null
let echarts: typeof ECharts | null = null

function handleResize() { chart?.resize() }

async function render() {
  if (!radarRef.value || !props.dimensions?.length) return
  if (!echarts) {
    echarts = await import('echarts')
  }
  if (!chart) {
    chart = echarts.init(radarRef.value, 'dark')
    window.addEventListener('resize', handleResize)
  }
  chart.setOption({
    radar: {
      indicator: props.dimensions.map(d => ({ name: d.name, max: 100 })),
      shape: 'polygon',
      splitArea: { areaStyle: { color: ['rgba(99,102,241,0.05)', 'rgba(99,102,241,0.1)'] } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: props.dimensions.map(d => d.score),
        name: '风险评分',
        areaStyle: { color: 'rgba(99,102,241,0.2)' },
        lineStyle: { color: '#6366f1' },
        itemStyle: { color: '#6366f1' },
      }],
    }],
  })
}

onMounted(render)
watch(() => props.dimensions, render, { deep: true })
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>
