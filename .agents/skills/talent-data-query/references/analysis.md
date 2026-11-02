# 方向与技能聚合（engine 1.2）

在 talent-query/1 顶层增加 analysis；只有受支持的规则、ID和词，不接受 SQL 或正则。策略、词表及顺序纳入结果内容/缓存键，不共享不同分类口径的结果。

```json
{
  "tracks": [
    {"key": "algorithm", "label": "算法研发", "titleAny": ["算法", "SLAM"]},
    {"key": "control", "label": "控制调试", "titleAny": ["控制", "调试"], "roleIds": ["123"]}
  ],
  "skills": ["Python", "C++", "ROS", "ROS2", "PLC"]
}
```

该对象放在 request.analysis；roleIds 仅为格式示例，实际先通过 resolve --kind role 查询并确认岗位类型ID，不能填产业ID。方向规则最多12组，key/label唯一；每组 titleAny 最多8个包含词、roleIds最多40个完整ID。同一规则内任一条件命中即可，规则按输入顺序取首个，未命中为 __other__/未分类。名称匹配沿用源库大小写语义；百分号、下划线转义为普通字符。

技能词1–60个，最长60字符、忽略大小写不能重复。skills-policy/1 对描述做LOWER子串匹配，每岗位每词最多一次；ROS会命中ROS2，多个词的计数可重叠，不加总为独立岗位数。描述为空、null或仅空白视为缺失；结果只返回聚合，不返回描述文本。

| 指标 | 结果 |
|---|---|
| track.distribution | track、label、count、share；含未分类，完整分布 |
| city_track.cross | province、city、track、label、count、share；分母为整组岗位，缺失地区独立 |
| track_salary.summary | 每组 count、validN、excludedN、summary；与 salary-policy/1 同算法，零有效薪酬的摘要为 null |
| skills.distribution | skill、count、share（全岗位分母）、describedShare（有描述分母）；总 describedN/missingN |
| track_skills.cross | track、skill、count、positions、describedN、share（方向全部岗位分母）、describedShare |

track_skills.cross 同时需要 tracks 和 skills；其他方向指标需要 tracks，skills.distribution需要skills。不自动推断规则。所有指标保留实际 evidenceIds；tracks/city_tracks 共享一个频数查询，技能词在一个条件聚合中计算；分方向薪酬复用同一份中点频数，不逐词或逐方向发查询。

方向方法为 track-policy/1；分析配置的内容指纹写入 method。规则或词表变化即新请求，不与旧报告无声混拼。LQ 可从完整 city_track.cross 计算：(本市方向数/本市总数)/(全样本方向数/全样本总数)，零分母不可计算；如使用不同地域覆盖基数须明确方法。

分组/字节/事务预算仍按共享限制执行。请求太宽导致超限即未完成，不抽样、不裁断后宣称全量。不提供同义词归并、词界解析或原始描述导出；这些需求需独立扩展策略。
