<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
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
const collapsed = reactive({ web: false, file: false })
const groups = computed(() => [
  { kind: 'web' as const, title: '网页', items: props.items.filter(item => item.kind === 'web') },
  { kind: 'file' as const, title: '文件', items: props.items.filter(item => item.kind === 'file') },
].filter(group => group.items.length))
let copyTimer: ReturnType<typeof setTimeout> | undefined

function reset() {
  expanded.value = desktop.matches
  copied.value = ''
  copyError.value = ''
  collapsed.web = false
  collapsed.file = false
  clearTimeout(copyTimer)
}
watch(() => props.conversationKey, reset)
function close() {
  expanded.value = false
  toggle.value?.focus({ preventScroll: true })
}
async function reveal(messageIndex?: number) {
  expanded.value = true
  collapsed.web = false
  collapsed.file = false
  await nextTick()
  const row = messageIndex === undefined ? undefined : root.value?.querySelector<HTMLElement>(`[data-message="${messageIndex}"]`)
  row?.scrollIntoView({ block: 'nearest', behavior: 'instant' })
  const action = (row ?? root.value)?.querySelector<HTMLElement>('.resource-action')
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
  } catch { copyError.value = '复制失败，可长按或右键操作按钮复制链接。' }
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
        <Icon name="file" :size="15" /><h2>生成资源</h2><span class="resources-count">{{ items.length }}</span>
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
        <button type="button" class="resource-group-toggle" :aria-expanded="!collapsed[group.kind]" :aria-controls="`resource-group-${group.kind}`" @click="collapsed[group.kind] = !collapsed[group.kind]">
          <Icon name="chev" :size="12" class="resource-group-chevron" :class="{ 'is-open': !collapsed[group.kind] }" />
          <svg class="resource-folder" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="M3 7V5h7l2 3h9v12H3Z" /></svg>
          <span>{{ group.title }}</span><span class="resource-group-count">{{ group.items.length }}</span>
        </button>
        <ul v-show="!collapsed[group.kind]" :id="`resource-group-${group.kind}`">
          <li v-for="item in group.items" :key="item.url" class="resource-row" :data-message="item.messageIndex">
            <Icon :name="item.kind === 'web' ? 'note' : 'file'" :size="15" class="resource-file-icon" :class="{ 'is-web': item.kind === 'web' }" />
            <span class="resource-name" :title="`${item.name}\n第 ${item.turn} 轮回复`">{{ item.name }}</span>
            <div class="resource-actions">
              <a v-if="item.kind === 'web'" class="resource-action is-open" :href="item.url" target="_blank" rel="noopener noreferrer" title="打开网页" :aria-label="`打开网页：${item.name}`"><Icon name="ext" :size="14" /></a>
              <a v-else class="resource-action is-download" :href="item.url" download title="下载文件" :aria-label="`下载文件：${item.name}`"><Icon name="download" :size="14" /></a>
              <button class="resource-action is-copy" type="button" :class="{ 'is-copied': copied === item.url }" :title="copied === item.url ? '已复制' : item.kind === 'web' ? '复制分享链接' : '复制下载链接'" :aria-label="`复制 ${item.name} 的${item.kind === 'web' ? '分享' : '下载'}链接`" @click="copyLink(item.url)">
                <Icon :name="copied === item.url ? 'check' : 'copy'" :size="14" />
              </button>
            </div>
          </li>
        </ul>
      </section>
    </div>
    <p v-if="expanded && copyError" class="resources-error" role="alert">{{ copyError }}</p>
    <p class="vh" role="status" aria-live="polite">{{ copied ? '链接已复制' : '' }}</p>
  </aside>
</template>

