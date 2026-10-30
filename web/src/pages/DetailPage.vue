<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { bySlug, catOf, audOf, FEATURES } from '../data/skills'
import { configOf } from '../data/useTaskConfigs'
import Icon from '../components/Icon.vue'
import Codebox from '../components/Codebox.vue'
import FeaturePreview from '../components/FeaturePreview.vue'

const route = useRoute()
const slug = computed(() => (typeof route.params.slug === 'string' ? route.params.slug : ''))
const skill = computed(() => bySlug.get(slug.value))

const returnTo = computed(() => {
  const raw = typeof route.query.return === 'string' ? route.query.return : ''
  return raw && /^#\/(?:\?|$|catalog|skills)/.test(raw) ? raw : '#/skills'
})

const cat = computed(() => (skill.value ? catOf(skill.value.categoryId) : undefined))
const audiences = computed(() =>
  skill.value ? skill.value.audiences.map(id => audOf(id).name).join('、') : '',
)
const feature = computed(() => (skill.value ? FEATURES.find(f => f.slug === skill.value!.slug) : undefined))

const pad2 = (i: number) => String(i + 1).padStart(2, '0')
</script>

<template>
  <section class="page">
    <div v-if="skill" class="wrap wrap-read" id="detail-content">
      <nav class="crumb" aria-label="面包屑">
        <a :href="returnTo">全部 SKILL</a><Icon name="chev" :size="14" />
        <a :href="`#/skills?category=${skill.categoryId}`">{{ cat!.name }}</a><Icon name="chev" :size="14" />
        <span class="cur">{{ skill.name }}</span>
      </nav>

      <header class="detail-head">
        <div class="detail-title">
          <span class="card-pic" :style="{ width: '46px', height: '46px' }">
            <Icon :name="cat!.id" :size="25" />
          </span>
          <div>
            <h1>{{ skill.name }}</h1>
            <p class="card-id">{{ skill.identifier }}</p>
          </div>
        </div>
        <p class="detail-summary">{{ skill.summary }}</p>
        <div class="detail-actions">
          <RouterLink class="btn btn-primary" :to="{ name: 'use', params: { slug: skill.slug } }">
            在线运行这个 SKILL<Icon name="arrow" :size="15" />
          </RouterLink>
          <span class="detail-actions-note">{{ configOf(skill.slug) ? '配置任务后运行，也可在在线对话中选择此技能。' : '进入在线对话，说明任务要求即可使用此技能。' }}</span>
        </div>
        <div class="meta-row">
          <div class="meta-item"><span class="meta-k">运行环境</span><span class="meta-v">{{ skill.compatibility.join(' / ') }}</span></div>
          <div class="meta-item"><span class="meta-k">适用角色</span><span class="meta-v">{{ audiences }}</span></div>
          <div class="meta-item">
            <span class="meta-k">仓库</span>
            <span class="meta-v mono">
              <a class="ext" :href="skill.repository" target="_blank" rel="noreferrer">{{ skill.repositoryLabel }}<Icon name="ext" :size="13" /></a>
            </span>
          </div>
        </div>
      </header>

      <section v-if="skill.introduction" class="block" v-reveal="40">
        <h2 class="block-title">SKILL 简介</h2>
        <p class="block-note detail-introduction">{{ skill.introduction }}</p>
      </section>

      <section class="block" v-reveal="60">
        <h2 class="block-title">跑完会得到什么</h2>
        <p class="block-note">按条目列出。具体文件名与目录结构以仓库当前发布资料为准。</p>
        <ul class="out-list">
          <li v-for="(item, i) in skill.outputs" :key="item" class="out-item"><span class="idx">{{ pad2(i) }}</span>{{ item }}</li>
        </ul>
        <div
          v-if="feature"
          class="feature-preview detail-preview"
          :style="{ '--art': `var(--cat-${cat!.id})`, '--art-soft': `var(--cat-${cat!.id}-soft)` }"
        >
          <FeaturePreview :feature="feature" detail />
        </div>
      </section>

      <section v-if="skill.slug !== 'career-guidance'" class="block" v-reveal="120">
        <h2 class="block-title">怎么用</h2>
        <p class="block-note">两步：先装上，再跑一次最小任务。</p>
        <div class="rail">
          <div class="rail-item">
            <span class="rail-no">1</span>
            <div class="rail-body">
              <p class="rail-title">安装</p>
              <p class="rail-desc">把这句话完整发给你使用的 AI 工具（Codex、Claude Code、Cursor 等），它会从指定仓库取回整个目录。</p>
              <Codebox label="安装提示词" :text="skill.installPrompt" message="安装提示词已复制" :primary="true" />
            </div>
          </div>
          <div class="rail-item">
            <span class="rail-no">2</span>
            <div class="rail-body">
              <p class="rail-title">跑一次最小任务</p>
              <p class="rail-desc">安装完成后从这里开始。把示例里的地区、资料或附件换成你自己的。</p>
              <Codebox label="最小输入示例" :text="skill.minimalInput" message="最小输入示例已复制" />
            </div>
          </div>
        </div>
      </section>

      <section class="block" v-reveal="180">
        <h2 class="block-title">运行条件与边界</h2>
        <p class="block-note">左边是能不能跑起来，右边是这个 SKILL 明确不做的事。</p>
        <div class="conds">
          <div class="cond-box">
            <h3>需要准备</h3>
            <ul><li v-for="d in skill.dependencies" :key="d">{{ d }}</li></ul>
          </div>
          <div class="cond-box is-limit">
            <h3>已知边界</h3>
            <ul><li v-for="d in skill.limitations" :key="d">{{ d }}</li></ul>
          </div>
        </div>
      </section>

      <section v-if="skill.slug !== 'career-guidance'" class="block" v-reveal="240">
        <h2 class="block-title">安装步骤</h2>
        <ol class="olist"><li v-for="d in skill.installation" :key="d">{{ d }}</li></ol>
        <div class="repo-line">
          <span class="repo-path">{{ skill.repositoryLabel }}</span>
          <a class="btn btn-quiet" :href="skill.repository" target="_blank" rel="noreferrer">打开 GitHub 仓库<Icon name="ext" :size="15" /></a>
        </div>
      </section>

      <p class="note">这一页的内容与产物清单都取自该仓库的发布资料；依赖、费用与许可以仓库当前内容为准。页面不会执行 SKILL。</p>

      <div class="detail-foot">
        <a class="btn btn-quiet" :href="returnTo"><Icon name="back" :size="15" />返回列表</a>
      </div>
    </div>

    <div v-else class="wrap wrap-read">
      <div class="empty">
        <svg class="ic" width="34" height="34" aria-hidden="true"><use href="#i-none" /></svg>
        <h2>没有这个 SKILL</h2>
        <p>链接可能拼错了，或者它指向的 SKILL 已经不在清单里。</p>
        <RouterLink class="btn btn-primary" to="/skills">回到全部 SKILL</RouterLink>
      </div>
    </div>
  </section>
</template>
