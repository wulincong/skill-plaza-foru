import { createHash, randomBytes, randomUUID, scryptSync, timingSafeEqual } from 'node:crypto'
import { chmodSync, mkdirSync, statSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { DatabaseSync } from 'node:sqlite'
import { piModelRef, piThinkingLevel } from './piRunner.ts'
import { GENERAL_SKILL_ID, SKILL_PROMPTS } from './skills.ts'

export class InputError extends Error {
  status: number
  constructor(message: string, status = 400) {
    super(message)
    this.status = status
  }
}

export const SESSION_SECONDS = 8 * 3600
export const thinkingLevels = ['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']
const deployModel = piModelRef()
export const models = [
  { id: 'deepseek-flash', name: 'DeepSeek Flash', provider: 'deepseek', modelId: 'deepseek-flash' },
  { id: 'deepseek-pro', name: 'DeepSeek Pro', provider: 'deepseek', modelId: 'deepseek-v4-pro' },
  { id: 'youcai', name: '优才之路产教融合大模型', provider: 'youcai', modelId: 'youcai' },
]
if (!models.some((m) => m.provider === deployModel.provider && m.modelId === deployModel.modelId)) {
  models.push({ id: 'deployment', name: deployModel.modelId, ...deployModel })
}
const defaultEndpoint =
  process.env.YOUCAI_BASE_URL?.trim() || 'https://u496025-7845e5610890.bjb2.seetacloud.com:8443/v1'

interface Settings {
  defaultModel: string
  allowModelChoice: boolean
  thinking: string
  reportThinking: string
  youcaiEndpoint: string
  timeoutMs: number
  installedTimeoutMs: number
  idleMs: number
}
interface KeyProfile {
  id: string
  name: string
  secret: string
}
interface Configuration {
  revision: number
  runtimeRevision: number
  settings: Settings
  disabledSkills: string[]
  activeKey: string
  keys: KeyProfile[]
}

function defaults(): Configuration {
  return {
    revision: 0,
    runtimeRevision: 0,
    disabledSkills: [],
    activeKey: 'environment',
    keys: [],
    settings: {
      defaultModel: models.find((m) => m.provider === deployModel.provider && m.modelId === deployModel.modelId)!
        .id,
      allowModelChoice: true,
      thinking: piThinkingLevel(),
      reportThinking: process.env.WECHAT_REPORT_THINKING?.trim() || '',
      youcaiEndpoint: defaultEndpoint,
      timeoutMs: 600_000,
      installedTimeoutMs: Number(process.env.RUN_TIMEOUT_MS) || 1_200_000,
      idleMs: Number(process.env.PI_IDLE_MS) || 1_800_000,
    },
  }
}

const initialConfiguration = defaults()

function textValue(value: unknown, max: number, label: string) {
  if (typeof value !== 'string' || !value.trim() || value.length > max || /[\x00-\x1f\x7f]/.test(value))
    throw new InputError('无效的' + label)
  return value.trim()
}
function validateSettings(body: any): Settings {
  if (
    !body ||
    !models.some((m) => m.id === body.defaultModel) ||
    !thinkingLevels.includes(body.thinking) ||
    (body.reportThinking !== '' && !thinkingLevels.includes(body.reportThinking)) ||
    typeof body.allowModelChoice !== 'boolean'
  )
    throw new InputError('模型或思考档位无效')
  const youcaiEndpoint = textValue(body.youcaiEndpoint, 512, '服务地址')
  let url: URL
  try {
    url = new URL(youcaiEndpoint)
  } catch {
    throw new InputError('请输入完整的模型服务地址')
  }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new InputError('请使用不含凭据和查询参数的 HTTP(S) 地址')
  }
  for (const field of ['timeoutMs', 'installedTimeoutMs', 'idleMs']) {
    if (!Number.isSafeInteger(body[field]) || body[field] < 1000 || body[field] > 86_400_000) {
      throw new InputError('时限必须在 1 秒至 24 小时之间')
    }
  }
  return {
    defaultModel: body.defaultModel,
    allowModelChoice: body.allowModelChoice,
    thinking: body.thinking,
    reportThinking: body.reportThinking,
    timeoutMs: body.timeoutMs,
    installedTimeoutMs: body.installedTimeoutMs,
    idleMs: body.idleMs,
    youcaiEndpoint,
  }
}

export function skillEnabled(config: Configuration, id: unknown): id is string {
  return typeof id === 'string' && Object.hasOwn(SKILL_PROMPTS, id) && !config.disabledSkills.includes(id)
}

export function publicConfig(config: Configuration) {
  const { keys, runtimeRevision, ...fields } = config
  return {
    ...fields,
    keys: keys.map(({ id, name }) => ({ id, name })),
    models,
    thinkingLevels,
    environmentKeyConfigured: Boolean(process.env.DEEPSEEK_API_KEY),
  }
}

const digest = (token: string) => createHash('sha256').update(token).digest('hex')

