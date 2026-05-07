<template>
  <div class="simulation">
    <h2 class="text-2xl font-bold mb-4">仿真大屏</h2>

    <el-row :gutter="20">
      <!-- 控制面板 -->
      <el-col :span="6">
        <el-card header="仿真控制">
          <el-input v-model="seedContent" type="textarea" :rows="4" placeholder="输入文案..." />
          <el-button type="primary" @click="startSimulation" :loading="loading" class="mt-2 w-full">
            启动仿真
          </el-button>
          <div v-if="wsConnected" class="mt-2">
            <el-tag type="success" size="small">WebSocket 已连接</el-tag>
          </div>
        </el-card>

        <!-- 实时指标 -->
        <el-card header="实时指标" class="mt-4" v-if="store.simStatus">
          <div class="space-y-2">
            <div>状态: <el-tag :type="store.simStatus.status === 'completed' ? 'success' : 'warning'" size="small">{{ store.simStatus.status }}</el-tag></div>
            <div>Tick: {{ store.simStatus.current_tick }} / {{ store.simStatus.total_ticks }}</div>
            <div>Agent数: {{ store.simStatus.total_agents }}</div>
          </div>
        </el-card>
      </el-col>

      <!-- 传播网络 -->
      <el-col :span="12">
        <el-card header="传播网络">
          <div ref="networkRef" style="height: 500px; background: #1a1a2e; border-radius: 8px;"></div>
        </el-card>
      </el-col>

      <!-- 实时图表 -->
      <el-col :span="6">
        <el-card header="传播动力学">
          <div ref="dynamicsRef" style="height: 230px;"></div>
        </el-card>
        <el-card header="极化指数" class="mt-4">
          <div ref="polarRef" style="height: 230px;"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onUnmounted } from 'vue'
import { useSimulationStore } from '../stores'
import * as echarts from 'echarts'

const store = useSimulationStore()
const seedContent = ref('')
const loading = ref(false)
const networkRef = ref<HTMLElement>()
const dynamicsRef = ref<HTMLElement>()
const polarRef = ref<HTMLElement>()
const { wsConnected } = store

async function startSimulation() {
  if (!seedContent.value) return
  loading.value = true
  try {
    const data = await store.createSimulation(seedContent.value)
    store.connectWebSocket(data.sim_id)
    // 初始渲染
    await nextTick()
    renderNetworkPlaceholder()
    renderDynamicsPlaceholder()
    renderPolarPlaceholder()
  } finally {
    loading.value = false
  }
}

function renderNetworkPlaceholder() {
  if (!networkRef.value) return
  const chart = echarts.init(networkRef.value)
  chart.setOption({
    backgroundColor: '#1a1a2e',
    title: { text: '传播网络 (等待仿真数据)', left: 'center', top: 10, textStyle: { color: '#aaa' } },
  })
}

function renderDynamicsPlaceholder() {
  if (!dynamicsRef.value) return
  const chart = echarts.init(dynamicsRef.value)
  chart.setOption({
    title: { text: '传播动力学', left: 'center', textStyle: { fontSize: 12 } },
    xAxis: { type: 'category', data: [] },
    yAxis: { type: 'value' },
    series: [{ type: 'line', data: [] }],
  })
}

function renderPolarPlaceholder() {
  if (!polarRef.value) return
  const chart = echarts.init(polarRef.value)
  chart.setOption({
    title: { text: '极化指数', left: 'center', textStyle: { fontSize: 12 } },
    xAxis: { type: 'category', data: [] },
    yAxis: { type: 'value', min: 0, max: 1 },
    series: [{ type: 'line', data: [] }],
  })
}

onUnmounted(() => {
  store.disconnectWebSocket()
})
</script>
