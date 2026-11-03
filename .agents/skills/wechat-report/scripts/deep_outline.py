"""Apply the user-approved multivariate chart policy to the evidence-bound report."""
from bound_report import project

SPECS={
    '招聘地域分布':{'path':'/city_profiles','op':'joint_city'},
    '学历要求':{'path':'/edu_exp','op':'joint_requirements'},
    '经验要求':{'path':'/edu_exp','op':'joint_experience'},
    '学历与经验交叉':{'path':'/edu_exp','op':'joint_access'},
    '薪酬结构':{'path':'/salary','op':'joint_salary','inputs':{'entry':{'path':'/voc_pool/salary'}}},
    '岗位方向结构':{'path':'/subtrack','op':'joint_tracks','inputs':{'salary':{'path':'/salary_by_track'}}},
    '方向薪酬比较':{'path':'/salary_by_track','op':'joint_track_salary'},
    '城市与岗位方向':{'path':'/city_track_rows','op':'joint_city_tracks'},
    '地域方向集中程度':{'path':'/city_track_rows','op':'joint_lq'},
    '人才能力关键词':{'path':'/job_skill_rows','op':'joint_skills'},
    '职教入门岗位观察':{'path':'/voc_pool/track','op':'joint_entry','inputs':{
        'all':{'path':'/subtrack'},'salary':{'path':'/voc_pool/salary_by_track'}}},
}


def upgrade(outline,data,binding):
    if not data.get('city_profiles'):raise ValueError('新版多维报告需要城市薪酬与城市学历的同口径统计')
    for i,screen in enumerate(outline['screens']):
        spec=SPECS.get(screen['title'])
        if not spec:continue
        for key in ['chart','chart2','chartA','chartB']:screen.pop(key,None)
        prefix=f'/screens/{i}/'
        for path in list(outline['bindings']):
            if path.startswith(prefix) and path[len(prefix):].split('/')[0] in ('chart','chart2','chartA','chartB'):
                del outline['bindings'][path]
        # Missing source sections are not fabricated; a text chapter keeps the declared gap.
        try:cfg=project(data,spec)
        except KeyError:cfg=None
        if not cfg:continue
        ids=[]
        for source_path in [spec['path']]+[item['path'] for item in spec.get('inputs',{}).values()]:
            matches=[path for path in binding['fields'] if source_path==path or source_path.startswith(path+'/')]
            if matches:ids+=binding['fields'][max(matches,key=len)]
        checked=dict(spec,metricIds=sorted(set(ids)))
        screen['chart']=cfg;outline['bindings'][prefix+'chart']=checked
    outline['presentation']='wechat-multivariate/1'
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
