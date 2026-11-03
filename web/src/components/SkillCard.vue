<script setup lang="ts">
import { computed } from 'vue'
import { type Skill, catOf, audOf } from '../data/skills'
import Icon from './Icon.vue'

const props = defineProps<{ skill: Skill }>()

const cat = computed(() => catOf(props.skill.categoryId))
const audiences = computed(() => props.skill.audiences.map(id => audOf(id).name).join('、'))
</script>

<template>
  <article class="card">
    <div class="card-top">
      <span class="card-pic" :style="{ width: '38px', height: '38px' }">
        <Icon :name="cat.id" :size="21" />
      </span>
      <div class="card-head">
        <h2 class="card-name">{{ skill.name }}</h2>
        <p class="card-id">{{ skill.identifier }}</p>
      </div>
    </div>
    <span class="card-cat" :style="{ background: `var(--cat-${cat.id}-soft)`, color: `var(--cat-${cat.id})` }">{{ cat.name }}</span>
    <p class="card-summary">{{ skill.summary }}</p>
    <div class="tags">
      <span v-for="tag in skill.tags" :key="tag" class="tag">{{ tag }}</span>
    </div>
    <div class="card-foot">
      <div class="card-cond">
        <div class="cond-row"><span class="cond-k">运行</span><span class="cond-v">在线运行 / API</span></div>
        <div class="cond-row"><span class="cond-k">需要</span><span class="cond-v">{{ skill.preconditions }}</span></div>
        <div class="cond-row"><span class="cond-k">适用</span><span class="cond-v">{{ audiences }}</span></div>
      </div>
    </div>
    <div class="card-actions">
      <RouterLink class="card-go is-quiet" :to="`/skill/${skill.slug}`">查看详情<Icon name="chev" :size="15" /></RouterLink>
      <RouterLink class="card-go" :to="{ name: 'use', params: { slug: skill.slug } }">在线运行</RouterLink>
    </div>
  </article>
</template>
