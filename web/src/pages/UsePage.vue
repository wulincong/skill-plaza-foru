<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { bySlug, catOf } from '../data/skills'
import { configOf, type TaskField } from '../data/useTaskConfigs'
import { checkHealth, type ApiState } from '../composables/useChatApi'
import { formatSize, uploadDemoFile, uploadFile, validateUploadFile } from '../composables/useUpload'
import { stashPendingFormTask } from '../composables/pendingTask'
import { CAREER_TEST_TEMPLATES } from '../data/careerTestTemplates'
import { DEMO_FILES } from '../data/demoFiles'
import { isTestEnv } from '../plazaEnv'
import { toast } from '../composables/toast'
import Icon from '../components/Icon.vue'

/* 「任务配置」表单页（智能体广场二级页）：结构化任务表单 + Mock 知识库选择。
   页面只负责把任务边界写清楚；提交后把提示词、标题、附件与上传沙箱会话
   交给在线对话页（/experience）挂载技能并运行。 */
const router = useRouter()

const props = defineProps<{ slug: string }>()
const slug = computed(() => props.slug)
const skill = computed(() => bySlug.get(slug.value)!)
const config = computed(() => configOf(skill.value.slug)!)
const catName = computed(() => catOf(skill.value.categoryId).name)

type FormValues = Record<string, string | string[]>
const form = reactive<FormValues>({})
const knowledge = ref<string[]>([])
const keyword = ref('')
const apiState = ref<ApiState>('checking')
const modelName = ref('')

/* ---------- 附件上传状态（声明需早于首次 resetForm 的 immediate watch） ---------- */
interface UploadItem { name: string; path: string; size: number }
const uploads = ref<UploadItem[]>([])
const uploading = ref(false)
const MAX_UPLOADS = 3
/** 内置演示附件本次访问是否已尝试过（移除后不再自动带回，换技能重置） */
const demoTried = ref(false)
const testTemplateId = ref('java')
const showTestTemplates = computed(() => isTestEnv() && skill.value.slug === 'career-guidance')
let uploadRevision = 0

/* ---------- 表单初始化 ---------- */
function resetForm() {
  for (const key of Object.keys(form)) delete form[key]
  for (const section of config.value.sections) {
    for (const field of section.fields) {
      form[field.id] = field.type === 'multi' ? [] : ''
    }
  }
  knowledge.value = config.value.knowledge.filter(item => item.default).map(item => item.id)
  keyword.value = ''
  uploads.value = []
  uploadRevision++
  testTemplateId.value = 'java'
  demoTried.value = false
}

/* 表单必须同步初始化：首次渲染时就会读取必填进度，不能等到 onMounted */
watch(() => skill.value.slug, () => {
  resetForm()
  /* 测试环境才带入演示默认值（PLAZA_ENV=test，见 web/.env）；
     「填入示例」按钮不受限，任何环境都可手动带入 */
  if (isTestEnv() && config.value.autoFillExample) applyExample()
  void probe()
}, { immediate: true })

/* ---------- 必填与进度 ---------- */
const requiredFields = computed(() => config.value.sections.flatMap(s => s.fields).filter(f => f.required))
const multi = (id: string): string[] => (Array.isArray(form[id]) ? (form[id] as string[]) : [])
const filled = (field: TaskField) => {
  const value = form[field.id]
  return field.type === 'multi' ? multi(field.id).length > 0 : Boolean(String(value ?? '').trim())
}
const completed = computed(() => requiredFields.value.filter(filled).length)
const percent = computed(() =>
  requiredFields.value.length ? Math.round((completed.value / requiredFields.value.length) * 100) : 0)

const summaryRows = computed(() =>
  config.value.sections.flatMap(s => s.fields)
    .map(field => ({ label: field.label, value: valueLabel(field) }))
    .filter(row => row.value)
    .slice(0, 3))

function valueLabel(field: TaskField) {
  return Array.isArray(form[field.id]) ? multi(field.id).join('、') : String(form[field.id] ?? '').trim()
}

const canRun = computed(() => apiState.value === 'ready' && !uploading.value)
const filteredKnowledge = computed(() => {
  const needle = keyword.value.trim().toLowerCase()
  if (!needle) return config.value.knowledge
  return config.value.knowledge.filter(item =>
    `${item.title} ${item.meta} ${item.tag}`.toLowerCase().includes(needle))
})

