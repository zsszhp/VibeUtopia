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
      <div class="setting-item">
        <label class="setting-label">账号（可选）</label>
        <div class="auth-row">
          <NInput v-model:value="auth.username" size="small" placeholder="用户名" />
          <NInput v-model:value="auth.password" size="small" type="password" show-password-on="click" placeholder="密码（至少8位）" />
        </div>
        <div class="auth-row">
          <NButton size="small" type="primary" :loading="auth.loading" @click="handleLogin">登录</NButton>
          <NButton size="small" :loading="auth.loading" @click="handleRegister">注册</NButton>
          <NButton size="small" quaternary @click="handleLogout">退出</NButton>
        </div>
        <span class="setting-hint">{{ auth.message || (auth.token ? `已登录：${auth.username}` : '配置 JWT 后可用；本地开发可跳过') }}</span>
      </div>
      <div class="setting-item">
        <label class="setting-label">服务状态</label>
        <div class="auth-row">
          <NButton size="small" :loading="health.loading" @click="checkHealth">检查后端</NButton>
          <NButton size="small" quaternary @click="loadMetrics">查看用量</NButton>
        </div>
        <span class="setting-hint">{{ health.message }}</span>
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
import axios from 'axios'
import { NModal, NInput, NSelect, NButton } from 'naive-ui'
import { loadSettings, saveSettings, resetSettings, DEFAULT_SETTINGS } from '../utils/settings'
import { api } from '../api'

const TOKEN_KEY = 'vibe_jwt'

function applyToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
  } else {
    localStorage.removeItem(TOKEN_KEY)
    delete axios.defaults.headers.common['Authorization']
  }
}

// 恢复已有 token
const savedToken = localStorage.getItem(TOKEN_KEY)
if (savedToken) {
  axios.defaults.headers.common['Authorization'] = `Bearer ${savedToken}`
}

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

const auth = reactive({
  username: localStorage.getItem('vibe_user') || '',
  password: '',
  token: localStorage.getItem(TOKEN_KEY) || '',
  loading: false,
  message: '',
})

const health = reactive({ loading: false, message: '' })

async function checkHealth() {
  health.loading = true
  health.message = ''
  try {
    const r = await axios.get('/health')
    health.message = `后端正常：${r.data?.status || 'ok'} v${r.data?.version || ''}`
  } catch (e: any) {
    health.message = e?.response?.data?.detail || e?.message || '无法连接后端'
  } finally {
    health.loading = false
  }
}

async function loadMetrics() {
  health.loading = true
  try {
    const r = await axios.get('/api/v1/metrics/summary', { params: { n: 5 } })
    const d = r.data || {}
    health.message = d.available
      ? `近${d.window ?? 5}次：调用 ${d.calls ?? d.total_calls ?? '—'}，失败率 ${((d.failure_rate ?? 0) * 100).toFixed(0)}%，p50 ${Math.round(d.latency_ms?.p50 ?? 0)}ms`
      : '暂无计量数据（需先跑分析）'
  } catch (e: any) {
    health.message = e?.response?.data?.detail || e?.message || '获取用量失败'
  } finally {
    health.loading = false
  }
}

async function handleLogin() {
  auth.loading = true
  auth.message = ''
  try {
    const r = await api.login(auth.username.trim(), auth.password)
    applyToken(r.data.access_token)
    auth.token = r.data.access_token
    auth.username = r.data.username || auth.username
    localStorage.setItem('vibe_user', auth.username)
    auth.message = '登录成功'
    auth.password = ''
  } catch (e: any) {
    auth.message = e?.response?.data?.detail || e?.message || '登录失败'
  } finally {
    auth.loading = false
  }
}

async function handleRegister() {
  auth.loading = true
  auth.message = ''
  try {
    const r = await api.registerUser(auth.username.trim(), auth.password)
    applyToken(r.data.access_token)
    auth.token = r.data.access_token
    localStorage.setItem('vibe_user', auth.username)
    auth.message = '注册成功并已登录'
    auth.password = ''
  } catch (e: any) {
    auth.message = e?.response?.data?.detail || e?.message || '注册失败'
  } finally {
    auth.loading = false
  }
}

function handleLogout() {
  applyToken(null)
  auth.token = ''
  auth.password = ''
  auth.message = '已退出'
}

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

.auth-row {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
  align-items: center;
}
</style>
