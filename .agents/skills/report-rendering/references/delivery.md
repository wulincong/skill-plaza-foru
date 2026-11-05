# 网页交付

脚本生成 index.html、report.css、theme.css，图稿完整内联。平台限制 object、embed、iframe，使用相对资源和系统字体离线打开。

网页声明追加到会话 delivery.json，保留已有 files 和其他 web 项。同一网页修订替换对应声明，写临时文件再原子替换。下例仅展示网页部分。

```json
{"web":[{"name":"报告网页版","directory":"output/public/site","entry":"index.html"}]}
```

产教报告先完成业务 report.py build 的四份原件与收据，再追加网页。平台发布实际文件并返回 URL。内部模型、原始材料、查询结果、图稿规格留在工作区，最终链接使用平台返回值。
