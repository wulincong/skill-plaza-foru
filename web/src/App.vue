<script setup lang="ts">
import SiteHead from './components/SiteHead.vue'
import SiteFoot from './components/SiteFoot.vue'
import LoginModal from './components/LoginModal.vue'
import { toasts } from './composables/toast'
import { useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()
const admin = computed(() => route.meta.admin === true)
const hideFoot = computed(() => admin.value || route.name === 'experience' || route.name === 'skillDocs')
</script>

<template>
  <!-- ============ 图标 ============ -->
  <svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
    <symbol id="i-industry" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 20.5V10l5-2.4V20.5" /><path d="M8 20.5V6.8l6.4 3v10.7" />
      <path d="M14.4 20.5v-6l6.6-3v9" /><path d="M2 20.5h20" />
    </symbol>
    <symbol id="i-teaching" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 7.2C10.2 5.7 7.6 5.1 4.5 5.4v11.7c3.1-.3 5.7.3 7.5 1.8 1.8-1.5 4.4-2.1 7.5-1.8V5.4c-3.1-.3-5.7.3-7.5 1.8Z" />
      <path d="M12 7.2v11.6" />
    </symbol>
    <symbol id="i-career" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="7.4" width="18" height="12.6" rx="2.6" />
      <path d="M8.6 7.4V6a2 2 0 0 1 2-2h2.8a2 2 0 0 1 2 2v1.4" /><path d="M3 12.6h18" />
    </symbol>
    <symbol id="i-data" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <ellipse cx="12" cy="5.8" rx="7.6" ry="2.9" />
      <path d="M4.4 5.8v6.1c0 1.6 3.4 2.9 7.6 2.9s7.6-1.3 7.6-2.9V5.8" />
      <path d="M4.4 11.9v6.1c0 1.6 3.4 2.9 7.6 2.9s7.6-1.3 7.6-2.9v-6.1" />
    </symbol>
    <symbol id="i-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M9 5.5l6.5 6.5L9 18.5" />
    </symbol>
    <symbol id="i-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4.5 12h14.5" /><path d="M13.5 6l6 6-6 6" />
    </symbol>
    <symbol id="i-chev-down" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
      <path d="M5.5 9l6.5 6.5L18.5 9" />
    </symbol>
    <symbol id="i-back" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M19.5 12H4.5" /><path d="M11 18.5L4.5 12 11 5.5" />
    </symbol>
    <symbol id="i-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="10.8" cy="10.8" r="6.3" /><path d="M15.5 15.5L20.5 20.5" />
    </symbol>
    <symbol id="i-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="10.8" cy="10.8" r="6.3" /><path d="M15.5 15.5L20.5 20.5" /><path d="M8.3 10.8h5" />
    </symbol>
    <symbol id="i-ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M13.5 4H20v6.5" /><path d="M19.6 4.4l-8.4 8.4" />
      <path d="M18 14.2v4.3A1.5 1.5 0 0 1 16.5 20h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6h4.3" />
    </symbol>
    <symbol id="i-copy" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="9" y="9" width="11" height="11" rx="2.2" />
      <path d="M15 6.6V5.2A2.2 2.2 0 0 0 12.8 3H5.2A2.2 2.2 0 0 0 3 5.2v7.6A2.2 2.2 0 0 0 5.2 15h1.4" />
    </symbol>
    <symbol id="i-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4.5 12.5l5 5 10-11" />
    </symbol>
    <symbol id="i-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.6v2.2M12 19.2v2.2M2.6 12h2.2M19.2 12h2.2M5.4 5.4l1.6 1.6M17 17l1.6 1.6M18.6 5.4L17 7M7 17l-1.6 1.6" />
    </symbol>
    <symbol id="i-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M20.2 14.8A8.6 8.6 0 0 1 9.2 3.8a8.6 8.6 0 1 0 11 11Z" />
    </symbol>
    <symbol id="i-note" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="8.4" /><path d="M12 11.2v5.2" /><path d="M12 7.9h.01" />
    </symbol>
    <symbol id="i-paperclip" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </symbol>
    <symbol id="i-chat" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
    </symbol>
    <symbol id="i-form" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M8 6h13" /><path d="M8 12h13" /><path d="M8 18h13" /><path d="M3 6h.01" /><path d="M3 12h.01" /><path d="M3 18h.01" />
    </symbol>
    <symbol id="i-brand" viewBox="0 0 24 24">
      <path d="M12 3.2 20.8 8 12 12.8 3.2 8Z" fill="currentColor" />
      <path d="M4.8 13.4 12 17.2l7.2-3.8" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round" stroke-linecap="round" />
    </symbol>
    <!-- SkillHub 语言补充图标（lucide ISC，via skillhub-ui-design skill） -->
    <symbol id="i-plus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M5 12h14" /><path d="M12 5v14" />
    </symbol>
    <symbol id="i-msg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </symbol>
    <symbol id="i-arrow-up" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="m5 12 7-7 7 7" /><path d="M12 19V5" />
    </symbol>
    <symbol id="i-terminal" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 19h8" /><path d="m4 17 6-6-6-6" />
    </symbol>
    <symbol id="i-wrench" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </symbol>
    <symbol id="i-download" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 15V3" /><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m7 10 5 5 5-5" />
    </symbol>
    <symbol id="i-file" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="M10 9H8" /><path d="M16 13H8" /><path d="M16 17H8" />
    </symbol>
    <symbol id="i-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" />
    </symbol>
    <symbol id="i-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M18 6 6 18" /><path d="m6 6 12 12" />
    </symbol>
    <symbol id="i-trash" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
      <path d="M10 11v6" /><path d="M14 11v6" />
    </symbol>
    <symbol id="i-archive" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect width="20" height="5" x="2" y="3" rx="1" />
      <path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" />
      <path d="M10 12h4" />
    </symbol>
    <symbol id="i-restore" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
    </symbol>
    <symbol id="i-loader" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </symbol>
    <symbol id="i-sparkles" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z" />
      <path d="M20 2v4" /><path d="M22 4h-4" />
    </symbol>
    <symbol id="i-logo" viewBox="0 0 24 24">
      <!-- 智能体搭子：两块拼图（页头品牌标） -->
      <g transform="rotate(-4 7.5 9)">
        <circle cx="7.5" cy="4.4" r="2.1" fill="#2E7CF6" />
        <rect x="2.6" y="4.8" width="10" height="10" rx="2.6" fill="#2E7CF6" />
      </g>
      <g transform="rotate(5 16.5 14.5)">
        <circle cx="16.4" cy="8.2" r="1.9" fill="#F6C21F" />
        <circle cx="20.6" cy="18.4" r="1.7" fill="#F6C21F" />
        <rect x="11" y="8.6" width="10" height="10" rx="2.6" fill="#F6C21F" />
      </g>
    </symbol>
    <linearGradient id="foru-scene-white" x1="0" y1="0" x2=".5" y2="1"><stop stop-color="#FFF" /><stop offset="1" stop-color="#DDE9F6" /></linearGradient>
    <linearGradient id="foru-scene-blue" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#A7E6FF" /><stop offset=".55" stop-color="#67ABFA" /><stop offset="1" stop-color="#3C65EF" /></linearGradient>
    <filter id="foru-scene-shadow" x="-30%" y="-30%" width="160%" height="180%"><feDropShadow dx="0" dy="12" stdDeviation="10" flood-color="#6B9FE9" flood-opacity=".20" /></filter>
    <symbol id="foru-scene-ai" viewBox="0 0 360 310">
      <path d="m0 230 177-82 183 82v80H0Z" fill="url(#foru-scene-white)" />
      <path d="m-4 267 187-95 190 97M-4 285l187-95 190 97" fill="none" stroke="#D0DEEB" stroke-width="2" />
      <g filter="url(#foru-scene-shadow)">
        <ellipse cx="198" cy="238" rx="126" ry="44" fill="#85BDF4" />
        <ellipse cx="198" cy="230" rx="126" ry="44" fill="#EEF7FD" />
        <ellipse cx="198" cy="230" rx="110" ry="34" fill="#D8EAF9" />
        <path d="M198 94c-33-31-74-7-74 21-20 8-30 32-16 49-10 25 12 46 31 46l19 26h49l-2-33c20-3 34-20 25-36 26-10 26-40 7-48 3-20-15-30-39-25Z" fill="url(#foru-scene-blue)" />
        <path d="m175 118-8 27 16 13m-43-7 17 15-4 18m-16 3 16 9m57-60-18 13 5 15m-33 44 18-13m-50-87 12 7" fill="none" stroke="#407DE8" stroke-width="5" stroke-linecap="round" />
        <path d="m55 227 41-19 30 13-42 20Z" fill="#5BAAF3" />
        <path d="m59 225 1-31 36-16v30Z" fill="#8BD8FF" />
        <path d="m276 192 20-9 23 11-20 10Z" fill="#75C8FF" />
        <path d="m297 184 4-20 21 11-3 20Z" fill="#5D9CE8" />
        <path d="M198 233v15m-73-22-13 8m167-8 14 8" stroke="#B0CCE8" stroke-width="2" />
      </g>
    </symbol>
  </svg>

  <a class="skip" href="#main">跳至内容</a>

  <SiteHead v-if="!admin" />

  <main id="main" tabindex="-1">
    <RouterView v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
    <noscript>
      <div class="wrap wrap-read">
        <p class="note">这份页面用 JavaScript 渲染 SKILL 清单、筛选和复制。请开启 JavaScript 后重新打开；页面不需要联网。</p>
      </div>
    </noscript>
  </main>

  <SiteFoot v-if="!hideFoot" />

  <LoginModal v-if="!admin" />

  <div class="toast-host" id="toast-host" aria-live="polite">
    <div v-for="t in toasts" :key="t.id" class="toast">{{ t.message }}</div>
  </div>

</template>

