<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSession } from '../composables/session'
import { isRunsTabVisible } from '../plazaEnv'

const route = useRoute()
const open = ref(false)
const isDark = ref(document.documentElement.getAttribute('data-mode') === 'dark')
const navToggle = ref<HTMLButtonElement | null>(null)
const menuOpen = ref(false)
const scrolled = ref(false)
const { user, openLogin, logout } = useSession()

/* 滚动后头部切换为液态玻璃；首屏顶部保持透明 */
function onScroll() { scrolled.value = window.scrollY > 12 }

const maskedPhone = () => {
  const p = user.value?.phone ?? ''
  return p.length === 11 ? `${p.slice(0, 3)}****${p.slice(7)}` : p
}

function toggleMenu() { menuOpen.value = !menuOpen.value }
function closeMenu() { menuOpen.value = false }
function onLogout() { logout(); closeMenu() }

function applyMode(mode: 'dark' | 'light') {
  if (mode === 'dark') document.documentElement.setAttribute('data-mode', 'dark')
  else document.documentElement.removeAttribute('data-mode')
  isDark.value = mode === 'dark'
  try { localStorage.setItem('skill-plaza:mode', mode) } catch { /* 忽略 */ }
}

function toggleMode() {
  applyMode(isDark.value ? 'light' : 'dark')
}

function closeNav(restore = false) {
  if (!open.value) return
  open.value = false
  document.body.style.overflow = ''
  if (restore) navToggle.value?.focus()
}

function toggleNav() {
  if (open.value) { closeNav(true); return }
  open.value = true
  document.body.style.overflow = 'hidden'
  document.querySelector<HTMLAnchorElement>('#site-nav a')?.focus()
}

function onDocClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (menuOpen.value && !target?.closest('.user-wrap')) closeMenu()
  if (!open.value) return
  const head = document.getElementById('site-head')
  if (head && !target?.closest('#site-head')) closeNav()
}

const onMedia = () => closeNav()
let media: MediaQueryList | undefined
onMounted(() => {
  document.addEventListener('click', onDocClick)
  media = matchMedia('(min-width: 901px)')
  media.addEventListener('change', onMedia)
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  media?.removeEventListener('change', onMedia)
  window.removeEventListener('scroll', onScroll)
})

/* 路由变化收起移动菜单与用户菜单 */
watch(() => route.fullPath, () => { closeNav(); closeMenu() })
</script>

<template>
  <header class="site-head" id="site-head" :class="{ 'is-open': open, 'is-scrolled': scrolled || open }">
    <div class="wrap head-inner">
      <RouterLink class="brand" to="/">
        <span class="brand-mark"><img src="/logo.png" alt="智能体搭子"></span>
      </RouterLink>
      <button ref="navToggle" id="nav-toggle" class="nav-toggle" aria-expanded="false" aria-controls="head-panel" @click="toggleNav">
        {{ open ? '关闭' : '菜单' }}
      </button>
      <div class="head-panel" id="head-panel">
        <nav class="site-nav" id="site-nav" aria-label="主导航">
          <RouterLink to="/" :aria-current="route.name === 'home' ? 'page' : undefined">首页</RouterLink>
          <RouterLink to="/skills" :aria-current="route.name === 'skills' || route.name === 'detail' ? 'page' : undefined">智能体广场</RouterLink>
          <RouterLink to="/experience" :aria-current="route.name === 'experience' ? 'page' : undefined">在线对话</RouterLink>
          <RouterLink v-if="isRunsTabVisible()" to="/runs" :aria-current="route.name === 'runs' || route.name === 'runDetail' ? 'page' : undefined">运行记录</RouterLink>
          <RouterLink to="/docs" :aria-current="route.name === 'skillDocs' ? 'page' : undefined">文档中心</RouterLink>
        </nav>
        <div class="head-tools">
          <RouterLink class="text-btn" to="/guide">怎么用？</RouterLink>
          <button type="button" class="icon-btn" id="mode-toggle" :aria-pressed="isDark" @click="toggleMode">
            <svg class="ic" width="18" height="18" aria-hidden="true"><use :href="isDark ? '#i-sun' : '#i-moon'" /></svg>
            <span class="vh">{{ isDark ? '切换浅色模式' : '切换深色模式' }}</span>
          </button>

          <template v-if="user">
            <div class="user-wrap" @keydown.escape="closeMenu">
              <button type="button" class="user-btn" :aria-expanded="menuOpen" aria-haspopup="menu" @click="toggleMenu">
                <span class="user-avatar" aria-hidden="true">{{ user.nickname.slice(-1) }}</span>
                <span class="user-name">{{ user.nickname }}</span>
                <svg class="ic" width="14" height="14" aria-hidden="true"><use href="#i-chev-down" /></svg>
              </button>
              <div v-if="menuOpen" class="user-menu" role="menu">
                <p class="user-menu-phone">{{ maskedPhone() }}</p>
                <button type="button" class="user-menu-item" role="menuitem" @click="onLogout">退出登录</button>
              </div>
            </div>
          </template>
          <button v-else type="button" class="login-btn" @click="openLogin">登录</button>
        </div>
      </div>
    </div>
  </header>
</template>
