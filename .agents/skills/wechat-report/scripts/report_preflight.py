"""Fail before model writing when saved statistics cannot support this report."""
from chart_recommender import MULTIVARIATE_SPECS,recommend_multivariate


def check(data,pack):
    if not data.get('total',{}).get('positions'):
        raise ValueError('当前范围无岗位记录，不生成研究报告，不放宽用户筛选')
    if 'city_profiles' not in data:
        raise ValueError('写作前预检：缺少城市联合统计。使用原地域/产业/学历/经验筛选，在plan.sections加入geography并重新collect；不要先写文案，不得扩大范围。')
    if len({row['section'] for row in pack['findings'] if row['section']!='overview'})<2:
        raise ValueError('写作前预检：仅有单一分析维度，无法支持跨维度核心发现；请按原筛选补充requirements、salary或适用的方向统计')
    choices=[{'topic':topic,**recommend_multivariate(topic,data)} for topic in MULTIVARIATE_SPECS]
    from regional_reasoning import section,core,opening
    from report_analysis import _narrative,entity_labels
    from executive_analysis import default_pairs
    from analysis_quality import problems
    labels=entity_labels(data);issues=[]
    fixed=[('摘要',{'interpretation':opening(data)})]
    fixed += [(key,section(data,key)) for key in pack['requiredSections']]
    fixed += [('核心结论',core(data,pair,index)) for index,pair in enumerate(default_pairs(pack))]
    for key,row in fixed:
        for field,text in row.items():
            try:_narrative(text,key+'.'+field,4 if field=='title' else 40,labels)
            except ValueError as exc:issues.append(str(exc))
            issues+=problems(text,key+'.'+field)
    if issues:raise ValueError('REPORT_TEMPLATE_ERROR：'+'；'.join(issues))
    return {'schema':'wechat-report-preflight/1','ready':True,
            'scope':{'region':data['meta']['region'],'industry':data['meta']['industry']},
            'cityGroups':len(data['city_profiles']),
            'fixedProse':'validated-before-model-writing',
            'optionalEntryPool':'available' if 'voc_pool' in data else 'not_available',
            'omittedComparisons':[{'topic':row['topic'],'reason':row['reason']} for row in choices if row['spec'] is None]}


if __name__=='__main__':
    import json
    from pathlib import Path
    from report_runtime import report_root
    from bound_report import load_data
    from report_analysis import evidence_pack
    root=report_root(__file__);data,binding=load_data(root/'report_data.json')
    print(json.dumps(check(data,evidence_pack(data,binding)),ensure_ascii=False))