<style scoped>
/* Zero4-UI: existing --sk tokens map to its iOS colors, glass and pill controls. */
.conversation-resources {
  position: sticky; top: calc(var(--head-h) + 16px); align-self: flex-start; flex: 0 0 320px;
  min-width: 0; max-height: min(480px, calc(100dvh - var(--head-h) - 32px)); margin: 16px 16px 16px 0;
  display: flex; flex-direction: column; border: 1px solid var(--sk-line); border-radius: 16px;
  background: var(--sk-glass); backdrop-filter: var(--sk-glass-blur); -webkit-backdrop-filter: var(--sk-glass-blur);
  box-shadow: var(--sk-glass-shadow), inset 0 1px var(--sk-glass-border); color: var(--sk-ink-1);
}
.conversation-resources:not(.is-expanded) { flex-basis: auto; border-radius: 999px; }
.resources-header { flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 46px; padding: 7px 10px 7px 14px; border-bottom: 1px solid var(--sk-line); }
.resources-heading { display: flex; align-items: center; gap: 7px; color: var(--sk-ink-2); }
.resources-heading h2 { margin: 0; color: var(--sk-ink-1); font-size: 12px; font-weight: 600; letter-spacing: -.01em; }
.resources-count { display: inline-flex; align-items: center; justify-content: center; min-width: 18px; padding: 0 5px; border-radius: 999px; background: var(--sk-fill); color: var(--sk-ink-2); font-size: 10px; font-weight: 500; line-height: 17px; font-variant-numeric: tabular-nums; }
.resources-toggle { display: flex; align-items: center; justify-content: center; gap: 7px; flex-shrink: 0; min-width: 28px; min-height: 28px; padding: 5px; border-radius: 7px; color: var(--sk-ink-2); transition: background .18s var(--sk-ease), color .18s var(--sk-ease); }
.resources-toggle:hover { color: var(--sk-ink-1); background: var(--sk-fill-hover); }
.resources-close-mobile { display: none; }
.conversation-resources:not(.is-expanded) .resources-header { min-height: 0; padding: 3px; border: none; }
.conversation-resources:not(.is-expanded) .resources-toggle { min-height: 32px; padding: 0 10px; border-radius: 999px; font-size: 12px; }
.resources-body { min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-width: thin; padding: 6px 6px 9px; }
.resource-group + .resource-group { margin-top: 4px; }
.resource-group-toggle { display: flex; align-items: center; gap: 6px; width: 100%; min-height: 28px; padding: 0 7px; border-radius: 6px; color: var(--sk-ink-2); font: inherit; font-size: 11px; text-align: left; }
.resource-group-toggle:hover { background: var(--sk-fill-hover); }
.resource-group-chevron { transition: transform .18s var(--sk-ease); }
.resource-group-chevron.is-open { transform: rotate(90deg); }
.resource-folder { flex-shrink: 0; color: var(--sk-ink-3); }
.resource-group-count { margin-left: auto; color: var(--sk-ink-3); font-size: 10px; font-variant-numeric: tabular-nums; }
.resource-group ul { position: relative; list-style: none; padding: 0 0 0 18px; margin: 0; }
.resource-group ul::before { position: absolute; top: 0; bottom: 2px; left: 13px; border-left: 1px solid var(--sk-line); content: ''; }
.resource-row { display: flex; align-items: center; gap: 7px; height: 34px; padding: 0 4px 0 6px; border-radius: 6px; }
.resource-row:hover, .resource-row:focus-within { background: var(--sk-fill-hover); }
.resource-file-icon { color: var(--sk-ink-3); }
.resource-file-icon.is-web { color: var(--sk-blue); }
.resource-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 400; line-height: 1.5; }
.resource-actions { display: flex; align-items: center; gap: 1px; flex-shrink: 0; }
.resource-action { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 5px; color: var(--sk-ink-2); transition: background .18s var(--sk-ease), color .18s var(--sk-ease), transform .18s var(--sk-spring); }
.resource-action:active { transform: scale(.97); }
.resource-action:hover { background: var(--sk-fill); color: var(--sk-ink-1); }
.resource-action.is-copied { color: var(--sk-green); }
.resources-error { margin: 0; padding: 7px 12px; border-top: 1px solid var(--sk-line); color: var(--sk-red); font-size: 11px; line-height: 1.6; }
@media (max-width: 1199px) {
  .conversation-resources { position: fixed; top: calc(var(--head-h) + 12px); right: 14px; z-index: 25; width: min(340px, calc(100vw - 28px)); max-height: min(480px, calc(100dvh - var(--head-h) - 28px)); margin: 0; }
  .resources-collapse-desktop { display: none; }
  .resources-close-mobile { display: block; }
  .conversation-resources:not(.is-expanded) { width: auto; }
  .conversation-resources:not(.is-expanded) .resources-toggle { min-height: 38px; }
  .resources-toggle { min-width: 36px; min-height: 36px; }
  .resource-group-toggle { min-height: 34px; }
  .resource-row { height: 44px; }
  .resource-action { width: 36px; height: 36px; }
}
@media (prefers-reduced-motion: reduce) {
  .resources-toggle, .resource-action, .resource-group-chevron { transition: none; }
}
</style>
