<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { publishedSkills } from '../composables/catalog'
import { FEATURES as allFeatures } from '../data/skills'
import FeaturePreview from './FeaturePreview.vue'

/* 移植原 initFeatures：左侧业务列表 + 右侧 sticky 叠卡 + 滚动联动 + 整组释放 */
const FEATURES = allFeatures.filter(f => publishedSkills.value.some(s => s.slug === f.slug))
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)')

const featureIndex = ref(0)
const released = ref(false)
const cardEls = ref<HTMLElement[]>([])
const copyEl = ref<HTMLElement | null>(null)
const stackEl = ref<HTMLElement | null>(null)
/* 释放后各卡/左列的 relative top（px），未释放时为 null 走 CSS sticky */
const cardTops = ref<(number | null)[]>([null, null, null, null])
const copyTop = ref<number | null>(null)

let featureRest: number[] = []
let copyRest = 0
let ticking = false
let media: MediaQueryList | undefined

const HOLD = 32         // 末卡钉住后再走多少 px 释放

function setFeatureIndex(index: number) {
  if (featureIndex.value === index) return
  featureIndex.value = index
}

function scrollToFeature(index: number) {
  const card = cardEls.value[index]
  if (!card) return
  card.scrollIntoView({ behavior: reduceMotion.matches ? 'auto' : 'smooth', block: 'start' })
  setFeatureIndex(index)
  featureIndex.value = index
}

function onKeydown(event: KeyboardEvent) {
  const delta = event.key === 'ArrowDown' ? 1 : event.key === 'ArrowUp' ? -1 : 0
  if (!delta) return
  event.preventDefault()
  const next = Math.min(FEATURES.length - 1, Math.max(0, featureIndex.value + delta))
  scrollToFeature(next)
}

function syncFromScroll() {
  let active = 0
  cardEls.value.forEach((card, i) => {
    const restingTop = featureRest[i] ?? parseFloat(getComputedStyle(card).top)
    if (card.getBoundingClientRect().top <= restingTop + 4) active = i
  })
  setFeatureIndex(active)
}

/* 释放逻辑：最后一张卡钉住 HOLD px 后，整组卡与左列文案一起随页面滚走。
   末卡是栈内最后一个元素，sticky 约束边界是父容器内容盒（padding 不算），
   栈尾有 ::after 占位提供固定余量。回滚到释放点之前恢复 sticky。 */
function updateRelease() {
  if (!cardEls.value.length) return
  if (!matchMedia('(min-width: 961px)').matches) {
    released.value = false
    cardTops.value = cardTops.value.map(() => null)
    copyTop.value = null
    return
  }
  const stack = stackEl.value
  if (!stack) return
  const stackTopDoc = stack.getBoundingClientRect().top + window.scrollY
  const cardH = cardEls.value[0].getBoundingClientRect().height
  const gap = parseFloat(getComputedStyle(stack).rowGap) || 0
  const natLast = (cardEls.value.length - 1) * (cardH + gap)
  const releaseAt = stackTopDoc + natLast - featureRest[cardEls.value.length - 1] + HOLD
  const isReleased = window.scrollY > releaseAt
  released.value = isReleased
  if (isReleased) {
    cardTops.value = cardEls.value.map((_, i) => {
      const natTop = i * (cardH + gap)
      return featureRest[i] - stackTopDoc - natTop + releaseAt
    })
    const areaTopDoc = (stack.parentElement as HTMLElement).getBoundingClientRect().top + window.scrollY
    copyTop.value = releaseAt + copyRest - areaTopDoc
  } else {
    cardTops.value = cardTops.value.map(() => null)
    copyTop.value = null
  }
}

function onScroll() {
  if (ticking) return
  ticking = true
  requestAnimationFrame(() => { syncFromScroll(); updateRelease(); ticking = false })
}