/* ---------- 交互 ---------- */
function applyExample() {
  for (const field of config.value.sections.flatMap(s => s.fields)) {
    const example = showTestTemplates.value
      ? CAREER_TEST_TEMPLATES.find(item => item.id === testTemplateId.value)!.values
      : config.value.example
    const value = example[field.id]
    form[field.id] = Array.isArray(value) ? [...value] : (value ?? '')
  }
}

function fillExample() {
  applyExample()
  toast('示例信息已填入，可继续修改')
}

function clearForm() {
  resetForm()
  toast('表单已恢复为初始状态')
}

function toggleKnowledge(id: string) {
  knowledge.value = knowledge.value.includes(id)
    ? knowledge.value.filter(item => item !== id)
    : [...knowledge.value, id]
}

function toggleOption(fieldId: string, option: string) {
  const current = (form[fieldId] as string[]) ?? []
  form[fieldId] = current.includes(option)
    ? current.filter(item => item !== option)
    : [...current, option]
}

function buildTaskTitle(): string {
  if (skill.value.slug === 'doc-translate') {
    return `${uploads.value[0]?.name.replace(/\.pdf$/i, '') ?? '文档'} · ${String(form.targetLanguage ?? '').trim()}译文`
  }
  const goal = String(form.goal ?? '').trim()
  const task = String(form.task ?? '').trim()
  if (skill.value.slug === 'career-guidance' && goal && task) {
    return `${goal}${task}分析`
  }
  if (goal && task) return `${goal}${task}`
  return `${skill.value.name}${task ? ` · ${task}` : ''}`
}

function buildPrompt(): string {
  const lines = config.value.sections.flatMap(s => s.fields)
    .map(field => (valueLabel(field) ? `- ${field.label}：${valueLabel(field)}` : ''))
    .filter(Boolean)
  const picked = config.value.knowledge
    .filter(item => knowledge.value.includes(item.id))
    .map(item => item.title)
  const fileList = uploads.value.map(item => item.name).join('、')
  return [
    `使用 $${skill.value.identifier} 完成以下任务：`,
    ...lines,
    ...(fileList ? [`- 已上传附件（随任务提供）：${fileList}`] : []),
    ...(config.value.knowledge.length ? [`- 参考知识库（前端 Mock 演示，本次运行未实际接入）：${picked.length ? picked.join('、') : '未选择'}`] : []),
    '',
    skill.value.slug === 'doc-translate'
      ? '请按所选范围翻译上传的 PDF；范围留空时翻译全文。生成译文 PDF 后只简短说明译文语言、页数和未覆盖项。'
      : '请先复述任务边界与缺失信息，再按该 SKILL 的方法推进。',
  ].join('\n')
}

const missingField = computed(() => requiredFields.value.find(field => !filled(field)))

/* ---------- 附件上传：文件落会话沙箱 uploads/，提交任务时随沙箱一起交接 ---------- */
const uploadSessionIds: Record<string, string> = {}
const sessionKey = (slug: string) => `pi:${slug}`

