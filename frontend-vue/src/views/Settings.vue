<template>
  <div class="settings">
    <h2 class="text-2xl font-bold mb-4">系统设置</h2>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card header="LLM 模型配置">
          <!-- 当前模型状态 -->
          <el-alert
            v-if="currentProvider || currentModel"
            :title="`当前模型: ${currentProviderName || currentProvider} / ${currentModel || '自动路由'}`"
            :type="currentModel ? 'success' : 'info'"
            :closable="false"
            class="mb-4"
          />

          <el-form label-width="100px">
            <el-form-item label="选择厂商">
              <el-select
                v-model="selectedProvider"
                placeholder="选择厂商"
                clearable
                @change="onProviderChange"
                style="width: 100%"
              >
                <el-option
                  v-for="p in providers"
                  :key="p.id"
                  :label="p.name"
                  :value="p.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="选择模型">
              <el-select
                v-model="selectedModel"
                placeholder="选择模型"
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="m in filteredModels"
                  :key="m.id"
                  :label="m.id"
                  :value="m.id"
                >
                  <span>{{ m.id }}</span>
                  <el-tag
                    :type="tierTagType(m.tier)"
                    size="small"
                    class="ml-2"
                  >{{ tierLabel(m.tier) }}</el-tag>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveModel" :loading="saving">保存并应用</el-button>
              <el-button @click="resetModel">恢复默认</el-button>
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

interface ModelOption {
  id: string
  tier: string
}

interface ProviderOption {
  id: string
  name: string
  models: ModelOption[]
}

const providers = ref<ProviderOption[]>([])
const selectedProvider = ref('')
const selectedModel = ref('')
const currentProvider = ref('')
const currentModel = ref('')
const saving = ref(false)

const dbStatus = ref<any>(null)
const dbLoading = ref(false)
const signalMode = ref('standard')
const signalInterval = ref(30)

const currentProviderName = computed(() => {
  const p = providers.value.find(p => p.id === currentProvider.value)
  return p ? p.name : currentProvider.value
})

const filteredModels = computed(() => {
  if (!selectedProvider.value) {
    return providers.value.flatMap(p => p.models)
  }
  const p = providers.value.find(p => p.id === selectedProvider.value)
  return p ? p.models : []
})

function tierLabel(tier: string) {
  const map: Record<string, string> = { advanced: '高级', standard: '标准', lite: '轻量' }
  return map[tier] || tier
}

function tierTagType(tier: string) {
  const map: Record<string, string> = { advanced: 'danger', standard: '', lite: 'info' }
  return map[tier] || ''
}

function onProviderChange() {
  selectedModel.value = ''
}

async function loadModels() {
  try {
    const resp = await api.getModels()
    providers.value = resp.data.providers || []
  } catch {
    providers.value = []
  }
}

async function loadModelSetting() {
  try {
    const resp = await api.getModelSetting()
    const runtime = resp.data.runtime || {}
    const env = resp.data.env || {}
    currentProvider.value = runtime.provider || env.provider || ''
    currentModel.value = runtime.model || env.model || ''
    selectedProvider.value = currentProvider.value
    selectedModel.value = currentModel.value
  } catch {
    // ignore
  }
}

async function saveModel() {
  saving.value = true
  try {
    await api.setModel(selectedProvider.value, selectedModel.value)
    currentProvider.value = selectedProvider.value
    currentModel.value = selectedModel.value
    ElMessage.success('模型切换成功，立即生效')
  } catch (e: any) {
    ElMessage.error('模型切换失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

async function resetModel() {
  saving.value = true
  try {
    await api.setModel('', '')
    currentProvider.value = ''
    currentModel.value = ''
    selectedProvider.value = ''
    selectedModel.value = ''
    ElMessage.success('已恢复默认模型路由')
  } catch (e: any) {
    ElMessage.error('恢复默认失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

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

onMounted(() => {
  loadModels()
  loadModelSetting()
  loadDbStatus()
})
</script>
