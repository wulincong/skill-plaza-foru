# 统一平台登录

点击页头登录，经统一平台认证后回到原页面，显示昵称和头像。刷新页面从后端重新获取用户资料；退出同时跳转中心退出入口。手机号验证码、微信扫码等由统一平台提供。

## 配置

后端读取 `web/.env`，默认正式环境；设置 `PLAZA_ENV=test` 使用参考教育项目 `.env.test` 的应用和上游。

| 配置 | 测试默认值 | 正式默认值 |
| --- | --- | --- |
| `PLAZA_AUTH_APP_ID` | `69543990ecb048a88f76ef9279e82fc5` | `dc8d609d021711ef8e910242ac120010` |
| `PLAZA_AUTH_PLATFORM_URL` | `http://192.168.8.2:19000` | `http://192.168.8.1:18800` |
| `PLAZA_AUTH_GATEWAY_URL` | 平台地址加 `/gateway` | 平台地址加 `/gateway` |
| `PLAZA_AUTH_CENTER_URL` | `https://login.tringai.cn` | 同左 |

参考项目 development 的 appId 为 `3f363349005111ef808d0242ac110006`；需要时显式覆盖，不能与 test 混淆。平台请求由广场后端发出，部署机器需可访问对应内网上游。

将实际前端 origin 加入 `PLAZA_ALLOWED_ORIGINS`。登录回调为该 origin 下的 `/api/auth/callback`，须由统一平台允许用于原 appId。认证接口同时要求 origin 的 host 与请求 Host 一致。反向代理应保留浏览器的 Host，并将 `/api/*` 原样转发到广场后端（包括查询参数和 Set-Cookie）；无需新增 `/platform-api` 或 `/gateway` 浏览器代理。

后端配置修改后，先确认无运行任务，再按项目约定用 systemd 重启后端；前端按现有流程构建和发布。

## 接口与边界

- `GET /api/auth/login?origin=...&returnTo=...`：创建十分钟登录事务，跳转中心；返回路径限制在站内。
- `GET /api/auth/callback?state=...&st=...`：校验浏览器事务、消费一次票据，调用平台 `POST /api/oauth/anno/unionLogin`，请求 `{code: st, skipLoginCache: true}`，再读取用户资料，成功后回原页。
- `GET /api/auth/me`：用平台 token 调用 `/gateway/user/auth/users/view`，返回 `{user:{id,nickname,phone,avatar}}`；未登录/失效为 401，上游暂不可用为 502。
- `POST /api/auth/logout`：要求允许的 Origin 和 `X-Plaza-Auth: 1`，清除本地 Cookie，返回中心退出 URL。

token 仅存于广场 host 的 HttpOnly Cookie，Path 为 `/api/auth`，有效期一天，HTTPS 下带 Secure；上游有效期仍由平台判断。测试和正式 Cookie 名隔离，不复用父域 `TOKEN`。前端清理旧演示 localStorage。登录事务暂存在进程内，服务重启后未完成的登录需要重新发起；部署多实例时需共享事务或启用粘性会话。

本阶段没有为聊天、历史、附件新增用户权限；用户 `id` 仅用于展示数据模型，尚未确认为跨应用稳定身份。其他站点退出时主动通知广场、账号切换即时同步属于后续范围。

## 验收

自动验证：`node --experimental-strip-types --test web/server/lib/unifiedAuth.test.mjs web/src/composables/useChatApi.test.mjs`；前端 `npm run build`。

真实环境仍需验证：从指定域名点击登录；中心允许原 appId 的新回调；真实票据换 token 和资料接口兼容；回原 hash 页面；刷新和新标签页恢复；退出后回访为未登录；过期票据、中心不可用时可重新登录。当前 HTTP 测试使用模拟上游，不能替代真实账号验收。

参考：`D:/project/cjrh-education-web/utils/auth.js`、`pages/unionLogin.vue`、`utils/request-cjrh.js`、`utils/request.js`、`api/user.js`、三份环境配置。旧架构背景见开发手记 132。
