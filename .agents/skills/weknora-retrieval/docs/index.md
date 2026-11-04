# 从 WeKnora 知识库查找并引用原文

业务技能可以在获准的知识库中查教材、专业标准和产业资料。检索结果带有文档标题和分块标识，可回到原文核对条款或数字。

按主题选库时，可先读带探测时间的[知识库盘点](inventory-20261104.md)。库名有时比实际收录范围窄，例如人工智能专业教学标准也收在纺织专业教学标准库。先用目录定位资料，再用原文核实要引用的结论。

## 找到目标文档

以“现代非织造技术专业面向哪些岗位”为例。从仓库根目录运行以下命令。需要 Python 3.10 或更高版本，并由调用方在进程环境中设置 `WEKNORA_API_KEY` 和 `WEKNORA_KB_IDS`。后者填写允许查询的库 ID，多个 ID 用逗号分隔。

```sh
tool=.agents/skills/weknora-retrieval/scripts/retrieve.py
python3 "$tool" bases
```

从返回的 `items` 中选出纺织专业教学标准所在的库，把它的 `id` 赋给 shell 变量 `KB_ID`，再按标题查目录。

```sh
python3 "$tool" documents --kb "$KB_ID" --keyword '现代非织造技术专业教学标准'
```

## 核对引文

从目录结果中核对专业名称和教育层次，将选中文档的 `id` 赋给 `DOC_ID`。用它限定搜索范围，再读取同一文档的原文分块。

```sh
python3 "$tool" search --kb "$KB_ID" --document "$DOC_ID" --query '该专业面向哪些职业岗位？'
python3 "$tool" chunks --kb "$KB_ID" --document "$DOC_ID" --page 1
```

搜索预览可能包含相邻段落。如果当前页还没有要引用的句子，按 `next_page` 翻页。引用时记录文档标题、文档 ID，以及实际包含该句的分块 `id` 和 `chunk_index`。仅按主题查资料时，省略 `--document` 即可搜索整库。

命令向标准输出返回 JSON。`empty` 表示这次查询或这一页没有结果。`forbidden` 表示无权访问该范围，`unavailable` 表示服务未能返回可用结果。
