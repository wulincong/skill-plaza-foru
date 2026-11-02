import { createHash } from 'node:crypto'

export const VERSION = 'talent-query-engine/1.2.0'
export class QueryError extends Error {
  constructor(code, message, details = {}) { super(message); this.code = code; this.details = details }
}
export const fail = (code, message, details) => { throw new QueryError(code, message, details) }
export const canonical = value => JSON.stringify(sortObject(value))
function sortObject(value) {
  if (Array.isArray(value)) return value.map(sortObject)
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, sortObject(value[key])]))
  return value
}
export const hash = value => createHash('sha256').update(typeof value === 'string' ? value : canonical(value)).digest('hex')
export const now = () => new Date().toISOString()
export function object(value, allowed, label) {
  if (!value || Array.isArray(value) || typeof value !== 'object') fail('INVALID_REQUEST', `${label} 必须为对象`)
  for (const key of Object.keys(value)) if (!allowed.includes(key)) fail('INVALID_REQUEST', `${label} 不支持字段：${key}`)
  return value
}
export function integer(value, low, high, label) {
  if (!Number.isSafeInteger(value) || value < low || value > high) fail('INVALID_REQUEST', `${label} 必须为 ${low}–${high} 的整数`)
  return value
}
export function textValue(value, max, label) {
  if (typeof value !== 'string' || !value.trim() || value.length > max || /[\x00-\x1f\x7f]/.test(value)) fail('INVALID_REQUEST', `${label} 必须为 1–${max} 字符的文本`)
  return value.trim()
}
export function terms(value = [], label = '关键词') {
  if (!Array.isArray(value) || value.length > 8) fail('INVALID_REQUEST', `${label} 最多 8 项`)
  return [...new Set(value.map(v => textValue(v, 60, label)))].sort()
}
export const ENUMS = {
  education: { BUXIAN: '学历不限', CHUZHONGJIYIXIA: '初中及以下', GAOZHONG: '高中', 'ZHONGZHUAN/ZHONGJI': '中专/中技', GAOZHI: '高职', DAZHUAN: '大专', BENKE: '本科', SHUOSHI: '硕士', BOSHI: '博士' },
  experience: { BUXIAN: '经验不限', ON_CAMPUS: '在校生', GRADUATING: '应届生', LESS_THAN_1: '1年以内', LESS_THAN_3: '3年以内', LESS_THAN_5: '5年以内', LESS_THAN_10: '10年以内', MORE_THAN_10: '10年以上' },
  jobType: { SHEZHAO: '社招', XIAOZHAO: '校招', SHIXI: '实习', JIANZHI: '兼职' },
}
export const METRICS = {
  'positions.count': { kind: 'scalar', unit: 'job_records', description: '去重岗位主键记录数' },
  'companies.count': { kind: 'scalar', unit: 'companies', description: '有效企业 ID 去重数；单列企业 ID 缺失量' },
  'education.distribution': { kind: 'distribution', unit: 'job_records', dimension: 'education', description: '原始学历枚举构成' },
  'experience.distribution': { kind: 'distribution', unit: 'job_records', dimension: 'experience', description: '经验上界枚举构成' },
  'jobType.distribution': { kind: 'distribution', unit: 'job_records', dimension: 'jobType', description: '招聘类型构成，与实习关键词/应届经验分开' },
  'source.distribution': { kind: 'distribution', unit: 'job_records', dimension: 'source', description: '数据来源构成' },
  'city.distribution': { kind: 'distribution', unit: 'job_records', dimension: 'city', description: '企业关联地址的城市分布' },
  'province.distribution': { kind: 'distribution', unit: 'job_records', dimension: 'province', description: '企业关联地址的省份分布' },
  'title.top': { kind: 'distribution', unit: 'job_records', dimension: 'title', description: '岗位名称排名，返回完整基数与其他/缺失量' },
  'education_experience.cross': { kind: 'cross', unit: 'job_records', dimensions: ['education', 'experience'], description: '学历×经验交叉频数' },
  'city_education.cross': { kind: 'cross', unit: 'job_records', dimensions: ['city', 'education'], description: '城市×学历交叉频数' },
  'salary.summary': { kind: 'summary', unit: 'K_CNY/month', description: '区间中点均值与 P25/P50/P75/P90' },
  'salary.distribution': { kind: 'distribution', unit: 'job_records', description: '有效薪资区间中点分箱' },
  'data_quality.summary': { kind: 'summary', unit: 'job_records', description: '按需统计地址/省市/企业/名称/来源缺失量，并读取样本最大平台更新时间' },
  'track.distribution': {kind:'distribution',unit:'job_records',analysis:true,description:'显式有序规则互斥归类，含未分类'},
  'city_track.cross': {kind:'cross',unit:'job_records',analysis:true,dimensions:['city'],description:'城市×同一互斥方向的完整频数'},
  'track_salary.summary': {kind:'distribution',unit:'K_CNY/month',analysis:true,description:'同一方向及薪酬策略的分组摘要'},
  'skills.distribution': {kind:'distribution',unit:'job_records',analysis:true,description:'描述中显式技能词的岗位提及计数，不返回描述'},
  'track_skills.cross': {kind:'cross',unit:'job_records',analysis:true,description:'方向×技能提及计数，保留全岗位和有效描述分母'},
}
export const DIMENSIONS = { education: 'p.education', experience: 'p.experience', jobType: 'p.type', source: 'p.data_source', city: 'a.city', province: 'a.province', title: 'p.name' }
export const LIMITS = { cohorts: 4, metrics: 19, dictionaryIds: 1000, resultRows: 40000, bytes: 32 * 1024 * 1024, deadlineMs: 360000, timeoutMs: 180000 }

