<script setup lang="ts">
import { computed, ref } from 'vue'
import { busy, save, state } from './state'
const config = computed(() => state.value!.config)
const draft = ref({ ...config.value.settings })
const name = ref('')
const secret = ref('')
const confirmId = ref('')
const keys = computed(() => [{ id: 'environment', name: '部署环境凭据' }, ...config.value.keys])
async function add() {
  if (
    await save('keys', { action: 'add', name: name.value, secret: secret.value }, '密钥已保存，可在列表中启用')
  ) {
    name.value = ''
    secret.value = ''
  }
}
async function remove(id: string) {
  if (confirmId.value !== id) {
    confirmId.value = id
    return
  }
  if (await save('keys', { action: 'delete', id }, '密钥已移除')) confirmId.value = ''
}
</script>
<template>
  <section>
    <p class="adm-kicker">03 / MODEL ROUTING</p>
    <h1>模型与密钥</h1>
    <p class="adm-sub">为新的运行选择模型和凭据，当前任务会继续使用原配置。</p>
    <form
      class="adm-panel adm-form"
      @submit.prevent="
        save(
          'settings',
          {
            settings: {
              ...config.settings,
              defaultModel: draft.defaultModel,
              thinking: draft.thinking,
              reportThinking: draft.reportThinking,
              allowModelChoice: draft.allowModelChoice,
              youcaiEndpoint: draft.youcaiEndpoint,
            },
          },
          '模型设置已生效',
        )
      "
    >
      <h2>模型路由</h2>
      <div class="adm-fields">
        <label
          >默认模型<select v-model="draft.defaultModel">
            <option v-for="m in config.models" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select></label
        >
        <label
          >思考档位<select v-model="draft.thinking">
            <option v-for="l in config.thinkingLevels" :key="l">{{ l }}</option>
          </select></label
        >
      </div>
      <label
        >公众号报告使用优才模型时的思考档位<select v-model="draft.reportThinking">
          <option value="">使用通用档位</option>
          <option v-for="l in config.thinkingLevels" :key="l">{{ l }}</option>
        </select></label
      >
      <label
        >优才模型服务地址<input v-model.trim="draft.youcaiEndpoint" required type="url" maxlength="512"
      /></label>
      <label class="adm-check"
        ><input v-model="draft.allowModelChoice" type="checkbox" />允许用户在网页对话中切换模型</label
      >
      <button class="adm-primary" :disabled="busy">保存模型设置</button>
    </form>
    <div class="adm-panel">
      <div class="adm-panel-head">
        <h2>DeepSeek API Key</h2>
        <p>Flash 和 Pro 共用当前凭据。优才模型无需密钥。</p>
      </div>
      <div v-for="key in keys" :key="key.id" class="adm-row">
        <div class="adm-row-copy">
          <b>{{ key.name }}</b
          ><small>{{
            key.id === 'environment'
              ? config.environmentKeyConfigured
                ? '服务环境已提供密钥'
                : '使用 Pi 部署认证'
              : '后台保存的凭据'
          }}</small>
        </div>
        <span v-if="config.activeKey === key.id" class="adm-badge on">使用中</span>
        <button
          v-else
          class="adm-btn"
          :disabled="busy"
          @click="save('keys', { action: 'activate', id: key.id }, '已切换 API Key')"
        >
          启用
        </button>
        <button
          v-if="key.id !== 'environment' && key.id !== config.activeKey"
          class="adm-text danger"
          :disabled="busy"
          @click="remove(key.id)"
        >
          {{ confirmId === key.id ? '确认移除' : '移除' }}
        </button>
      </div>
      <form class="adm-form adm-inset" @submit.prevent="add">
        <h3>添加凭据</h3>
        <div class="adm-fields">
          <label>名称<input v-model.trim="name" required maxlength="64" placeholder="例如：业务主账号" /></label>
          <label
            >API Key<input
              v-model.trim="secret"
              type="password"
              required
              maxlength="2048"
              autocomplete="new-password"
              placeholder="输入新的 API Key"
          /></label>
        </div>
        <button class="adm-btn" :disabled="busy">添加密钥</button>
      </form>
    </div>
  </section>
</template>
