<script setup lang="ts">
import { computed, ref } from 'vue'
import { busy, catalog, save } from './state'
const query = ref('')
const filter = ref('all')
const filtered = computed(() =>
  catalog.value.filter(
    (s) =>
      (filter.value === 'all' || s.enabled === (filter.value === 'on')) &&
      (s.title + s.id).toLowerCase().includes(query.value.trim().toLowerCase()),
  ),
)
</script>
<template>
  <section>
    <p class="adm-kicker">02 / CATALOG</p>
    <h1>技能管理</h1>
    <p class="adm-sub">上架后即可在广场和 API 中使用。下架会停止接受该技能的新任务。</p>
    <div class="adm-panel">
      <div class="adm-toolbar">
        <input v-model="query" type="search" aria-label="搜索技能" placeholder="搜索技能名称或标识" />
        <select v-model="filter" aria-label="发布状态">
          <option value="all">全部状态</option>
          <option value="on">已上架</option>
          <option value="off">已下架</option>
        </select>
      </div>
      <div class="adm-row" v-for="skill in filtered" :key="skill.id">
        <div class="adm-row-copy">
          <b>{{ skill.title }}</b
          ><code>{{ skill.id }}</code
          ><small>{{ skill.description }}</small>
        </div>
        <span class="adm-badge" :class="{ on: skill.enabled }">{{ skill.enabled ? '已上架' : '已下架' }}</span>
        <button
          type="button"
          role="switch"
          class="adm-switch"
          :aria-checked="skill.enabled"
          :aria-label="skill.title + '上架状态'"
          :disabled="busy"
          @click="
            save('skills', { id: skill.id, enabled: !skill.enabled }, skill.enabled ? '技能已下架' : '技能已上架')
          "
        >
          <i />
        </button>
      </div>
      <p v-if="!filtered.length" class="adm-empty">没有符合条件的技能。</p>
    </div>
  </section>
</template>
