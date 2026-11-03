import type { RouteRecordRaw } from 'vue-router'

export const adminRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('./AdminShell.vue'),
    meta: { admin: true },
    children: [
      {
        path: '',
        name: 'overview',
        component: () => import('./Overview.vue'),
        meta: { title: '工作台 · 管理后台' },
      },
      {
        path: 'skills',
        name: 'publishing',
        component: () => import('./Publishing.vue'),
        meta: { title: '技能管理 · 管理后台' },
      },
      {
        path: 'models',
        name: 'models',
        component: () => import('./Models.vue'),
        meta: { title: '模型与密钥 · 管理后台' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('./Settings.vue'),
        meta: { title: '运行设置 · 管理后台' },
      },
      {
        path: 'account',
        name: 'account',
        component: () => import('./Account.vue'),
        meta: { title: '账号设置 · 管理后台' },
      },
      {
        path: 'runs',
        name: 'runs',
        component: () => import('../pages/RunListPage.vue'),
        meta: { title: '运行记录 · 管理后台' },
      },
      {
        path: 'runs/:runId',
        name: 'runDetail',
        component: () => import('../pages/RunDetailPage.vue'),
        meta: { title: '运行详情 · 管理后台' },
      },
      { path: ':pathMatch(.*)*', redirect: '/' },
    ],
  },
]
