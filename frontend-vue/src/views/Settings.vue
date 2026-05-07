<template>
  <div class="settings">
    <h2 class="text-2xl font-bold mb-4">系统设置</h2>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card header="LLM配置">
          <el-form label-width="120px">
            <el-form-item label="默认Provider">
              <el-input v-model="settings.defaultProvider" placeholder="留空使用配置文件" />
            </el-form-item>
            <el-form-item label="默认模型">
              <el-input v-model="settings.defaultModel" placeholder="留空使用配置文件" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="settings.apiKey" type="password" show-password placeholder="DEEPSEEK_API_KEY" />
            </el-form-item>
            <el-form-item label="超时时间(秒)">
              <el-input-number v-model="settings.timeout" :min="10" :max="120" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card header="数据库状态">
          <div v-if="dbStatus">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="数据库类型">{{ dbStatus.db_type }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag type="success">已连接</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="表数量">{{ dbStatus.table_count }}</el-descriptions-item>
            </el-descriptions>
          </div>
          <el-button @click="loadDbStatus" :loading="dbLoading" class="mt-2">刷新状态</el-button>
        </el-card>

        <el-card header="信号采集调度" class="mt-4">
          <el-form label-width="120px">
            <el-form-item label="采集模式">
              <el-select v-model="signalMode">
                <el-option label="标准模式" value="standard" />
                <el-option label="深度模式" value="deep" />
                <el-option label="快速模式" value="quick" />
              </el-select>
            </el-form-item>
            <el-form-item label="采集间隔(分钟)">
              <el-input-number v-model="signalInterval" :min="5" :max="120" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { api } from '../api'

const settings = reactive({
  defaultProvider: '',
  defaultModel: '',
  apiKey: '',
  timeout: 30,
})
const dbStatus = ref<any>(null)
const dbLoading = ref(false)
const signalMode = ref('standard')
const signalInterval = ref(30)

async function loadDbStatus() {
  dbLoading.value = true
  try {
    const resp = await api.getDbStatus()
    dbStatus.value = resp.data
  } catch {
    dbStatus.value = null
  } finally {
    dbLoading.value = false
  }
}

onMounted(loadDbStatus)
</script>
