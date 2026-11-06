"""Compact related questions without discarding analyses or metric bindings."""
import re

POLICY='wechat-readable-layout/1'
PAIRS={
 'education':('experience','学历与经验：门槛怎样组合','门槛观察'),
 'city_tracks':('lq','城市与赛道：规模之外看专长','区域比较'),
 'skills':('track_skills','能力画像：共同基础与方向差别','能力结构'),
}

def compact(outline,data,binding):
    original=outline['screens'];by_key={s.get('analysis_key'):i for i,s in enumerate(original)}
    removed=set();moves={};old_refs=outline['bindings'];new=[]
    for old,screen in enumerate(original):
        if old in removed:continue
        key=screen.get('analysis_key');target=len(new);moves[old]=(target,{})
        if key in PAIRS and PAIRS[key][0] in by_key:
            other,title,kicker=PAIRS[key];second_index=by_key[other]
            second=original[second_index]
            # Retain two complete paragraphs and both chapters' source-bound charts.
            charts=[]
            for source in (screen,second):
                slots=[name for name in ('chart','chart2','chartA','chartB') if source.get(name)]
                if len(slots)!=1:break
                charts.append(slots[0])
            if len(charts)!=2:
                new.append(screen)
                continue
            first=dict(screen);first['analysis_keys']=[key,other]
            first['title']=title;first['section']=kicker;first.pop('no',None)
            from editorial_prose import section,spec as editorial_spec,compact_fact
            from report_analysis import derive_findings
            items={r['key']:r for r in outline['analysis']['sections']};facts={r['id']:r for r in derive_findings(data)}
            first['paragraphs']=screen['paragraphs']+[section(data,items[other],facts,[compact_fact(facts[fid]['text']) for fid in items[key]['findingIds']])]
            old_refs[f'/screens/{second_index}/paragraphs/0']=editorial_spec(data,items[other],'section-distinct',binding,items[key])
            for slot in ('chart','chart2','chartA','chartB'):first.pop(slot,None)
            first['type']='chart';first['chart']=screen[charts[0]];first['chart2']=second[charts[1]]
            first['summary']={'title':kicker,'text':screen['summary']['text']+' '+second['summary']['text']}
            first['compact_pair']=True
            moves[old]=(target,{charts[0]:'chart'})
            moves[second_index]=(target,{charts[1]:'chart2','paragraphs/0':'paragraphs/1'})
            removed.add(second_index);screen=first
        new.append(screen)
    refs={}
    for path,spec in old_refs.items():
        match=re.match(r'^/screens/(\d+)/(.*)$',path)
        if not match:refs[path]=spec;continue
        index,suffix=int(match[1]),match[2]
        target,slots=moves[index]
        for old_slot,new_slot in sorted(slots.items(),key=lambda item:-len(item[0])):
            if suffix==old_slot or suffix.startswith(old_slot+'/'):
                suffix=new_slot+suffix[len(old_slot):];break
        path=f'/screens/{target}/{suffix}'
        if path in refs:raise ValueError('合并章节出现重复数据绑定：'+path)
        refs[path]=spec
    chapter=0
    for screen in new:
        if screen.get('analysis_key'):
            chapter+=1;screen['no']=f'{chapter:02}'
            if screen.get('section'):screen['section']=f'{chapter:02} / '+screen['section']
    outline.update(screens=new,bindings=refs,readableLayout=POLICY)
    return outline

def merged_expected(screen,items,facts,data):
    from editorial_prose import paragraphs
    keys=screen.get('analysis_keys',[])
    if len(keys)!=2 or keys[0] not in PAIRS or PAIRS[keys[0]][0]!=keys[1]:raise ValueError('未知的合并章节')
    a,sa=paragraphs(data,items[keys[0]],facts)
    b,sb=paragraphs(data,items[keys[1]],facts)
    from editorial_prose import section,compact_fact
    b=[section(data,items[keys[1]],facts,[compact_fact(facts[fid]['text']) for fid in items[keys[0]]['findingIds']])]
    return a+b,{'title':PAIRS[keys[0]][2],'text':sa['text']+' '+sb['text']}
