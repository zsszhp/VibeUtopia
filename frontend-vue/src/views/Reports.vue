<template>
  <div class="reports">
    <h2 class="text-2xl font-bold mb-4">历史报告</h2>

    <el-tabs v-model="activeType">
      <el-tab-pane label="风控报告" name="risk" />
      <el-tab-pane label="仿真报告" name="simulation" />
      <el-tab-pane label="趋势报告" name="trend" />
      <el-tab-pane label="决策报告" name="decision" />
    </el-tabs>

    <el-table :data="reports" stripe style="width: 100%" class="mt-4">
      <el-table-column prop="report_id" label="报告ID" width="200" />
      <el-table-column prop="title" label="标题" min-width="250" />
      <el-table-column prop="report_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ row.report_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="生成时间" width="180" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="viewReport(row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 报告详情 -->
    <el-dialog v-model="showReport" :title="currentReport?.title" width="70%">
      <div v-html="renderMarkdown(currentReport?.content || '')" class="prose max-w-none"></div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { api } from '../api'

const activeType = ref('risk')
const reports = ref<any[]>([])
const showReport = ref(false)
const currentReport = ref<any>(null)

async function loadReports() {
  try {
    const resp = await api.getReports(activeType.value)
    reports.value = resp.data.reports || resp.data || []
  } catch {
    reports.value = []
  }
}

function viewReport(report: any) {
  currentReport.value = report
  showReport.value = true
}

function renderMarkdown(text: string): string {
  // 简单Markdown渲染 - 生产环境应使用markdown-it等库
  return text
    .replace(/^### (.*$)/gm, '<h3>$1</h3>')
    .replace(/^## (.*$)/gm, '<h2>$1</h2>')
    .replace(/^# (.*$)/gm, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

watch(activeType, loadReports)
onMounted(loadReports)
</script>
