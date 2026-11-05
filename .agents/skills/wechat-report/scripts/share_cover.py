"""A landscape cover for WeChat cards; report pages remain unchanged."""
from pathlib import Path
from PIL import Image,ImageDraw
from publish_draft import _font

def make_cover(report,out):
    image=Image.new('RGB',(900,500),'#122a53');draw=ImageDraw.Draw(image)
    for y in range(500):
        mix=y/500
        draw.line((0,y,900,y),fill=(int(17+mix*10),int(41+mix*18),int(82+mix*24)))
    draw.rectangle((46,45,53,80),fill='#edac55')
    draw.text((70,42),'产业观察  /  人才需求',font=_font(24),fill='#f5c785')
    region=report.get('region') or report.get('meta',{}).get('region','')
    industry=report.get('industry') or report.get('meta',{}).get('industry','')
    draw.text((48,112),region,font=_font(31),fill='#cfdaed')
    font=_font(53)
    while draw.textlength(industry+'产业人才需求报告',font=font)>800:font=_font(font.size-2)
    draw.text((46,164),industry+'产业人才需求报告',font=font,fill='white')
    draw.text((49,244),'招聘格局 · 岗位门槛 · 薪酬与能力',font=_font(25,False),fill='#bdcce5')
    draw.line((50,307,850,307),fill='#3b5278',width=1)
    values=[(report.get('positions',0),'在招岗位记录'),(report.get('companies',0),'招聘企业'),(report.get('cities',0),'企业关联城市')]
    for index,(value,label) in enumerate(values):
        x=52+index*272
        draw.text((x,333),format(value or 0,','),font=_font(40),fill='#f4b568' if index==0 else 'white')
        draw.text((x,390),label,font=_font(21,False),fill='#b7c8e2')
    draw.text((52,457),'优才知路 · 产业人才数据观察',font=_font(16,False),fill='#a7bad9')
    Path(out).parent.mkdir(parents=True,exist_ok=True)
    image.save(out,'PNG',optimize=True)
