"""Guard claims that require evidence the platform snapshot does not contain."""
import re


def problems(text,field,semantic=True):
    issues=[]
    if re.search(r'(?:确保|保证|保障).{0,40}(?:就业|录用|匹配|符合|具备|对应|对接|成效|能力)',text):issues.append(field+'使用未经成效验证的承诺；改为明确的任务、成果与评价标准')
    from editorial_prose import PROCESS_WORDS
    if PROCESS_WORDS.search(text):issues.append(field+'含不适合成品的过程性措辞，请改写为完成的观察或具体课程建议')
    for sentence in re.split(r'[。！？；，,]',text):
        qualified=bool(re.search(r'不能|不等于|无法|不足以|尚不能|不宜|不应|不推断|而非|避免(?:直接|简单)?推断|待核实|待验证|假设|是否',sentence))
        conditional=bool(re.match(r'\s*(?:调整条件[：:]\s*)?(?:若|如果|一旦)',sentence))
        if re.search(r'已给事实|凭空声称|本批次|findingIds|写作规则|文案字段|不补零不猜测|词表完美',sentence,re.I):
            issues.append(field+'把内部写作提示写进了成品；改为读者需要的数据边界、判断或行动：'+sentence[:140])
        qualified=qualified or conditional
        if re.search(r'增长最快|快速增长|增速|保持稳定|持续释放|招聘节奏|显著高于|远高于|溢价|样本代表性',sentence) and not qualified:
            issues.append(field+'包含当前横截面无法证明的动态、回报或显著性判断：'+sentence[:140])
        if re.search(r'源于|得益于|导致|带动了|必然|证明了',sentence) and not (qualified or re.search(r'可能|需核|核实|核对|检验|避免|防止|若|如果',sentence)):
            issues.append(field+'把解释写成已证实因果；需核实机制并排除替代解释：'+sentence[:140])
        if not semantic:continue
        if re.search(r'显著|稳定需求|人才短缺|供不应求|人才缺口|吸引力|高端岗位|低端岗位|领先全省|更倾向|重视程度|产业阶段|产业优势',sentence) and not qualified:
            issues.append(field+'包含未获当前样本支持的显著性、供需、时间或产业层次判断：'+sentence[:80])
        bounded=conditional or bool(re.search(r'不能|不等于|无法|不足以|不应|不代表|并非|而非|尚不能|待核实|待验证|假设|是否',sentence))
        unsupported_label_inference=(
            re.search(r'(?:反映|体现|说明|表明).{0,45}(?:任务复杂度|知识基础|系统性知识|实践能力|实践深度|知识偏好)',sentence)
            or re.search(r'条件比例.{0,25}(?:反映|代表|显示).{0,15}(?:实际进入机会|录用率|就业机会|通过率)',sentence))
        if unsupported_label_inference and not bounded:
            issues.append(field+'由招聘标签推断了未测量的能力或录用结果；改为解释条件如何联合筛选，并明确待核实的岗位职责：'+sentence[:140])
        degree_task=(re.search(r'(?:本科|专科|大专|硕士|博士)(?:生|学生|组|及以下|及以上)?.{0,18}(?:侧重|适合|负责|定位|聚焦|应培养|参与|安排|进入|配置|开展|接受|从事).{0,30}(?:算法|研发|数据|工具|理论|基础|模型|系统|开发|项目|任务)',sentence) or re.search(r'(?:算法|研发|数据|模型|系统|开发|项目|任务).{0,24}(?:面向|仅安排|只安排).{0,16}(?:本科|专科|大专|硕士|博士)',sentence))
        if degree_task and not re.search(r'不按学历|不以学历|共同参与|均可参与|不限定学历|任务完成情况|任务准备度|作品表现|项目产出',sentence):
            issues.append(field+'仅按学历分配了未经验证的技能任务；按任务准备度和作品表现分流，所有学历共享任务入口：'+sentence[:140])
        if re.search(r'(?:高薪|低薪).{0,15}(?:侧重|说明|代表|意味着).{0,15}(?:高级|高阶|复杂|基础|低阶)',sentence) and not bounded:
            issues.append(field+'把薪酬层次替代了技能任务难度；课程应依据具体职责与能力验证：'+sentence[:140])
        if re.search(r'上四分位.{0,15}(?:作为上限|设为上限|薪酬封顶|起薪上限)',sentence) and not re.search(r'不是|不应|不能|未把|未将|不要|不把|不将|而非|而不是|中间一半|四分位区间',sentence):
            issues.append(field+'将上四分位当成了薪酬上限；它只是分布区间边界：'+sentence[:140])
        if re.search(r'提及率.{0,12}(?:低|偏低).{0,15}(?:则|需|应).{0,12}(?:补充|强化|增加)',sentence) and not re.search(r'企业确认|产出测评|职责核实|不能|不等于',sentence):
            issues.append(field+'由低词频反推出培养缺口；需经职责核实和学生产出测评后决定：'+sentence[:140])
        actual_acceptance=re.search(r'(?:说明|证明|表明).{0,35}(?:企业|岗位).{0,30}(?:接收|录用|接受|吸纳).{0,10}(?:毕业生|应届)',sentence)
        negates_acceptance=re.search(r'不能(?:据此)?(?:推断|说明|证明|认定)|不(?:等于|代表)|无法(?:判断|证明|确认)|尚未(?:核实|确认)|待核实|是否',sentence)
        if actual_acceptance and not (conditional or negates_acceptance):
            issues.append(field+'将招聘标签/筛选条件推断成实际接收或录用；当前只支持口径比较，需核实企业反馈：'+sentence[:140])
        if re.search(r'(?:覆盖率|份额).{0,8}高的企业|(?:提高|提升|降低).{0,8}(?:录用率|合作成功率)',sentence) and not bounded:
            issues.append(field+'使用了尚未测量的企业覆盖率或成功率；改为候选城市/岗位调研与可核实产出：'+sentence[:140])
        if re.search(r'标题|\.title$',field) and re.search(r'决定|确保|保障',sentence) and not bounded:
            issues.append(field+'承诺了未经成效验证的结果；标题应写数据支持的结构差异或有条件决策：'+sentence[:100])
    return issues
