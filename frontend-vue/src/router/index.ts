import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/workbench',
  },
  {
    path: '/workbench',
    name: 'Workbench',
    component: () => import('../views/Workbench.vue'),
    meta: { title: '风控工作台', icon: 'Monitor' },
  },
  {
    path: '/video-review',
    name: 'VideoReview',
    component: () => import('../views/VideoReview.vue'),
    meta: { title: '视频审核', icon: 'Film' },
  },
  {
    path: '/signals',
    name: 'Signals',
    component: () => import('../views/Signals.vue'),
    meta: { title: '信号监控', icon: 'Connection' },
  },
  {
    path: '/simulation',
    name: 'Simulation',
    component: () => import('../views/Simulation.vue'),
    meta: { title: '仿真大屏', icon: 'DataLine' },
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('../views/Reports.vue'),
    meta: { title: '历史报告', icon: 'Document' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/Settings.vue'),
    meta: { title: '系统设置', icon: 'Setting' },
  },
  {
    path: '/blogger',
    name: 'Blogger',
    component: () => import('../views/Blogger.vue'),
    meta: { title: '博主服务', icon: 'User' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
