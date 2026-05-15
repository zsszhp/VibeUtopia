<template>
  <div class="signal-panel">
    <div class="panel-header">
      <h3 class="section-title">信号采集</h3>
      <div class="header-actions">
        <NSelect
          v-model:value="currentPlatform"
          :options="platformOptions"
          size="tiny"
          style="width: 100px"
          @update:value="fetchHotlist"
        />
      </div>
    </div>

    <!-- 调度器控制 -->
    <div class="scheduler-control">
      <div class="scheduler-status">
        <span class="status-dot" :class="{ active: schedulerStatus.is_running }"></span>
        <span class="status-text">{{ schedulerStatus.is_running ? '运行中' : '已停止' }}</span>
        <NTag v-if="schedulerStatus.current_mode" size="tiny" :type="schedulerStatus.is_running ? 'success' : 'default'" round>
          {{ schedulerStatus.current_mode }}
        </NTag>
      </div>
      <div class="scheduler-actions">
        <NSelect
          v-model:value="schedulerMode"
          :options="modeOptions"
          size="tiny"
          style="width: 90px"
          :disabled="schedulerStatus.is_running"
        />
        <NButton size="tiny" type="primary" @click="startScheduler" :disabled="schedulerStatus.is_running">
          启动
        </NButton>
        <NButton size="tiny" @click="stopScheduler" :disabled="!schedulerStatus.is_running">
          停止
        </NButton>
      </div>
    </div>

    <!-- 热榜列表 -->
    <div class="hotlist-section">
      <div class="sub-title">热榜</div>
      <div v-if="hotlist.length" class="hotlist-items">
        <div v-for="(item, idx) in hotlist" :key="item.signal_id" class="hotlist-item">
          <span class="rank" :class="{ top3: idx < 3 }">{{ idx + 1 }}</span>
          <div class="item-content">
            <span class="item-title">{{ item.title }}</span>
            <div class="item-meta">
              <NTag size="tiny" round>{{ item.platform }}</NTag>
              <span v-if="item.is_new" class="new-badge">NEW</span>
              <span class="meta-text">{{ formatTime(item.last_seen) }}</span>
            </div>
          </div>
        </div>
      </div>
      <p v-else class="empty-hint">暂无热榜数据</p>
    </div>

    <!-- 事件时间线 -->
    <div class="events-section">
      <div class="sub-title">事件检测</div>
      <div v-if="events.length" class="events-timeline">
        <div v-for="event in events" :key="event.event_id" class="event-item">
          <div class="event-dot" :class="eventStrengthClass(event.signal_strength)"></div>
          <div class="event-content">
            <span class="event-title">{{ event.title }}</span>
            <div class="event-meta">
              <NTag size="tiny" :type="eventStrengthType(event.signal_strength)" round>
                {{ event.signal_strength?.toFixed(2) }}
              </NTag>
              <span class="meta-text">{{ event.category }}</span>
            </div>
          </div>
        </div>
      </div>
      <p v-else class="empty-hint">暂无事件数据</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NButton, NSelect, NTag } from 'naive-ui'
import { v3Api } from '../api'

const currentPlatform = ref<string | null>(null)
const schedulerMode = ref('standard')
const hotlist = ref<any[]>([])
const events = ref<any[]>([])
const schedulerStatus = ref<any>({ is_running: false, current_mode: 'manual' })

const platformOptions = [
  { label: '全部', value: null },
  { label: '微博', value: 'weibo' },
  { label: '抖音', value: 'douyin' },
  { label: '小红书', value: 'xiaohongshu' },
  { label: '知乎', value: 'zhihu' },
  { label: 'B站', value: 'bilibili' },
]

const modeOptions = [
  { label: '实时', value: 'realtime' },
  { label: '标准', value: 'standard' },
  { label: '经济', value: 'economy' },
  { label: '手动', value: 'manual' },
]

async function fetchHotlist() {
  try {
    const resp = await v3Api.getSignalHotlist(currentPlatform.value || undefined)
    hotlist.value = resp.data.hotlist || []
  } catch {
    hotlist.value = []
  }
}

async function fetchEvents() {
  try {
    const resp = await v3Api.getSignalEvents()
    events.value = resp.data.events || []
  } catch {
    events.value = []
  }
}

async function fetchSchedulerStatus() {
  try {
    const resp = await v3Api.getSchedulerStatus()
    schedulerStatus.value = resp.data
  } catch {
    schedulerStatus.value = { is_running: false, current_mode: 'manual' }
  }
}

async function startScheduler() {
  try {
    await v3Api.startScheduler(schedulerMode.value)
    await fetchSchedulerStatus()
  } catch {}
}

async function stopScheduler() {
  try {
    await v3Api.stopScheduler()
    await fetchSchedulerStatus()
  } catch {}
}

function formatTime(isoStr: string | null) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

function eventStrengthClass(strength: number) {
  if (strength >= 0.8) return 'strength-high'
  if (strength >= 0.5) return 'strength-medium'
  return 'strength-low'
}

function eventStrengthType(strength: number) {
  if (strength >= 0.8) return 'error' as const
  if (strength >= 0.5) return 'warning' as const
  return 'info' as const
}

onMounted(() => {
  fetchHotlist()
  fetchEvents()
  fetchSchedulerStatus()
})
</script>

<style scoped>
.signal-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  font-size: 13px;
  color: #888;
  font-weight: 600;
  margin: 0;
}

.sub-title {
  font-size: 12px;
  color: #666;
  font-weight: 600;
  margin-bottom: 6px;
}

.scheduler-control {
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  padding: 8px;
}

.scheduler-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #555;
}

.status-dot.active {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}

.status-text {
  font-size: 11px;
  color: #aaa;
}

.scheduler-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.hotlist-section, .events-section {
  margin-top: 4px;
}

.hotlist-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 200px;
  overflow-y: auto;
}

.hotlist-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 6px;
  background: #1a1a2e;
  border-radius: 4px;
}

.rank {
  font-size: 12px;
  font-weight: 700;
  color: #555;
  min-width: 18px;
  text-align: center;
}

.rank.top3 {
  color: #f97316;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 12px;
  color: #ccc;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}

.new-badge {
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 2px;
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  font-weight: 600;
}

.meta-text {
  font-size: 10px;
  color: #666;
}

.events-timeline {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.event-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  border-left: 2px solid #1e1e2e;
  padding-left: 10px;
  position: relative;
}

.event-dot {
  position: absolute;
  left: -5px;
  top: 8px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #555;
}

.event-dot.strength-high { background: #ef4444; }
.event-dot.strength-medium { background: #f97316; }
.event-dot.strength-low { background: #6366f1; }

.event-content {
  flex: 1;
}

.event-title {
  font-size: 12px;
  color: #ccc;
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}

.empty-hint {
  font-size: 12px;
  color: #444;
}
</style>
