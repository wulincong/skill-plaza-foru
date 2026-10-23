# 075 · 沙箱 pi 上下文隔离：--no-context-files + 沙箱说明显式注入

- 状态：已实现（2026-10-19。后端重启后真实探针会话验证：上下文只含沙箱说明/工具声明/工程边界，无任何开发 AGENTS.md 内容）。
- 动机：用户指出仓库根 AGENTS.md 是**开发用**（zcode 等在本仓库工作的开发智能体）的，不是广场运行智能体的。实证根因：pi 从沙箱 cwd（`web/server/workspace/sess-*`）沿父目录**链式加载** AGENTS.md（pi resource-loader `loadProjectContextFiles`：cwd 逐级向上 + 全局 agentDir），把仓库根开发 AGENTS.md 装进了用户运行上下文；沙箱智能体据此执行「完成后必须新增编号手记」条款——2026-10-19 08:29 的 073 号观察记录即由当天广场在线运行会话自己写入（trace `20261019-082511-6zdp.json` 内有查索引、取号 073、写文件的推理原文），这也是手记中 25 条运行观察与编号重复（012/030/032/… 各两次）的主要来源（该 073 文件与对应索引行在 2026-10-19 手记重组中一并清除，见 076）。

## 约定细节

- `piRunner.createSession`（`web/server/lib/piRunner.ts`）新增两个启动参数：
  - `--no-context-files`——关闭 AGENTS.md/CLAUDE.md 目录链发现。pi 源码实证：`noContextFiles` → `agentsFiles = []`（含全局 agentDir 与全部祖先目录，一刀切）。
  - `--append-system-prompt <workspaceDir>/AGENTS.md`——沙箱说明改为**显式注入**系统提示词 addendum。pi `resolvePromptInput` 对存在的路径读取文件内容（resource-loader.js:21-23），两个 createSession 调用点（index.ts 新建 / 会话回收重建）均先经 `workspaceDirFor()` 写好该文件，注入路径恒存在。
- 沙箱 AGENTS.md 模板（index.ts `sandboxAgentsMd`）新增「工程边界」节：本目录之外的项目文件（源码、web/、开发文档与开发手记等）是广场工程资料，不要读取、不要在沙箱外创建或修改；仓库内容只能通过已声明的工具脚本和已挂载技能目录访问。
- 009 的沙箱 AGENTS.md 工具声明不变，仅送达方式从「cwd 链式发现」改为「显式注入」。

## 成本与取舍

- 否决「沙箱 AGENTS.md 写一句『忽略父目录 AGENTS.md』」：软约束，模型可能仍遵循已装入的开发条款，且根因（链式装入）未除。
- 否决「workspace 根挪出仓库」：改动面大（uploads、报告捕获 readWorkspaceHtmlReport、既有会话目录与 .pi-sessions 连续性），`--no-context-files` 一行即断链。
- 残余风险（诚实记录）：智能体仍可主动用 read/bash 打开仓库任意路径（本地进程同用户权限，pi 无按路径禁读的工具限制）；「工程边界」节是意图层防线，不是硬隔离。硬隔离需 pi 支持路径级工具白名单或容器化沙箱，暂不做。

## 后续扩展路线

- 若 pi 提供 per-path 工具限制，把「仓库仅可读 scripts/ 工具与已挂载技能目录」升级为硬边界。
- 硬隔离第一步已定稿落地：低权系统用户运行 pi（078，文件系统写边界）。

## 验证（2026-10-19 实测）

- 重启后端后 curl `POST /api/chat`（general）探针「列出上下文中的项目级说明 + 是否存在开发手记要求」：回答仅含六项沙箱说明（会话沙箱/联网检索/MySQL 工具/城市热点图规范/查询强制性/工程边界）+ pi 内置工具指南 + 广场通用智能体角色提示词，并明确回答**没有**任何读写开发手记、维护编号记录、遵循仓库协作约定的要求。
- 新会话 trace（`traces/20261019-085922-2e0g.json`）中「开发手记」字样仅出现于探针提问与回答引用本身；对照修复前同日 trace（`20261019-082511-6zdp.json`）含 16 处 plaza-dev-notes 引用与写手记的推理。
