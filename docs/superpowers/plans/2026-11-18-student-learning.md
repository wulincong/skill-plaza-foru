# Student Learning Implementation Plan

> 使用 superpowers:executing-plans 在当前会话顺序实施。用户已授权开始，不再重复确认方案。

**Goal:** 四字段学生需求经知识库课程包匹配，交付带可访问教材链接的个性化学习报告。

**Architecture:** Python 管理 WeKnora 检索和分类；Node 提供限库会话中继与持久逐文档授权入口；Pi 挂载共享工具和报告呈现；Vue 复用通用表单。

**Tech Stack:** Python 3.10+ 标准库、Node 内置模块、TypeScript、Vue 3、现有 report-rendering。

**Spec:** docs/superpowers/specs/2026-11-18-student-learning-design.md

## Global Constraints

- 仅四字段；目标岗位必填；默认知识库 b627daef-d505-4f16-9ee9-76474a6e5bde。
- Key 不进报告、工具结果、版本管理或 Pi 沙箱。
- 分类和文档响应必须核对归属，所有分页可访问；不把错误当空结果。
- 报告任务引用真实课程文档，时间预算和假设可核对。
- 保留用户 AGENTS.md 改动。服务操作仅 systemd，重启前查运行任务。

## Review Focus

- 分类接口嵌套分页形状与普通文档分页不同：Python 回归覆盖。
- 跨库、无效文档与非法路径不得签发教材入口：宿主回归覆盖。
- 无配置及上游错误不得泄露 Key：中继与材料请求回归覆盖。
- 分享页不共享主站鉴权：教材采用逐文档持久随机授权入口，测试重启读取。
- 取消和会话回收关闭中继：Pi 生命周期回归和集成验证。

## Task 1：共享检索

Files: weknora-retrieval/scripts/retrieve.py、tests/test_retrieve.py、SKILL.md、docs/index.md。
- [x] 先写 tags、分类筛选、归属校验与正文预览测试并确认失败。
- [x] 增加 tags --kb --keyword --page 和 documents --tag；保留正文预览，返回原始 API 地址。
- [x] 运行 Python 回归，真实列分类及分类下目录。

## Task 2：受限中继与教材访问

Files: web/server/lib/weknora.ts、weknora.test.mjs、weknora-retrieval/scripts/pi-tools.mjs、piRunner.ts、index.ts。
Interfaces: openKnowledgeRelay(workspace), handleLearningMaterial(req,res)；工具 weknora_retrieve。
- [x] 先测未授权路由、限库拒绝、参数验证、错误脱敏、链接签发和重启读取。
- [x] 宿主调用 Python（Key 仅子进程环境），按配置库限制会话；分类文档签发材料链接并核对归属。
- [x] 材料注册表落持久私有目录，仅代理固定上游文档 preview/download；Key 留后端。
- [x] 挂载 Pi 工具与生命周期清理，运行 Node 回归和真实 HTTP 验证。

## Task 3：技能和表单

Files: student-learning/SKILL.md、docs/index.md、skills.ts、useTaskConfigs.ts、UsePage.vue、前端 skills.ts。
- [x] 添加四字段表单、技能注册和用户指南；提示词覆盖匹配/补充/自主规划/错误停止。
- [x] 与 report-rendering 对接，完整每日任务、时间和教材链接验收。
- [x] 验证注册与表单、docs:check、Vue 构建和接口回归。

## Task 4：验收与版本

- [x] 实测分类匹配、带/不带上游 Key、真实 Pi 报告与 Chrome 下载；当前用户执行，生产低权待部署。
- [x] 更新 107 与新增 125 开发手记的接入点、实测与剩余限制。
- [ ] 检查密钥未入暂存，提交已验证文件并在当前分支打标签。

## 实施裁定与实际边界

- Ruling: 在当前工作区顺序实施、保留既有未提交改动，不新增 worktree — 之前的 WeKnora 改动是本功能依赖，AGENTS.md 用户改动不纳入提交。
- Ruling: 材料采用逐文档随机能力链接 — 复用报告的持链接可访问模式，避免报告暴露 Key；后续账户鉴权另做。
- Ruling: 构建器以计划文件定位工作区并阻止来源改写 — 真实模型首轮暴露 cwd 错误和来源重建，已修复并用真实来源重建验证。
- Ruling: 不同步另一个在线仓库或操作 wlc 服务 — 当前仓库不同且没有该用户服务管理权限，生产低权验收明确保留。
