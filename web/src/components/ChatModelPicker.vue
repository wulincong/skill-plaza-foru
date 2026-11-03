<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import Icon from './Icon.vue'
import type { ChatModelId, ChatModelOption } from '../composables/useChatApi'

const props = defineProps<{ options: ChatModelOption[]; disabled: boolean }>()
const selected = defineModel<ChatModelId>()
const choice = computed(() => props.options.find(m => m.id === selected.value))
const open = ref(false)
const root = ref<HTMLElement>()
const trigger = ref<HTMLButtonElement>()
const menu = ref<HTMLElement>()

function focusItem(i: number) {
  const items = menu.value?.querySelectorAll<HTMLButtonElement>('button')
  if (items?.length) items[(i + items.length) % items.length].focus()
}
async function show() {
  open.value = true
  await nextTick()
  focusItem(Math.max(0, props.options.findIndex(m => m.id === selected.value)))
}
function close(returnFocus = false) {
  open.value = false
  if (returnFocus) trigger.value?.focus()
}
function pick(id: ChatModelId) {
  selected.value = id
  close(true)
}
function onOutside(e: Event) {
  if (!root.value?.contains(e.target as Node)) close()
}
watch(open, (shown, _, onCleanup) => {
  if (!shown) return
  document.addEventListener('pointerdown', onOutside)
  document.addEventListener('focusin', onOutside)
  onCleanup(() => {
    document.removeEventListener('pointerdown', onOutside)
    document.removeEventListener('focusin', onOutside)
  })
})
watch(() => props.disabled, disabled => { if (disabled) close() })
</script>

<template>
  <div ref="root" class="exp-model" @keydown.esc.stop.prevent="close(true)">
    <button ref="trigger" type="button" class="exp-model-trigger" :disabled="disabled" aria-haspopup="menu"
      :aria-expanded="open" :aria-label="`选择对话模型，当前为${choice?.name}`" :title="choice?.name"
      @click="open ? close() : show()" @keydown.down.prevent="show()" @keydown.up.prevent="show()">
      <Icon name="sparkles" :size="14" />{{ choice?.id === 'youcai' ? '优才大模型' : choice?.name }}<Icon name="chev-down" :size="12" />
    </button>
    <div v-if="open" ref="menu" class="exp-model-menu" role="menu" aria-label="对话模型">
      <div class="exp-model-caption">对话模型</div>
      <button v-for="(option, i) in options" :key="option.id" type="button" role="menuitemradio"
        :aria-checked="selected === option.id" tabindex="-1" @click="pick(option.id)"
        @keydown.enter.prevent="pick(option.id)" @keydown.space.prevent="pick(option.id)"
        @keydown.down.prevent="focusItem(i+1)" @keydown.up.prevent="focusItem(i-1)"
        @keydown.home.prevent="focusItem(0)" @keydown.end.prevent="focusItem(options.length-1)">
        {{ option.name }}<Icon v-if="selected === option.id" name="check" :size="15" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.exp-model { position: relative; }
.exp-model-trigger, .exp-model-menu button {
  display: flex; align-items: center; gap: 6px; border: 0; font: inherit; color: var(--sk-ink-2);
  background: transparent; cursor: pointer;
}
.exp-model-trigger { height: 32px; padding: 0 9px; border-radius: 8px; }
.exp-model-trigger:hover, .exp-model-trigger[aria-expanded=true], .exp-model-menu button:hover,
.exp-model-menu button:focus-visible { background: var(--sk-fill-hover); }
.exp-model-trigger:disabled { opacity: .55; cursor: default; }
.exp-model button:focus-visible { outline: 2px solid var(--sk-blue); outline-offset: -2px; }
.exp-model-menu {
  position: absolute; z-index: 30; right: 0; bottom: calc(100% + 8px); width: 218px; max-width: calc(100vw - 64px);
  padding: 5px; border: 1px solid var(--sk-line); border-radius: 14px;
  background: var(--surface-card); box-shadow: var(--sk-glass-shadow); animation: sk-menu-in .16s var(--sk-ease);
}
.exp-model-caption { padding: 6px 10px; color: var(--sk-ink-3); font-size: 11px; }
.exp-model-menu button { width: 100%; min-height: 36px; justify-content: space-between; border-radius: 9px; padding: 0 10px; font-size: 13px; }
.exp-model-menu button[aria-checked=true] { color: var(--sk-blue); font-weight: 600; }
@media (pointer: coarse) { .exp-model-menu button { min-height: 44px; } }
</style>
