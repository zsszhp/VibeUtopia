<template>
  <div class="risk-gauge">
    <div ref="gaugeRef" style="width: 200px; height: 200px"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  score: number
  level: string
}>()

const gaugeRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function handleResize() { chart?.resize() }

function render() {
  if (!gaugeRef.value) return
  if (!chart) {
    chart = echarts.init(gaugeRef.value, 'dark')
    window.addEventListener('resize', handleResize)
  }
  const colorMap: Record<string, string> = { green: '#22c55e', yellow: '#eab308', orange: '#f97316', red: '#ef4444' }
  chart.setOption({
    series: [{
      type: 'gauge',
      startAngle: 220,
      endAngle: -40,
      min: 0,
      max: 100,
      pointer: { show: true },
      detail: { formatter: '{value}', fontSize: 28, color: '#e0e0e0', offsetCenter: [0, '70%'] },
      data: [{ value: props.score, name: props.level.toUpperCase() }],
      axisLine: { lineStyle: { width: 12, color: [[0.35, '#22c55e'], [0.55, '#eab308'], [0.75, '#f97316'], [1, '#ef4444']] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      title: { fontSize: 14, color: colorMap[props.level] || '#888', offsetCenter: [0, '90%'] },
    }],
  })
}

onMounted(render)
watch(() => props.score, render)
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.risk-gauge { display: flex; justify-content: center; }
</style>
