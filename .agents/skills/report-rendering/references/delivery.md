# 网页交付

脚本生成 index.html、report.css、theme.css，图稿完整内联。平台限制 object、embed、iframe，使用相对资源和系统字体离线打开。

网页声明追加到会话 delivery.json，保留已有 files 和其他 web 项。同一网页修订替换对应声明，写临时文件再原子替换。下例仅展示网页部分。

```json
{"web":[{"name":"报告网页版","directory":"output/public/site","entry":"index.html"}]}
```

完成页面并验收后，在会话工作区运行：

```sh
python3 <渲染技能目录>/scripts/register_delivery.py output/public/site-r1 --name 报告网页版
```

脚本检查入口存在、原子更新清单；同名网页替换为新修订目录，其他网页及下载保留。它只登记平台交付，尚未生成公开 URL。

产教新报告先完成业务 report.py build 的四份原件与收据，再登记网页，不在四份文件生成后结束。纯排版或补图修订可以复用上一已交付的业务版本，不需要重查或重建业务内容：从 industry-report-input.json 读取 previousBuildRun，使用对应 industry-build-<previousBuildRun>.json 的四份原件；按本次新目录重排，登记时传 `--files-from industry-build-<previousBuildRun>.json`。脚本回查原件指纹，平台再次验证并为本轮关联同一内容版本。改动业务内容则重新复核、build 后再交接。

每轮修订必须重新登记 delivery.json，不能只修改已声明目录里的 HTML。平台发布实际文件并返回 URL。内部模型、原始材料、查询结果、图稿规格留在工作区，最终链接使用平台返回值。

平台对业务成稿中的分布、同单位/地域/时期/统计对象的多项数值检查网页是否有已绘制统计图。只交总量卡片、数值表或未评估占位不能通过该检查；纯文字、单个标量或不可比指标无需凑图。图型仍由本技能按真实关系选择。
