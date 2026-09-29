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
        <NInput v-model:value="form.apiBase" size="small" placeholder="留空使用同源 /api" />
        <span class="setting-hint">修改后需保存生效；留空表示与前端同源部署</span>
      </div>

      <div class="setting-item">
        <label class="setting-label">默认分析深度</label>
        <NSelect
          v-model:value="form.defaultDepth"
          size="small"
          :options="depthOptions"
        />
        <span class="setting-hint">新建预审时左栏「分析深度」的默认值</span>
      </div>

      <div class="setting-item">
        <label class="setting-label">主题</label>
        <NSelect
          v-model:value="form.theme"
          size="small"
          :options="themeOptions"
          disabled
        />
        <span class="setting-hint">当前版本仅提供暗色主题（Instrument Dark），浅色暂未开放</span>
      </div>

      <div class="setting-item">
        <label class="setting-label">模型选择</label>
        <NSelect
          v-model:value="form.model"
          size="small"
          :options="modelOptions"
          placeholder="自动选择"
          disabled
        />
        <span class="setting-hint">模型由服务端按本机算力档位自动调度，此项暂不可用</span>
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
import { loadSettings, saveSettings, resetSettings, DEFAULT_SETTINGS } from '../utils/settings'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
}>()

const depthOptions = [
  { label: '快速 (60s)', value: 'quick' },
  { label: '标准 (3min)', value: 'standard' },
  { label: '深度 (10min)', value: 'deep' },
  { label: '大规模 (30min)', value: 'large_scale' },
]

const themeOptions = [
  { label: '暗色', value: 'dark' },
  { label: '浅色（未开放）', value: 'light' },
]

const modelOptions = [
  { label: '自动选择', value: 'auto' },
]

const form = reactive({ ...DEFAULT_SETTINGS })

function loadForm() {
  Object.assign(form, loadSettings())
}

function handleSave() {
  saveSettings({
    apiBase: form.apiBase.trim(),
    defaultDepth: form.defaultDepth,
  })
  // 深度/API 变更即时生效；主题与模型项不可用，不参与保存
  emit('update:show', false)
  window.location.reload()
}

function handleReset() {
  resetSettings()
  Object.assign(form, DEFAULT_SETTINGS)
}

watch(() => props.show, (val) => {
  if (val) loadForm()
})
</script>

<style scoped>
.settings-body {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.setting-label {
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  font-weight: 600;
}

.setting-hint {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.settings-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
}
</style>
