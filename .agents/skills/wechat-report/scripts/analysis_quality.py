"""Guard claims that require evidence the platform snapshot does not contain."""
import re


def problems(text,field):
    issues=[]
    for sentence in re.split(r'[。！？；]',text):
        qualified=bool(re.search(r'不能|不等于|无法|不足以|尚不能|不宜|不应|不推断|而非|避免(?:直接|简单)?推断|待核实|待验证|假设|是否',sentence))
        if re.search(r'显著|稳定需求|人才短缺|供不应求|人才缺口|吸引力|高端岗位|低端岗位|领先全省|更倾向|重视程度|产业阶段|产业优势',sentence) and not qualified:
            issues.append(field+'包含未获当前样本支持的显著性、供需、时间或产业层次判断：'+sentence[:80])
        bounded=bool(re.search(r'不能|不等于|无法|不足以|不应|不代表|并非|而非|尚不能|待核实|待验证|假设|是否',sentence))
        unsupported_label_inference=(
            re.search(r'(?:反映|体现|说明|表明).{0,45}(?:任务复杂度|知识基础|系统性知识|实践能力|实践深度|知识偏好)',sentence)
            or re.search(r'条件比例.{0,25}(?:反映|代表|显示).{0,15}(?:实际进入机会|录用率|就业机会|通过率)',sentence))
        if unsupported_label_inference and not bounded:
            issues.append(field+'由招聘标签推断了未测量的能力或录用结果；改为解释条件如何联合筛选，并明确待核实的岗位职责：'+sentence[:140])
        if re.search(r'标题|\.title$',field) and re.search(r'决定|确保|保障',sentence) and not bounded:
            issues.append(field+'承诺了未经成效验证的结果；标题应写数据支持的结构差异或有条件决策：'+sentence[:100])
    return issues
