<template>
  <div class="signals">
    <h2 class="text-2xl font-bold mb-4">信号监控</h2>
    <el-button type="primary" @click="fetchSignals" :loading="loading" class="mb-4">
      采集信号
    </el-button>
    <el-table :data="signals" stripe style="width: 100%">
      <el-table-column prop="source_platform" label="平台" width="120" />
      <el-table-column prop="title" label="标题" min-width="300" />
      <el-table-column prop="signal_strength" label="信号强度" width="120">
        <template #default="{ row }">
          <el-progress :percentage="Math.min(100, (row.signal_strength || row.rank || 0))" :stroke-width="6" />
        </template>
      </el-table-column>
      <el-table-column prop="is_new" label="新信号" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.is_new" type="danger" size="small">新</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="appearance_count" label="出现次数" width="100" />
      <el-table-column prop="first_seen" label="首次发现" width="180" />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const signals = ref<any[]>([])
const loading = ref(false)

async function fetchSignals() {
  loading.value = true
  try {
    await api.fetchSignals('standard')
    const resp = await api.getSignals(100)
    signals.value = resp.data.signals || resp.data
  } finally {
    loading.value = false
  }
}

onMounted(fetchSignals)
</script>
