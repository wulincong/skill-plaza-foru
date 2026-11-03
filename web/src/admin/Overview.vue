<script setup lang="ts">
import { computed, onMounted } from 'vue'
import Icon from '../components/Icon.vue'
import { action, activeModel, busy, catalog, refresh, state } from './state'
const published = computed(() => catalog.value.filter((s) => s.enabled).length)
onMounted(() => {
  void action(refresh)
})
</script>
<template>
  <section v-if="state">
    <p class="adm-kicker">01 / OVERVIEW</p>
    <div class="adm-heading">
      <div>
        <h1>工作台</h1>
        <p class="adm-sub">查看智能体广场的发布状态与运行情况。</p>
      </div>
      <button class="adm-btn" :disabled="busy" @click="action(refresh)">
        <Icon name="refresh" :size="14" /> 刷新
      </button>
    </div>
    <div class="adm-metrics">
      <RouterLink to="/skills"
        ><span>已上架技能</span
        ><strong
          >{{ published }}<small>/ {{ catalog.length }}</small></strong
        ><em>公开可运行</em></RouterLink
      >
      <RouterLink to="/runs"
        ><span>累计运行</span><strong>{{ state.stats.total.toLocaleString() }}</strong
        ><em>包含归档记录</em></RouterLink
      >
      <RouterLink to="/runs"
        ><span>近 24 小时</span><strong>{{ state.stats.last24h }}</strong
        ><em>{{ state.stats.successes }} 次成功运行</em></RouterLink
      >
    </div>
    <div class="adm-feature">
      <div>
        <p class="adm-kicker">MODEL ROUTING</p>
        <small>当前默认模型</small>
        <h2>{{ activeModel?.name }}</h2>
        <code>{{ activeModel?.provider }}/{{ activeModel?.modelId }}</code>
        <RouterLink to="/models" class="adm-feature-link"
          >管理模型与密钥 <Icon name="arrow" :size="15"
        /></RouterLink>
      </div>
      <svg class="adm-orbit" viewBox="0 0 230 180" aria-hidden="true">
        <g fill="none" stroke="currentColor">
          <ellipse
            v-for="i in 12"
            :key="i"
            cx="115"
            cy="90"
            rx="91"
            ry="35"
            :transform="'rotate(' + i * 15 + ' 115 90)'"
          />
        </g>
        <circle cx="115" cy="90" r="4" fill="currentColor" />
      </svg>
    </div>
    <h2 class="adm-section-title">管理入口</h2>
    <div class="adm-gridlinks">
      <RouterLink to="/skills"
        ><Icon name="industry" :size="21" /><b>技能管理</b><small>调整公开目录和运行权限</small><Icon name="arrow"
      /></RouterLink>
      <RouterLink to="/runs"
        ><Icon name="note" :size="21" /><b>运行记录</b><small>查找任务、用量和执行过程</small><Icon name="arrow"
      /></RouterLink>
      <RouterLink to="/settings"
        ><Icon name="wrench" :size="21" /><b>运行设置</b><small>配置时限和会话回收</small><Icon name="arrow"
      /></RouterLink>
    </div>
  </section>
</template>
