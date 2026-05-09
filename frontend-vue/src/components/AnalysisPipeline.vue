<template>
  <div class="pipeline">
    <div
      v-for="(step, idx) in steps"
      :key="step.key"
      class="pipeline-node"
      :class="{ active: step.key === currentStep, done: stepIndex > idx, pending: stepIndex < idx }"
    >
      <div class="node-dot"></div>
      <span class="node-label">{{ step.label }}</span>
      <div v-if="idx < steps.length - 1" class="node-line"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  currentStep: string
  progress: number
}>()

const steps = [
  { key: 'understanding', label: '内容理解' },
  { key: 'assessment', label: '风险评估' },
  { key: 'signal', label: '信号采集' },
  { key: 'simulation', label: '仿真推演' },
  { key: 'report', label: '报告生成' },
]

const stepIndex = computed(() => steps.findIndex(s => s.key === props.currentStep))
</script>

<style scoped>
.pipeline {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 12px 16px;
  background: #12121a;
  border-radius: 8px;
  border: 1px solid #1e1e2e;
}

.pipeline-node {
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative;
}

.node-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #333;
  flex-shrink: 0;
  transition: all 0.3s;
}

.pipeline-node.active .node-dot {
  background: #6366f1;
  box-shadow: 0 0 8px #6366f1;
  animation: pulse 1.5s infinite;
}

.pipeline-node.done .node-dot {
  background: #22c55e;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 4px #6366f1; }
  50% { box-shadow: 0 0 12px #6366f1; }
}

.node-label {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}

.pipeline-node.active .node-label {
  color: #6366f1;
  font-weight: 600;
}

.pipeline-node.done .node-label {
  color: #22c55e;
}

.node-line {
  width: 40px;
  height: 2px;
  background: #1e1e2e;
  margin: 0 8px;
}
</style>
