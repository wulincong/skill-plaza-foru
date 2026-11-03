<script setup lang="ts">
import { ref } from 'vue'
import { action, api, busy, state } from './state'
const current = ref('')
const next = ref('')
const confirm = ref('')
async function submit() {
  await action(async () => {
    if (next.value !== confirm.value) throw new Error('两次输入的新密码不一致')
    await api('password', 'POST', { currentPassword: current.value, password: next.value })
    state.value = undefined
  }, '密码已修改，请使用新密码重新登录')
}
</script>
<template>
  <section v-if="state">
    <p class="adm-kicker">06 / ACCOUNT</p>
    <h1>账号设置</h1>
    <p class="adm-sub">当前以 {{ state.username }} 身份管理这个工作区。</p>
    <form class="adm-panel adm-form" @submit.prevent="submit">
      <h2>修改登录密码</h2>
      <label>当前密码<input v-model="current" type="password" autocomplete="current-password" required /></label>
      <div class="adm-fields">
        <label
          >新密码<input
            v-model="next"
            type="password"
            autocomplete="new-password"
            minlength="12"
            required
            placeholder="至少 12 个字符"
        /></label>
        <label
          >确认新密码<input v-model="confirm" type="password" autocomplete="new-password" minlength="12" required
        /></label>
      </div>
      <small>保存后，所有设备上的管理员会话都将退出。</small
      ><button class="adm-primary" :disabled="busy">修改密码</button>
    </form>
  </section>
</template>
