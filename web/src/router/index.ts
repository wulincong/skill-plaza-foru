import { createRouter, createWebHashHistory } from 'vue-router'
import HomePage from '../pages/HomePage.vue'
import SkillsPage from '../pages/SkillsPage.vue'
import ExperiencePage from '../pages/ExperiencePage.vue'
import UsePage from '../pages/UsePage.vue'
import RunListPage from '../pages/RunListPage.vue'
import RunDetailPage from '../pages/RunDetailPage.vue'
import DetailPage from '../pages/DetailPage.vue'
import GuidePage from '../pages/GuidePage.vue'
import MissingPage from '../pages/MissingPage.vue'
import { bySlug } from '../data/skills'
import { configOf } from '../data/useTaskConfigs'

/* 兼容旧地址：/catalog → /skills */
const routes = [
  { path: '/', name: 'home', component: HomePage, meta: { title: '智能体搭子', nav: '' } },
  { path: '/skills', name: 'skills', component: SkillsPage, meta: { title: '智能体广场 · 智能体搭子', nav: 'skills' } },
  { path: '/catalog', redirect: '/skills' },
  { path: '/skill/:slug', name: 'detail', component: DetailPage, meta: { nav: 'skills' } },
  { path: '/experience', name: 'experience', component: ExperiencePage, meta: { title: '在线对话 · 智能体搭子', nav: 'experience' } },
  { path: '/use/:slug?', name: 'use', component: UsePage, meta: { nav: 'skills' } },
  { path: '/runs', name: 'runs', component: RunListPage, meta: { title: '运行记录 · 智能体搭子', nav: 'runs' } },
  { path: '/runs/:runId', name: 'runDetail', component: RunDetailPage, meta: { title: '运行详情 · 智能体搭子', nav: 'runs' } },
  { path: '/docs/:slug?/:topic?', name: 'skillDocs', component: () => import('../pages/SkillDocsPage.vue'), meta: { nav: 'guide' } },
  { path: '/guide', name: 'guide', component: GuidePage, meta: { title: '使用指南 · 智能体搭子', nav: 'guide' } },
  { path: '/:pathMatch(.*)*', name: 'missing', component: MissingPage, meta: { title: '没有这个地址 · 智能体搭子', nav: 'skills' } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

/* 已注册但没有任务表单的技能直接进入对话，避免回落到其他技能的表单。 */
router.beforeEach(to => {
  const slug = typeof to.params.slug === 'string' ? to.params.slug : ''
  if (to.name === 'use' && bySlug.has(slug) && !configOf(slug)) {
    return { name: 'experience', query: { ...to.query, skill: slug } }
  }
})

router.afterEach(to => {
  if (to.name === 'detail') {
    const slug = typeof to.params.slug === 'string' ? to.params.slug : ''
    const skill = bySlug.get(slug)
    document.title = (skill ? skill.name + ' · ' : '没有这个 SKILL · ') + '智能体搭子'
  } else if (to.name === 'use') {
    const slug = typeof to.params.slug === 'string' ? to.params.slug : ''
    const skill = bySlug.get(slug)
    document.title = (skill ? '任务配置 · ' + skill.name : '任务配置') + ' · 智能体搭子'
  } else if (to.meta.title) {
    document.title = to.meta.title as string
  }
})

export default router
