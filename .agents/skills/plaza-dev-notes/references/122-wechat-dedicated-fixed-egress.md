# 122 · 微信接口专用固定公网出口

状态：客户端接入、依赖、专用公钥与部署模板已准备，96项回归通过；公网服务器管理授权缺失，未启用固定出口，未修改公司主机路由或现有公网转发。当前公众号仍使用已加入白名单的办公网出口。

## 动机

192.168.10.7固定内网地址不代表固定公网出站源IP。biubiubiu.vip解析到115.231.218.150，已有frpc.ini将公网6001转发回报告主机127.0.0.1:22；通过该端口SSH并非登录公网服务器。当前wlc密钥访问115.231.218.150默认SSH端口未获授权。白名单和回调URL不会改变出站路由。

## 约定与接入

- 机器人`wxbot/wechat_http.py`只接受api.weixin.qq.com的HTTPS/443，`config.WECHAT_API_PROXY`为空时直接访问；配置后只接受socks5h://127.0.0.1:<1024..65535>。线程独享Session复用连接，trust_env=False；强制TLS验证、禁止重定向，错误不保留敏感URL。隧道断开不能回落办公网直连。
- `access_token.py`、`followers.py`、`customer_service.py`和`scripts/configure_account.py`共用该客户端；`report_bridge.py`在调用`save_report`时明确注入。主库`scripts/report_drafts.py:36`增加transport参数，`:103`附近save_report增加可选http_transport，所有正文图片、封面素材、draft/add调用使用同一客户端。既有默认调用、超时unknown和同版本幂等不变。
- 不修改REPORT_AGENT_URL/LLM客户端、Pi或数据库路由；AppSecret继续仅保存在原受限账号配置，不发到代理进程或云端应用。HTTPS透过SSH隧道仍与微信端到端验证。
- `deploy/wechat-egress.service`通过SSH -NT和本地127.0.0.1 SOCKS端口建立通道，systemd负责重连。`scripts/prepare_wechat_egress.py`只准备私有目录、密钥、SSH配置和单元副本，不安装/启动；目标/端口/用户名验证，文件符号链接拒绝，私钥0600且不打印，host key严格校验。
- 云端模板`deploy/sshd-wechat-egress.conf`仅作用于专用账号，AllowTcpForwarding local、PermitOpen api.weixin.qq.com:443、MaxSessions 0，禁远程转发、shell/subsystem、agent/X11/PTY/TUN。管理员需验证sshd -t及-T有效限制和原管理员登录，再重载。没有在未知服务器上执行模板。
- `deploy/wechat-bot-egress.conf`只提供WECHAT_API_PROXY进程变量。`scripts/check_wechat_egress.py`只验证token与draft/count，无proxy时拒绝验证。服务端授权、host key和实际出站地址确认、只读预检通过及生产空闲后才切换，回退仅移除对应独立drop-in。

## 验证边界

69项机器人回归（含7项专用传输测试）和27项主库草稿/成品库回归通过。覆盖代理失败不直连、目标白名单、TLS/重定向不能被调用者覆盖、配置错误联网前拒绝、异常不泄露URL、图片上传/草稿创建使用注入客户端。旧客服联调使用显式本地HTTP fixture transport；生产官方域名白名单不放宽。PySocks已安装，systemd-analyze verify和ssh -G配置解析通过，私有密钥未进入仓库。

主机侧实际直连token与原用户subscribe=1复验通过，当前出口14.19.90.74。以上不能代替公网隧道实测；115.231.218.150的实际出站地址、SSH授权、连接重建、真实卡片/草稿在新出口的验收尚未验证。未声称固定出口已经生效，未向真实粉丝发测试消息或新建草稿。

## 成本与取舍

复用既有固定IP服务器和SSH，不开放公网通用代理，也不迁移公众号Secret或整套报告计算。选择socks5h避免本机解析出的IP与服务端PermitOpen域名规则不一致。仅进程级微信客户端接入，避免全局HTTPS_PROXY把本机Pi、岗位库或其他用户流量带走。未对公司路由器、FRP及其他业务实施变更。

## 后续

取得115.231.218.150管理连接或由其管理员完成专用公钥授权；确认该服务器出站IP固定并与微信白名单匹配。先独立只读预检，后空闲切换；做断线不回落、自动重连、真实用户报告卡片及经明确确认的草稿保存回读。运维步骤见机器人deploy/egress-operations.md。

参考：Requests官方Advanced Usage代理/SOCKS文档；OpenSSH官方ssh(1)、sshd_config(5)。


### 2026-11-16 独立FRP微信信道实测

用户明确要求只在192.168.10.7新增微信信道并请求一次token后，建立独立STCP测试配置。既有frpc版本0.63.0；复制其common运行参数到~/.config/wechat-frp-probe/channel.ini（目录0700、配置0600），但不复制原SSH代理段，不更改原frpc.ini。移除独立进程会冲突的admin/start/includes配置，使用新的provider/visitor名称、随机STCP密钥及独立日志。provider和visitor均位于报告主机；visitor仅监听127.0.0.1:19443，provider固定连接api.weixin.qq.com:443，不开放公网端口或通用SOCKS代理。配置verify和systemd单元检查通过，以独立wechat-frp-probe.service启动，未启用自启或设置生产WECHAT_API_PROXY。

测试严格走本机visitor→115.231.218.150公网frps→本机provider→微信。Python HTTPSConnection只将底层TCP固定连接到本机visitor端口，TLS使用系统默认信任及api.weixin.qq.com SNI/主机名校验，没有直连回落。仅发出一次GET token，AppID和Secret在运行内存中读取，query和token不进入日志或回执。微信HTTP 200但业务返回40164，错误明确回显来源14.19.93.239，未获得token；总耗时0.962秒，TLSv1.2校验通过。凭据获取成功与HTTP连接成功不得混淆。

该实验实证：公网frps中转后又交回本机provider连接目标，并不能将目标看到的来源改成frps公网IP。若用FRP实现固定微信出口，应让负责连接微信的provider/受限代理运行于固定公网出口一侧；只在本机增配映射不够。亦不能在内网frpc启用socks5/http_proxy插件后，就认定出站发生在frps侧。官方参考：https://gofrp.org/zh-cn/docs/examples/stcp/ 及 https://gofrp.org/zh-cn/docs/features/common/client-plugin/ 。

完成后停止测试服务，保留私有配置和复测脚本~/.config/wechat-frp-probe/request-token.py。公众号与前后端生产服务仍active，既有SSH/网站配置未修改。复测需先启动该独立服务，再从wechat-ai-bot工作目录使用其venv和PYTHONPATH=.运行复测脚本；默认不应将这个已证实不能固定出口的实验信道接入生产。证据：web/server/traces/wechat-frp-token-probe-20261116.json（脱敏，无token/Secret）。公网出口节点授权仍待完成。
