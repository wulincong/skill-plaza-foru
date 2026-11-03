<script setup lang="ts">
import { ref } from 'vue'
import { CHECKED_ON, SKILLS } from '../data/skills'
import Icon from '../components/Icon.vue'
import Codebox from '../components/Codebox.vue'

/* 多 AI 工具接入：每个工具给出接入步骤与验证方式；安装提示词全工具通用 */
const INSTALL_PROMPT = '根据 https://github.com/wulincong/skill-plaza-foru 的 wlc 分支安装智能体搭子精选。'

interface ToolGuide {
  id: string
  name: string
  vendor: string
  intro: string
  steps: string[]
  verify: string
  tip?: string
}

const TOOLS: ToolGuide[] = [
  {
    id: 'codex',
    name: 'Codex',
    vendor: 'OpenAI',
    intro: 'OpenAI 的编码智能体（CLI / IDE 均可），能联网读取 GitHub 仓库，自动安装体验最好。',
    steps: [
      '复制下方安装提示词',
      '在 Codex 对话框中粘贴并发送，它会从 GitHub 拉取完整目录',
      '完成后让它列出已安装的 SKILL，确认安装成功',
    ],
    verify: '# 安装完成后，在 Codex 中输入：\n列出我已安装的 SKILL，并说明各自的用途\n# → 能看到 智能体搭子的全部 SKILL 即安装成功',
  },
  {
    id: 'claude-code',
    name: 'Claude Code',
    vendor: 'Anthropic',
    intro: 'Anthropic 的终端智能体，支持 SKILL 目录约定；发提示词或手动放置目录都可以。',
    steps: [
      '方式一：复制安装提示词，在 claude 会话中粘贴发送',
      '方式二：手动安装——把仓库克隆到 ~/.claude/skills/ 目录',
      '新开会话，询问已安装的 SKILL 确认',
    ],
    verify: '# 手动安装（可选）：\ngit clone --branch wlc --recurse-submodules https://github.com/wulincong/skill-plaza-foru ~/.claude/skills/skill-plaza-foru\n\n# 新会话中验证：\n我有哪些 SKILL 可以用？',
  },
  {
    id: 'cursor',
    name: 'Cursor',
    vendor: 'Anysphere',
    intro: 'AI 代码编辑器，Agent 模式可以联网访问仓库并执行命令。',
    steps: [
      '打开 Cursor 的 Agent 对话框',
      '粘贴安装提示词并发送，允许其访问网络与执行命令',
      '完成后让 Cursor 列出已安装的 SKILL',
    ],
    verify: '# 在 Agent 对话框中输入：\n列出刚安装的 智能体搭子 SKILL，以及每个的用途\n# → 全部可见即安装成功',
  },
  {
    id: 'workbuddy',
    name: 'WorkBuddy',
    vendor: '',
    intro: '支持技能扩展的 AI 工作台，对话中直接安装。',
    steps: [
      '复制下方安装提示词',
      '在 WorkBuddy 对话框中粘贴并发送',
      '完成后询问已安装的 SKILL 确认',
    ],
    verify: '# 在对话框中输入：\n我装了哪些 SKILL？分别适合什么场景？\n# → 能逐个说明即安装成功',
  },
  {
    id: 'doubao',
    name: '豆包',
    vendor: '字节跳动',
    intro: '字节跳动旗下 AI 助手，桌面版具备联网与文件能力时可用。',
    steps: [
      '复制下方安装提示词',
      '在豆包对话框中粘贴并发送',
      '完成后询问已安装的 SKILL 确认',
    ],
    verify: '# 在对话框中输入：\n根据 智能体搭子 的安装结果，列出可用的 SKILL\n# → 能看到完整清单即安装成功',
    tip: '若豆包无法访问 GitHub，可先手动下载仓库，再让它把文件放入技能目录。',
  },
  {
    id: 'general',
    name: '其他 AI 工具',
    vendor: '',
    intro: '任何能联网读取 GitHub、可按指令执行安装的对话式智能体都能使用。',
    steps: [
      '复制下方安装提示词',
      '粘贴到该工具的对话框发送',
      '若工具不支持自动拉取仓库，可手动下载后放入它的技能目录',
    ],
    verify: '# 通用验证方式：\n列出你当前可用的 SKILL\n# → 与 智能体搭子 清单一致即安装成功',
  },
]

