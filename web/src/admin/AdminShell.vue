<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '../components/Icon.vue'
import { action, api, busy, errorMessage, refresh, state } from './state'
import './admin.css'

const route = useRoute()
const loading = ref(true)
const username = ref('')
const password = ref('')
const dark = ref(document.documentElement.dataset.mode === 'dark')
const tabs = [
  { name: 'overview', title: '工作台', icon: 'brand' },
  { name: 'publishing', title: '技能管理', icon: 'industry' },
  { name: 'models', title: '模型与密钥', icon: 'terminal' },
  { name: 'runs', title: '运行记录', icon: 'note' },
  { name: 'settings', title: '运行设置', icon: 'wrench' },
  { name: 'account', title: '账号设置', icon: 'career' },
]
function toggleTheme() {
  dark.value = !dark.value
  document.documentElement.dataset.mode = dark.value ? 'dark' : 'light'
  localStorage.setItem('skill-plaza:mode', dark.value ? 'dark' : 'light')
}
async function login() {
  await action(async () => {
    await api('login', 'POST', { username: username.value, password: password.value })
    password.value = ''
    await refresh()
  })
}
async function logout() {
  await action(async () => {
    await api('logout', 'POST')
    state.value = undefined
    password.value = ''
  })
}
onMounted(async () => {
  try {
    await refresh()
  } catch (e) {
    if (e instanceof Error && e.message !== '请登录管理后台') errorMessage.value = '无法连接管理服务，请刷新重试。'
  } finally {
    loading.value = false
  }
})
watch(
  () => route.fullPath,
  () => {
    errorMessage.value = ''
  },
)
</script>
<template>
  <div class="adm">
    <header class="adm-top">
      <div class="adm-topin">
        <a href="/admin" class="adm-brand"
          ><Icon name="logo" :size="29" /><strong>智能体搭子</strong><span>管理后台</span></a
        >
        <div class="adm-tools">
          <a href="/#/skills">返回广场 <Icon name="ext" :size="12" /></a
          ><button class="adm-icon" :aria-label="dark ? '浅色模式' : '深色模式'" @click="toggleTheme">
            <Icon :name="dark ? 'sun' : 'moon'" :size="17" />
          </button>
        </div>
      </div>
    </header>
    <div v-if="loading" class="adm-loading" role="status">正在连接管理工作区…</div>
    <div v-else-if="!state" class="adm-login">
      <form class="adm-login-card" @submit.prevent="login">
        <span class="adm-emblem"><Icon name="logo" :size="48" /></span>
        <p class="adm-kicker">PLAZA CONSOLE</p>
        <h1>管理员登录</h1>
        <p class="adm-sub">登录以管理广场技能、模型与运行记录。</p>
        <label
          >管理员账号<input
            v-model.trim="username"
            name="username"
            required
            maxlength="64"
            autocomplete="username"
            placeholder="输入管理员账号"
        /></label>
        <label
          >密码<input
            v-model="password"
            name="password"
            required
            type="password"
            autocomplete="current-password"
            placeholder="输入登录密码"
        /></label>
        <p v-if="errorMessage" class="adm-error" role="alert">{{ errorMessage }}</p>
        <button class="adm-primary" :disabled="busy">
          {{ busy ? '正在登录…' : '登录后台' }} <Icon name="arrow" :size="16" />
        </button>
      </form>
    </div>
    <div v-else class="adm-layout">
      <aside class="adm-side">
        <p class="adm-kicker">WORKSPACE</p>
        <nav aria-label="后台导航">
          <RouterLink
            v-for="tab in tabs"
            :key="tab.name"
            :to="{ name: tab.name }"
            :class="{ selected: route.name === tab.name || (tab.name === 'runs' && route.name === 'runDetail') }"
            ><Icon :name="tab.icon" :size="17" />{{ tab.title }}</RouterLink
          >
        </nav>
        <div class="adm-identity">
          <i>{{ state.username.charAt(0).toUpperCase() }}</i>
          <div>
            <b>{{ state.username }}</b
            ><small>管理员</small>
          </div>
          <button :disabled="busy" @click="logout">退出</button>
        </div>
      </aside>
      <div class="adm-content">
        <p v-if="errorMessage" class="adm-error" role="alert">{{ errorMessage }}</p>
        <RouterView :key="route.path" />
      </div>
    </div>
  </div>
</template>
