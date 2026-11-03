# 057 · 公网入口 origin 白名单：PLAZA_ALLOWED_ORIGINS

状态：已实现并实测通过（2026-10-15；curl 四场景验证，浏览器公网回归待用户确认）。

## 动机

用户经公网映射地址（`http://115.231.218.150:14188` → vite:4188）访问前端时，
所有 `/api` 请求返回 403「不允许跨站调用本地 API」。链路：前端只发相对路径
`/api/*`，vite 代理 `changeOrigin: false` 原样保留浏览器 `Origin` 头；同源 POST
浏览器一律附带 Origin，后端 `originAllowed`（web/server/index.ts）只认
本机/内网来源，公网页面 origin 直接被拒。防护本意是防公网恶意网页驱动访客
浏览器调用本地 agent 服务（CSRF / DNS rebinding 类），但把自己的公网入口也拦了。

## 约定

- 默认行为不变：无 `Origin` 头（同源 GET/非浏览器）放行；`Origin` 是
  localhost/127.0.0.1/::1/`*.local`/10.x/192.168.x/172.16-31.x 放行；其余 403。
- 新增 `web/.env`（或外部环境变量）`PLAZA_ALLOWED_ORIGINS`：逗号分隔的
  **完整 origin（含端口）**，如
  `PLAZA_ALLOWED_ORIGINS=http://115.231.218.150:14188,https://plaza.example.com`。
  命中白名单的 origin 放行（比较前做 trim/去尾斜杠/小写归一）。
- 白名单在模块加载时读入常量 `EXTRA_ALLOWED_ORIGINS`；改配置需重启后端。
- 生效范围：`originAllowed` 的全部调用点——`/api/runs*`、运行文件、
  `/api/chat`、`/v1/chat/completions`、报告路由。

## 成本与取舍

- 否决「公网 origin 一律放行」：agent 服务能联网检索、写沙箱文件，任意公网
  页面可驱动它是实际风险；白名单只登记自有入口，防护不放松。
- 否决「按 Host 头判断」：Origin 才是浏览器跨站语义的事实标准，Host 校验
  属 DNS rebinding 另一层（未做，维持现状）。
- 端口必须写全：前端经 vite 代理走同源（页面上看是 14188），漏端口必失配。

## 验证（2026-10-15，curl）

| 场景 | 结果 |
| --- | --- |
| `Origin: http://115.231.218.150:14188` → GET /api/runs | 200（放行） |
| `Origin: http://evil.example` → GET /api/runs | 403（防护仍在） |
| `Origin: http://127.0.0.1:4188` → GET /api/runs | 200（本机不受影响） |
| `Origin: http://evil.example` → POST /v1/chat/completions | 403 invalid_request_error |

## 后续路线

- 若后续加域名/HTTPS 入口，继续在 `PLAZA_ALLOWED_ORIGINS` 追加即可；
  多入口公网部署时可考虑改为启动时校验 origin 合法性并打日志。
- `.env.example` 已加模板说明（`web/.env.example` 顶部）。

## 补注（2026-11-03）：公网入口的真实链路与 SSH 隧道端口

排查"连不上服务器"时核实的部署拓扑，供后续运维参考：

- 公网入口不是云主机上直接跑的服务，而是 **frp 内网穿透**：云主机
  `test.deckmanager.net`（115.231.218.150，root@22 可登）跑 frps（bind 7000），
  广场开发机（本机 wlc-Precision-3660）以 root 级 frpc
  （`/usr/local/bin/frp/frpc.ini`）注册映射：4188→14188（前端）、8767→18767（后端），
  另有 alist/lumi/wechat-wx-bot 等无关代理。广场服务本体在本机，云主机上没有项目目录。
- **SSH 隧道端口是 6001**（frpc `[ssh-vision]` 127.0.0.1:22→6001），不是旧配置里的
  6000；6000 不属于任何在册代理（frps 监听列表实测：5544/6001/6002/7000/8008/
  8012/14188/18088/18767/26888）。6002 属另一台客户端机器（vision123-Precision-3660）。
  本机 `~/.ssh/config` 已改为 6001，并把本机自身公钥补进 `authorized_keys`，
  `ssh test.deckmanager.net` 端到端验证通过。其他外部电脑（authorized_keys 已在列）
  连接时同样需把端口改为 6001。
- 云主机 frps 日志显示持续有扫描 IP 用错误 token 尝试注册（已被 token 校验拦截）；
  frp token 与 frpc admin 密码明文存于上述配置，属已知部署现状，本轮未改动。
