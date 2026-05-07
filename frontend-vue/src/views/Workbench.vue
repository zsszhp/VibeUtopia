<template>
  <div class="workbench">
    <h2 class="text-2xl font-bold mb-4">风控工作台</h2>

    <el-row :gutter="20">
      <!-- 左侧: 输入 -->
      <el-col :span="12">
        <el-card header="文案输入">
          <el-input
            v-model="textInput"
            type="textarea"
            :rows="8"
            placeholder="输入至少10个字符的文案内容..."
          />
          <div class="mt-4 flex gap-2">
            <el-button type="primary" @click="submitAnalysis('quick')" :loading="loading">
              快速评估 (MVP+信号增强)
            </el-button>
            <el-button type="warning" @click="submitAnalysis('deep')" :loading="loading">
              深度评估 (仿真增强)
            </el-button>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧: 结果 -->
      <el-col :span="12">
        <el-card header="评估结果">
          <template v-if="!result">
            <el-empty description="提交文案开始评估" />
          </template>
          <template v-else>
            <!-- 风险等级 -->
            <div class="mb-4">
              <el-tag :type="riskTagType" size="large" effect="dark">
                综合风险: {{ result.overall_risk_level?.toUpperCase() }}
              </el-tag>
              <span class="ml-2 text-gray-500">
                MVP: {{ result.mvp_score }}分 → V2: {{ result.v2_score }}分
              </span>
            </div>

            <!-- 7维雷达图 -->
            <div ref="radarRef" style="height: 300px"></div>

            <!-- 风险句子 -->
            <div class="mt-4">
              <h4>风险句子标注</h4>
              <div v-for="(item, idx) in result.risk_items" :key="idx" class="mb-2">
                <el-tag type="danger" size="small">{{ item.dimension }}</el-tag>
                <span class="ml-2">{{ item.sentence }}</span>
              </div>
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- V2增强结果 -->
    <el-row :gutter="20" class="mt-4" v-if="v2Result">
      <el-col :span="8">
        <el-card header="热点关联">
          <div v-for="(match, idx) in v2Result.signal_matches" :key="idx" class="mb-2">
            <el-tag size="small">{{ match.signal_title }}</el-tag>
            <span class="ml-1 text-gray-400">相关度: {{ match.relevance?.toFixed(2) }}</span>
          </div>
          <el-empty v-if="!v2Result.signal_matches?.length" description="无热点关联" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card header="实体风险链">
          <div v-for="(chain, idx) in v2Result.entity_risk_chains" :key="idx" class="mb-2">
            <el-tag type="warning" size="small">{{ chain.entity }}</el-tag>
            <span class="ml-1">{{ chain.risk_description }}</span>
          </div>
          <el-empty v-if="!v2Result.entity_risk_chains?.length" description="无实体风险链" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card header="仿真平台反应">
          <div v-if="v2Result.simulation_summary">
            <div v-for="(platform, name) in v2Result.simulation_summary.platforms" :key="name" class="mb-1">
              <span class="font-medium">{{ name }}:</span>
              正面{{ platform.positive?.toFixed(0) }}%
              负面{{ platform.negative?.toFixed(0) }}%
            </div>
          </div>
          <el-empty v-else description="未运行仿真" />
          <div class="mt-2 text-gray-400 text-sm">
            可信度: {{ v2Result.confidence?.toFixed(2) }}
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { useAnalysisStore } from '../stores'
import * as echarts from 'echarts'

const store = useAnalysisStore()
const textInput = ref('')
const loading = ref(false)
const result = ref<any>(null)
const v2Result = ref<any>(null)
const radarRef = ref<HTMLElement>()

const riskTagType = computed(() => {
  const level = result.value?.overall_risk_level || 'safe'
  const map: Record<string, string> = { safe: 'success', low: 'info', medium: 'warning', high: 'danger', critical: 'danger' }
  return map[level] || 'info'
})

async function submitAnalysis(mode: 'quick' | 'deep') {
  if (!textInput.value || textInput.value.trim().length < 10) {
    return
  }
  loading.value = true
  try {
    const data = await store.submitText(textInput.value, mode)
    // 轮询等待结果
    pollResult(data.task_id)
  } finally {
    loading.value = false
  }
}

async function pollResult(taskId: string) {
  const maxAttempts = 60
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 3000))
    const data = await store.fetchResult(taskId)
    if (data?.status === 'completed') {
      result.value = data.mvp_result
      v2Result.value = data.v2_result
      await nextTick()
      renderRadar(data.mvp_result?.dimensions)
      break
    }
    if (data?.status === 'failed') break
  }
}

function renderRadar(dimensions: Record<string, number>) {
  if (!radarRef.value || !dimensions) return
  const chart = echarts.init(radarRef.value)
  const dimNames = ['政治敏感', '法律合规', '民族宗教', '性别议题', '道德伦理', '群体冒犯', '时事踩雷']
  const dimKeys = ['political', 'legal', 'ethnic', 'gender', 'moral', 'group', 'current']
  chart.setOption({
    radar: { indicator: dimNames.map(name => ({ name, max: 100 })) },
    series: [{ type: 'radar', data: [{ value: dimKeys.map(k => dimensions[k] || 0), name: '风险评分' }] }],
  })
}
</script>