export class AdminStore {
  db: DatabaseSync
  constructor() {
    const directory = process.env.ADMIN_STATE_DIR || join(homedir(), '.local/state/skill-plaza/admin')
    mkdirSync(directory, { recursive: true, mode: 0o700 })
    if (process.platform !== 'win32' && (statSync(directory).mode & 0o077) !== 0) {
      throw new Error('ADMIN_STATE_DIR 必须是服务账号专用的 0700 目录')
    }
    const file = join(directory, 'control.sqlite')
    this.db = new DatabaseSync(file)
    chmodSync(file, 0o600)
    this.db.exec(`
      PRAGMA busy_timeout=5000;
      CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY CHECK(id=1), username TEXT, salt TEXT, hash TEXT);
      CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, expires INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS configuration (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
    `)
  }
  get config(): Configuration {
    const row = this.db.prepare('SELECT data FROM configuration WHERE id=1').get()
    if (!row) return structuredClone(initialConfiguration)
    const config: Configuration = JSON.parse(String(row.data))
    config.settings = { ...initialConfiguration.settings, ...config.settings }
    // The deployment route may disappear when PI_MODEL changes to a built-in model.
    if (!models.some((model) => model.id === config.settings.defaultModel))
      config.settings.defaultModel = initialConfiguration.settings.defaultModel
    return config
  }
  save(section: string, body: any) {
    const c = this.config
    if (body.revision !== c.revision) throw new InputError('配置已在其他页面更新，请刷新后重试', 409)
    if (section === 'skills') {
      if (
        typeof body.id !== 'string' ||
        !Object.hasOwn(SKILL_PROMPTS, body.id) ||
        body.id === GENERAL_SKILL_ID ||
        typeof body.enabled !== 'boolean'
      )
        throw new InputError('无效的技能或发布状态')
      c.disabledSkills = c.disabledSkills.filter((id) => id !== body.id)
      if (!body.enabled) c.disabledSkills.push(body.id)
    } else if (section === 'settings') {
      const next = validateSettings(body.settings)
      if (
        next.thinking !== c.settings.thinking ||
        next.reportThinking !== c.settings.reportThinking ||
        next.youcaiEndpoint !== c.settings.youcaiEndpoint
      )
        c.runtimeRevision++
      c.settings = next
    } else if (section === 'keys' && body.action === 'add') {
      const name = textValue(body.name, 64, '密钥名称')
      const secret = textValue(body.secret, 2048, 'API Key')
      if (c.keys.length >= 30 || c.keys.some((k) => k.name === name))
        throw new InputError('名称重复或密钥数量已达上限')
      c.keys.push({ id: randomUUID(), name, secret })
    } else if (section === 'keys' && body.action === 'activate') {
      if (body.id !== 'environment' && !c.keys.some((k) => k.id === body.id)) throw new InputError('密钥不存在')
      if (c.activeKey !== body.id) c.runtimeRevision++
      c.activeKey = body.id
    } else if (section === 'keys' && body.action === 'delete') {
      if (body.id === c.activeKey || !c.keys.some((k) => k.id === body.id))
        throw new InputError('请先切换正在使用的凭据，或检查密钥是否存在')
      c.keys = c.keys.filter((k) => k.id !== body.id)
    } else throw new InputError('未知配置项')
    c.revision++
    this.db.prepare('INSERT OR REPLACE INTO configuration VALUES (1,?)').run(JSON.stringify(c))
    return publicConfig(c)
  }
  verify(username: unknown, password: unknown) {
    if (typeof password !== 'string' || Buffer.byteLength(password) > 512) return false
    const row = this.db.prepare('SELECT * FROM account WHERE id=1').get()
    const hash = scryptSync(password, String(row?.salt ?? 'unconfigured-account'), 64)
    return Boolean(row && timingSafeEqual(hash, Buffer.from(String(row.hash), 'hex')) && username === row.username)
  }
  setAccount(username: string, password: string) {
    const name = textValue(username, 64, '账号名')
    if (typeof password !== 'string' || password.length < 12 || Buffer.byteLength(password) > 512)
      throw new InputError('密码至少 12 个字符，最多 512 字节')
    const salt = randomBytes(24).toString('hex')
    const hash = scryptSync(password, salt, 64).toString('hex')
    this.db.exec('BEGIN IMMEDIATE')
    try {
      this.db.prepare('INSERT OR REPLACE INTO account VALUES (1,?,?,?)').run(name, salt, hash)
      this.db.exec('DELETE FROM sessions; COMMIT')
    } catch (error) {
      this.db.exec('ROLLBACK')
      throw error
    }
  }
  createSession() {
    this.db.prepare('DELETE FROM sessions WHERE expires<=?').run(Date.now())
    const token = randomBytes(32).toString('hex')
    this.db.prepare('INSERT INTO sessions VALUES (?,?)').run(digest(token), Date.now() + SESSION_SECONDS * 1000)
    return token
  }
  username(token: string) {
    return this.db
      .prepare('SELECT username FROM account JOIN sessions ON account.id=1 WHERE token=? AND expires>?')
      .get(digest(token), Date.now())?.username as string | undefined
  }
  logout(token: string) {
    this.db.prepare('DELETE FROM sessions WHERE token=?').run(digest(token))
  }
}
