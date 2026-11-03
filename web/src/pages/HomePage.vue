<script setup lang="ts">
import { SKILLS } from '../data/skills'
import HeroSection from '../components/HeroSection.vue'
import FeatureStack from '../components/FeatureStack.vue'
import SkillCard from '../components/SkillCard.vue'
import HowItWorks from '../components/HowItWorks.vue'
</script>

<template>
  <section class="page page-catalog">
    <HeroSection />
    <FeatureStack />

    <div class="wrap">
      <div class="section-head" v-reveal>
        <h2>SKILL 推荐</h2>
        <p>查看智能体的任务示例和所需材料，选择在线运行或 API 接入。</p>
      </div>

      <div class="grid" id="home-recs">
        <SkillCard v-for="(skill, i) in SKILLS" :key="skill.slug" v-reveal="i * 60" :skill="skill" />
      </div>

      <p class="rec-more" v-reveal="240">
        <RouterLink class="text-btn" to="/skills">查看全部 SKILL，按角色和业务分类筛选 →</RouterLink>
      </p>
    </div>

    <HowItWorks />
  </section>
</template>
