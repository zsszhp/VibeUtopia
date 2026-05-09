<template>
  <div ref="radarRef" style="width: 100%; height: 300px"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import * as echarts from 'echarts'
import type { RiskDimension } from '../api'

const props = defineProps<{ dimensions: RiskDimension[] }>()
const radarRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function render() {
  if (!radarRef.value || !props.dimensions?.length) return
  if (!chart) chart = echarts.init(radarRef.value, 'dark')
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
</script>
