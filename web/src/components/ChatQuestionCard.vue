<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChatQuestion } from '../../shared/chatQuestion'
import Icon from './Icon.vue'

const props = defineProps<{ request: ChatQuestion; pending: boolean; disabled: boolean; answer?: string; runId?: string }>()
const emit = defineEmits<{ answer: [text: string] }>()
const single = ref('')
const multiple = ref<string[]>([])
const custom = ref(false)
const input = ref('')
const typing = computed(() => props.request.kind === 'input' || custom.value)
const selected = computed(() => {
  if (typing.value) return input.value.trim()
  if (props.request.kind === 'multiple') return props.request.options.filter(o => multiple.value.includes(o.label)).map(o => o.label).join('、')
  return single.value
})
const titles = { confirm: '需要确认', single: '单选', multiple: '多选', input: '补充信息' }
function submit(text = selected.value) {
  if (props.pending && !props.disabled && text) emit('answer', text)
}
</script>

<template>
  <section class="question-card" :class="{ pending }" :aria-labelledby="'question-' + runId">
    <header>
      <span class="question-icon"><Icon name="chat" :size="15" /></span>
      <strong>{{ titles[request.kind] }}</strong>
      <small role="status"><Icon v-if="answer" name="check" :size="13" />{{ answer ? '已回复' : pending ? '等待你的回复' : '已结束' }}</small>
    </header>
    <h3 :id="'question-' + runId">{{ request.question }}</h3>
    <p v-if="request.note" class="question-note">{{ request.note }}</p>
    <details v-if="!pending && request.options.length" class="question-options">
      <summary>查看 {{ request.options.length }} 个选项</summary>
      <ol><li v-for="o in request.options" :key="o.label"><b>{{ o.label }}</b><span v-if="o.description"> · {{ o.description }}</span></li></ol>
    </details>
    <p v-if="answer" class="question-answer">{{ answer }}</p>
    <fieldset v-else-if="pending" :disabled="disabled" :aria-label="request.question">
      <template v-if="typing">
        <textarea v-model="input" rows="2" aria-label="你的回复" placeholder="写下你的回复…" @keydown.enter.exact="e => { if (!e.isComposing) { e.preventDefault(); submit() } }" />
      </template>
      <div v-else-if="request.kind === 'confirm'" class="actions" @keydown.esc.prevent="submit(request.options[1]!.label)">
        <button v-for="(o, i) in request.options" :key="o.label" type="button" :class="i === 0 ? 'primary' : 'secondary'" @click="submit(o.label)">
          {{ o.label }}<span v-if="o.description" class="confirm-detail">{{ o.description }}</span>
        </button>
      </div>
      <div v-else class="choices">
        <label v-for="o in request.options" :key="o.label" class="choice">
          <input v-if="request.kind === 'multiple'" v-model="multiple" type="checkbox" :value="o.label" />
          <input v-else v-model="single" type="radio" :name="'choice-' + runId" :value="o.label" />
          <span><b>{{ o.label }}</b><small v-if="o.description">{{ o.description }}</small></span>
        </label>
      </div>
      <div class="actions">
        <button v-if="typing || request.kind !== 'confirm'" type="button" class="primary" :disabled="!selected" @click="submit()">{{ typing ? '提交回复' : '确认选择' }}</button>
        <button v-if="request.kind !== 'input'" type="button" class="link" @click="custom = !custom">{{ custom ? '返回选项' : '自己填写' }}</button>
      </div>
    </fieldset>
  </section>
</template>

<style scoped>
.question-card { margin: 12px 0; max-width: 620px; padding: 14px 16px; border: 1px solid var(--sk-line); border-radius: 16px; background: var(--surface-card); color: var(--sk-ink-1); overflow-wrap: anywhere; }
.question-card.pending { border-color: color-mix(in srgb, var(--sk-blue) 36%, var(--surface-card)); box-shadow: 0 3px 14px var(--sk-blue-soft); }
header, .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
header strong, button, .choice b { font-size: 13px; font-weight: 600; }
.question-icon { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 8px; background: var(--sk-blue-soft); color: var(--sk-blue); }
header small { margin-left: auto; display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--sk-ink-2); }
header small svg { color: var(--sk-green); }
.pending header small { color: var(--sk-blue); }
.pending header small::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
h3 { margin: 10px 0 0; font-size: 15px; line-height: 1.6; letter-spacing: var(--sk-track-sm); }
.question-note, .choice small { color: var(--sk-ink-2); font-size: 12px; line-height: 1.65; }
.question-options { margin-top: 8px; font-size: 12px; color: var(--sk-ink-2); }
.question-options summary { cursor: pointer; }
.question-options ol { padding-inline-start: 20px; line-height: 1.7; }
.question-note { margin: 4px 0 0; }
fieldset { border: 0; padding: 0; margin: 12px 0 0; min-width: 0; }
.choices { display: grid; gap: 6px; }
.choice { display: flex; align-items: center; gap: 10px; min-height: 42px; padding: 8px 12px; border: 1px solid var(--sk-input-border); border-radius: 11px; cursor: pointer; }
.choice:has(:checked) { background: var(--sk-blue-soft); border-color: var(--sk-blue); }
.choice small, .confirm-detail { display: block; }
.choice input { margin: 0; width: 18px; height: 18px; flex: none; accent-color: var(--sk-blue); }
:global(html[data-mode="dark"]) .choice input { color-scheme: dark; }
textarea { display: block; width: 100%; box-sizing: border-box; padding: 10px 12px; resize: vertical; border: 1px solid var(--sk-input-border); border-radius: 11px; background: var(--surface-card); color: inherit; font: inherit; }
.actions { margin-top: 10px; }
fieldset > .actions:first-child { margin-top: 0; }
button { max-width: 100%; min-height: 38px; padding: 6px 16px; border: 1px solid transparent; border-radius: 99px; cursor: pointer; transition: background .15s var(--sk-ease); overflow-wrap: anywhere; }
.primary { background: var(--sk-blue); color: white; }
.primary:hover:enabled { background: var(--sk-blue-hover); }
.secondary { background: var(--surface-card); border-color: var(--sk-input-border); color: var(--sk-ink-1); }
.confirm-detail { font-size: 12px; font-weight: 400; }
.link { background: transparent; color: var(--sk-ink-2); }
button:disabled, fieldset:disabled { opacity: .5; cursor: default; }
button:focus-visible, textarea:focus-visible, .choice:has(:focus-visible) { outline: 2px solid var(--sk-blue); outline-offset: 2px; }
.question-answer { margin: 8px 0 0; padding: 4px 10px; border-left: 2px solid var(--sk-blue); color: var(--sk-ink-1); font-size: 14px; white-space: pre-wrap; }
@media (pointer: coarse) { button, .choice { min-height: 44px; } }
@media (prefers-reduced-motion: no-preference) {
  .pending header small::before { animation: question-pulse 2.4s ease-in-out infinite; }
  @keyframes question-pulse { 50% { box-shadow: 0 0 0 3px var(--sk-blue-ring); } }
}
</style>
