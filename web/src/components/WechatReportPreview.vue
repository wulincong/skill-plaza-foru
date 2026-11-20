<script setup lang="ts">
import { computed } from 'vue'
import Icon from './Icon.vue'
const props=defineProps<{links:Array<{name:string;url:string}>;canConfirm?:boolean}>()
const emit=defineEmits<{confirm:[url:string]}>()
const report=computed(()=>props.links.find(link=>{
  try {const url=new URL(link.url,window.location.href);return url.origin===window.location.origin && /^\/p\/[a-f0-9]{32}\/\d+\//.test(url.pathname)}
  catch{return false}
}))
</script>

<template>
  <section v-if="report" class="wechat-preview" aria-label="图片报告预览">
    <header><strong>{{ report.name }}</strong><a :href="report.url" target="_blank" rel="noopener noreferrer">打开完整报告<Icon name="ext" :size="14" /></a></header>
    <details open><summary>查看报告内容</summary><iframe :src="report.url" :title="report.name" loading="lazy" sandbox="allow-scripts allow-downloads" referrerpolicy="no-referrer" /></details>
    <footer><p>需要修改时，直接在对话中说明章节和调整要求。</p><button v-if="canConfirm" type="button" @click="emit('confirm',report.url)">确认报告质量</button></footer>
  </section>
</template>

<style scoped>
.wechat-preview{margin:14px 0;border:1px solid var(--sk-line);border-radius:16px;background:var(--surface-card);overflow:hidden;color:var(--sk-ink-1)}
header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 16px;flex-wrap:wrap}
header strong{font-size:14px;line-height:1.7}header a{display:inline-flex;align-items:center;gap:5px;color:var(--sk-blue);font-size:13px}
summary{cursor:pointer;padding:9px 16px;border-top:1px solid var(--sk-line);font-size:12px;color:var(--sk-ink-2)}
iframe{display:block;width:100%;height:min(680px,70dvh);min-height:360px;border:0;background:var(--sk-fill)}
footer{padding:12px 16px;border-top:1px solid var(--sk-line);display:flex;align-items:center;gap:12px;justify-content:space-between;flex-wrap:wrap}
footer p{margin:0;font-size:12px;line-height:1.7;color:var(--sk-ink-2)}footer button{padding:9px 16px;border-radius:999px;background:var(--sk-blue);color:white;font-size:13px;min-height:36px}
</style>
