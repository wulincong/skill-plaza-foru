"""Compare the browser's actual ECharts series with the evidence-bound spec.

This catches transpose/order/unit/omitted-series errors that a nonblank SVG or
an image hash alone cannot catch. Pixel and geometry checks remain independent.
"""
import math


def equivalent(actual,expected):
    if isinstance(actual,(int,float)) and isinstance(expected,(int,float)):
        return math.isfinite(actual) and math.isfinite(expected) and math.isclose(actual,expected,rel_tol=1e-8,abs_tol=1e-6)
    if isinstance(actual,list) and isinstance(expected,list):
        return len(actual)==len(expected) and all(equivalent(a,b) for a,b in zip(actual,expected))
    return actual==expected


def errors(cfg,observed):
    kind=cfg['kind'];data=cfg.get('data',[])
    series=observed.get('series',[]);problems=[]
    def check(label,actual,expected):
        if not equivalent(actual,expected):problems.append(label+'与绑定数据不符')
    def values(index):return series[index].get('data') if index<len(series) else None
    def names(index):return series[index].get('names') if index<len(series) else None
    def raw(index):return series[index].get('rawData',[]) if index<len(series) else []
    def axis(key):
        axes=observed.get(key,[])
        return axes[0] if axes else None
    if kind=='city_combo':
        check('城市顺序',axis('xAxis'),[row[0] for row in data])
        check('薪酬中位数',values(0),[row[3] for row in data])
        check('本科要求比例',values(1),[[i,row[4]] for i,row in enumerate(data)])
        rendered=observed.get('texts',[])
        for row in data:
            if 'n='+format(row[1],',') not in rendered:problems.append('岗位规模标签未实际显示')
    elif kind=='requirements_flow':
        check('门槛节点频数',sorted([[row['name'],row['value']] for row in raw(0)]),sorted([[row['name'],row['value']] for row in cfg['nodes']]))
        actual=series[0].get('links',[]) if series else []
        check('学历经验连接频数',sorted([[row['source'],row['target'],row['value']] for row in actual]),sorted([[row['source'],row['target'],row['value']] for row in cfg['links']]))
    elif kind=='paired_share':
        check('经验顺序',axis('yAxis'),[row[0] for row in data])
        for j in range(2):check('学历组内经验份额',values(j),[[row[j+1],i] for i,row in enumerate(data)])
    elif kind=='bubble_matrix':
        check('矩阵行',axis('yAxis'),cfg['rows']);check('矩阵列',axis('xAxis'),cfg['cols'])
        check('矩阵岗位量与条件比例',values(0),[[col,row,count,color] for row,col,count,color in cfg['cells']])
    elif kind=='track_treemap':
        check('方向规模与薪酬定位',[[row['name'],row['value'],row.get('median'),row.get('valid')] for row in raw(0)],
              [[row['name'],row['value'],row.get('median'),row.get('valid')] for row in data])
    elif kind=='quantile_interval':
        check('方向顺序',axis('yAxis'),[row[0] for row in data])
        check('区间端点与样本量',values(0),[[i,row[2],row[4],row[3],row[1]] for i,row in enumerate(data)])
        check('中位点与样本量',values(1),[[row[3],i,row[1]] for i,row in enumerate(data)])
    elif kind=='specialization_dot':
        check('城市与方向顺序',axis('yAxis'),[row[0] for row in data])
        check('LQ与岗位规模',values(0),[[row[1],i,row[2],row[3]] for i,row in enumerate(data)])
    elif kind=='skill_network':
        check('方向与技能节点',sorted([[row['name'],row['value']] for row in raw(0)]),sorted([[row['name'],row['value']] for row in cfg['nodes']]))
        actual=series[0].get('links',[]) if series else []
        check('能力提及连接',sorted([[row['source'],row['target'],row['value']] for row in actual]),sorted([[row['source'],row['target'],row['value']] for row in cfg['links']]))
    elif kind=='entry_scatter':
        check('入门方向多维定位',values(0),[[row[1],row[2],row[3],row[4],row[5]] for row in data])
        check('入门方向名称',names(0),[row[0] for row in data])
    elif kind in ('hbar','vbar'):
        check('分类顺序',axis('yAxis' if kind=='hbar' else 'xAxis'),[row[0] for row in data])
        check('柱图数值/单位',values(0),[row[2] if cfg.get('pct_label') else row[1] for row in data])
    elif kind in ('pie','donut'):
        check('构成数量',values(0),[row[1] for row in data])
        # Legend names include a computed percentage; category prefixes must stay exact.
        check('构成分类',names(0),[row[0]+'  '+str(round(row[1]/sum(d[1] for d in data)*100,1))+'%' for row in data])
    elif kind=='heatmap':
        check('矩阵列',axis('xAxis'),cfg['cols']);check('矩阵行',axis('yAxis'),cfg['rows'])
        check('矩阵坐标和数值',values(0),[[col,row,value] for row,col,value in cfg['cells']])
    elif kind=='range_dot':
        check('方向顺序',axis('yAxis'),[row[0] for row in data])
        check('区间起点',values(0),[row[2] for row in data])
        check('区间跨度',values(1),[row[4]-row[2] for row in data])
        check('中位点',values(2),[[row[3],i] for i,row in enumerate(data)])
    elif kind=='stacked_pct':
        check('组内构成行',axis('yAxis'),cfg['rows'])
        check('组内构成分类',[s.get('name') for s in series],cfg['cols'])
        matrix={(r,c):v for r,c,v in cfg['cells']}
        for col in range(len(cfg['cols'])):
            check('组内构成比例',values(col),[matrix.get((row,col),0) for row in range(len(cfg['rows']))])
    elif kind=='dumbbell_pct':
        check('城市顺序',axis('yAxis'),[row[0] for row in data])
        check('全部岗位份额',values(2),[[row[1],i] for i,row in enumerate(data)])
        check('入门池份额',values(3),[[row[2],i] for i,row in enumerate(data)])
        check('比较连接线',values(1),[abs(row[1]-row[2]) for row in data])
    elif kind=='line':
        check('时间顺序',axis('xAxis'),[row[0] for row in data]);check('折线数值',values(0),[row[1] for row in data])
    elif kind=='scatter':
        check('散点组数量',len(series),len(data))
        for i,row in enumerate(data):check('散点坐标',values(i),[[row[1],row[2]]])
    elif kind=='funnel':
        check('阶段数值',values(0),[row[1] for row in data]);check('阶段顺序',names(0),[row[0] for row in data])
    else:problems.append('未支持的图表语义检查：'+kind)
    return problems