const activeTool = ref(TOOLS[0].id)
const tool = () => TOOLS.find(t => t.id === activeTool.value) ?? TOOLS[0]
</script>

<template>
  <section class="page">
    <div class="wrap wrap-read" id="guide-content">
      <header class="guide-head">
        <h1>使用指南</h1>
        <p>两种用法：在「在线运行」工作台里跑一次，或把 SKILL 装进你的 AI 工具长期用。页面只提供入口和提示词，执行在你的 AI 工具里完成。</p>
      </header>

      <section class="block" v-reveal>
        <h2 class="block-title">先跑一次，再决定要不要装</h2>
        <p class="block-note">工作台适合快速拿到结果；装进 AI 工具适合长期反复使用。</p>

        <div class="rail">
          <div class="rail-item">
            <span class="rail-no">01</span>
            <div class="rail-body">
              <h3 class="rail-title">在线运行（不用安装）</h3>
              <p class="rail-desc">
                进「在线运行」选一个 SKILL，填结构化任务信息、勾选可参考的知识库，点「开始运行」即可拿到结果。
                运行通过本机 <code>python3 server.py</code> 代理调用模型，接口密钥只留在本机，不会写进页面或仓库。
              </p>
              <RouterLink class="text-btn" to="/use">打开工作台 →</RouterLink>
            </div>
          </div>
          <div class="rail-item">
            <span class="rail-no">02</span>
            <div class="rail-body">
              <h3 class="rail-title">安装到 AI 工具（长期使用）</h3>
              <p class="rail-desc">
                复制安装提示词发给你的 AI 工具，它会从 GitHub 拉取完整目录。装好之后，
                <code>references</code>、<code>scripts</code>、<code>assets</code> 等资源都能用上，能力比页面里更完整。
              </p>
            </div>
          </div>
        </div>
      </section>

      <section class="block" v-reveal>
        <h2 class="block-title">三步装进你的 AI 工具</h2>
        <p class="block-note">第一步全局通用，第二步按工具选择，第三步验证是否成功。</p>

        <div class="callout">
          <strong>保留仓库完整目录。</strong>这些 SKILL 依赖 <code>references</code>、<code>scripts</code>、<code>assets</code>、<code>examples</code> 或 <code>requirements.txt</code>。只复制 <code>SKILL.md</code> 会丢掉执行规则、脚本、模板和示例，装完看着成功但跑不起来。详情页的安装提示词里已经写明了这一条。
        </div>

        <div class="tool-tabs" role="tablist" aria-label="选择 AI 工具">
          <button
            v-for="t in TOOLS"
            :key="t.id"
            type="button"
            class="chip"
            :class="{ 'is-on': t.id === activeTool }"
            :aria-pressed="t.id === activeTool"
            role="tab"
            :aria-selected="t.id === activeTool"
            @click="activeTool = t.id"
          >{{ t.name }}</button>
        </div>

        <div class="tool-panel" role="tabpanel">
          <p class="tool-intro">
            <strong>{{ tool().name }}</strong>
            <span v-if="tool().vendor" class="tool-vendor">{{ tool().vendor }}</span>
          </p>
          <p class="tool-desc">{{ tool().intro }}</p>

          <ol class="olist">
            <li v-for="(step, i) in tool().steps" :key="i">{{ step }}</li>
          </ol>

          <div class="rail-item">
            <div class="rail-body">
              <Codebox label="安装提示词（全工具通用）" :text="INSTALL_PROMPT" message="安装提示词已复制" :primary="true" />
            </div>
          </div>

          <div class="rail-item">
            <div class="rail-body">
              <Codebox label="验证" :text="tool().verify" message="验证命令已复制" />
            </div>
          </div>

          <p v-if="tool().tip" class="tool-tip"><Icon name="note" :size="15" />{{ tool().tip }}</p>
        </div>
      </section>

      <section class="block" v-reveal>
        <h2 class="block-title">常见问题</h2>
        <div class="faq">
          <details>
            <summary>在线运行和安装到 AI 工具有什么区别？<Icon name="chev-down" :size="16" /></summary>
            <p>在线运行适合在这个页面里快速完成一次文本任务，所见即所得；安装到 AI 工具后，SKILL 还能用到仓库里的 <code>references</code>、<code>scripts</code>、<code>assets</code>、<code>examples</code> 等完整资源，适合长期反复使用。</p>
          </details>
          <details>
            <summary>直接运行为什么要启动本地服务？<Icon name="chev-down" :size="16" /></summary>
            <p>浏览器只访问本机 <code>/api/chat</code>，由 Python 服务带着密钥去请求模型接口。密钥不写进页面文件，也不进仓库，所以不会随页面一起公开。未启动服务时，工作台的表单和知识库选择仍可正常预览。</p>
          </details>
          <details>
            <summary>这个页面需要 npm 或联网吗？<Icon name="chev-down" :size="16" /></summary>
            <p>目录、详情和工作台表单都能离线浏览；只有点「开始运行」时才需要本地服务与网络。构建后的静态产物可直接部署到静态托管，不需要后端。</p>
          </details>
          <details>
            <summary>支持哪些 AI 工具？<Icon name="chev-down" :size="16" /></summary>
            <p>Codex、Claude Code、Cursor、WorkBuddy、豆包等能联网读取 GitHub 的对话式智能体都已给出接入步骤（见上方工具列表）。其他工具只要能按提示词联网拉取仓库，按"其他 AI 工具"的通用方式尝试即可；也可以手动把仓库放进该工具的技能目录。</p>
          </details>
          <details>
            <summary>能从页面直接执行 SKILL 吗？<Icon name="chev-down" :size="16" /></summary>
            <p>「在线运行」工作台通过本机代理由模型按 SKILL 规则完成一次任务；完整的工具能力（读仓库脚本、处理附件等）仍需装进你的 AI 工具后运行。页面本身不保存账号、收藏或评论。</p>
          </details>
          <details>
            <summary>提示词里的 <code>$名字</code> 是什么？<Icon name="chev-down" :size="16" /></summary>
            <p>是 SKILL 的调用名，用来告诉 AI 工具这次调用哪一个。它和详情页标题下的 <code>identifier</code> 是同一个字符串。</p>
          </details>
          <details>
            <summary>依赖、费用和许可去哪里确认？<Icon name="chev-down" :size="16" /></summary>
            <p>以各 SKILL 仓库的发布资料为准。页面上的依赖和边界都抄自仓库说明，不额外推断版本、价格或授权范围。</p>
          </details>
          <details>
            <summary>为什么没有评分、下载量和更新日期？<Icon name="chev-down" :size="16" /></summary>
            <p>这些数据没有可靠来源，页面不生成推测值，所以也不提供按更新时间的排序。清单最后核对时间是 {{ CHECKED_ON }}。</p>
          </details>
        </div>
      </section>

      <section class="block" v-reveal>
        <h2 class="block-title">来源与边界</h2>
        <ul class="src-list">
          <li><Icon name="note" :size="16" /><span>{{ SKILLS.length }} 个条目都指向公开 GitHub 仓库，仓库可匿名读取。</span></li>
          <li><Icon name="note" :size="16" /><span>「在线运行」的模型密钥由本机服务读取，不进页面文件、不进仓库。</span></li>
          <li><Icon name="note" :size="16" /><span>知识库为 Mock 选择，仅演示前端状态，不上传也不读取真实文档。</span></li>
          <li><Icon name="note" :size="16" /><span>页面不执行仓库脚本，不提供账号系统；模型调用只走本机代理。</span></li>
          <li><Icon name="note" :size="16" /><span>不生成推测的日期、版本、评分或下载量。</span></li>
          <li><Icon name="note" :size="16" /><span>清单最后核对：{{ CHECKED_ON }}。条目有变动会重新核对。</span></li>
        </ul>
      </section>

      <div class="detail-foot">
        <RouterLink class="btn btn-quiet" to="/skills">回到全部 SKILL</RouterLink>
      </div>
    </div>
  </section>
</template>
