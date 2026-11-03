# 088 · 生成产物交付：网页分享与资源下载

**状态**：已实现并在公网验证（2026-11-03）。仅保留网页分享与资源下载；原复杂资源中心方案已废弃，保留在 Git 历史。当前公开入口为 `http://biubiubiu.vip:14188`。

## 动机与范围

原有交付依赖少量技能的固定 HTML/PDF 路径，公众号文章、引用图片和 ZIP 缺少统一出口。用一个小清单将明确交付的产物保存到持久目录，网页在线访问，其他文件下载，不建设 PDF/图片/Excel 查看器、资源中心或版本系统。

| 类型 | 用户操作 |
|---|---|
| HTML 与网页依赖 | 打开网页、复制链接；接收方无需原聊天会话 |
| PDF、图片、Excel、JSON、ZIP 等 | 下载；多文件由生成脚本打 ZIP |

## 交付契约与保存

会话工作区根目录 `delivery.json`：

~~~json
{
  "web": [{"name":"人才需求报告","directory":"output/public/site","entry":"index.html"}],
  "files": [{"name":"整套报告","path":"output/public/report.zip"}]
}
~~~

两组数组可省略其一，名称非空；路径相对于会话根，不接受绝对路径、点路径段、隐藏路径、internal/uploads、符号链接或特殊文件。directory 是独立公开目录，整目录都会公开；内部 SQL、核查表、密码、原始追踪不能放入。上限 20 个网页、100 个下载、2000 个非空文件、256 MiB，入口须存在且为 HTML。

`web/server/lib/delivery.ts:48` 指纹结合 inode、mtime/ctime 和内容摘要：只有本轮新建或改写清单才收集。生成脚本先写完文件、最后原子替换清单；纯追问不重写。无清单是无文件交付，无效新清单则明确失败，不伪造链接。旧 HTML 同时检查本轮文件更新，避免把上轮报告再交付。

`web/server/lib/delivery.ts:78` 扫描并验证后分配 128 位随机 ID，用已检查的普通文件 inode 复制内容；拒绝收集期间文件变化。先写私有暂存目录，完整后 rename 生效，失败清理暂存。元数据只保存允许提供的名称、入口和文件清单，不另建数据库。

~~~text
deliveries/<deliveryId>/
  metadata.json
  web/0/index.html
  web/0/assets/...
  files/0.zip
~~~

`DELIVERIES_DIR` 默认 `web/server/deliveries/`（已 gitignore），部署需持久保留。会话清理与服务重启不会删此目录；首期不自动清理，不承诺无限期保存。每次交付新 ID，旧链接保持原产物，无 latest 指针或版本切换。

## 托管与下载

`web/server/lib/delivery.ts:192` 由现有 Node 服务提供只读资源路由：

- `GET/HEAD /p/:deliveryId/:index/`：重定向到真实入口路径，保留子目录相对依赖；只提供 metadata 声明的静态文件，不暴露工作区或 metadata。
- `GET/HEAD /api/deliveries/:deliveryId/files/:index`：固定 attachment，中文文件名使用 filename*；PDF/图片也直接下载。
- 其余方法返回 405，缺失、越界、未声明路径返回 404。访问不调用模型或数据库。

最终采用**复用现有公开入口、浏览器沙箱隔离**，无需新增端口、域名或进程。网页 CSP 使用 `sandbox allow-scripts`，不授予 allow-same-origin，因此不共享主站存储/权限；connect-src 仅允许公开 origin 的 `/p/` 静态路径，禁止主站 API、表单、iframe、worker。静态资源独立允许 CORS，以支持该不透明来源读取网页内数据与字体。允许脚本、相对 CSS/图片/字体和目录内 JSON，外部服务、嵌入页面及动态后端不属于支持范围。

这是原方案中“等效隔离静态入口”的具体实现；否决另开内容端口作为首期前置条件，因为现有入口即可满足用户的简单分享需求。浏览器实测覆盖正常脚本/图片/CSS/JSON、存储拒绝和 API 请求拒绝，不把 CSP 当成身份鉴权。

`DELIVERY_PUBLIC_BASE_URL` 为完整 HTTP(S) origin；未配置时采用通过入口校验的请求 Origin，非浏览器回退 Host。HTTPS 代理部署应显式配置。当前本地 `.env` 已配置 `http://biubiubiu.vip:14188` 并加入 PLAZA_ALLOWED_ORIGINS；密钥未提交。`web/vite.config.ts:9` 的 `/p/` 代理与域名 allowedHosts 已生效；生产反向代理同样必须将 `/p/` 和 `/api/` 转给 Node，不能回落 SPA。当前公网实测为 HTTP，未宣称已配置 HTTPS。

