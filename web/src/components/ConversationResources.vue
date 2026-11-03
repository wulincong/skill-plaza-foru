<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Icon from './Icon.vue'
import type { ConversationResource } from '../composables/conversationResources'

const props = defineProps<{
  items: ConversationResource[]
  conversationKey: number | null
}>()
const desktop = matchMedia('(min-width: 1200px)')
const expanded = ref(desktop.matches)
const root = ref<HTMLElement>()
const toggle = ref<HTMLButtonElement>()
const copied = ref('')
const copyError = ref('')
const groups = computed(() => [
  { kind: 'web', title: '网页分享', items: props.items.filter(item => item.kind === 'web') },
  { kind: 'file', title: '文件下载', items: props.items.filter(item => item.kind === 'file') },
].filter(group => group.items.length))
let copyTimer: ReturnType<typeof setTimeout> | undefined

function reset() {
  expanded.value = desktop.matches
  copied.value = ''
  copyError.value = ''
  clearTimeout(copyTimer)
}
watch(() => props.conversationKey, reset)
function close() {
  expanded.value = false
  toggle.value?.focus({ preventScroll: true })
}
async function reveal(messageIndex?: number) {
  expanded.value = true
  await nextTick()
  const card = messageIndex === undefined ? undefined : root.value?.querySelector<HTMLElement>(`[data-message="${messageIndex}"]`)
  card?.scrollIntoView({ block: 'nearest', behavior: 'instant' })
  const action = (card ?? root.value)?.querySelector<HTMLElement>('.resource-action')
  action?.focus({ preventScroll: true })
}
defineExpose({ reveal })

