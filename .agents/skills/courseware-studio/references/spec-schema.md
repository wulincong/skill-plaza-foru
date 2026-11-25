# courseware-spec/1：课件构建契约

状态：已实现（`scripts/spec_model.py` 为校验权威，本文与其一一对应）。

spec 是课件的唯一事实源：PPTX 与网页预览都由它渲染，附录页（出处总表/版权/确认清单）也从它派生。改 spec 不改本文档视为违约。

## 顶层结构

```json
{
  "version": "courseware-spec/1",
  "meta": { "title", "hours", "course?", "unit?", "audience?", "teacher?", "style?", "final" },
  "standards": [ { "id", "code?", "title", "source" } ],
  "materials": [ { "id", "name", "kind", "pages?", "file?" } ],
  "slides": [ ... ],
  "copyright": [ { "materialId", "content", "license", "status" } ],
  "resources": [ { "name", "kind", "source", "file?" } ],
  "pendingConfirmations": [ { "id", "aspect", "text", "relatedSlides" } ],
  "confirmations": [ { "id", "decision", "note?" } ]
}
```

- `meta.title`/`hours` 必填；`style` 取值 clean-blue / warm-orange / ink-green / print-gray；`final` 默认 false。
- `materials.kind`：textbook / lesson-plan / training-guide / standard / kb-doc / image / other。`file` 为工作区相对路径（如 `uploads/xx.pdf`），存在即校验不越界。
- `copyright.status`：confirmed / pending（pending 在档案与预览中标「待教师确认」）。
- `resources.kind`：diagram / figure / case / image / table。

## slides 与页型

页型：cover / agenda / objectives / intro / concept / diagram / procedure / safety-warning / quiz / rubric / summary。

- 第一页必须是 cover；cover 不接受 blocks（课程、单元、课时、对象来自 meta）。
- 除 cover、agenda 外每页必须 `sources: [{materialId, pages?, note?}]` 非空——这是「逐页出处可查」的机器校验位。
- `knowledgePoints: [{name, standardId | extension:true}]`：挂课标或标拓展，二者必有其一。
- 附录页不要手写：构建器自动追加「材料与逐页出处总表」「版权与素材授权说明」「教师确认与资源入库」。

## blocks（内容块）

| kind | 字段 | 用途 |
|---|---|---|
| bullets | items[] | 要点列表 |
| paragraph | text | 段落说明 |
| two-col | left/right {title, items[]} | 对比栏 |
| steps | items[]（≥2） | 实训步骤（自动编号） |
| table | header[] + rows[][]（列数一致） | 测验、评分表 |
| image | path + caption + schematic? | 教师素材/教材图；示意图标 schematic |
| callout | tone(warn/info) + title + text | 安全警示卡、提示 |
| gap | text | 材料未覆盖，渲染为「待教师补充」占位 |

## 安全强制位

`safety-warning` 页必须：blocks 含 callout(warn)；`safety.requiresConfirmation=true`；`safety.items` 逐条列出步骤；且顶层 `pendingConfirmations` 存在 `aspect="safety-order"` 的条目指向该页。校验器强制这四点同时成立。

## 定稿门

`meta.final=true` 时，每条 `pendingConfirmations` 都必须有对应 `confirmations[]`（`decision:"confirmed"`）。未确认导出定稿会被 `load_spec` 直接拒绝——这是「未获教师确认不得定稿」的机器强制位，不要绕过（例如删掉 pendingConfirmations 再标 final）。

## 参考实现

`tests/examples/valid-spec.json` 是覆盖全部块类型与安全页的完整样例；单元测试 `tests/test_build.py` 同时是 schema 行为的成文规范。
