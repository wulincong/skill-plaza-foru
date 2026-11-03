"""Readable ECharts SVG views for verified multi-variable report specifications."""
import json
import math

KINDS={'city_combo','requirements_flow','paired_share','bubble_matrix','track_treemap',
       'quantile_interval','specialization_dot','skill_network','entry_scatter'}


def height(cfg):
    kind=cfg['kind']
    if kind=='city_combo':return 850
    if kind in ('requirements_flow','skill_network'):return 850
    if kind=='track_treemap':return 1100
    if kind=='entry_scatter':return 1000
    if kind=='bubble_matrix':return max(680,94*len(cfg.get('rows',[]))+240)
    if kind in ('paired_share','quantile_interval','specialization_dot'):return max(420,100*len(cfg.get('data',[]))+170)
    return 850


def chart_js(cfg,el,theme):
    kind=cfg['kind'];data=cfg.get('data',[])
    primary,accent,text,sub=[theme[key] for key in ['primary','accent','text','sub']]
    colors=theme['chart_palette']
    axis={'axisLine':{'show':False},'axisTick':{'show':False},'axisLabel':{'fontSize':25,'lineHeight':32,'color':text,'interval':0}}
    opt={'animation':False,'tooltip':{'show':False},'textStyle':{'fontSize':26,'color':text}}
    scripts=[]
    if kind=='city_combo':
        labels=[row[0] for row in data]
        opt.update(grid=[{'left':75,'right':35,'top':80,'height':280},{'left':75,'right':35,'top':470,'height':210}],
            xAxis=[dict(axis,type='category',data=labels,gridIndex=0,axisLabel={'show':False}),dict(axis,type='category',data=labels,gridIndex=1)],
            yAxis=[dict(axis,type='value',name='薪酬中位数（K/月）',gridIndex=0,nameLocation='middle',nameGap=55,nameTextStyle={'fontSize':23},splitLine={'lineStyle':{'color':'#E5E7EB'}}),
                   dict(axis,type='value',name='本科要求比例（%）',gridIndex=1,min=0,max=100,nameLocation='middle',nameGap=55,nameTextStyle={'fontSize':23},splitLine={'lineStyle':{'color':'#E5E7EB'}})],
            series=[{'type':'bar','xAxisIndex':0,'yAxisIndex':0,'barMaxWidth':52,'data':[row[3] for row in data],
                     'itemStyle':{'color':primary,'borderRadius':[7,7,0,0]},'label':{'show':True,'position':'top','fontSize':23,'lineHeight':28,'color':text}},
                    {'type':'scatter','xAxisIndex':1,'yAxisIndex':1,'symbolSize':23,'data':[[i,row[4]] for i,row in enumerate(data)],
                     'itemStyle':{'color':accent},'label':{'show':True,'position':'top','fontSize':24,'color':text}}])
        scripts += ["opt.series[0].label.formatter=p=>R[p.dataIndex][3]+' K\\nn='+R[p.dataIndex][1].toLocaleString();",
                    "opt.series[1].label.formatter=p=>R[p.dataIndex][4]+'%';"]
    elif kind=='requirements_flow':
        nodes=[]
        for row in cfg['nodes']:
            education=row['name'].startswith('学历｜')
            nodes.append(dict(row,itemStyle={'color':primary if education else accent},label={'position':'left' if education else 'right'}))
        opt.update(series=[{'type':'sankey','left':190,'right':200,'top':20,'bottom':25,'nodeWidth':18,'nodeGap':38,
            'layoutIterations':0,'nodeAlign':'justify','draggable':False,'data':nodes,'links':cfg['links'],
            'lineStyle':{'color':'source','opacity':.26,'curveness':.5},'label':{'fontSize':25,'color':text,'lineHeight':32}}])
        scripts += ["opt.series[0].label.formatter=p=>{let n=p.name.split('｜').slice(1).join('｜');if(n.startsWith('未知枚举'))n='未知枚举';return wrapChartLabel(n,170,25);};"]
    elif kind=='paired_share':
        maximum=max([value for row in data for value in row[1:3]] or [1])
        opt.update(grid={'left':210,'right':65,'top':95,'bottom':70},
            legend={'top':0,'textStyle':{'fontSize':24,'color':text}},
            xAxis=dict(axis,type='value',min=0,max=min(100,math.ceil(maximum/10)*10+10),axisLabel={'fontSize':24,'formatter':'{value}%'}),
            yAxis=dict(axis,type='category',inverse=True,data=[row[0] for row in data]),
            series=[{'type':'scatter','name':cfg['groups'][j]+'（n='+format(cfg['denominators'][j],',')+'）',
                     'data':[[row[j+1],i] for i,row in enumerate(data)],'symbol':'circle' if j==0 else 'diamond','symbolSize':21,
                     'itemStyle':{'color':primary if j==0 else accent},'label':{'show':True,'fontSize':22,'position':'top' if j==0 else 'bottom','color':text}}
                     for j in range(2)])
        scripts += ["opt.series.forEach(s=>s.label.formatter=p=>p.data[0]+'%');"]
    elif kind=='bubble_matrix':
        cells=cfg['cells'];max_count=max([row[2] for row in cells] or [1])
        opt.update(grid={'left':205,'right':30,'top':25,'bottom':190},
            xAxis=dict(axis,type='category',data=cfg['cols'],splitArea={'show':True,'areaStyle':{'color':['#FFFFFF','#F3F6FA']}}),
            yAxis=dict(axis,type='category',inverse=True,data=cfg['rows'],splitArea={'show':True,'areaStyle':{'color':['#FFFFFF','#F3F6FA']}}),
            visualMap={'type':'continuous','dimension':3,'min':0,'max':cfg['colorMax'],'orient':'horizontal','left':'center','bottom':0,
                       'itemWidth':24,'itemHeight':230,'text':[str(cfg['colorMax'])+cfg['colorUnit'],'0'],'textStyle':{'fontSize':23},
                       'inRange':{'color':theme['heat']}},
            series=[{'type':'scatter','data':[[col,row,count,color] for row,col,count,color in cells],
                     'label':{'show':True,'fontSize':21,'color':text,'textBorderColor':'#FFFFFF','textBorderWidth':3}}])
        scripts += [f"opt.series[0].symbolSize=v=>v[2]>0?12+44*Math.sqrt(v[2]/{max_count}):0;",
                    f"opt.series[0].label.formatter=p=>p.data[2]>={max_count*.07}&&p.data[2]>0?p.data[2].toLocaleString():'';",
                    "opt.xAxis.axisLabel.formatter=v=>wrapChartLabel(v,(document.getElementById("+json.dumps(el)+").clientWidth-235)/opt.xAxis.data.length-6,24);"]
    elif kind=='track_treemap':
        maximum=max([row['median'] for row in data if row['median'] is not None] or [1])
        def color(row):
            if row['median'] is None or row['key']=='__other__':return '#D1D5DB'
            t=row['median']/maximum;a=(219,234,254);b=(30,58,138)
            return '#'+''.join(format(round(x+(y-x)*t),'02x') for x,y in zip(a,b))
        numbers='①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬'
        nodes=[dict(row,itemStyle={'color':color(row)},label={'show':row['value']>=sum(d['value'] for d in data)*.015,'formatter':numbers[i]}) for i,row in enumerate(data)]
        opt.update(series=[{'type':'treemap','left':10,'right':10,'top':15,'bottom':350,'data':nodes,'roam':False,'nodeClick':False,
            'breadcrumb':{'show':False},'visibleMin':0,'label':{'fontSize':26,'color':'#FFFFFF','lineHeight':34,'textBorderColor':'#263248','textBorderWidth':2},
            'itemStyle':{'borderColor':'#FFFFFF','borderWidth':4,'gapWidth':4}}],
            graphic=[{'type':'text','left':15 if i%2==0 else 405,'bottom':285-(i//2)*58,
                'style':{'text':numbers[i]+' '+row['name']+'\n'+format(row['value'],',')+' 条 · 中位数 '+(str(row['median'])+'K' if row['median'] is not None else '未提供'),
                         'fontSize':22,'lineHeight':28,'fill':text}} for i,row in enumerate(data)]+
                [{'type':'text','left':15,'bottom':5,'style':{'text':'面积：岗位数；色深：薪酬中位数；灰色：未分类/小样本','fontSize':22,'fill':sub}}])
    elif kind=='quantile_interval':
        maximum=max([row[1] for row in data] or [1])
        limit=math.ceil(max([row[4] for row in data] or [1])/5)*5+5
        opt.update(grid={'left':220,'right':85,'top':30,'bottom':70},
            xAxis=dict(axis,type='value',min=0,max=limit,name='K/月',nameTextStyle={'fontSize':24},splitLine={'lineStyle':{'color':'#E5E7EB'}}),
            yAxis=dict(axis,type='category',inverse=True,data=[row[0] for row in data]),
            series=[{'type':'custom','silent':True,'encode':{'x':[1,2],'y':0},'data':[[i,row[2],row[4],row[3],row[1]] for i,row in enumerate(data)]},
                    {'type':'scatter','data':[[row[3],i,row[1]] for i,row in enumerate(data)],'itemStyle':{'color':accent},
                     'label':{'show':True,'position':'top','fontSize':24,'color':text}}])
        scripts += ["opt.series[0].renderItem=(params,api)=>{const y=api.value(0),a=api.coord([api.value(1),y]),b=api.coord([api.value(2),y]);return {type:'group',children:[{type:'line',shape:{x1:a[0],y1:a[1],x2:b[0],y2:b[1]},style:{stroke:"+json.dumps(primary)+",lineWidth:7}},{type:'line',shape:{x1:a[0],y1:a[1]-10,x2:a[0],y2:a[1]+10},style:{stroke:"+json.dumps(primary)+",lineWidth:3}},{type:'line',shape:{x1:b[0],y1:b[1]-10,x2:b[0],y2:b[1]+10},style:{stroke:"+json.dumps(primary)+",lineWidth:3}}]};};",
                    f"opt.series[1].symbolSize=v=>Math.max(8,42*Math.sqrt(v[2]/{maximum}));",
                    "opt.series[1].label.formatter=p=>p.data[0]+' K';",
                    "opt.yAxis.axisLabel.formatter=v=>wrapChartLabel(v,195,25)+'\\nn='+R.find(r=>r[0]===v)[1].toLocaleString();"]
    elif kind=='specialization_dot':
        maximum=max([row[2] for row in data] or [1])
        opt.update(grid={'left':290,'right':100,'top':30,'bottom':70},
            xAxis=dict(axis,type='value',min=0,name='LQ',nameTextStyle={'fontSize':24},splitLine={'lineStyle':{'color':'#E5E7EB'}}),
            yAxis=dict(axis,type='category',inverse=True,data=[row[0] for row in data]),
            series=[{'type':'scatter','data':[[row[1],i,row[2],row[3]] for i,row in enumerate(data)],'itemStyle':{'color':primary},
                     'label':{'show':True,'position':'right','fontSize':24,'lineHeight':32,'color':text},
                     'markLine':{'silent':True,'symbol':'none','label':{'show':False},'lineStyle':{'color':accent,'type':'dashed'},'data':[{'xAxis':1}]}}])
        scripts += [f"opt.series[0].symbolSize=v=>17+31*Math.sqrt(v[2]/{maximum});",
                    "opt.series[0].label.formatter=p=>p.data[0].toFixed(2)+'\\nn='+p.data[2].toLocaleString();"]
    elif kind=='skill_network':
        groups={0:[],1:[]}
        for row in cfg['nodes']:groups[row['group']].append(row)
        nodes=[];maximum=max([row['value'] for row in cfg['nodes']] or [1])
        for group,rows in groups.items():
            for i,row in enumerate(rows):
                nodes.append({'name':row['name'],'display':row['label'],'value':row['value'],'x':group,'y':i/(len(rows)-1) if len(rows)>1 else .5,
                    'symbolSize':18+34*math.sqrt(row['value']/maximum),'itemStyle':{'color':primary if group==0 else accent},
                    'label':{'position':'left' if group==0 else 'right'}})
        max_link=max([row['value'] for row in cfg['links']] or [1])
        links=[dict(row,lineStyle={'width':1+8*math.sqrt(row['value']/max_link),'color':'#94A3B8','opacity':.38}) for row in cfg['links']]
        opt.update(series=[{'type':'graph','layout':'none','left':205,'right':195,'top':60,'bottom':95,'data':nodes,'links':links,
            'roam':False,'lineStyle':{'curveness':.12},'label':{'show':True,'fontSize':25,'lineHeight':32,'color':text}}])
        scripts += ["opt.series[0].label.formatter=p=>wrapChartLabel(p.data.display,165,25)+'\\n'+p.value.toLocaleString();"]
    elif kind=='entry_scatter':
        maximum=max([row[3] for row in data] or [1]);numbers='①②③④⑤⑥⑦⑧'
        labeled=set(range(min(3,len(data))))
        if data:labeled.add(max(range(len(data)),key=lambda i:data[i][1]))
        opt.update(grid={'left':85,'right':65,'top':60,'bottom':400},
            xAxis=dict(axis,type='value',name='入门池薪酬中位数（K/月）',nameLocation='middle',nameGap=50,nameTextStyle={'fontSize':24},splitLine={'lineStyle':{'color':'#E5E7EB'}}),
            yAxis=dict(axis,type='value',min=0,max=100,name='方向内入门池份额（%）',nameLocation='middle',nameGap=55,nameTextStyle={'fontSize':24},splitLine={'lineStyle':{'color':'#E5E7EB'}}),
            graphic=[{'type':'text','left':20 if i%2==0 else 400,'bottom':235-(i//2)*64,
                      'style':{'text':numbers[i]+' '+row[0]+'\n'+str(row[1])+'K · '+str(row[2])+'% · n='+format(row[3],','),
                               'fontSize':22,'lineHeight':28,'fill':colors[i%len(colors)]}} for i,row in enumerate(data)],
            series=[{'type':'scatter','data':[{'name':row[0],'value':[row[1],row[2],row[3],row[4],row[5]],
                     'symbolSize':22+52*math.sqrt(row[3]/maximum),'itemStyle':{'color':colors[i%len(colors)],'opacity':.82},
                     'label':{'show':i in labeled,'formatter':numbers[i]}} for i,row in enumerate(data)],
                     'label':{'show':True,'position':'right','fontSize':23,'color':text,
                              'textBorderColor':'#FFFFFF','textBorderWidth':3},
                     'labelLine':{'show':True,'lineStyle':{'color':sub}},'labelLayout':{'moveOverlap':'shiftY'}}])
    else:raise ValueError('未知多维图表类型：'+kind)
    for axes in [opt.get('yAxis')]:
        for item in axes if isinstance(axes,list) else [axes] if axes else []:
            if item.get('type')=='category':
                item['axisLabel']=dict(item.get('axisLabel',{}),width=260 if kind=='specialization_dot' else 195,overflow='break',lineHeight=32)
    encoded=json.dumps(opt,ensure_ascii=False).replace('</','<\\/')
    return '(()=>{const R='+json.dumps(data,ensure_ascii=False).replace('</','<\\/')+';const opt='+encoded+';'+''.join(scripts)+'chart('+json.dumps(el)+',opt);})();\n'
