# 安装与受信报告入口

开发者在安装技能目录创建.venv，安装requirements.txt与系统Chrome/Chromium。Playwright复用系统浏览器，WECHAT_REPORT_BROWSER可指定路径。Node≥20及MySQL只读配置仅由共享talent-data-query部署持有。

Pi调用安装目录的绝对路径：`.venv/bin/python scripts/report.py --workdir <会话根>/wechat-report <任务>`。这里scripts/report.py必须指向**安装目录**，不是数据目录。平台已提供实际完整命令时直接使用，不再猜路径或复制代码。report.py在进入底层脚本前设置WECHAT_REPORT_WORKDIR并切换数据目录，底层Python通过report_runtime读取数据根；代码仍来自安装目录。数据目录不能落在安装目录内。

| 任务 | 行为 |
|---|---|
| init | 只复制必要资产，返回planTemplate与profile命令说明；不复制脚本、.venv、凭据或历史输出 |
| next | 返回下一个短写作批次、模板、已绑定事实和分析问题 |
| accept report_part.json | 校验片段、持久保存进度，返回下一批；全部完成后自动组装analysis |
| analyze | 可选完整稿入口：输出写作简报与writing_draft |
| assemble report_writing.json | 可选完整稿合并与统一校验 |
| build | 连续重验当前稿、排版、质检、出图、私有文章与公开打包 |
| check --stage final | 最终复验，不能替代实际生成 |

取数仍使用安装目录scripts/collect_data.mjs，在数据目录执行并传--plan plan.json；共享CLI由安装关系或TALENT_DATA_QUERY_CLI定位，不复制密码配置。新增城市薪酬必须来自city_salary.summary，同城市学历基数对账；不能从旧快照的城市计数推算薪酬。

工作目录只存assets、data、plan.json、report_part.json/最终文案及output。短批次进度在output/analysis/writing_progress.json，数据指纹改变不能混用旧进度。已有真实数据在续写、修订、重启后直接读取，不因查询缓存过十五分钟重查。旧副本脚本不再作为正常入口；prepare_session.py --legacy-scripts仅保留独立离线兼容方式。

公开交付output/public/site与report.zip，图片manifest和quality.json绑定实际PNG、数据、排版与系列数值；build_receipt.json记录真实子进程步骤及程序指纹，仅内部留存。生成期间代码版本改变则停止交付，沿用数据重试。公开产物最后才生成会话根delivery.json，平台收集并提供网页/下载。

公众号账号凭据仅留wechat-ai-bot配置，明确确认后平台私有桥保存草稿。离线publish_draft.py操作记录不能作为在线成功证明；当前40164需官方账号IP白名单变更，不能用样例或模拟回执冒充成功。