onMounted(() => {
  cardEls.value = [...stackEl.value!.querySelectorAll<HTMLElement>('.fx-card')]
  /* 在页面未滚动、sticky 未生效时捕获声明值（固定后 computed top 会失真） */
  featureRest = cardEls.value.map(card => parseFloat(getComputedStyle(card).top))
  copyEl.value = document.querySelector<HTMLElement>('.feature-copy')
  copyRest = copyEl.value ? parseFloat(getComputedStyle(copyEl.value).top) : 0
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', updateRelease)
  syncFromScroll()
  updateRelease()
  media = matchMedia('(min-width: 961px)')
  media.addEventListener('change', updateRelease)
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('resize', updateRelease)
  media?.removeEventListener('change', updateRelease)
})

const pad2 = (i: number) => String(i + 1).padStart(2, '0')

/* 被叠卡片的灰色分层：越靠上层（深度越大）越深，形成类似渐变的层次。
   depth 1（刚被盖住）≈7%、2≈12%、3≈16%，最深也就 16% 保证可读。 */
function coveredTone(i: number): { bg: string } | null {
  const depth = featureIndex.value - i
  if (depth <= 0) return null
  const pct = Math.min(16.5, 3 + depth * 4.5).toFixed(1)
  const mixed = `color-mix(in srgb, var(--ink-strong) ${pct}%, var(--surface-sunken))`
  return { bg: mixed }
}

function cardStyle(i: number) {
  const style: Record<string, string> = { '--stack-i': String(i) }
  const top = cardTops.value[i]
  if (top !== null) style.top = `${top}px`
  const tone = coveredTone(i)
  if (tone) {
    style.background = tone.bg
    style.borderColor = tone.bg /* 边框同色，层与层之间只留灰度台阶 */
  }
  return style
}

const copyStyle = computed(() =>
  copyTop.value !== null
    ? { position: 'relative' as const, top: `${copyTop.value}px` }
    : {},
)
</script>

<template>
  <section v-show="FEATURES.length" class="feature-sec" id="features" aria-label="产物效果预览">
    <div class="wrap">
      <div class="feature-area" id="feature-area">
        <div ref="copyEl" class="feature-copy" :style="copyStyle">
          <h2>先看效果，<br>再决定使用</h2>
          <p class="fc-sub">报告、课堂、面试和数据，按业务任务了解能力。</p>
          <div class="feature-tabs" id="feature-tabs" role="tablist" aria-label="按业务任务切换预览" aria-orientation="vertical">
            <button
              v-for="(feature, i) in FEATURES"
              :key="feature.id"
              type="button"
              :id="`feature-tab-${feature.id}`"
              role="tab"
              class="feature-tab"
              :class="{ 'is-active': i === featureIndex }"
              :aria-selected="i === featureIndex"
              :aria-controls="`feature-card-${feature.id}`"
              :tabindex="i === featureIndex ? 0 : -1"
              @click="scrollToFeature(i)"
              @keydown="onKeydown"
            >{{ feature.title }}</button>
          </div>
          <button type="button" class="fc-cta" id="feature-cta" @click="$router.push('/skills')">
            浏览全部 SKILL<svg class="ic" width="14" height="14" aria-hidden="true"><use href="#i-chev" /></svg>
          </button>
        </div>
        <div ref="stackEl" class="feature-stack" id="feature-stack">
          <article
            v-for="(feature, i) in FEATURES"
            :key="feature.id"
            :id="`feature-card-${feature.id}`"
            class="fx-card"
            :class="{ 'is-active': i === featureIndex, 'is-covered': i < featureIndex, 'is-released': cardTops[i] !== null }"
            :style="cardStyle(i)"
            role="tabpanel"
            :aria-labelledby="`feature-tab-${feature.id}`"
          >
            <div class="fx-info">
              <span class="fx-num">{{ pad2(i) }}</span>
              <span class="fx-label">{{ feature.title }}</span>
              <p class="fx-desc">{{ feature.description }}</p>
            </div>
            <div
              class="fx-shot"
              :style="{ '--art': `var(--cat-${feature.catId})`, '--art-soft': `var(--cat-${feature.catId}-soft)` }"
            >
              <FeaturePreview :feature="feature" />
            </div>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>

<style>
/* fc-cta 内的图标：保持与原版一致的行内 svg 尺寸 */
.fc-cta .ic { display: inline-flex; }
</style>
