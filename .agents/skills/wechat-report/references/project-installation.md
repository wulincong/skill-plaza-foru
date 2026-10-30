# 项目安装与运行

来源：<https://github.com/MJL629/Official-Account-Skill> 的 `wechat-report/`，固定提交 `286cee93072e1b8e8539a88b80487967440a2f74`（2026-10-30）。保留完整脚本、参考文档、图表资源与两份上游示例数据；示例不代表当前数据库查询结果。

本地适配：补充技能 frontmatter、Python 依赖清单、Linux 浏览器与中文字体支持，修正数据库配置的保存位置及横向柱状图模板参数顺序，并在广场注册对话入口。不注册任务表单，也不套用现有 HTML/PDF 报告的固定文件协议。

## 安装依赖（开发者执行一次）

在技能安装目录执行：

```bash
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

运行时使用安装目录 `.venv/bin/python` 的绝对路径，避免沙箱 PATH 与开发环境的 Python 不一致。图片渲染自动查找 Edge、Chrome 或 Chromium，也可用 `WECHAT_REPORT_BROWSER` 指定浏览器可执行文件。

## 每个会话的工作副本

Pi 的当前目录是本次会话 workspace。将**本次加载的 SKILL.md 所在目录**作为 `SKILL_DIR`，不要猜路径。首次执行时，只把 `scripts/`、`assets/`、`references/`、`example/`、`position_type_dict.json` 复制到当前目录的 `wechat-report/`；不要复制 `.venv/`、历史输出或真实密钥文件。后续轮次沿用该副本，避免覆盖用户编辑的大纲。

例如把 `SKILL_DIR` 替换为本次加载的真实绝对目录后：

```bash
mkdir ./wechat-report
cp -R "$SKILL_DIR/scripts" "$SKILL_DIR/assets" "$SKILL_DIR/references" \
  "$SKILL_DIR/example" "$SKILL_DIR/position_type_dict.json" ./wechat-report/
cd ./wechat-report
```

所有后续脚本均在副本中运行，解释器仍使用 `"$SKILL_DIR/.venv/bin/python"`。

## 数据与交付

- 真实岗位查询需要副本根目录的 `db_config.json`（host/port/user/password/database/charset）；由用户或部署者通过本地配置提供，`scripts/db_setup.py` 可交互验证并保存。**不从示例复制连接信息，不回显密码。**本次安装没有创建数据库或公众号凭据。
- 用户明确要离线演示时，将 `example/report_data.json` 复制为副本根目录的 `report_data.json`，运行 `scripts/gen_outline.py`。先呈现 `output/outline/outline.md` 供确认。
- 大纲确认后，运行 `scripts/render_report.py`、`scripts/build_article.py` 与 `scripts/evidence_sheet.py`，按上游 `verify_data.py` / `render_check.py` 规则核验。示例验证只说明工具可运行，不证明真实岗位数据或报告质量。
- `output/report/` 包含分屏 PNG、长图与 manifest，`output/article/` 包含 Markdown/HTML，`output/evidence_核查表.xlsx` 是核查表。当前项目没有为该技能增加图片/ZIP 下载协议，回复真实生成的文件位置，不伪造下载链接。
- `assets/mp_config.example.json` 仅是模板。推送草稿需要用户明确要求，并在副本配置真实的 `assets/mp_config.json`、账号权限和 IP 白名单；本次安装未做微信接口调用。

## 使用入口

在线对话选择 `$wechat-report`，或从广场点击“在线运行”，直接进入已挂载该技能的对话。最小输入：`使用 $wechat-report，为广东省人工智能产业拟一份公众号报告大纲，读者是院校管理者；先说明所需数据。`
