"""Evidence-only multi-panel specifications. Every value is derived from saved data.

Horizontal composition follows the cumulative stacking pattern illustrated by
Matplotlib's horizontal_barchart_distribution gallery. This implementation uses
the project's ECharts renderer; it does not copy the gallery's sample data/code.
"""
from collections import defaultdict


def requirements_composition(rows):
    totals=defaultdict(int);columns=defaultdict(int);cells=defaultdict(int)
    for education,experience,count in rows:
        totals[education]+=count;columns[experience]+=count
        cells[(education,experience)]+=count
    groups=sorted(totals,key=lambda label:(-totals[label],label))
    categories=sorted(columns,key=lambda label:(-columns[label],label))
    return {'kind':'stacked_pct','caption':'每类学历内部的经验构成（%）；各行分母不同',
            'rows':groups,'cols':categories,'counts':[totals[label] for label in groups],
            'cells':[[i,j,round(cells[(group,category)]/totals[group]*100,4)]
                     for i,group in enumerate(groups) for j,category in enumerate(categories)]}


def city_concentration(data):
    rows=sorted(data['city'],key=lambda row:(-row[1],row[0]))
    head=rows[:2];remainder=data['total']['positions']-sum(row[1] for row in head)
    result=[[label,count] for label,count in head]
    if remainder>0:result.append(['其余地区及地址未归属',remainder])
    return {'kind':'donut','caption':'头部城市与其余样本的份额（分母为全部岗位记录）','data':result}


def salary_cohorts(data):
    rows=[]
    for label,salary in [('全部岗位',data.get('salary') or {}),
                         ('职教入门池',(data.get('voc_pool') or {}).get('salary') or {})]:
        if salary.get('valid',0)>=30 and all(salary.get(key) is not None for key in ('p25','median','p75')):
            rows.append([label,salary['valid'],salary['p25'],salary['median'],salary['p75']])
    if len(rows)<2:return None
    return {'kind':'range_dot','caption':'总体与入门池薪酬对比：中间一半与中位数（K/月）','data':rows}


def cohort_cities(data):
    pool=data.get('voc_pool') or {};total=data['total']['positions'];pn=pool.get('count',0)
    if not total or not pn:return None
    overall=dict(data.get('city',[]));entry=dict(pool.get('city',[]))
    labels=sorted(overall,key=lambda label:(-overall[label],label))[:6]
    return {'kind':'dumbbell_pct','caption':'各城市在总体与入门池中的份额（%）；比较的是份额，不是录用率',
            'data':[[label,round(overall[label]/total*100,2),round(entry.get(label,0)/pn*100,2)] for label in labels]}