function analysisPolicy(raw,metrics) {
  const a=object(raw??{},['tracks','skills'],'analysis'),out={}
  if(a.tracks!==undefined) {
    if(!Array.isArray(a.tracks)||!a.tracks.length||a.tracks.length>12)fail('INVALID_REQUEST','analysis.tracks 需要1–12个有序方向规则')
    out.tracks=a.tracks.map(g=>{
      object(g,['key','label','titleAny','roleIds'],'方向规则')
      const key=textValue(g.key,40,'方向 key')
      if(!/^[a-zA-Z0-9_-]+$/.test(key)||key.toLowerCase()==='__other__')fail('INVALID_REQUEST','方向 key 无效或保留')
      const titleAny=terms(g.titleAny,'方向名称词'),roleIds=g.roleIds??[]
      if(!Array.isArray(roleIds)||roleIds.length>40||roleIds.some(id=>!/^\d{1,10}$/.test(String(id))||Number(id)<1||Number(id)>2147483647))fail('INVALID_REQUEST','方向 roleIds 必须为最多40个有效岗位类型ID')
      if(!titleAny.length&&!roleIds.length)fail('INVALID_REQUEST','方向规则必须声明 titleAny 或 roleIds')
      return {key,label:textValue(g.label,60,'方向 label'),titleAny,roleIds:[...new Set(roleIds.map(String))].sort()}
    })
    if(new Set(out.tracks.map(g=>g.key.toLowerCase())).size!==out.tracks.length)fail('INVALID_REQUEST','方向 key 不得重复（忽略大小写）')
    if(new Set(out.tracks.map(g=>g.label)).size!==out.tracks.length)fail('INVALID_REQUEST','方向 label 不得重复')
    if(out.tracks.some(g=>g.label==='未分类'))fail('INVALID_REQUEST','未分类为保留方向名称')
  }
  if(a.skills!==undefined) {
    if(!Array.isArray(a.skills)||!a.skills.length||a.skills.length>60)fail('INVALID_REQUEST','analysis.skills 需要1–60个技能词')
    out.skills=a.skills.map(v=>textValue(v,60,'技能词'))
    if(new Set(out.skills.map(v=>v.toLowerCase())).size!==out.skills.length)fail('INVALID_REQUEST','技能词不能重复（忽略大小写）')
  }
  if(metrics.some(m=>['track.distribution','city_track.cross','track_salary.summary','track_skills.cross'].includes(m))&&!out.tracks)fail('INVALID_REQUEST','方向指标需要显式 analysis.tracks')
  if(metrics.some(m=>['skills.distribution','track_skills.cross'].includes(m))&&!out.skills)fail('INVALID_REQUEST','技能指标需要显式 analysis.skills')
  return Object.keys(out).length?out:undefined
}

