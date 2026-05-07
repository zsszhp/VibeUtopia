<template>
  <el-container class="h-screen">
    <el-aside width="220px" class="bg-gray-900 text-white">
      <div class="p-4 text-xl font-bold text-center border-b border-gray-700">
        VibeUtopia
      </div>
      <el-menu
        :default-active="currentRoute"
        class="bg-gray-900 border-none"
        text-color="#ccc"
        active-text-color="#409eff"
        @select="handleMenuSelect"
      >
        <el-menu-item index="/workbench">
          <el-icon><Monitor /></el-icon>
          <span>风控工作台</span>
        </el-menu-item>
        <el-menu-item index="/video-review">
          <el-icon><Film /></el-icon>
          <span>视频审核</span>
        </el-menu-item>
        <el-menu-item index="/signals">
          <el-icon><Connection /></el-icon>
          <span>信号监控</span>
        </el-menu-item>
        <el-menu-item index="/simulation">
          <el-icon><DataLine /></el-icon>
          <span>仿真大屏</span>
        </el-menu-item>
        <el-menu-item index="/reports">
          <el-icon><Document /></el-icon>
          <span>历史报告</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
        <el-menu-item index="/blogger">
          <el-icon><User /></el-icon>
          <span>博主服务</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="bg-gray-50 p-6 overflow-auto">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Monitor, Film, Connection, DataLine, Document, Setting, User } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const currentRoute = computed(() => route.path)

function handleMenuSelect(index: string) {
  router.push(index)
}
</script>
