<script setup lang="ts">
import { computed, onMounted, ref, watch, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import catalog, { guide } from 'virtual:skill-docs'
import Icon from '../components/Icon.vue'
import Codebox from '../components/Codebox.vue'

const route = useRoute()
const query = ref('')
const menuOpen = ref(false)
const menuButton = ref<HTMLButtonElement>()
const outlineOpen = ref(false)
const outlineButton = ref<HTMLButtonElement>()
const skill = computed(() => catalog.find(s => s.id === route.params.slug))
const guidePath = '/docs/guide'
const articles = [
  { path: guidePath, page: guide },
  ...catalog.flatMap(s => s.pages.map(p => ({ path: docPath(s.id, p.key), page: p }))),
]
const currentIndex = computed(() => articles.findIndex(a =>
  a.path === docPath(String(route.params.slug), String(route.params.topic || 'index')),
))
const page = computed(() => articles[currentIndex.value]?.page)
const nextArticle = computed(() => {
  if (!route.params.slug) return articles[0]
  if (page.value) return articles[currentIndex.value + 1]
})
const guideMatches = computed(() => [guide.title, ...guide.outline.map(h => h.title)].join(' ')
  .toLowerCase().includes(query.value.trim().toLowerCase()))
const matches = computed(() => {
  const term = query.value.trim().toLowerCase()
  return catalog.filter(s => [s.id, s.summary, ...s.pages.map(p => p.title)].join(' ').toLowerCase().includes(term))
})

function docPath(id: string, key = 'index') {
  return key === 'index' ? `/docs/${id}` : `/docs/${id}/${key}`
}

function closeMenu() {
  if (!menuOpen.value) return
  menuOpen.value = false
  menuButton.value?.focus({ preventScroll: true })
}
function closeOutline() {
  if (!outlineOpen.value) return
  outlineOpen.value = false
  outlineButton.value?.focus({ preventScroll: true })
}
watch(() => route.fullPath, () => {
  closeMenu()
  closeOutline()
})
watchEffect(() => {
  if (route.name !== 'skillDocs') return
  document.title = `${route.params.slug ? page.value?.title ?? '未找到文档' : '技能文档中心'} · 智能体搭子`
})
// A direct link may mount after the router's scroll hook during the page transition.
onMounted(() => {
  if (route.hash) document.getElementById(route.hash.slice(1))?.scrollIntoView()
})
</script>

<template>
  <section class="wrap docs-layout">
    <aside class="docs-sidebar" @keydown.esc="closeMenu">
      <button ref="menuButton" type="button" class="menu-toggle" :aria-expanded="menuOpen"
        aria-controls="doc-navigation" @click="menuOpen = !menuOpen">
        <Icon name="form" />文档目录<Icon name="chev-down" />
      </button>
      <nav id="doc-navigation" aria-label="文档目录" :class="{ open: menuOpen }">
        <h2 class="sidebar-title">文档目录</h2>
        <label class="search-box">
          <Icon name="search" /><span class="vh">搜索文档</span>
          <input id="doc-search" v-model="query" type="search" placeholder="搜索指南、技能或专题" />
        </label>
        <RouterLink class="nav-link" to="/docs" @click="closeMenu">文档首页</RouterLink>
        <RouterLink v-if="guideMatches" class="nav-link" :to="guidePath" @click="closeMenu">{{ guide.title }}</RouterLink>
        <h3 class="nav-label">技能指南</h3>
        <ul class="nav-tree">
          <li v-for="item in matches" :key="item.id">
            <RouterLink class="nav-link" :to="docPath(item.id)" @click="closeMenu">
              {{ item.pages[0].title }}
            </RouterLink>
            <ul v-if="item.pages.length > 1" class="nav-children">
              <li v-for="topic in item.pages.slice(1)" :key="topic.key">
                <RouterLink class="nav-link" :to="docPath(item.id, topic.key)" @click="closeMenu">{{ topic.title }}</RouterLink>
              </li>
            </ul>
          </li>
        </ul>
        <p v-if="!matches.length" class="empty-search" role="status">没有匹配的技能或专题。</p>
      </nav>
    </aside>

    <div class="docs-reader" :class="{ 'with-outline': page?.outline.length }">
      <template v-if="!route.params.slug">
        <header class="reader-head">
          <h1>技能文档中心</h1>
          <p>选择与你的任务相符的指南，准备所需材料，复制示例提示词，再用自己的要求开始对话。</p>
          <RouterLink v-if="guideMatches" class="guide-link" :to="guidePath">{{ guide.title }}<Icon name="arrow" :size="15" /></RouterLink>
        </header>
        <div class="index-heading"><h2>按技能浏览</h2><span role="status">{{ matches.length }} 个技能</span></div>
        <ul class="doc-index">
          <li v-for="item in matches" :key="item.id">
            <RouterLink :to="docPath(item.id)">
              <span class="card-id">{{ item.id }}</span>
              <strong>{{ item.pages[0].title }}<Icon name="chev" :size="14" /></strong>
              <span>{{ item.summary }}</span>
            </RouterLink>
          </li>
        </ul>
        <p v-if="!matches.length">没有匹配的指南。<button class="text-btn" @click="query = ''">清除搜索</button></p>
      </template>

      <template v-else-if="page">
        <nav class="crumb" aria-label="面包屑">
          <RouterLink to="/docs">文档中心</RouterLink><Icon name="chev" :size="14" />
          <template v-if="skill && page.key !== 'index'">
            <RouterLink :to="docPath(skill.id)">{{ skill.pages[0].title }}</RouterLink><Icon name="chev" :size="14" />
          </template>
          <span class="cur">{{ page.title }}</span>
        </nav>
        <header class="reader-head">
          <span v-if="skill" class="card-id">{{ skill.id }}</span>
          <h1>{{ page.title }}</h1>
        </header>
        <nav v-if="page.outline.length" class="page-outline" aria-label="本页章节" @keydown.esc="closeOutline">
          <h2 class="outline-title">本页章节</h2>
          <button ref="outlineButton" type="button" class="outline-toggle" :aria-expanded="outlineOpen"
            aria-controls="doc-sections" @click="outlineOpen = !outlineOpen">
            本页章节<Icon name="chev-down" :size="14" />
          </button>
          <ul id="doc-sections" class="nav-tree" :class="{ open: outlineOpen }">
            <li v-for="heading in page.outline" :key="heading.id">
              <RouterLink class="section-link" :to="{ path: route.path, hash: '#' + heading.id }"
                :aria-current-value="route.hash === '#' + heading.id ? 'location' : 'false'"
                @click="closeOutline">{{ heading.title }}</RouterLink>
            </li>
          </ul>
        </nav>
        <article :key="articles[currentIndex].path" class="doc-body">
          <template v-for="(block, i) in page.blocks" :key="i">
            <div v-if="block.kind === 'markdown'" class="md-body" v-html="block.html"></div>
            <Codebox v-else :class="block.kind === 'prompt' ? 'prompt-example' : 'command-example'"
              :label="block.kind === 'prompt' ? '提示词示例' : '终端命令'" :text="block.text"
              :message="block.kind === 'prompt' ? '提示词已复制' : '命令已复制'" />
          </template>
        </article>
      </template>

      <div v-else class="empty">
        <h1>未找到文档</h1>
        <p>这个技能或章节的地址可能已经变更。</p>
        <RouterLink class="btn btn-primary" to="/docs">回到技能文档中心</RouterLink>
      </div>
      <nav v-if="nextArticle" class="doc-next" aria-label="阅读导航">
        <RouterLink :to="nextArticle.path" rel="next">
          <span>下一页</span><strong>{{ nextArticle.page.title }}</strong><Icon name="arrow" />
        </RouterLink>
      </nav>
    </div>
  </section>
</template>

<style scoped>
.docs-layout { display: grid; grid-template-columns: 15rem minmax(0, 1fr); align-items: start; gap: clamp(2rem, 5vw, 5rem); padding-block: 2rem 4rem; }
.docs-sidebar { position: sticky; top: calc(var(--head-h) + 1rem); max-height: calc(100dvh - var(--head-h) - 2rem); overflow-y: auto; border-right: 1px solid var(--line-hair); padding-right: 1.25rem; }
.menu-toggle { display: none; }
.sidebar-title { font-size: 1rem; }
.search-box { display: flex; align-items: center; gap: .5rem; margin: .75rem 0 1rem; padding: .5rem .65rem; border: 1px solid var(--line-edge); border-radius: var(--r-ctl); background: var(--surface-card); }
.search-box:focus-within { outline: 2px solid var(--brand); outline-offset: 2px; }
.search-box input { width: 100%; min-width: 0; background: transparent; border: 0; color: var(--ink-strong); outline: 0; }
.nav-label { margin: 1rem 0 .4rem; padding-top: 1rem; border-top: 1px solid var(--line-hair); font-size: var(--fs-sm); }
.nav-tree, .nav-children, .doc-index { padding: 0; margin: 0; list-style: none; }
.nav-children { margin-left: .7rem; padding-left: .55rem; border-left: 1px solid var(--line-edge); }
.nav-link, .section-link { display: block; padding: .4rem .6rem; border-radius: var(--r-ctl); color: var(--ink-body); font-size: var(--fs-md); }
.nav-link:hover, .section-link:hover { background: var(--surface-sunken); color: var(--ink-strong); }
.nav-link[aria-current=page], .section-link[aria-current=location] { color: var(--sk-blue); background: var(--sk-blue-soft); font-weight: 600; }
.empty-search { margin: .6rem; font-size: var(--fs-sm); }
.docs-reader { width: 100%; max-width: 52rem; min-width: 0; }
.page-outline { margin-top: 1rem; border-bottom: 1px solid var(--line-hair); }
.outline-title { display: none; font-size: var(--fs-sm); }
.outline-toggle { display: flex; align-items: center; justify-content: space-between; width: 100%; padding: .7rem 0; color: var(--ink-strong); }
.outline-toggle[aria-expanded=true] svg { transform: rotate(180deg); }
#doc-sections:not(.open) { display: none; }
.section-link { overflow-wrap: anywhere; }
@media (min-width: 1024px) {
  .docs-reader.with-outline {
    display: grid;
    grid-template-columns: minmax(0, 1fr) clamp(10rem, 15vw, 12rem);
    grid-template-areas: "crumb outline" "title outline" "body outline" "next outline";
    column-gap: clamp(1.5rem, 3vw, 3rem);
    max-width: none;
  }
  .with-outline > .crumb { grid-area: crumb; }
  .with-outline > .reader-head { grid-area: title; }
  .with-outline > .doc-body { grid-area: body; min-width: 0; }
  .with-outline > .doc-next { grid-area: next; }
  .page-outline {
    grid-area: outline; align-self: start; position: sticky; top: calc(var(--head-h) + 1rem);
    max-height: calc(100dvh - var(--head-h) - 2rem); overflow-y: auto; margin: 0;
    border: 0; border-left: 1px solid var(--line-hair); padding-left: 1rem;
  }
  .outline-title { display: block; margin: 0 0 .5rem; }
  .outline-toggle { display: none; }
  #doc-sections:not(.open) { display: block; }
}
.reader-head { padding-bottom: 1.25rem; border-bottom: 1px solid var(--line-hair); }
.crumb { margin-bottom: 1.25rem; }
.reader-head h1 { font-size: clamp(1.8rem, 3vw, 2.4rem); line-height: 1.25; }
.reader-head p { margin-top: .75rem; max-width: 42rem; font-size: 1rem; line-height: 1.75; }
.guide-link { display: inline-flex; align-items: center; gap: .5rem; margin-top: 1rem; text-decoration: underline; text-underline-offset: .2em; }
.index-heading { display: flex; align-items: baseline; gap: .7rem; margin: 1.75rem 0 .8rem; }
.index-heading h2 { font-size: 1.2rem; }
.index-heading span, .card-id { font-size: var(--fs-sm); }
.doc-index { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 17rem), 1fr)); gap: .85rem; }
.doc-index a { height: 100%; display: grid; align-content: start; gap: .45rem; padding: 1rem; border: 1px solid var(--line-edge); border-radius: var(--r-box); color: var(--ink-body); }
.doc-index a:hover { background: var(--surface-sunken); }
.doc-index strong { display: flex; align-items: center; justify-content: space-between; color: var(--ink-strong); font-size: var(--fs-lg); }
.doc-body { margin: 1.4rem 0 2rem; }
.doc-body .md-body { color: var(--ink-body); font-size: 1rem; }
.doc-body :deep(h2[id]) { scroll-margin-top: calc(var(--head-h) + 1.5rem); }
.doc-body :deep(ul) { list-style: disc; }
.doc-body :deep(ol) { list-style: decimal; }
.doc-next { display: flex; justify-content: flex-end; margin-top: 2rem; border-top: 1px solid var(--line-hair); padding-top: 1rem; }
.doc-next a { display: grid; grid-template-columns: 1fr auto; column-gap: .65rem; align-items: center; text-align: end; padding: .6rem; border-radius: var(--r-ctl); }
.doc-next a:hover { background: var(--surface-sunken); }
.doc-next span { grid-column: 1 / -1; color: var(--ink-body); font-size: var(--fs-sm); }
.prompt-example, .command-example { margin: 1.2rem 0; }
.prompt-example :deep(pre) { font: inherit; line-height: 1.8; }
@media (max-width: 760px) {
  .docs-layout { display: block; padding-block: 0 2.5rem; }
  .docs-sidebar { top: var(--head-h); z-index: 5; padding: 0; border: 0; border-bottom: 1px solid var(--line-edge); background: var(--surface-card); max-height: calc(100dvh - var(--head-h)); }
  .menu-toggle { display: flex; align-items: center; gap: .5rem; width: 100%; padding: .8rem .2rem; }
  .menu-toggle svg:last-child { margin-left: auto; }
  .menu-toggle[aria-expanded=true] svg:last-child { transform: rotate(180deg); }
  #doc-navigation { display: none; padding-bottom: 1rem; }
  #doc-navigation.open { display: block; }
  .sidebar-title { display: none; }
  .docs-reader { padding-top: 1.2rem; }
  .doc-body :deep(h2[id]) { scroll-margin-top: calc(var(--head-h) + 4rem); }
}
</style>