分享按“持链接可访问”，不新增账号/授权表；随机 ID 不代表鉴权。不要将私密材料列入公开清单。

## 运行协议与界面

在原 done 中增加可选数组，不新增事件类型：

~~~json
{
  "webLinks": [{"name":"人才需求报告","url":"http://biubiubiu.vip:14188/p/<deliveryId>/0/"}],
  "downloads": [{"name":"整套报告","url":"http://biubiubiu.vip:14188/api/deliveries/<deliveryId>/files/0"}]
}
~~~

- `web/server/index.ts:153`：通用沙箱说明注入清单格式，模型不自行拼 URL。
- `web/server/index.ts:1159`：终态只收集一次，保存成功后再发链接；超时/断连时尝试保存已完成产物；未开始的忙会话请求不收集。
- `web/server/index.ts:897`：Plaza SSE、OpenAI 流式扩展和非流式 JSON 均携带数组。
- `web/server/lib/traceExport.ts:201`：数组写入原运行索引；`web/server/lib/conversation.ts:67` 按原用户轮次恢复，追问后仍保留前轮产物。
- `web/server/lib/delivery.ts:164`：已验证的旧 HTML/PDF 从服务端 trace 目录适配新交付，不向 Agent 控制的目录写文件；原 reportUrl 接口继续兼容旧记录。
- `web/src/components/ReportOutput.vue:70`：名称加“打开网页 / 复制链接”，名称加“下载”；有新交付时不重复显示旧报告按钮。HTTP 环境复制使用原生复制回落。
- `web/src/pages/ExperiencePage.vue:415`、`:741`：实时和历史均传递两组链接，分别留在对应回答。

接口说明同步至 `docs/agent-api.md:12`；不新增资源中心、预览组件、画廊或发布状态机。

## wechat-report 接入

`pack_delivery.py:14` 从同一已绑定大纲和本次图片 manifest 生成自包含网页，只复制声明图片；公开 ZIP 继续排除来源绑定和内部核查表。`pack_delivery.py:48` 最后原子写交付清单。副本位于会话 wechat-report/ 时传 `--workspace ..`，路径相对于会话根；独立运行可省略。技能说明与安装流程已同步。

网页分享不等于微信公众号推送；publish_draft 仍需用户明确要求。

## 验证与证据边界

2026-11-03：

- 共享数据/公众号流水线与后端模块、对话恢复、SSE 回归 96 项通过；新增完整 HTTP 集成测试通过，合计 97 项。集成测试使用确定性 Pi 传输，不调用模型：覆盖真实路由、Plaza done、OpenAI 两种响应、追问历史、无效交付、删工作区和重启恢复。
- 集成测试带 `DELIVERY_BROWSER=/usr/bin/google-chrome`：图片、CSS、脚本和静态 JSON 正常，localStorage 与主站 API 被拒绝。
- Vue 类型检查及生产构建通过，Python 技能校验通过。额外经公开域名浏览器挂载真实 ReportOutput 组件，确认两类操作和复制按钮，无额外预览操作。
- 复用 11-02 已保存的广州低空经济真实统计报告，没有重新查库。公网网页、17 张引用图片全部 200；ZIP 200、attachment、与源 ZIP 字节一致。Chrome 截图已检查。验证摘要保存在忽略目录 `web/server/traces/delivery-acceptance-20261103.json`。
- 后端已重启，公开域名白名单、静态代理和真实分享链接已验证。公众号报告在线智能体从提示词到新数据/新交付的长任务未重跑；本轮验证的是已有真实产物的打包/托管，以及确定性运行器下的完整接入链。

验证命令：

~~~bash
node --experimental-strip-types --test scripts/talent-data/*.test.mjs web/server/lib/*.test.* web/src/composables/useChatApi.test.mjs
DELIVERY_BROWSER=/usr/bin/google-chrome node --experimental-strip-types --test web/server/delivery-api.test.mjs
(cd web && npm run build)
python3 /home/wlc/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/wechat-report
~~~

## 成本与取舍、后续路线

每次交付增加一份文件复制和少量 JSON；同步复制有 256 MiB 上限，未做对象存储/CDN、SQLite、账号分享、预览或独立站点容器。页面脚本受沙箱限制，有外部 API、跨站嵌入或动态后台需求时需另行设计，不能声称静态托管支持。

后续只按实际需求增加维护清理/撤销入口或调整容量，不预建复杂管理。部署迁移时需连同 deliveries 目录和公开 origin 配置迁移；仅搬 Git 仓库不能恢复已生成文件。
