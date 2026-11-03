"""Apply the user-approved multivariate chart policy to the evidence-bound report."""
from bound_report import project
from chart_recommender import MULTIVARIATE_SPECS as SPECS,MULTIVARIATE_POLICY,recommend_multivariate

def upgrade(outline,data,binding):
    if 'city_profiles' not in data:raise ValueError('新版多维报告缺城市同口径指标；应在写作前预检并以原筛选补齐geography，不能扩大地域或学历范围')
    decisions=[]
    for i,screen in enumerate(outline['screens']):
        choice=recommend_multivariate(screen['title'],data)
        if not choice:continue
        for key in ['chart','chart2','chartA','chartB']:screen.pop(key,None)
        prefix=f'/screens/{i}/'
        for path in list(outline['bindings']):
            if path.startswith(prefix) and path[len(prefix):].split('/')[0] in ('chart','chart2','chartA','chartB'):
                del outline['bindings'][path]
        spec=choice['spec']
        if not spec:
            decisions.append({'topic':screen['title'],'status':'omitted','reason':choice['reason']});continue
        # Missing source sections are not fabricated; a text chapter keeps the declared gap.
        try:cfg=project(data,spec)
        except KeyError:cfg=None
        if not cfg:
            decisions.append({'topic':screen['title'],'status':'omitted','reason':'缺少同口径有效样本，不回退为边际猜测'});continue
        ids=[]
        for source_path in [spec['path']]+[item['path'] for item in spec.get('inputs',{}).values()]:
            matches=[path for path in binding['fields'] if source_path==path or source_path.startswith(path+'/')]
            if matches:ids+=binding['fields'][max(matches,key=len)]
        checked=dict(spec,metricIds=sorted(set(ids)))
        screen['chart']=cfg;outline['bindings'][prefix+'chart']=checked
        decisions.append({'topic':screen['title'],'status':'selected','operation':spec['op'],'kind':cfg['kind'],'reason':choice['reason']})
    outline['presentation']='wechat-multivariate/1'
    outline['chart_selection']={'policy':MULTIVARIATE_POLICY,'decisions':decisions}
    return outline


def verify_policy(outline):
    if outline.get('presentation')!='wechat-multivariate/1':raise ValueError('报告尚未采用新版多维呈现规范')
    charts=[screen[key] for screen in outline['screens'] for key in ['chart','chart2','chartA','chartB'] if screen.get(key)]
    columns=[chart for chart in charts if chart['kind'] in ('hbar','vbar','stacked_pct','city_combo')]
    if len(columns)>1:raise ValueError('整份报告最多一张柱状图')
    if columns and (columns[0]['kind']!='city_combo' or set(columns[0].get('metrics',[]))!={'salary_median','bachelor_share','positions'}):
        raise ValueError('柱状图必须联合薪酬、学历要求占比与岗位规模三个指标')
    if outline['analysis'].get('schema')!='wechat-analysis/2':raise ValueError('核心发现尚未采用有跨维度论证的总分总结构')
    return True
