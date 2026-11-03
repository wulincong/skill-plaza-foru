<script setup lang="ts">
import { ref } from 'vue'
import { busy, save, state } from './state'
const settings = state.value!.config.settings
const fields = [
  { key: 'timeoutMs', title: '通用对话与提示词技能时限' },
  { key: 'installedTimeoutMs', title: '已安装技能单次运行时限' },
  { key: 'idleMs', title: '空闲会话回收时限' },
] as const
const seconds = ref({
  timeoutMs: settings.timeoutMs / 1000,
  installedTimeoutMs: settings.installedTimeoutMs / 1000,
  idleMs: settings.idleMs / 1000,
})
function submit() {
  const next = { ...state.value!.config.settings }
  for (const { key } of fields) next[key] = Math.round(seconds.value[key] * 1000)
  void save('settings', { settings: next }, '运行设置已保存')
}
</script>
<template>
  <section v-if="state">
    <p class="adm-kicker">05 / RUNTIME</p>
    <h1>运行设置</h1>
    <p class="adm-sub">为通用任务和专业技能分别设置执行时间。</p>
    <form class="adm-panel adm-form" @submit.prevent="submit">
      <h2>任务与会话</h2>
      <label v-for="field in fields" :key="field.key"
        >{{ field.title }}（秒）<input
          v-model.number="seconds[field.key]"
          required
          type="number"
          min="1"
          max="86400"
          step="0.001"
      /></label>
      <button class="adm-primary" :disabled="busy">保存运行设置</button>
    </form>
    <div class="adm-panel">
      <div class="adm-panel-head">
        <h2>部署信息</h2>
        <p>来自当前服务进程的环境配置。</p>
      </div>
      <dl class="adm-detail">
        <div>
          <dt>运行环境</dt>
          <dd>{{ state.deployment.environment }}</dd>
        </div>
        <div>
          <dt>执行引擎</dt>
          <dd>Pi RPC</dd>
        </div>
        <div>
          <dt>沙箱账户</dt>
          <dd>{{ state.deployment.sandbox || '当前服务用户' }}</dd>
        </div>
        <div>
          <dt>人才数据库</dt>
          <dd>{{ state.deployment.databaseConfigured ? '已配置连接参数' : '未配置' }}</dd>
        </div>
      </dl>
    </div>
  </section>
</template>
