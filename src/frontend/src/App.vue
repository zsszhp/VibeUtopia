<template>
  <NConfigProvider :theme="darkTheme" :theme-overrides="themeOverrides" :locale="zhCN" :date-locale="dateZhCN">
    <div class="app-root">
      <!-- 顶部栏 -->
      <header class="app-header">
        <div class="header-left">
          <span class="app-title">VibeUtopia</span>
          <span class="app-subtitle">内容预审风控平台</span>
        </div>
        <div class="header-right">
          <n-tag :type="tierTagType" size="small" round>{{ tierLabel }}</n-tag>
          <n-button quaternary circle size="small" @click="showSettings = true">
            <template #icon><SettingsOutline /></template>
          </n-button>
        </div>
      </header>

      <!-- 全局错误条 -->
      <div v-if="reviewStore.error || historyStore.error" class="global-error-bar">
        <NAlert
          v-if="reviewStore.error"
          type="error"
          title="任务出错"
          closable
          @close="reviewStore.clearError()"
        >
          {{ reviewStore.error }}
        </NAlert>
        <NAlert
          v-if="historyStore.error"
          type="warning"
          title="历史记录"
          closable
          class="error-alert-gap"
          @close="historyStore.clearError()"
        >
          {{ historyStore.error }}
        </NAlert>
      </div>

      <!-- 主体三面板 -->
      <div class="app-body">
        <!-- 左栏 -->
        <aside class="panel-left">
          <LeftPanel />
        </aside>

        <!-- 主内容区 -->
        <main class="panel-main">
          <router-view />
        </main>

        <!-- 右栏（可折叠） -->
        <aside class="panel-right" :class="{ collapsed: rightCollapsed }">
          <button class="collapse-btn" @click="rightCollapsed = !rightCollapsed">
            {{ rightCollapsed ? '<' : '>' }}
          </button>
          <div v-show="!rightCollapsed" class="panel-right-content">
            <RightPanel />
          </div>
        </aside>
      </div>

      <!-- 底部状态栏 -->
      <footer class="app-footer">
        <span class="footer-step">{{ stepLabel }}</span>
        <div class="footer-progress">
          <div class="progress-bar" :style="{ width: progressPercent + '%' }"></div>
        </div>
        <span class="footer-percent">{{ Math.round(progressPercent) }}%</span>
      </footer>

      <!-- WebSocket连接管理 -->
      <WebSocketManager />

      <!-- 设置弹窗 -->
      <SettingsDialog v-model:show="showSettings" />
    </div>
  </NConfigProvider>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { NTag, NButton, NAlert, NConfigProvider, darkTheme, zhCN, dateZhCN } from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'
import { SettingsOutline } from '@vicons/ionicons5'
import { useReviewStore, useHistoryStore, useModelsStore } from './stores'
import LeftPanel from './components/LeftPanel.vue'
import RightPanel from './components/RightPanel.vue'
import WebSocketManager from './components/WebSocketManager.vue'
import SettingsDialog from './components/SettingsDialog.vue'

const reviewStore = useReviewStore()
const historyStore = useHistoryStore()
const modelsStore = useModelsStore()

const rightCollapsed = ref(false)
const showSettings = ref(false)

// Instrument Dark：与 tokens.css 对齐的 Naive 主题覆盖
const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#6366F1',
    primaryColorHover: '#818CF8',
    primaryColorPressed: '#4F46E5',
    primaryColorSuppl: '#818CF8',
    bodyColor: '#0B0D12',
    cardColor: '#171B24',
    modalColor: '#171B24',
    popoverColor: '#1C2230',
    borderColor: '#2E3648',
    dividerColor: '#232936',
    textColorBase: '#E6EAF2',
    textColor1: '#E6EAF2',
    textColor2: '#B7C0D4',
    textColor3: '#8B94A8',
    placeholderColor: '#5C6578',
    borderRadius: '8px',
    fontSize: '13px',
    fontFamily: "'Inter', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif",
    fontFamilyMono: "'JetBrains Mono', ui-monospace, monospace",
  },
  Tag: { borderRadius: '999px' },
  Button: { borderRadiusMedium: '8px', borderRadiusSmall: '6px' },
  Card: { borderRadius: '12px' },
}

const progressPercent = computed(() => reviewStore.progressPercent)
const currentStep = computed(() => reviewStore.currentStep)

const stepLabels: Record<string, string> = {
  understanding: '内容理解',
  assessment: '风险评估',
  signal: '信号采集',
  simulation: '仿真推演',
  report: '报告生成',
}
const stepLabel = computed(() => stepLabels[currentStep.value] || '就绪')

const tierLabel = computed(() => {
  const tier = modelsStore.hardwareTier
  const map: Record<string, string> = { lite: 'Lite', standard: 'Standard', pro: 'Pro', ultra: 'Ultra' }
  return map[tier] || 'Lite'
})
const tierTagType = computed(() => {
  const tier = modelsStore.hardwareTier
  if (tier === 'pro' || tier === 'ultra') return 'success' as const
  if (tier === 'standard') return 'warning' as const
  return 'default' as const
})

modelsStore.fetchModels()
</script>

<style scoped>
.app-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: var(--font-sans);
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 var(--sp-4);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.app-title {
  font-size: var(--fs-xl);
  font-weight: 700;
  color: var(--brand-400);
}

.app-subtitle {
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.global-error-bar {
  padding: var(--sp-2) var(--sp-4) 0;
  flex-shrink: 0;
}

.error-alert-gap {
  margin-top: var(--sp-2);
}

.app-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.panel-left {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-subtle);
  overflow-y: auto;
}

.panel-main {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-4);
}

.panel-right {
  width: 320px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-left: 1px solid var(--border-subtle);
  overflow-y: auto;
  position: relative;
  transition: width var(--dur-base);
}

.panel-right.collapsed {
  width: 28px;
}

.collapse-btn {
  position: absolute;
  top: 50%;
  left: 0;
  transform: translateY(-50%);
  width: 20px;
  height: 40px;
  background: var(--bg-overlay);
  border: none;
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: var(--fs-sm);
  z-index: 10;
}

.collapse-btn:hover {
  background: var(--border-default);
  color: var(--text-secondary);
}

.panel-right-content {
  padding: var(--sp-3);
}

.app-footer {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  height: 28px;
  padding: 0 var(--sp-4);
  background: var(--bg-surface);
  border-top: 1px solid var(--border-subtle);
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.footer-progress {
  flex: 1;
  max-width: 200px;
  height: 4px;
  background: var(--border-subtle);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--brand-600);
  border-radius: 2px;
  transition: width var(--dur-base);
}

.footer-percent {
  min-width: 36px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
