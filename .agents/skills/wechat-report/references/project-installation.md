# 项目安装与运行

本技能使用共享人才查询工具取数，Python 仅负责报告、图片和核查工作簿。Node ≥20 与 MySQL 客户端属于 talent-data-query 的部署依赖；连接配置只由共享工具读取。

## 安装与工作副本

开发者在技能目录创建 Linux .venv 并安装 requirements.txt；报告使用已安装的 Pillow、openpyxl，以及系统 Chrome/Chromium。浏览器可通过 WECHAT_REPORT_BROWSER 指定。

将本次加载的技能目录作为 SKILL_DIR。首次执行只复制 scripts、references、example 和必要资产到会话的 wechat-report/；不要复制 .venv、历史输出或真实微信配置。资产白名单：brand.json、themes.json、curriculum_map.json、echarts.min.js、mp_config.example.json。已有副本沿用，避免覆盖用户编辑。

Node 收集入口使用安装目录绝对路径，避免复制后丢失共享依赖定位；或通过 TALENT_DATA_QUERY_CLI/--query-cli 指定部署提供的共享入口。执行 cwd 为会话工作副本，所有请求、结果和输出留在本次会话。

## 真实数据流程

在工作副本写 plan.json，示例见 [data-aggregation.md](data-aggregation.md)，然后：

~~~bash
node "$SKILL_DIR/scripts/collect_data.mjs" --plan plan.json
"$SKILL_DIR/.venv/bin/python" scripts/report_analysis.py
# 阅读完整数据和 output/analysis/analysis_evidence.md，由智能体撰写 report_analysis.json
"$SKILL_DIR/.venv/bin/python" scripts/generate_report.py --workspace ..
~~~

collect_data 也接受 --result 指向本会话已保存且可核验的 talent-result/1，适配时不查库。已保存的数据不依赖15分钟查询缓存；刷新需重新收集并完成新版本分析，再生成新大纲。report_analysis.py 只生成事实证据和空分析结构；必须按 research-analysis.md 写出解释、行动和验证方式，不可直接把 analysis_draft.json 当完成稿。

以上命令在会话的 wechat-report/ 工作副本执行，--workspace .. 将 delivery.json 写到会话根；独立运行且技能目录就是工作区时省略该参数。pack_delivery 生成 output/public/site/index.html 和引用图片、output/public/report.zip，清单路径相对于会话根。广场在完成时统一持久保存，对话右侧资源栏显示“打开网页 / 复制链接”和“下载文件”；窄屏通过资源入口展开，回复下方保留“查看资源”，不暴露工作区。输出 report_data.json、report_binding.json、data/ 下共享原工件、output/outline、output/report、output/article。内部核查表位于 output/internal/，不进入公开ZIP或网页。不存在独立数据库配置或交互式连接设置流程；共享工具不可用时说明错误，不回退样例。

## 演示与公众号

用户明确要求演示时，将 example/report_data.json 复制到工作副本的 report_data.json，生成大纲、渲染、文章、校验和核查表时显式传 --demo。演示不证明真实查询通过，当前公开打包入口仅接受真实绑定结果。

网页分享由广场静态交付服务提供，公开网页只含报告图片。成品入库与保存确认由平台处理，公众号凭据仅在wechat-ai-bot本地配置中，由私有草稿桥读取；工作副本不创建mp_config.json，不直接调用发布脚本。独立离线维护脚本保留旧本地配置方式，不能与在线流程混用。

Linux 低权运行器与后端通过工作区共享组交接：打包脚本为公开 site 目录保留组读/穿行权限，清单为 0640。若平台提示权限错误，保留原清单路径，检查共享组与生成权限；不要仅为修复按钮而移动整套产物。

默认流程连续执行到最终图片。outline.json/md 只是内部排版结构，不需要向用户展示或等待确认。实际渲染使用 SVG 图表、字体就绪与 DOM 测高；布局证据和 PNG 指纹存入 manifest，最终质检生成 quality.json，打包拒绝缺失或过期的质检。