function selectors(raw = [], label) {
  if (!Array.isArray(raw) || raw.length > 8) fail('INVALID_REQUEST', `${label} 最多 8 项`)
  return raw.map(value => {
    object(value, ['id', 'name', 'includeDescendants'], label)
    if ((value.id === undefined) === (value.name === undefined)) fail('INVALID_REQUEST', `${label} 每项只能指定 id 或 name`)
    if (value.includeDescendants !== undefined && typeof value.includeDescendants !== 'boolean') fail('INVALID_REQUEST', 'includeDescendants 必须为布尔值')
    if(value.id!==undefined && !((typeof value.id==='number'&&Number.isSafeInteger(value.id)) || (typeof value.id==='string'&&/^[1-9]\d{0,9}$/.test(value.id))))fail('INVALID_REQUEST',`${label}.id 必须为正整数或数字字符串`)
    return { ...(value.id !== undefined ? { id: String(integer(Number(value.id), 1, 2147483647, `${label}.id`)) } : { name: textValue(value.name, 80, `${label}.name`) }), includeDescendants: value.includeDescendants !== false }
  }).sort((a,b) => canonical(a).localeCompare(canonical(b)))
}
export function validateRequest(raw) {
  object(raw, ['schema', 'sourceId', 'cohorts', 'metrics', 'policies', 'execution', 'output','analysis'], 'request')
  if (raw.schema !== 'talent-query/1') fail('INVALID_REQUEST', 'schema 必须为 talent-query/1')
  if (raw.sourceId !== undefined && raw.sourceId !== 'talent-main') fail('UNSUPPORTED', '仅支持 talent-main 数据源')
  if (!Array.isArray(raw.cohorts) || !raw.cohorts.length || raw.cohorts.length > LIMITS.cohorts) fail('INVALID_REQUEST', 'cohorts 必须有 1–4 个样本组')
  const cohorts = raw.cohorts.map(cohort => {
    object(cohort, ['id', 'filters'], 'cohort')
    const id = textValue(cohort.id, 40, 'cohort.id')
    if (!/^[a-zA-Z0-9_-]+$/.test(id)) fail('INVALID_REQUEST', 'cohort.id 仅限字母数字和下划线/短横线')
    const f = object(cohort.filters, ['region', 'title', 'industries', 'roles', 'education', 'experience', 'jobType', 'updatedAt', 'state'], 'filters')
    const region = object(f.region, ['level', 'name', 'province'], 'region')
    if (!['national', 'province', 'city'].includes(region.level)) fail('UNSUPPORTED', '地域支持 national/province/city，区县尚未支持')
    if (region.level === 'national' && (region.name !== undefined || region.province !== undefined)) fail('INVALID_REQUEST', 'national 不接受 name/province')
    if (region.level === 'province' && region.province !== undefined) fail('INVALID_REQUEST', 'province 层级使用 name 字段')
    const normalizedRegion = { level: region.level }
    if (region.level !== 'national') normalizedRegion.name = textValue(region.name, 40, 'region.name')
    if (region.province !== undefined) normalizedRegion.province = textValue(region.province, 40, 'region.province')
    const title = object(f.title ?? {}, ['any', 'all', 'exclude'], 'title')
    if (f.state !== undefined && f.state !== 'publishing') fail('UNSUPPORTED', '首期仅统计在招且未删除的岗位')
    const filters = { region: normalizedRegion, title: { any: terms(title.any), all: terms(title.all), exclude: terms(title.exclude) }, industries: selectors(f.industries, 'industries'), roles: selectors(f.roles, 'roles'), state: 'publishing' }
    for (const field of Object.keys(ENUMS)) {
      filters[field] = terms(f[field], field)
      if (filters[field].some(v => !Object.hasOwn(ENUMS[field], v))) fail('INVALID_REQUEST', `${field} 含不支持的枚举，请使用 capabilities 列表`)
    }
    if (f.updatedAt !== undefined) {
      object(f.updatedAt, ['from', 'to'], 'updatedAt')
      const entries = Object.entries(f.updatedAt)
      if (!entries.length || entries.some(([,v]) => typeof v !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(v) || !Number.isFinite(Date.parse(v)) || new Date(v).toISOString().slice(0,10) !== v)) fail('INVALID_REQUEST', 'updatedAt 使用有效的 YYYY-MM-DD 日期')
      if (f.updatedAt.from && f.updatedAt.to && f.updatedAt.from >= f.updatedAt.to) fail('INVALID_REQUEST', 'updatedAt.to 为不含当天的上界，必须大于 from')
      filters.updatedAt = { ...f.updatedAt }
    }
    return { id, filters }
  })
  if (new Set(cohorts.map(c=>c.id)).size !== cohorts.length) fail('INVALID_REQUEST', 'cohort.id 不得重复')
  if (!Array.isArray(raw.metrics) || !raw.metrics.length || raw.metrics.length > LIMITS.metrics || raw.metrics.some(m => typeof m !== 'string' || !Object.hasOwn(METRICS,m))) fail('UNSUPPORTED', 'metrics 含不支持的指标，请调用 capabilities')
  const analysis=analysisPolicy(raw.analysis,raw.metrics)
  const policies = object(raw.policies ?? {}, ['salary', 'consistency'], 'policies')
  if (policies.salary !== undefined && policies.salary !== 'salary-policy/1') fail('UNSUPPORTED', '仅支持 salary-policy/1')
  if (policies.consistency !== undefined && policies.consistency !== 'consistent-read') fail('UNSUPPORTED', '仅支持同连接一致性只读事务')
  const execution = object(raw.execution ?? {}, ['freshness', 'maxAgeMs', 'deadlineMs', 'timeoutMs', 'snapshotId'], 'execution')
  const freshness = execution.freshness ?? 'cache-ok'
  if (!['live', 'cache-ok', 'snapshot-only'].includes(freshness)) fail('INVALID_REQUEST', 'freshness 必须为 live/cache-ok/snapshot-only')
  if (execution.snapshotId !== undefined && (typeof execution.snapshotId !== 'string' || !/^[a-f0-9]{64}$/.test(execution.snapshotId))) fail('INVALID_REQUEST', 'snapshotId 必须为工具返回的 64 位 key')
  if (freshness === 'snapshot-only' && !execution.snapshotId) fail('INVALID_REQUEST', 'snapshot-only 必须指定 snapshotId')
  const output = object(raw.output ?? {}, ['previewRows', 'topN', 'exports'], 'output')
  const exports = output.exports ?? []
  if (!Array.isArray(exports) || exports.length > 3 || exports.some(v => !['json','csv','markdown'].includes(v))) fail('INVALID_REQUEST', 'exports 支持 json/csv/markdown')
  return { schema: 'talent-query/1', sourceId: 'talent-main', cohorts, ...(analysis?{analysis}:{}), metrics: [...new Set(raw.metrics)].sort(), policies: { salary: 'salary-policy/1', consistency: 'consistent-read' }, execution: { freshness, deadlineMs: integer(execution.deadlineMs ?? 240000, 1000, LIMITS.deadlineMs, 'deadlineMs'), timeoutMs: integer(execution.timeoutMs ?? 120000, 1000, LIMITS.timeoutMs, 'timeoutMs'), maxAgeMs: integer(execution.maxAgeMs ?? 900000, 0, 900000, 'maxAgeMs'), ...(execution.snapshotId ? {snapshotId:execution.snapshotId}: {}) }, output: { previewRows: integer(output.previewRows ?? 10, 0, 20, 'previewRows'), topN: integer(output.topN ?? 20, 1, 100, 'topN'), exports: [...new Set(exports)] } }
}

