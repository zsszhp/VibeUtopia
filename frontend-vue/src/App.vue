<template>
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

    <!-- 主体三面板 -->
    <div class="app-body">
      <!-- 左栏 -->
      <aside class="panel-left">
        <router-view name="left" />
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
          <router-view name="right" />
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { NTag, NButton } from 'naive-ui'
import { SettingsOutline } from '@vicons/ionicons5'
import { useReviewStore, useModelsStore } from './stores'

const reviewStore = useReviewStore()
const modelsStore = useModelsStore()

const rightCollapsed = ref(false)
const showSettings = ref(false)

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
  if (tier === 'pro' || tier === 'ultra') return 'success'
  if (tier === 'standard') return 'warning'
  return 'default'
})

modelsStore.fetchModels()
</script>

<style scoped>
.app-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0a0a0f;
  color: #e0e0e0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 16px;
  background: #12121a;
  border-bottom: 1px solid #1e1e2e;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.app-title {
  font-size: 18px;
  font-weight: 700;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.app-subtitle {
  font-size: 12px;
  color: #666;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.app-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.panel-left {
  width: 240px;
  flex-shrink: 0;
  background: #0f0f18;
  border-right: 1px solid #1e1e2e;
  overflow-y: auto;
}

.panel-main {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.panel-right {
  width: 320px;
  flex-shrink: 0;
  background: #0f0f18;
  border-left: 1px solid #1e1e2e;
  overflow-y: auto;
  position: relative;
  transition: width 0.2s;
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
  background: #1e1e2e;
  border: none;
  border-radius: 0 4px 4px 0;
  color: #888;
  cursor: pointer;
  font-size: 12px;
  z-index: 10;
}

.collapse-btn:hover {
  background: #2a2a3e;
  color: #aaa;
}

.panel-right-content {
  padding: 12px;
}

.app-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 28px;
  padding: 0 16px;
  background: #12121a;
  border-top: 1px solid #1e1e2e;
  font-size: 12px;
  color: #888;
  flex-shrink: 0;
}

.footer-progress {
  flex: 1;
  max-width: 200px;
  height: 4px;
  background: #1e1e2e;
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 2px;
  transition: width 0.3s;
}

.footer-percent {
  min-width: 36px;
  text-align: right;
}
</style>
