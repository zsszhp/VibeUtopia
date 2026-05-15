<template>
  <NModal
    :show="show"
    preset="card"
    title="应用设置"
    :style="{ maxWidth: '480px', width: '90vw' }"
    :mask-closable="true"
    @update:show="$emit('update:show', $event)"
  >
    <div class="settings-body">
      <div class="setting-item">
        <label class="setting-label">API 地址</label>
        <NInput v-model:value="form.apiBase" size="small" placeholder="http://localhost:8000" />
      </div>

      <div class="setting-item">
        <label class="setting-label">默认分析深度</label>
        <NSelect
          v-model:value="form.defaultDepth"
          size="small"
          :options="depthOptions"
        />
      </div>

      <div class="setting-item">
        <label class="setting-label">主题</label>
        <NSelect
          v-model:value="form.theme"
          size="small"
          :options="themeOptions"
        />
      </div>

      <div class="setting-item">
        <label class="setting-label">模型选择</label>
        <NSelect
          v-model:value="form.model"
          size="small"
          :options="modelOptions"
          placeholder="自动选择"
          clearable
        />
      </div>
    </div>

    <template #footer>
      <div class="settings-footer">
        <NButton size="small" @click="handleReset">重置</NButton>
        <NButton size="small" type="primary" @click="handleSave">保存</NButton>
      </div>
    </template>
  </NModal>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import { NModal, NInput, NSelect, NButton } from 'naive-ui'

const props = defineProps<{
  show: boolean
}>()

defineEmits<{
  'update:show': [value: boolean]
}>()

const STORAGE_KEY = 'vibeutopia_settings'

const depthOptions = [
  { label: '快速 (60s)', value: 'quick' },
  { label: '标准 (3min)', value: 'standard' },
  { label: '深度 (10min)', value: 'deep' },
  { label: '大规模 (30min)', value: 'large_scale' },
]

const themeOptions = [
  { label: '暗色', value: 'dark' },
  { label: '亮色', value: 'light' },
]

const modelOptions = [
  { label: '自动选择', value: 'auto' },
  { label: 'GPT-4', value: 'gpt-4' },
  { label: 'Claude', value: 'claude' },
  { label: '本地模型', value: 'local' },
]

const defaults = {
  apiBase: '',
  defaultDepth: 'standard' as string,
  theme: 'dark' as string,
  model: 'auto' as string,
}

const form = reactive({ ...defaults })

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const saved = JSON.parse(raw)
      Object.assign(form, { ...defaults, ...saved })
    }
  } catch {
    Object.assign(form, defaults)
  }
}

function handleSave() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...form }))
  window.location.reload()
}

function handleReset() {
  Object.assign(form, defaults)
  localStorage.removeItem(STORAGE_KEY)
}

watch(() => props.show, (val) => {
  if (val) loadSettings()
})
</script>

<style scoped>
.settings-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setting-label {
  font-size: 12px;
  color: #888;
  font-weight: 600;
}

.settings-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
