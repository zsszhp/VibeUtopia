<template>
  <div class="video-review">
    <h2 class="text-2xl font-bold mb-4">视频审核</h2>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card header="视频输入">
          <el-input v-model="videoUrl" placeholder="粘贴B站/抖音等视频链接..." class="mb-2" />
          <el-input v-model="videoPath" placeholder="本地视频路径(可选)" class="mb-4" />
          <div class="flex gap-2 mb-4">
            <el-button @click="extractText" :loading="extractLoading">提取文案</el-button>
            <el-button type="primary" @click="analyzeVideo('quick')" :loading="analyzeLoading">快速审核</el-button>
            <el-button type="warning" @click="analyzeVideo('deep')" :loading="analyzeLoading">深度审核</el-button>
          </div>
          <el-slider v-model="maxFrames" :min="10" :max="100" label="最大关键帧数" />
        </el-card>

        <!-- 提取文案 -->
        <el-card v-if="extractData" header="提取结果" class="mt-4">
          <p><strong>标题:</strong> {{ extractData.title }}</p>
          <p v-if="extractData.subtitles"><strong>字幕:</strong> {{ extractData.subtitles?.slice(0, 500) }}</p>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card header="多模态审核结果">
          <template v-if="!videoResult">
            <el-empty description="提交视频开始审核" />
          </template>
          <template v-else>
            <!-- 综合风险 -->
            <div class="mb-4">
              <el-tag :type="riskTagType" size="large" effect="dark">
                {{ videoResult.overall_risk_level?.toUpperCase() }} ({{ videoResult.overall_risk_score }}分)
              </el-tag>
            </div>

            <el-row :gutter="10" class="mb-4">
              <el-col :span="8">
                <el-statistic title="画面风险" :value="videoResult.frame_risk_level" />
              </el-col>
              <el-col :span="8">
                <el-statistic title="OCR引擎" :value="videoResult.ocr_engine || '未启用'" />
              </el-col>
              <el-col :span="8">
                <el-statistic title="音频引擎" :value="videoResult.audio_engine || '未启用'" />
              </el-col>
            </el-row>

            <!-- OCR文字 -->
            <el-collapse v-if="videoResult.ocr_text">
              <el-collapse-item title="OCR识别文字">
                <p class="whitespace-pre-wrap">{{ videoResult.ocr_text }}</p>
              </el-collapse-item>
            </el-collapse>

            <!-- 音频转写 -->
            <el-collapse v-if="videoResult.audio_text">
              <el-collapse-item title="音频转写">
                <p class="whitespace-pre-wrap">{{ videoResult.audio_text }}</p>
              </el-collapse-item>
            </el-collapse>

            <!-- 关键帧 -->
            <el-collapse v-if="videoResult.frames?.length">
              <el-collapse-item :title="`关键帧 (${videoResult.frames.length}帧)`">
                <el-row :gutter="10">
                  <el-col :span="8" v-for="frame in videoResult.frames.slice(0, 9)" :key="frame.frame_index">
                    <el-card shadow="hover" class="mb-2">
                      <div class="text-sm font-medium">帧 {{ frame.frame_index }} ({{ frame.timestamp?.toFixed(1) }}s)</div>
                      <el-tag :type="frameRiskType(frame.risk_level)" size="small" class="mt-1">
                        {{ frame.risk_level }}
                      </el-tag>
                      <p v-if="frame.ocr_text" class="text-xs text-gray-400 mt-1">{{ frame.ocr_text?.slice(0, 50) }}</p>
                    </el-card>
                  </el-col>
                </el-row>
              </el-collapse-item>
            </el-collapse>

            <div class="mt-2 text-gray-400 text-xs">
              分析耗时: {{ videoResult.analysis_time?.toFixed(1) }}s | 关键帧: {{ videoResult.keyframe_count }} | 方法: {{ videoResult.keyframe_method }}
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { api } from '../api'

const videoUrl = ref('')
const videoPath = ref('')
const maxFrames = ref(50)
const extractLoading = ref(false)
const analyzeLoading = ref(false)
const extractData = ref<any>(null)
const videoResult = ref<any>(null)

const riskTagType = computed(() => {
  const map: Record<string, string> = { safe: 'success', low: 'info', medium: 'warning', high: 'danger', critical: 'danger' }
  return map[videoResult.value?.overall_risk_level || 'safe'] || 'info'
})

function frameRiskType(level: string) {
  const map: Record<string, string> = { safe: 'success', low: 'info', medium: 'warning', high: 'danger', critical: 'danger' }
  return map[level] || 'info'
}

async function extractText() {
  if (!videoUrl.value) return
  extractLoading.value = true
  try {
    const resp = await api.extractVideo(videoUrl.value)
    extractData.value = resp.data
  } finally {
    extractLoading.value = false
  }
}

async function analyzeVideo(mode: string) {
  if (!videoUrl.value && !videoPath.value) return
  analyzeLoading.value = true
  try {
    const resp = await api.analyzeVideoV2(videoUrl.value, videoPath.value, mode, maxFrames.value)
    const taskId = resp.data.task_id
    // 轮询
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 3000))
      const frameResp = await api.getFrameResults(taskId)
      if (frameResp.data.status === 'completed') {
        videoResult.value = frameResp.data
        break
      }
      if (frameResp.data.status === 'failed') {
        videoResult.value = { error: frameResp.data.error }
        break
      }
    }
  } finally {
    analyzeLoading.value = false
  }
}
</script>
