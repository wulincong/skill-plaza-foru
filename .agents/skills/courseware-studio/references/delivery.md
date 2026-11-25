# 交付布局与原子登记

状态：已实现（对齐平台 088 交付契约与 089 低权权限约定）。

## 会话工作区布局

```
uploads/                     教师材料（平台上传通道，只读边界）
courseware/
  spec.json                  courseware-spec/1，课件唯一事实源（内部，不公开）
courseware.pptx              课件成品（files[] 交付）
courseware-archive.md        课件档案：版权/待确认/资源清单（files[] 交付）
output/site/
  index.html                 网页预览（web[] 交付入口）
  assets/figureN.*           预览引用的图片副本
material-images/             教材图提取产物（内部，按需带入 spec）
delivery.json                交付清单（最后原子写入）
```

- 公开边界：`output/site/` 整目录公开，其中只放预览必需文件；spec、材料摘录、提取中间物不入 `output/`。
- `uploads/`、隐藏目录与绝对路径不得出现在 delivery.json；`register_delivery.py` 已做越界与符号链接拒绝。

## 登记命令

```
python3 <本技能目录>/scripts/register_delivery.py output/site \
  --file "课件成品（PPTX）=courseware.pptx" \
  --file "课件档案=courseware-archive.md" --workspace .
```

- `web[]` 以目录 `output/site` 为键去重替换（校订稿→定稿重建时不产生重复网页条目）；`files[]` 整组替换并带 sha256。
- 清单 `chmod 0640`、`os.replace` 原子生效；任一文件缺失/越界保持旧清单不变并报错。
- 平台对每个交付版本分配独立 ID 并返回 `/p/<id>/` 预览链接与下载链接；模型不自行拼 URL、不声称已交付，以平台返回为准。

## 重建语义

- 校订稿→定稿：改 spec（confirmations + final）→ 重建 pptx/preview/archive → 重新登记。同名网页条目替换到新目录，旧链接保留旧版本。
- 仅呈现修订（风格/措辞）：同样全链重建，避免 PPTX 与预览内容漂移。

## PPTX 技术边界

stdlib OOXML 写入（zipfile + XML，1 母版 + 2 版式 + 主题），PowerPoint/WPS 可直接编辑文本、表格与图片。v1 无备注页（speaker notes）：出处由页脚标注 + 预览侧栏 + 附录页承载，路线见开发手记 122。