// UTF-8 hex literals have no quote/backslash SQL-mode ambiguity. LIKE wildcards are literal by default.
export const sqlString = value => `CONVERT(X'${Buffer.from(String(value),'utf8').toString('hex')}' USING utf8mb4)`
export const likeTerm = value => sqlString(`%${value.replaceAll('!','!!').replaceAll('%','!%').replaceAll('_','!_')}%`)
export function semanticRequest(request,engine=VERSION) {
  return { schema: request.schema, sourceId: request.sourceId, cohorts: request.cohorts, metrics: request.metrics, policies: request.policies, topN: request.output.topN, engine, ...(request.analysis?{analysis:request.analysis}:{}) }
}
export function capabilities() {
  return { schema: 'talent-capabilities/1', engine: VERSION, sourceIds: ['talent-main'], operations: ['capabilities','resolve','plan','query','inspect','export'], filters: ['region','title.any','title.all','title.exclude','industries','roles','education','experience','jobType','updatedAt','state'], analysis:{tracks:'1–12个有序titleAny/roleIds规则，首个命中；未分类独立',skills:'1–60个显式词；不区分大小写的子串岗位计数'}, metrics: METRICS, enums: ENUMS, limits: LIMITS, policies: ['cohort-policy/1','category-policy/1','salary-policy/1'], unsupported: ['专业关联（P1）','岗位真实发布时间趋势','就业率/市场总量','任意SQL'], defaultFreshness: 'cache-ok', maxCacheAgeMs: 900000 }
}
