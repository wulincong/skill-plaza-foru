import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router'
import HomePage from '../pages/HomePage.vue'
import SkillsPage from '../pages/SkillsPage.vue'
import ExperiencePage from '../pages/ExperiencePage.vue'
import UsePage from '../pages/UsePage.vue'
import { publishedSkills, refreshCatalog } from '../composables/catalog'
import { adminRoutes } from '../admin/routes'
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
  { path: '/use/:slug?', name: 'use', component: UsePage, props: true, meta: { nav: 'skills' } },
  { path: '/runs/:runId?', component: MissingPage, beforeEnter: (to: import('vue-router').RouteLocationNormalized) => {
    location.replace('/admin/runs' + (to.params.runId ? '/' + encodeURIComponent(String(to.params.runId)) : ''))
    return false
  } },
  { path: '/docs/:slug?/:topic?', name: 'skillDocs', component: () => import('../pages/SkillDocsPage.vue'), meta: { nav: 'guide' } },
  { path: '/guide', name: 'guide', component: GuidePage, meta: { title: '使用指南 · 智能体搭子', nav: 'guide' } },
  { path: '/:pathMatch(.*)*', name: 'missing', component: MissingPage, meta: { title: '没有这个地址 · 智能体搭子', nav: 'skills' } },
]

const adminPath = /^\/admin(?:\/|$)/.test(location.pathname)
const router = createRouter({
  history: adminPath ? createWebHistory('/admin') : createWebHashHistory(),
  routes: adminPath ? adminRoutes : routes,
  scrollBehavior: () => ({ top: 0 }),
})

/* 已注册但没有任务表单的技能直接进入对话，避免回落到其他技能的表单。 */
router.beforeEach(async (to, from) => {
  if (adminPath) return
  if (['home','skills','use','detail','experience'].includes(String(to.name)) && (to.name !== from.name || to.path !== from.path || to.query.skill !== from.query.skill)) {
    await refreshCatalog()
    const requested = to.name === 'experience' ? to.query.skill : ['use','detail'].includes(String(to.name)) ? to.params.slug : ''
    if (requested && !publishedSkills.value.some(s => s.slug === requested)) return '/unavailable'
    if (to.name === 'use' && !requested) {
      const first = publishedSkills.value[0]
      return first ? { name: 'use', params: { slug: first.slug } } : '/skills'
    }
  }
  const slug = typeof to.params.slug === 'string' ? to.params.slug : ''
  if (to.name === 'use' && slug && !configOf(slug)) {
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
