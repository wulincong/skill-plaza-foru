# tech-forecast

「新岗位·新技术预判」技能。**直接内置于技能广场主仓库**（[skill-plaza-foru](https://github.com/wulincong/skill-plaza-foru) 的 `.agents/skills/tech-forecast/`），不设独立父仓库；由 Pi 通过 `--skill` 加载。

## 功能

面向院校与培训机构：新兴技术成熟度分析（雷达图）、技能演进路径（桑基图）、新兴岗位预测、新兴技能预测与培训方向建议，输出固定七章结构的 HTML 报告（写入会话 workspace/report.html）。预测字段强制标注证据等级（库内实测 / 内置文档 / 分析推断），不编造趋势数据。

## 结构

- `SKILL.md`：技能入口与报告协议。
- `references/output-schemas.md`：报告 HTML 骨架与各表字段。
- `references/technology-snapshots.md`：新兴技术清单与成熟度评估框架（编辑判断快照）。
- `references/skill-evolution-map.md`：传统技能 → 新兴技能演进对照。
- `references/major-mapping.md`：技术领域与院校专业对照。
- `agents/openai.yaml`：智能体接口元信息。