async function copyLink(url: string) {
  const absolute = new URL(url, window.location.href).href
  copyError.value = ''
  try {
    let success = false
    if (navigator.clipboard?.writeText) {
      try { await navigator.clipboard.writeText(absolute); success = true } catch { /* HTTP/permissions fallback below */ }
    }
    if (!success) {
      const previousFocus = document.activeElement as HTMLElement | null
      const input = document.createElement('textarea')
      input.value = absolute
      input.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
      root.value?.appendChild(input)
      try { input.select(); success = document.execCommand('copy') }
      finally { input.remove(); previousFocus?.focus({ preventScroll: true }) }
    }
    if (!success) throw new Error('copy')
    copied.value = url
    clearTimeout(copyTimer)
    copyTimer = setTimeout(() => { copied.value = '' }, 2200)
  } catch { copyError.value = '复制失败，请从“打开网页”复制链接地址。' }
}
function onOutside(event: PointerEvent) {
  if (!desktop.matches && expanded.value && !root.value?.contains(event.target as Node)) expanded.value = false
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && expanded.value) { event.preventDefault(); close() }
}
function onBreakpoint() { reset() }
onMounted(() => {
  desktop.addEventListener('change', onBreakpoint)
  document.addEventListener('pointerdown', onOutside)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  clearTimeout(copyTimer)
  desktop.removeEventListener('change', onBreakpoint)
  document.removeEventListener('pointerdown', onOutside)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <aside ref="root" class="conversation-resources" :class="{ 'is-expanded': expanded }" aria-label="对话资源">
    <header class="resources-header">
      <div v-show="expanded" class="resources-heading">
        <p class="resources-eyebrow">本次对话</p>
        <h2>生成资源 <span class="resources-count">{{ items.length }}</span></h2>
      </div>
      <button
        ref="toggle" type="button" class="resources-toggle"
        :aria-label="expanded ? '收起资源列表' : `展开资源列表，共 ${items.length} 项`"
        :aria-expanded="expanded" aria-controls="conversation-resource-list"
        @click="expanded = !expanded"
      >
        <template v-if="expanded"><Icon name="chev" class="resources-collapse-desktop" :size="17" /><Icon name="x" class="resources-close-mobile" :size="17" /></template>
        <Icon v-else name="file" :size="17" />
        <template v-if="!expanded"><span>资源</span><span class="resources-count">{{ items.length }}</span></template>
      </button>
    </header>
    <div v-show="expanded" id="conversation-resource-list" class="resources-body">
      <section v-for="group in groups" :key="group.kind" class="resource-group" :aria-label="group.title">
        <h3>{{ group.title }}<span>{{ group.items.length }}</span></h3>
        <ul>
          <li v-for="item in group.items" :key="item.url" class="resource-card" :data-message="item.messageIndex">
            <div class="resource-card-top">
              <span class="resource-kind-icon" :class="{ 'is-web': item.kind === 'web' }"><Icon :name="item.kind === 'web' ? 'ext' : 'file'" :size="18" /></span>
              <span class="resource-origin">第 {{ item.turn }} 轮回复</span>
            </div>
            <p class="resource-name">{{ item.name }}</p>
            <p class="resource-description">{{ item.kind === 'web' ? '在线浏览，可分享给他人' : '下载并保存到设备' }}</p>
            <div class="resource-actions">
              <template v-if="item.kind === 'web'">
                <a class="resource-action is-open" :href="item.url" target="_blank" rel="noopener noreferrer">打开网页<Icon name="ext" :size="12" /></a>
                <button class="resource-action is-copy" type="button" :aria-label="`复制 ${item.name} 的分享链接`" @click="copyLink(item.url)">
                  <Icon :name="copied === item.url ? 'check' : 'copy'" :size="13" />{{ copied === item.url ? '已复制' : '复制链接' }}
                </button>
              </template>
              <a v-else class="resource-action is-download" :href="item.url" download><Icon name="download" :size="14" />下载文件</a>
            </div>
          </li>
        </ul>
      </section>
    </div>
    <footer v-show="expanded" class="resources-footer">
      <p v-if="copyError" role="alert">{{ copyError }}</p>
      <p v-else role="status" aria-live="polite">{{ copied ? '分享链接已复制' : '对话中的资源会保留在这里' }}</p>
    </footer>
  </aside>
</template>

<style scoped>
/* Zero4-UI: existing --sk tokens map to its iOS colors, glass and pill controls. */
.conversation-resources {
  position: sticky; top: var(--head-h); align-self: flex-start; flex: 0 0 308px;
  height: calc(100dvh - var(--head-h)); min-height: 240px; min-width: 0;
  display: flex; flex-direction: column; background: var(--surface-canvas);
  border-left: 1px solid var(--sk-line); color: var(--sk-ink-1);
}
.conversation-resources:not(.is-expanded) { flex-basis: 72px; }
.resources-header { flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 22px 18px 18px; }
.resources-eyebrow { margin: 0 0 5px; color: var(--sk-ink-3); font-size: 11px; }
.resources-heading h2 { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 18px; font-weight: 600; letter-spacing: -.02em; }
.resources-count { display: inline-flex; align-items: center; justify-content: center; min-width: 21px; padding: 2px 6px; border-radius: 999px; background: var(--sk-fill); color: var(--sk-ink-2); font-size: 11px; font-weight: 500; line-height: 16px; font-variant-numeric: tabular-nums; }
.resources-toggle { display: flex; align-items: center; justify-content: center; gap: 7px; flex-shrink: 0; min-width: 34px; min-height: 34px; padding: 7px; border: 1px solid var(--sk-line); border-radius: 10px; color: var(--sk-ink-2); background: var(--surface-card); transition: background .18s var(--sk-ease), color .18s var(--sk-ease); }
.resources-toggle:hover { color: var(--sk-ink-1); background: var(--sk-fill-hover); }
.resources-close-mobile { display: none; }
.conversation-resources:not(.is-expanded) .resources-header { justify-content: center; padding: 20px 10px; }
.conversation-resources:not(.is-expanded) .resources-toggle { flex-direction: column; gap: 8px; border: none; background: transparent; font-size: 11px; }
.resources-body { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-width: thin; padding: 0 16px 18px; }
.resource-group + .resource-group { margin-top: 22px; }
.resource-group h3 { display: flex; align-items: center; justify-content: space-between; margin: 0 2px 10px; color: var(--sk-ink-2); font-size: 11px; font-weight: 500; letter-spacing: .02em; }
.resource-group h3 span { color: var(--sk-ink-3); font-variant-numeric: tabular-nums; }
.resource-group ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
.resource-card { padding: 15px; border: 1px solid var(--sk-line); border-radius: 16px; background: var(--surface-card); box-shadow: 0 1px 2px rgba(0,0,0,.03); }
.resource-card-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 12px; }
.resource-kind-icon { display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: 10px; background: var(--sk-fill-hover); color: var(--sk-ink-2); }
.resource-kind-icon.is-web { background: var(--sk-blue-soft); color: var(--sk-blue); }
.resource-origin { color: var(--sk-ink-3); font-size: 10.5px; }
.resource-name { margin: 0; font-size: 13px; font-weight: 600; line-height: 1.6; letter-spacing: -.01em; overflow-wrap: anywhere; }
.resource-description { margin: 5px 0 14px; color: var(--sk-ink-3); font-size: 11px; line-height: 1.6; }
.resource-actions { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.resource-action { display: inline-flex; align-items: center; justify-content: center; gap: 5px; min-height: 32px; padding: 0 11px; border-radius: 999px; font: inherit; font-size: 11px; font-weight: 500; white-space: nowrap; transition: background .18s var(--sk-ease), transform .18s var(--sk-spring); }
.resource-action:active { transform: scale(.97); }
.resource-action.is-open { background: var(--sk-blue-soft); color: var(--sk-blue); }
.resource-action.is-open:hover { background: var(--sk-blue-ring); }
.resource-action.is-copy { color: var(--sk-ink-2); }
.resource-action.is-copy:hover { background: var(--sk-fill-hover); color: var(--sk-ink-1); }
.resource-action.is-download { width: 100%; background: var(--sk-btn); color: var(--sk-btn-on); }
.resource-action.is-download:hover { background: var(--sk-btn-hover); }
.resources-footer { flex-shrink: 0; border-top: 1px solid var(--sk-line); margin: 0 18px; padding: 13px 0 17px; }
.resources-footer p { margin: 0; color: var(--sk-ink-3); font-size: 10.5px; line-height: 1.6; }
.resources-footer [role='alert'] { color: var(--sk-red); }
@media (max-width: 1199px) {
  .conversation-resources { position: fixed; top: calc(var(--head-h) + 12px); right: 14px; z-index: 25; width: min(340px, calc(100vw - 28px)); height: min(640px, calc(100dvh - var(--head-h) - 28px)); min-height: 0; border: 1px solid var(--sk-line); border-radius: 20px; background: var(--sk-glass); backdrop-filter: var(--sk-glass-blur); -webkit-backdrop-filter: var(--sk-glass-blur); box-shadow: var(--sk-glass-shadow); }
  .resources-collapse-desktop { display: none; }
  .resources-close-mobile { display: block; }
  .conversation-resources:not(.is-expanded) { width: auto; min-height: 0; height: auto; border-radius: 999px; }
  .conversation-resources:not(.is-expanded) .resources-header { padding: 0; }
  .conversation-resources:not(.is-expanded) .resources-toggle { flex-direction: row; gap: 7px; min-height: 42px; padding: 0 13px; font-size: 12px; border-radius: 999px; }
  .resources-header { padding: 16px 18px; }
  .resources-toggle { min-width: 42px; min-height: 42px; }
  .resource-action { min-height: 40px; padding: 0 13px; font-size: 12px; }
}
@media (prefers-reduced-motion: reduce) {
  .resources-toggle, .resource-action { transition: none; }
}
</style>
