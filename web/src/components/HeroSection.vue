<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { publishedSkills as SKILLS } from '../composables/catalog'
import { catOf } from '../data/skills'
import Icon from './Icon.vue'

/* 3 列 marquee 轮播恢复 + 入场：卡片先叠成一叠（带微旋转），随后依次散开成一排 */
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)')

const viewport = ref<HTMLElement | null>(null)
const HERO_SET = SKILLS.value.length
const trackCards = ref(1) // 1 组（静态回退）或 3 组（轮播）
let heroTimer: ReturnType<typeof setInterval> | null = null
let heroPos = 0
const offset = ref(0)
const noAnim = ref(false)

function stepPx(): number {
  const track = viewport.value?.querySelector<HTMLElement>('.hero-track')
  if (!track || !track.children.length) return 0
  const gap = parseFloat(getComputedStyle(track).gap) || 0
  return (track.children[0] as HTMLElement).getBoundingClientRect().width + gap
}

function apply(animate: boolean) {
  if (!animate) noAnim.value = true
  offset.value = heroPos * stepPx()
  if (!animate) {
    requestAnimationFrame(() => { noAnim.value = false })
  }
}

function heroTick() {
  heroPos += 1
  apply(true)
  if (heroPos >= HERO_SET) {
    setTimeout(() => { heroPos -= HERO_SET; apply(false) }, 720)
  }
}

function setup() {
  const marquee = matchMedia('(min-width: 961px)').matches && !reduceMotion.matches
  trackCards.value = marquee ? 3 : 1
  if (heroTimer) { clearInterval(heroTimer); heroTimer = null }
  heroPos = 0
  apply(false)
  if (marquee && HERO_SET > 1) heroTimer = setInterval(heroTick, 5000)
}

let media: MediaQueryList | undefined
onMounted(() => {
  setup()
  media = matchMedia('(min-width: 961px)')
  media.addEventListener('change', setup)
  reduceMotion.addEventListener?.('change', setup)
})
onBeforeUnmount(() => {
  if (heroTimer) clearInterval(heroTimer)
  media?.removeEventListener('change', setup)
  reduceMotion.removeEventListener?.('change', setup)
})

/* 每张卡的"叠"姿态：居中收窄成一叠（shift 把卡 i 平移到容器中心），交替微旋带少量错位 */
const GATHER = [
  { shift: 1, r: -2.5, jx: '0%', jy: '0px' },
  { shift: 0, r: 2, jx: '2.5%', jy: '-8px' },
  { shift: -1, r: -3.5, jx: '-1.5%', jy: '8px' },
  { shift: -2, r: 3, jx: '1.5%', jy: '-2px' },
]
function cardVars(idx: number) {
  const g = GATHER[idx % GATHER.length]
  return {
    '--gather-x': `calc(${g.shift} * (100% + 16px))`,
    '--gather-r': `${g.r}deg`,
    '--gather-jx': g.jx,
    '--gather-jy': g.jy,
    '--spread-delay': `${0.35 + idx * 0.18}s`,
    zIndex: String(SKILLS.value.length - idx),
  }
}
/* 标题逐字动画：从模糊到清晰，从左到右；🧩 作为最后一个"字符"压轴弹出 */
const LINE1 = '备课、练习和求职，'
const LINE2 = '找智能体搭子'
const chars1 = LINE1.split('')
const chars2 = LINE2.split('')
const line2Start = 60 + chars1.length * 26 + 150
const emojiDelay = line2Start + chars2.length * 26 + 60
const nb = (ch: string) => (ch === ' ' ? '\u00A0' : ch)

function catName(id: string) { return catOf(id).name }
</script>

<template>
  <div class="hero" id="hero">
    <div class="hero-inner">
      <h1 class="hero-title" aria-label="备课、练习和求职，找智能体搭子">
        <span aria-hidden="true"><span v-for="(ch, i) in chars1" :key="'a' + i" class="hero-char" :style="{ animationDelay: `${60 + i * 26}ms` }">{{ nb(ch) }}</span></span>
        <br aria-hidden="true">
        <span aria-hidden="true"><span v-for="(ch, i) in chars2" :key="'b' + i" class="hero-char" :style="{ animationDelay: `${line2Start + i * 26}ms` }">{{ nb(ch) }}</span></span><span class="hero-emoji" :style="{ animationDelay: `${emojiDelay}ms` }" aria-hidden="true">🧩</span>
      </h1>
      <p class="hero-sub">{{ SKILLS.length }} 个智能体，支持课程答疑、课堂练习、模拟面试、就业指导和数据实践。</p>
      <div class="hero-actions">
        <RouterLink class="btn btn-primary" to="/experience">在线对话<Icon name="arrow" :size="15" /></RouterLink>
        <RouterLink class="btn btn-quiet" to="/skills">浏览全部 SKILL</RouterLink>
      </div>
      <p class="hero-hint">要在自己的应用里使用？<RouterLink class="text-btn" to="/docs/guide">查看 API 接入指南 →</RouterLink></p>
    </div>
    <div class="hero-strip">
      <div ref="viewport" class="hero-cards" id="hero-cards" aria-label="SKILL 速览">
        <div class="hero-track" :class="{ 'no-anim': noAnim }" :style="{ transform: `translateX(${-offset}px)` }">
          <template v-for="copy in trackCards" :key="copy">
            <a
              v-for="(skill, idx) in SKILLS"
              :key="`${copy}-${skill.slug}`"
              class="hero-card"
              :href="`#/skill/${skill.slug}`"
              :tabindex="copy > 1 ? -1 : undefined"
              :aria-hidden="copy > 1 ? 'true' : undefined"
              :style="cardVars(idx)"
            >
              <span class="hc-title">{{ skill.name }}</span>
              <span class="hc-desc">{{ skill.summary }}</span>
              <span class="hc-divider" aria-hidden="true"></span>
              <span class="hc-foot">
                <span class="hc-num">{{ skill.outputs.length }}</span>
                <span class="hc-unit">项产物</span>
                <span class="hc-note"><i class="hc-dot" :style="{ background: `var(--cat-${skill.categoryId})` }" aria-hidden="true"></i>{{ catName(skill.categoryId) }}</span>
                <span class="hc-link" aria-label="查看详情"><Icon name="arrow" :size="17" /></span>
              </span>
            </a>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
