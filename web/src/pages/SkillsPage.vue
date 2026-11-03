<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AUDIENCES, CATEGORIES, type Skill } from '../data/skills'
import SkillCard from '../components/SkillCard.vue'

import { publishedSkills as entries, catalogUnavailable } from '../composables/catalog'

const route = useRoute()
const router = useRouter()

const q = ref(typeof route.query.q === 'string' ? route.query.q : '')
const role = ref(typeof route.query.role === 'string' ? route.query.role : 'all')
const category = ref(typeof route.query.category === 'string' ? route.query.category : 'all')

const searchInput = ref<HTMLInputElement | null>(null)
let hashTimer: ReturnType<typeof setTimeout> | undefined

/* 从 URL 进入（含返回键）时同步本地状态 */
watch(() => route.fullPath, () => {
  if (route.name !== 'skills') return
  const nextQ = typeof route.query.q === 'string' ? route.query.q : ''
  const nextRole = typeof route.query.role === 'string' ? route.query.role : 'all'
  const nextCategory = typeof route.query.category === 'string' ? route.query.category : 'all'
  if (nextQ !== q.value) q.value = nextQ
  role.value = nextRole
  category.value = nextCategory
})

function matches(skill: Skill, except: 'q' | 'role' | 'category' | null, r: string, c: string, needle: string) {
  if (except !== 'q' && needle) {
    const hay = [skill.name, skill.identifier, skill.summary, ...skill.tags].join(' ').toLowerCase()
    if (!hay.includes(needle)) return false
  }
  if (except !== 'role' && r !== 'all' && !skill.audiences.includes(r)) return false
  if (except !== 'category' && c !== 'all' && skill.categoryId !== c) return false
  return true
}

const needle = computed(() => q.value.trim().toLowerCase())
const isFiltered = computed(() => Boolean(q.value.trim()) || role.value !== 'all' || category.value !== 'all')

const visible = computed(() =>
  entries.value.filter(s => matches(s, null, role.value, category.value, needle.value)),
)

const roleItems = computed(() => [{ id: 'all', name: '全部' }, ...AUDIENCES].map(item => ({
  ...item,
  count: entries.value.filter(s => matches(s, 'role', role.value, category.value, needle.value) && (item.id === 'all' || s.audiences.includes(item.id))).length,
})))

const catItems = computed(() => [{ id: 'all', name: '全部' }, ...CATEGORIES].map(item => ({
  ...item,
  count: entries.value.filter(s => matches(s, 'category', role.value, category.value, needle.value) && (item.id === 'all' || s.categoryId === item.id)).length,
})))

function commit() {
  const query: Record<string, string> = {}
  if (q.value.trim()) query.q = q.value
  if (role.value !== 'all') query.role = role.value
  if (category.value !== 'all') query.category = category.value
  router.replace({ path: '/skills', query })
}

function setRole(id: string) { role.value = id; commit() }
function setCategory(id: string) { category.value = id; commit() }

function onSearchInput() {
  clearTimeout(hashTimer)
  hashTimer = setTimeout(commit, 200)
}

function clearFilters(focusSearch: boolean) {
  q.value = ''
  role.value = 'all'
  category.value = 'all'
  commit()
  if (focusSearch) searchInput.value?.focus()
}
</script>

<template>
  <section class="page page-skills" id="page-skills">
    <div class="wrap">
      <div class="section-head" v-reveal>
        <h2>发现值得使用的 SKILL</h2>
        <p>按角色或业务分类筛选，选择智能体在线运行，或用详情页的标识调用 API。</p>
      </div>

      <p v-if="catalogUnavailable" role="alert">技能目录暂时无法连接，请刷新重试。</p>
      <div class="filters" v-reveal="70">
        <div class="facet" id="facet-role">
          <span class="facet-label" id="lbl-role">适用角色</span>
          <div class="chips" role="group" aria-labelledby="lbl-role">
            <button
              v-for="item in roleItems"
              :key="item.id"
              type="button"
              class="chip"
              :class="{ 'is-on': item.id === role, 'is-empty': item.count === 0 && item.id !== role }"
              :aria-pressed="item.id === role"
              @click="setRole(item.id)"
            >{{ item.name }}<span class="n">{{ item.count }}</span></button>
          </div>
        </div>
        <div class="facet" id="facet-category">
          <span class="facet-label" id="lbl-category">业务分类</span>
          <div class="chips" role="group" aria-labelledby="lbl-category">
            <button
              v-for="item in catItems"
              :key="item.id"
              type="button"
              class="chip"
              :class="{ 'is-on': item.id === category, 'is-empty': item.count === 0 && item.id !== category }"
              :aria-pressed="item.id === category"
              @click="setCategory(item.id)"
            >{{ item.name }}<span class="n">{{ item.count }}</span></button>
          </div>
        </div>
        <div class="facet" id="facet-search">
          <span class="facet-label" id="lbl-search">搜索</span>
          <div class="search" id="search-box">
            <svg class="ic" width="17" height="17" aria-hidden="true"><use href="#i-search" /></svg>
            <input ref="searchInput" v-model="q" @input="onSearchInput" type="search" autocomplete="off" aria-labelledby="lbl-search" placeholder="名称、用途或关键词">
          </div>
        </div>
      </div>

      <div class="list-status" role="status" aria-live="polite" v-reveal="140">
        <span id="list-status">
          <template v-if="isFiltered">筛选出 <strong>{{ visible.length }}</strong> 个 · 全部 <strong>{{ entries.length }}</strong> 个</template>
          <template v-else>共 <strong>{{ entries.length }}</strong> 个 SKILL</template>
        </span>
        <button type="button" class="text-btn" :hidden="!isFiltered" @click="clearFilters(true)">清除筛选</button>
      </div>

      <div class="grid" id="skill-grid" :hidden="visible.length === 0">
        <SkillCard
          v-for="(skill, i) in visible"
          :key="skill.slug"
          v-reveal="Math.min(i, 8) * 40"
          :skill="skill"
        />
      </div>
    </div>
  </section>
</template>
