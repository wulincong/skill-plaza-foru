<script setup lang="ts">
import { computed, ref, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import catalog from 'virtual:skill-docs'
import Icon from '../components/Icon.vue'
import { bySlug } from '../data/skills'

const route = useRoute()
const query = ref('')
const skill = computed(() => catalog.find(s => s.id === route.params.slug))
const page = computed(() => skill.value?.pages.find(p => p.key === (route.params.topic || 'index')))
const matches = computed(() => {
  const term = query.value.trim().toLowerCase()
  return catalog.filter(s => [s.id, s.summary, ...s.pages.map(p => p.title)].join(' ').toLowerCase().includes(term))
})
function docPath(id: string, key = 'index') {
  return key === 'index' ? `/docs/${id}` : `/docs/${id}/${key}`
}
watchEffect(() => {
  if (route.name !== 'skillDocs') return
  document.title = `${route.params.slug ? page.value?.title ?? '未找到文档' : '技能文档中心'} · 智能体搭子`
})
</script>

<template>
  <section class="page">
    <div class="wrap wrap-read">
      <template v-if="!route.params.slug">
        <header class="guide-head">
          <h1>技能文档中心</h1>
          <p>按任务找到技能，查看需要准备的材料、可以直接尝试的提问，以及如何使用结果。</p>
          <div class="detail-actions">
            <RouterLink class="btn btn-quiet" to="/guide">在线运行与 API 接入指南<Icon name="arrow" :size="15" /></RouterLink>
          </div>
        </header>
        <div class="block">
          <label class="doc-label" for="doc-search">查找技能文档</label>
          <input id="doc-search" v-model="query" type="search" placeholder="输入技能名称、标识或任务关键词" />
          <p class="doc-count" role="status">共 {{ matches.length }} 个技能</p>
          <ul class="doc-index">
            <li v-for="item in matches" :key="item.id">
              <RouterLink :to="docPath(item.id)">
                <span class="doc-title">{{ item.pages[0].title }} <Icon name="chev" :size="14" /></span>
                <code class="card-id">{{ item.id }}</code>
                <span class="doc-summary">{{ item.summary }}</span>
              </RouterLink>
            </li>
          </ul>
          <p v-if="!matches.length" class="block-note">没有匹配的文档。试试「简历」「课堂」或技能的英文标识。</p>
        </div>
      </template>

      <template v-else-if="skill && page">
        <nav class="crumb" aria-label="面包屑">
          <RouterLink to="/docs">技能文档中心</RouterLink><Icon name="chev" :size="14" />
          <RouterLink v-if="page.key !== 'index'" :to="docPath(skill.id)">{{ skill.pages[0].title }}</RouterLink>
          <Icon v-if="page.key !== 'index'" name="chev" :size="14" />
          <span class="cur">{{ page.title }}</span>
        </nav>
        <header class="guide-head">
          <p class="card-id">{{ skill.id }}</p>
          <h1>{{ page.title }}</h1>
        </header>
        <nav v-if="skill.pages.length > 1" class="topics" aria-label="本技能文档">
          <RouterLink v-for="p in skill.pages" :key="p.key" :to="docPath(skill.id, p.key)"
            :aria-current="p.key === page.key ? 'page' : undefined">{{ p.key === 'index' ? '使用指南' : p.title }}</RouterLink>
        </nav>
        <article class="md-body doc-body" v-html="page.html"></article>
        <div class="detail-actions">
          <RouterLink v-if="bySlug.has(skill.id)" class="btn btn-primary" :to="{ name: 'experience', query: { skill: skill.id } }">用这个技能开始对话<Icon name="arrow" :size="15" /></RouterLink>
          <RouterLink v-else class="btn btn-primary" to="/guide">通过 API 使用这个技能</RouterLink>
          <RouterLink class="btn btn-quiet" to="/docs">全部技能文档</RouterLink>
        </div>
      </template>

      <div v-else class="empty">
        <h1>未找到文档</h1>
        <p>这个技能或章节的地址可能已经变更。</p>
        <RouterLink class="btn btn-primary" to="/docs">回到技能文档中心</RouterLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.doc-label, .doc-title { display: block; font-weight: 600; color: var(--ink-strong); }
#doc-search { width: min(100%, 30rem); margin: .6rem 0; padding: .7rem 1rem; border: 1px solid var(--line-edge); border-radius: var(--r-ctl); background: var(--surface-card); color: var(--ink-strong); font: inherit; }
.doc-count, .doc-summary { color: var(--ink-body); font-size: var(--fs-md); }
.doc-index { list-style: none; padding: 0; margin-top: 1rem; }
.doc-index li { border-top: 1px solid var(--line-hair); }
.doc-index a { display: grid; gap: .35rem; padding: 1rem .2rem; }
.doc-index a:hover .doc-title, .topics a:hover { color: var(--brand); }
.doc-title { font-size: var(--fs-lg); }
.doc-title svg { display: inline-block; vertical-align: middle; }
.topics { display: flex; flex-wrap: wrap; gap: .5rem 1rem; margin-top: 1rem; }
.topics a { padding: .3rem 0; }
.topics a[aria-current=page] { color: var(--brand); border-bottom: 2px solid currentColor; }
.doc-body { margin: 1.5rem 0 2rem; font-size: 1rem; color: var(--ink-body); }
.doc-body :deep(ul) { list-style: disc; }
.doc-body :deep(ol) { list-style: decimal; }
</style>