async function onPickFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' /* 允许连续选择同名文件 */
  if (!file) return
  if (uploads.value.length >= MAX_UPLOADS) { toast(`最多同时附 ${MAX_UPLOADS} 个文件`); return }
  const invalid = validateUploadFile(file)
  if (invalid) { toast(invalid); return }
  const required = config.value.requiredUpload
  if (required && !file.name.toLowerCase().endsWith(required.accept)) { toast(`请上传${required.label}`); return }
  if (apiState.value !== 'ready') { toast('需要先启动本地服务'); return }
  const key = sessionKey(skill.value.slug)
  uploading.value = true
  try {
    const uploaded = await uploadFile(file, uploadSessionIds[key])
    uploadSessionIds[key] = uploaded.sessionId
    uploads.value.push({ name: uploaded.name, path: uploaded.path, size: uploaded.size })
  } catch (exc) {
    toast(exc instanceof Error ? exc.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

function removeUpload(path: string) {
  uploads.value = uploads.value.filter(item => item.path !== path)
}

/* 内置演示附件（一键测试）：仅测试环境（PLAZA_ENV=test），后端就绪且附件区为空时自动上传一次 */
watch([apiState, () => skill.value.slug], () => {
  if (!isTestEnv() || apiState.value !== 'ready' || demoTried.value) return
  const demoKey = config.value.uploads?.find(u => u.demoFile)?.demoFile
  const demo = demoKey ? DEMO_FILES[demoKey] : undefined
  if (!demo || uploads.value.length) return
  demoTried.value = true
  const key = sessionKey(skill.value.slug)
  const revision = uploadRevision
  uploading.value = true
  void uploadDemoFile(demo.filename, demo.content, uploadSessionIds[key])
    .then(uploaded => {
      if (revision !== uploadRevision) return
      uploadSessionIds[key] = uploaded.sessionId
      uploads.value.push({ name: uploaded.name, path: uploaded.path, size: uploaded.size })
      toast(`已附带${uploaded.name}，可移除后换自己的文件`)
    })
    .catch(() => { /* 演示附件上传失败可通过应用模板重试 */ })
    .finally(() => { uploading.value = false })
})

/** 先上传到新沙箱，成功后一起替换表单与附件；失败保留当前输入。 */
async function applyTestTemplate() {
  if (!showTestTemplates.value || !canRun.value) return
  const template = CAREER_TEST_TEMPLATES.find(item => item.id === testTemplateId.value)!
  const demo = DEMO_FILES[template.demoFile]
  const target = skill.value.slug
  const key = sessionKey(target)
  const revision = ++uploadRevision
  uploading.value = true
  try {
    const uploaded = await uploadDemoFile(demo.filename, demo.content)
    if (revision !== uploadRevision || target !== skill.value.slug) return
    for (const oldKey of Object.keys(uploadSessionIds)) {
      if (oldKey.endsWith(`:${target}`)) delete uploadSessionIds[oldKey]
    }
    uploadSessionIds[key] = uploaded.sessionId
    applyExample()
    uploads.value = [{ name: uploaded.name, path: uploaded.path, size: uploaded.size }]
    demoTried.value = true
    toast(`已应用「${template.label}」，表单与附件已替换`)
  } catch (error) {
    toast(error instanceof Error ? error.message : '模板简历上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

/* ---------- 提交：任务交接给在线对话页运行 ---------- */
function run() {
  if (apiState.value !== 'ready') { toast('需要先启动本地服务'); return }
  if (uploading.value) return
  if (missingField.value) {
    toast(`请先填写「${missingField.value.label}」`)
    return
  }
  const required = config.value.requiredUpload
  if (required && !uploads.value.some(item => item.name.toLowerCase().endsWith(required.accept))) {
    toast(`请先上传${required.label}`)
    return
  }
  stashPendingFormTask({
    slug: skill.value.slug,
    prompt: buildPrompt(),
    taskTitle: buildTaskTitle(),
    attachments: uploads.value.length
      ? uploads.value.map(item => ({ name: item.name, path: item.path }))
      : undefined,
    /* 沿用上传沙箱：在线对话页以同一会话续跑，引擎才能读到附件 */
    sessionId: uploadSessionIds[sessionKey(skill.value.slug)],
  })
  void router.push({ name: 'experience' })
}

async function probe() {
  apiState.value = 'checking'
  const result = await checkHealth()
  if (result.ok) {
    apiState.value = 'ready'
    modelName.value = result.model ?? ''
    return
  }
  apiState.value = result.reason === 'nokey' ? 'nokey' : 'offline'
}

const statusText = computed(() => {
  if (apiState.value === 'checking') return '正在检查 API'
  if (apiState.value === 'ready') {
    const model = modelName.value
    return `API 已就绪${model ? ' · ' + model : ''}`
  }
  if (apiState.value === 'nokey') return '未读到模型配置'
  return '需要启动本地服务'
})

const engineHint = '确认 Pi 所选模型的凭据已配置（如 DEEPSEEK_API_KEY），或将其写入 web/.env 后重启服务。'

</script>

<template>
  <section class="page page-use">
    <div class="wrap">
      <RouterLink class="use-back" :to="{ name: 'skills' }">
        <Icon name="back" :size="14" /> 返回智能体广场
      </RouterLink>

      <header class="use-head">
        <span class="use-mark" :data-cat="skill.categoryId"><Icon :name="skill.categoryId" :size="22" /></span>
        <div class="use-head-copy">
          <p class="use-kicker">{{ config.eyebrow }} · {{ catName }}</p>
          <h1 class="use-name">{{ skill.name }}</h1>
          <p class="use-lead">{{ config.lead }}</p>
        </div>
        <div class="use-head-side">
          <span class="use-api" :class="`is-${apiState}`"><i></i>{{ statusText }}</span>
          <RouterLink class="use-detail-link" :to="{ name: 'detail', params: { slug: skill.slug }, query: { from: 'use' } }">
            查看能力详情<Icon name="ext" :size="13" />
          </RouterLink>
        </div>
      </header>

      <aside v-if="showTestTemplates" class="use-test-templates" aria-label="开发侧测试模板">
        <div>
          <strong>开发侧 · 测试模板</strong>
          <p>合成示例。应用后替换表单和全部附件；已有运行记录保留。</p>
        </div>
        <label class="use-select">
          <select v-model="testTemplateId" aria-label="选择测试模板" :disabled="uploading">
            <option v-for="item in CAREER_TEST_TEMPLATES" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
          <Icon name="chev-down" :size="14" />
        </label>
        <button type="button" class="btn btn-quiet" :disabled="!canRun" @click="applyTestTemplate">
          {{ uploading ? '上传中…' : '应用模板' }}
        </button>
      </aside>

      <ol class="use-steps">
        <li :class="{ 'is-on': completed > 0 }"><b>1</b>配置任务</li>
        <li :class="{ 'is-on': knowledge.length > 0 }"><b>2</b>选择知识库</li>
        <li :class="{ 'is-on': !missingField }"><b>3</b>提交任务</li>
      </ol>

      <p v-if="apiState === 'offline'" class="use-setup">
        <strong>在线运行需要本地后端。</strong>
        在 <code>web/</code> 目录执行 <code>npm run server</code> 后刷新页面；表单与 Mock 知识库仍可正常预览。
        <button type="button" class="text-btn" @click="probe">重新检查</button>
      </p>
      <p v-else-if="apiState === 'nokey'" class="use-setup">
        <strong>本地服务已启动，但没有读到模型配置。</strong>
        {{ engineHint }}
        <button type="button" class="text-btn" @click="probe">重新检查</button>
      </p>

      <div class="use-layout">
        <main class="use-builder">
          <form id="skill-task-form" class="use-form" @submit.prevent="run">
            <section v-for="section in config.sections" :key="section.number" class="use-section">
              <header class="use-section-head">
                <span class="use-section-no">{{ section.number }}</span>
                <div>
                  <h2>{{ section.title }}</h2>
                  <p>{{ section.description }}</p>
                </div>
              </header>

              <div class="use-fields">
                <template v-for="field in section.fields" :key="field.id">
                  <fieldset v-if="field.type === 'choice' || field.type === 'multi'"
                    class="use-field" :class="{ 'is-full': field.span === 'full' }">
                    <legend>{{ field.label }}<em v-if="field.required">必填</em></legend>
                    <div class="use-options">
                      <label v-for="option in field.options" :key="option" class="use-option"
                        :class="{ 'is-on': field.type === 'multi'
                          ? multi(field.id).includes(option)
                          : form[field.id] === option }">
                        <input v-if="field.type === 'multi'" type="checkbox" :value="option"
                          :checked="multi(field.id).includes(option)"
                          @change="toggleOption(field.id, option)" />
                        <input v-else type="radio" :name="field.id" :value="option"
                          :checked="form[field.id] === option" @change="form[field.id] = option" />
                        <span>{{ option }}</span>
                      </label>
                    </div>
                    <small v-if="field.help">{{ field.help }}</small>
                  </fieldset>

                  <label v-else-if="field.type === 'select'"
                    class="use-field" :class="{ 'is-full': field.span === 'full' }">
                    <span class="use-label">{{ field.label }}<em v-if="field.required">必填</em></span>
                    <span class="use-select">
                      <select :value="form[field.id] as string" @change="form[field.id] = ($event.target as HTMLSelectElement).value">
                        <option value="" disabled>请选择</option>
                        <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
                      </select>
                      <Icon name="chev-down" :size="14" />
                    </span>
                    <small v-if="field.help">{{ field.help }}</small>
                  </label>

                  <label v-else-if="field.type === 'textarea'"
                    class="use-field" :class="{ 'is-full': field.span === 'full' }">
                    <span class="use-label">{{ field.label }}<em v-if="field.required">必填</em></span>
                    <textarea class="use-textarea" rows="4" maxlength="8000" :placeholder="field.placeholder"
                      :value="form[field.id] as string" @input="form[field.id] = ($event.target as HTMLTextAreaElement).value"></textarea>
                    <small v-if="field.help">{{ field.help }}</small>
                  </label>

                  <label v-else class="use-field" :class="{ 'is-full': field.span === 'full' }">
                    <span class="use-label">{{ field.label }}<em v-if="field.required">必填</em></span>
                    <input class="use-input" type="text" maxlength="500" :placeholder="field.placeholder"
                      :value="form[field.id] as string" @input="form[field.id] = ($event.target as HTMLInputElement).value" />
                    <small v-if="field.help">{{ field.help }}</small>
                  </label>
                </template>
              </div>
            </section>

            <section v-if="config.uploads?.length" class="use-section">
              <header class="use-section-head">
                <span class="use-section-no">附</span>
                <div>
                  <h2>上传材料</h2>
                  <p>文件进入本次运行的沙箱目录，提交任务时随沙箱一起交给在线对话。</p>
                </div>
              </header>
              <div class="use-fields">
                <div v-for="uf in config.uploads" :key="uf.id" class="use-field is-full">
                  <span class="use-label">{{ uf.label }}</span>
                  <div class="use-upload">
                    <label class="use-upload-btn" :class="{ 'is-busy': uploading }">
                      <Icon name="paperclip" :size="15" />
                      <span>{{ uploading ? '上传中…' : '选择文件' }}</span>
                      <input type="file" hidden :accept="uf.accept"
                        :disabled="apiState !== 'ready' || uploading" @change="onPickFile" />
                    </label>
                    <div v-if="uploads.length" class="use-upload-files">
                      <span v-for="f in uploads" :key="f.path" class="use-file-chip">
                        <Icon name="file" :size="12" />{{ f.name }} · {{ formatSize(f.size) }}
                        <button type="button" class="use-file-del" :aria-label="`移除 ${f.name}`"
                          @click="removeUpload(f.path)"><Icon name="x" :size="11" /></button>
                      </span>
                    </div>
                    <small v-if="uf.help">{{ uf.help }}</small>
                    <small v-if="apiState !== 'ready'" class="use-upload-off">
                      启动本地服务（web/ 下 npm run server）后可上传文件。</small>
                  </div>
                </div>
              </div>
            </section>
          </form>
        </main>

        <aside class="use-side">
          <section v-if="config.knowledge.length" class="use-side-card use-knowledge">
            <header class="use-side-head">
              <div>
                <span>知识库</span>
                <h2>选择参考资料</h2>
              </div>
              <b>Mock</b>
            </header>
            <p class="use-side-note">选择本次允许 SKILL 使用的资料范围。当前仅演示前端状态，不会上传或读取真实文档。</p>
            <label class="use-kb-search">
              <Icon name="search" :size="15" />
              <input v-model="keyword" type="search" placeholder="搜索知识库" aria-label="搜索知识库" />
            </label>
            <div class="use-kb-list">
              <label v-for="item in filteredKnowledge" :key="item.id" class="use-kb-item"
                :class="{ 'is-on': knowledge.includes(item.id) }">
                <input type="checkbox" :checked="knowledge.includes(item.id)" @change="toggleKnowledge(item.id)" />
                <span class="use-kb-check"><Icon name="check" :size="11" /></span>
                <span class="use-kb-copy">
                  <strong>{{ item.title }}</strong>
                  <small>{{ item.meta }}</small>
                </span>
                <em>{{ item.tag }}</em>
              </label>
              <p v-if="!filteredKnowledge.length" class="use-kb-empty">没有匹配的知识库</p>
            </div>
            <button type="button" class="use-kb-add" @click="toast('当前为前端 Mock，真实知识库接入将在下一阶段完成')">添加知识库</button>
          </section>

          <section class="use-side-card use-run">
            <div class="use-run-progress">
              <span>已完成 {{ completed }} / {{ requiredFields.length }} 项必填信息</span>
              <b v-if="config.knowledge.length">已选 {{ knowledge.length }} 个知识库</b>
            </div>
            <div class="use-track" role="progressbar" aria-label="任务信息完成度"
              aria-valuemin="0" aria-valuemax="100" :aria-valuenow="percent"><i :style="{ width: percent + '%' }"></i></div>
            <h3>执行摘要</h3>
            <ul class="use-summary">
              <li v-for="row in summaryRows" :key="row.label"><span>{{ row.label }}</span><strong>{{ row.value }}</strong></li>
              <li v-if="!summaryRows.length" class="is-empty">填写任务信息后，这里会生成执行摘要。</li>
            </ul>
            <p class="use-output"><span>预计产出</span><strong>{{ config.output }}</strong></p>
            <!-- 按钮在表单外的侧栏中，靠 form 属性关联提交 -->
            <button type="submit" form="skill-task-form" class="use-run-btn" :disabled="!canRun">
              提交任务，转在线对话<Icon name="arrow" :size="15" />
            </button>
            <div class="use-run-sub">
              <button type="button" class="use-run-quiet" :disabled="uploading" @click="fillExample">填入示例</button>
              <button type="button" class="use-run-quiet" :disabled="uploading" @click="clearForm">重置表单</button>
            </div>
            <small class="use-run-note">提交前请确认资料授权范围，不要填写敏感个人信息。提交后进入在线对话运行，并可在那里继续追问。</small>
          </section>
        </aside>
      </div>
    </div>
  </section>
</template>
