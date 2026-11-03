/* ============================================================
   环境标识（web/.env 的 PLAZA_ENV，模板见 .env.example）
   ------------------------------------------------------------
   test = 测试环境：工作台进入页面自动带入示例默认值，
          并自动附带内置测试简历（一键运行测试）。
   prod / 未设置 = 生产环境：表单干净，什么都不预填。
   前端经 vite envPrefix 读 import.meta.env.PLAZA_ENV；
   后端经 loadLocalEnv 读 process.env.PLAZA_ENV，同一份 .env。
   ============================================================ */

export const PLAZA_ENV = String(import.meta.env.PLAZA_ENV ?? '').trim().toLowerCase()

/** 是否测试环境（演示默认值总开关） */
export const isTestEnv = (): boolean => PLAZA_ENV === 'test'
