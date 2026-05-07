<template>
  <div class="blogger">
    <h2 class="text-2xl font-bold mb-4">博主服务</h2>

    <el-tabs v-model="activeTab">
      <!-- 画像生成 -->
      <el-tab-pane label="博主画像" name="profile">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-card header="博主信息">
              <el-form label-width="80px">
                <el-form-item label="博主ID">
                  <el-input v-model="bloggerId" placeholder="输入博主唯一标识" />
                </el-form-item>
                <el-form-item label="名称">
                  <el-input v-model="bloggerName" placeholder="博主名称" />
                </el-form-item>
                <el-form-item label="平台">
                  <el-select v-model="bloggerPlatform">
                    <el-option label="抖音" value="douyin" />
                    <el-option label="B站" value="bilibili" />
                    <el-option label="小红书" value="xiaohongshu" />
                    <el-option label="微博" value="weibo" />
                    <el-option label="微信公众号" value="wechat" />
                  </el-select>
                </el-form-item>
                <el-form-item label="历史内容">
                  <el-input v-model="contents" type="textarea" :rows="6" placeholder="每行一条历史内容..." />
                </el-form-item>
                <el-button type="primary" @click="generateProfile" :loading="loading">生成画像</el-button>
              </el-form>
            </el-card>
          </el-col>

          <el-col :span="16">
            <el-card header="5维风格画像" v-if="profile">
              <div class="mb-4">
                <el-tag type="info" size="large">{{ profile.overall_style }}</el-tag>
                <span class="ml-2 text-gray-400">置信度: {{ (profile.confidence * 100).toFixed(0) }}%</span>
              </div>

              <!-- 风格标签 -->
              <div class="mb-4">
                <el-tag v-for="tag in profile.style_tags" :key="tag" class="mr-1" size="small">{{ tag }}</el-tag>
              </div>

              <el-row :gutter="10">
                <!-- 词汇特征 -->
                <el-col :span="8">
                  <el-card shadow="hover">
                    <template #header><strong>词汇特征</strong></template>
                    <div>平均句长: {{ profile.vocabulary?.avg_sentence_length }}字</div>
                    <div>专业词汇比: {{ (profile.vocabulary?.professional_ratio * 100).toFixed(0) }}%</div>
                    <div>可读性: {{ profile.vocabulary?.readability_score }}/100</div>
                    <div v-if="profile.vocabulary?.top_words?.length" class="mt-2">
                      <strong>高频词:</strong>
                      <el-tag v-for="w in profile.vocabulary.top_words.slice(0, 5)" :key="w.word" size="small" class="mr-1">
                        {{ w.word }}({{ w.count }})
                      </el-tag>
                    </div>
                  </el-card>
                </el-col>

                <!-- 表达风格 -->
                <el-col :span="8">
                  <el-card shadow="hover">
                    <template #header><strong>表达风格</strong></template>
                    <div>语气: {{ profile.expression?.tone }}</div>
                    <div>Emoji频率: {{ profile.expression?.emoji_usage }}</div>
                    <div>感叹句比: {{ (profile.expression?.exclamation_ratio * 100).toFixed(0) }}%</div>
                    <div v-if="profile.expression?.rhetoric_devices?.length" class="mt-2">
                      <strong>修辞:</strong> {{ profile.expression.rhetoric_devices.join('、') }}
                    </div>
                  </el-card>
                </el-col>

                <!-- 主题偏好 -->
                <el-col :span="8">
                  <el-card shadow="hover">
                    <template #header><strong>主题偏好</strong></template>
                    <div v-for="t in profile.topics?.primary_topics?.slice(0, 3)" :key="t.topic" class="mb-1">
                      <el-progress :percentage="t.weight * 100" :stroke-width="8">
                        <span>{{ t.topic }}</span>
                      </el-progress>
                    </div>
                    <div class="mt-1">多样性: {{ (profile.topics?.content_diversity * 100).toFixed(0) }}%</div>
                    <div>热点敏感度: {{ (profile.topics?.trending_sensitivity * 100).toFixed(0) }}%</div>
                  </el-card>
                </el-col>
              </el-row>

              <el-row :gutter="10" class="mt-2">
                <!-- 受众画像 -->
                <el-col :span="12">
                  <el-card shadow="hover">
                    <template #header><strong>受众画像</strong></template>
                    <div>目标年龄: {{ profile.audience?.target_age }}</div>
                    <div>目标性别: {{ profile.audience?.target_gender }}</div>
                    <div>互动风格: {{ profile.audience?.engagement_style }}</div>
                    <div>粉丝忠诚度: {{ (profile.audience?.fan_loyalty * 100).toFixed(0) }}%</div>
                  </el-card>
                </el-col>

                <!-- 风险偏好 -->
                <el-col :span="12">
                  <el-card shadow="hover">
                    <template #header><strong>风险偏好</strong></template>
                    <div>
                      风险容忍度:
                      <el-tag :type="riskToleranceType" size="small">{{ profile.risk?.risk_tolerance }}</el-tag>
                    </div>
                    <div>历史风险次数: {{ profile.risk?.historical_risk_count }}</div>
                    <div>险些踩雷: {{ profile.risk?.near_miss_count }}次</div>
                    <div v-if="profile.risk?.sensitive_topics?.length">
                      敏感话题: {{ profile.risk.sensitive_topics.join('、') }}
                    </div>
                  </el-card>
                </el-col>
              </el-row>
            </el-card>
            <el-empty v-else description="输入博主信息生成画像" />
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 选题推荐 -->
      <el-tab-pane label="选题推荐" name="recommend">
        <el-card header="选题推荐">
          <el-form :inline="true">
            <el-form-item label="博主ID">
              <el-input v-model="recBloggerId" placeholder="已生成画像的博主ID" />
            </el-form-item>
            <el-button type="primary" @click="getRecommendations" :loading="recLoading">获取推荐</el-button>
          </el-form>

          <el-table :data="recommendations" stripe class="mt-4" v-if="recommendations.length">
            <el-table-column prop="topic" label="选题" min-width="200" />
            <el-table-column prop="angle" label="切入点" width="200" />
            <el-table-column prop="trend_score" label="热度" width="80">
              <template #default="{ row }">{{ (row.trend_score * 100).toFixed(0) }}%</template>
            </el-table-column>
            <el-table-column prop="style_match" label="风格匹配" width="80">
              <template #default="{ row }">{{ (row.style_match * 100).toFixed(0) }}%</template>
            </el-table-column>
            <el-table-column prop="risk_level" label="风险" width="80">
              <template #default="{ row }">
                <el-tag :type="row.risk_level === 'safe' ? 'success' : row.risk_level === 'low' ? 'info' : 'danger'" size="small">
                  {{ row.risk_level }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="80" sortable />
            <el-table-column prop="risk_note" label="风险提示" width="200" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 竞品对标 -->
      <el-tab-pane label="竞品对标" name="competitor">
        <el-card header="竞品对标分析">
          <el-form :inline="true">
            <el-form-item label="博主ID">
              <el-input v-model="compBloggerId" placeholder="已生成画像的博主ID" />
            </el-form-item>
            <el-form-item label="竞品ID">
              <el-input v-model="compCompetitorId" placeholder="竞品博主ID" />
            </el-form-item>
            <el-button type="primary" @click="compareCompetitors" :loading="compLoading">开始对比</el-button>
          </el-form>

          <div v-if="compareResult" class="mt-4">
            <el-alert :title="compareResult.overall_assessment" type="info" :closable="false" class="mb-4" />

            <h4>风格对比</h4>
            <el-table :data="compareResult.style_comparisons" stripe class="mb-4">
              <el-table-column prop="dimension" label="维度" width="120" />
              <el-table-column prop="blogger_value" label="博主" width="120" />
              <el-table-column prop="competitor_value" label="竞品" width="120" />
              <el-table-column prop="gap" label="差异" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.gap === 'same' ? 'success' : row.gap === 'different' ? 'warning' : 'info'" size="small">
                    {{ row.gap }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>

            <h4>差异化建议</h4>
            <el-table :data="compareResult.suggestions" stripe>
              <el-table-column prop="strategy" label="策略" width="150" />
              <el-table-column prop="description" label="描述" min-width="300" />
              <el-table-column prop="priority" label="优先级" width="80" sortable />
              <el-table-column prop="effort" label="难度" width="80" />
              <el-table-column prop="expected_impact" label="预期效果" width="150" />
            </el-table>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const activeTab = ref('profile')

// 画像
const bloggerId = ref('')
const bloggerName = ref('')
const bloggerPlatform = ref('douyin')
const contents = ref('')
const loading = ref(false)
const profile = ref<any>(null)

const riskToleranceType = computed(() => {
  const t = profile.value?.risk?.risk_tolerance
  if (t === 'aggressive') return 'danger'
  if (t === 'moderate') return 'warning'
  return 'success'
})

async function generateProfile() {
  if (!bloggerId.value) return
  loading.value = true
  try {
    const contentList = contents.value.split('\n').filter(s => s.trim())
    const axios = (await import('axios')).default
    const resp = await axios.post('/api/blogger/analyze', {
      blogger_id: bloggerId.value,
      name: bloggerName.value,
      platform: bloggerPlatform.value,
      contents: contentList,
    })
    profile.value = resp.data
  } catch (e: any) {
    console.error('画像生成失败', e)
  } finally {
    loading.value = false
  }
}

// 选题推荐
const recBloggerId = ref('')
const recLoading = ref(false)
const recommendations = ref<any[]>([])

async function getRecommendations() {
  if (!recBloggerId.value) return
  recLoading.value = true
  try {
    const axios = (await import('axios')).default
    const resp = await axios.post('/api/blogger/recommend', {
      blogger_id: recBloggerId.value,
    })
    recommendations.value = resp.data.recommendations || []
  } catch (e) {
    console.error('推荐获取失败', e)
  } finally {
    recLoading.value = false
  }
}

// 竞品对标
const compBloggerId = ref('')
const compCompetitorId = ref('')
const compLoading = ref(false)
const compareResult = ref<any>(null)

async function compareCompetitors() {
  if (!compBloggerId.value || !compCompetitorId.value) return
  compLoading.value = true
  try {
    const axios = (await import('axios')).default
    const resp = await axios.post('/api/competitor/compare', {
      blogger_id: compBloggerId.value,
      competitor_id: compCompetitorId.value,
    })
    compareResult.value = resp.data
  } catch (e) {
    console.error('竞品对比失败', e)
  } finally {
    compLoading.value = false
  }
}
</script>
