/* Local, dependency-free adaptation of the FORU skill's starter. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const icon = name => `<svg viewBox="0 0 56 56" aria-hidden="true"><use href="#foru-${name}"/></svg>`;
  const iconNames = {industry:'building',teaching:'learning',interview:'jobs',data:'assessment'};
  const features = [
    {id:'industry',title:'规划产业与专业',description:'让产业、岗位和专业建议回到证据与口径。',tags:['产业分析','专业建设','证据报告'],slug:'industry-education-report',icon:'building'},
    {id:'teaching',title:'开发课程与教学',description:'在授权课程资料内生成答疑、要点和练习。',tags:['授权资料','定位引用','课堂练习'],slug:'classroom-assistant',icon:'learning'},
    {id:'interview',title:'组织实训与就业',description:'围绕目标岗位和简历完成面试练习闭环。',tags:['能力地图','逐题追问','回答复盘'],slug:'ai-interview',icon:'jobs'},
    {id:'data',title:'治理训练数据',description:'把样本构造、机器质检和专家抽检连成流程。',tags:['数据集划分','泄漏检查','专家抽检'],slug:'training-data-qa',icon:'assessment'}
  ];
  const usePageConfigs = {
    'industry-education-report': {
      eyebrow:'产业研究工作台', lead:'填写报告对象与研究边界，组合所需专题，再从右侧选择可参考的知识库。', output:'产业与专业建设决策报告',
      sections:[
        {number:'01',title:'确定报告边界',description:'先明确服务对象、研究地区与时间口径。',fields:[
          {id:'audience',label:'服务对象',type:'choice',required:true,options:['院校管理者','政府部门','产业园区']},
          {id:'region',label:'目标地区',type:'text',required:true,placeholder:'例如：广东省佛山市'},
          {id:'baseline',label:'报告基期',type:'select',required:true,options:['2026 年','2025 年','2024 年','2023 年']},
          {id:'purpose',label:'报告用途',type:'select',required:true,options:['专业建设与调整','区域产教融合规划','产业招商与人才研判','项目申报与评审']}
        ]},
        {number:'02',title:'选择研究专题',description:'可多选；SKILL 会按选择组织报告章节与证据清单。',fields:[
          {id:'topics',label:'重点专题',type:'multi',required:true,span:'full',options:['区域产业链','岗位人才需求','重点企业','专业与课程','就业去向','招商建议']},
          {id:'context',label:'已有材料或特别要求',type:'textarea',span:'full',placeholder:'例如：已有学校专业目录，希望重点比较新能源汽车与智能网联方向……',help:'可以先写资料名称，后续再补充附件。'}
        ]}
      ],
      example:{audience:'院校管理者',region:'广东省佛山市',baseline:'2024 年',purpose:'专业建设与调整',topics:['区域产业链','岗位人才需求','专业与课程','就业去向'],context:'为某高职院校论证新能源汽车专业建设方向，结论需要区分事实、推断和建议。'},
      knowledge:[
        {id:'industry-policy',title:'区域产业政策资料库',meta:'政策与规划 · 38 份',tag:'政策',default:true},
        {id:'job-market',title:'重点产业岗位需求库',meta:'招聘与岗位画像 · 12,680 条',tag:'岗位',default:true},
        {id:'major-course',title:'院校专业与课程库',meta:'专业目录与课程样本 · 216 份',tag:'院校'},
        {id:'employment-flow',title:'毕业生就业去向库',meta:'匿名统计样例 · 8 个数据集',tag:'就业'}
      ]
    },
    'classroom-assistant': {
      eyebrow:'课程教学工作台', lead:'用结构化选项说明课程、对象和教学任务，再限定本次允许引用的知识范围。', output:'课堂材料与带引用教学内容',
      sections:[
        {number:'01',title:'设置教学任务',description:'选择课程场景与本次希望完成的工作。',fields:[
          {id:'course',label:'课程名称',type:'text',required:true,placeholder:'例如：人工智能导论'},
          {id:'learners',label:'授课对象',type:'select',required:true,options:['高职一年级','高职二年级','本科低年级','本科高年级','职业培训学员']},
          {id:'task',label:'任务类型',type:'choice',required:true,span:'full',options:['课程答疑','要点总结','生成练习','整理答疑记录']}
        ]},
        {number:'02',title:'定义输出要求',description:'设置内容规模与教学侧重点。',fields:[
          {id:'amount',label:'内容数量',type:'select',required:true,options:['3 项','5 项','8 项','10 项']},
          {id:'difficulty',label:'难度',type:'choice',required:true,options:['基础','进阶','综合']},
          {id:'focus',label:'教学侧重点',type:'multi',span:'full',options:['概念理解','案例分析','操作实践','课堂互动','考核复习']},
          {id:'context',label:'补充说明',type:'textarea',span:'full',placeholder:'例如：需要附参考答案，并标出引用所在章节……'}
        ]}
      ],
      example:{course:'人工智能导论',learners:'高职一年级',task:'生成练习',amount:'3 项',difficulty:'基础',focus:['概念理解','案例分析'],context:'基于第 1 章生成课堂练习，附参考答案和资料定位引用。'},
      knowledge:[
        {id:'course-textbook',title:'《人工智能导论》课程资料',meta:'讲义、课件与章节索引 · 24 份',tag:'课程',default:true},
        {id:'teaching-plan',title:'课程标准与授课计划',meta:'教学目标与周次安排 · 6 份',tag:'标准',default:true},
        {id:'exercise-bank',title:'课堂练习样例库',meta:'已审核练习 · 186 题',tag:'题库'},
        {id:'faq-records',title:'历史课堂答疑记录',meta:'匿名问答 · 92 条',tag:'答疑'}
      ]
    },
    'ai-interview': {
      eyebrow:'模拟面试工作台', lead:'补充目标岗位与练习方式，让每轮提问都围绕岗位要求和真实经历展开。', output:'交互式模拟面试与证据化复盘',
      sections:[
        {number:'01',title:'设置目标岗位',description:'岗位信息越具体，问题和追问越贴近真实场景。',fields:[
          {id:'role',label:'目标岗位',type:'text',required:true,placeholder:'例如：Java 后端实习生'},
          {id:'stage',label:'求职阶段',type:'select',required:true,options:['实习','校招','社招转岗','升职竞聘']},
          {id:'mode',label:'练习模式',type:'choice',required:true,span:'full',options:['完整模拟','专项突破','压力追问']}
        ]},
        {number:'02',title:'配置面试节奏',description:'选择题量和希望重点观察的能力。',fields:[
          {id:'questions',label:'基础题量',type:'choice',required:true,options:['3 题','5 题','8 题']},
          {id:'language',label:'面试语言',type:'select',required:true,options:['中文','中英混合','英文']},
          {id:'focus',label:'重点能力',type:'multi',span:'full',options:['专业基础','项目经历','问题解决','沟通表达','职业动机','压力应对']},
          {id:'resume',label:'匿名经历摘要',type:'textarea',required:true,span:'full',placeholder:'简述教育背景、项目和实习经历；请删除姓名、电话等敏感信息。'}
        ]}
      ],
      example:{role:'Java 后端实习生',stage:'实习',mode:'完整模拟',questions:'3 题',language:'中文',focus:['专业基础','项目经历','问题解决'],resume:'计算机相关专业，完成过 Spring Boot 校园二手交易平台项目，负责接口设计与 MySQL 数据建模。'},
      knowledge:[
        {id:'role-competency',title:'数字技术岗位能力库',meta:'岗位能力模型 · 42 类',tag:'岗位',default:true},
        {id:'interview-rubric',title:'结构化面试评价标准',meta:'评分维度与行为锚点 · 18 份',tag:'评价',default:true},
        {id:'question-bank',title:'企业面试题样例库',meta:'匿名真题与追问 · 326 题',tag:'题库'},
        {id:'resume-evidence',title:'简历证据识别规则',meta:'项目与经历核验规则 · 12 份',tag:'规则'}
      ]
    },
    'training-data-qa': {
      eyebrow:'数据治理工作台', lead:'描述数据任务、规模与验收重点，再选择标注规范和业务规则知识库。', output:'训练样本、质检报告与抽检任务',
      sections:[
        {number:'01',title:'定义数据任务',description:'说明数据用途和预期处理规模。',fields:[
          {id:'task',label:'任务类型',type:'select',required:true,options:['文本分类','信息抽取','问答生成','对话指令','多轮对话']},
          {id:'amount',label:'目标样本量',type:'text',required:true,placeholder:'例如：200 条'},
          {id:'stage',label:'当前阶段',type:'choice',required:true,span:'full',options:['黄金种子','批量扩增','标注验收','版本封存']}
        ]},
        {number:'02',title:'配置质量检查',description:'选择数据划分和本轮必须通过的质量门禁。',fields:[
          {id:'split',label:'数据集划分',type:'select',required:true,options:['80 / 10 / 10','70 / 15 / 15','自定义划分','仅独立评测集']},
          {id:'format',label:'交付格式',type:'choice',required:true,options:['JSONL','JSON','CSV']},
          {id:'checks',label:'质检项目',type:'multi',required:true,span:'full',options:['Schema','事实证据','业务规则','重复样本','数据泄漏','分布偏差']},
          {id:'schema',label:'字段与标注说明',type:'textarea',required:true,span:'full',placeholder:'例如：input 为用户问题，output 为标准答复，category 为一级意图标签……'}
        ]}
      ],
      example:{task:'问答生成',amount:'200 条',stage:'黄金种子',split:'80 / 10 / 10',format:'JSONL',checks:['Schema','事实证据','重复样本','数据泄漏','分布偏差'],schema:'基于客服问答数据构造候选黄金种子；input 为问题，output 为答复，category 为业务意图。'},
      knowledge:[
        {id:'annotation-schema',title:'标注 Schema 与字段字典',meta:'字段定义与示例 · 16 份',tag:'Schema',default:true},
        {id:'business-rules',title:'业务规则与禁答边界',meta:'规则条目 · 286 条',tag:'规则',default:true},
        {id:'golden-examples',title:'已验收黄金样本库',meta:'专家确认样本 · 1,240 条',tag:'样本'},
        {id:'qa-rubric',title:'数据质检验收标准',meta:'门禁与抽检规范 · 9 份',tag:'质检'}
      ]
    }
  };
  const state = {q:'',category:'全部',sort:'featured',page:'home'};
  const categories = ['全部','产业与专业建设','课程与教学开发','实训与就业','数据治理与模型底座'];
  const featureTabs = $('#feature-tabs');
  const nav = $('#foru-nav');
  const navToggle = $('#nav-toggle');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const narrow = matchMedia('(max-width: 767px)');
  let activeFeature=0, elapsed=0, previous=0, frame=0, visible=false, paused=false, hover=false, focused=false, toastTimer;
  let activeUseSkill=skills[0], useBusy=false, useApiReady=false, healthRequest=0;
  const useSessions=new Map();

  function catalogHash() {
    const p = new URLSearchParams();
    if(state.q)p.set('q',state.q);
    if(state.category!=='全部')p.set('category',state.category);
    if(state.sort!=='featured')p.set('sort',state.sort);
    return '#/catalog'+(p.size?'?'+p:'');
  }
  const detailHash = (slug,returnTo=catalogHash()) => `#/skill/${encodeURIComponent(slug)}?return=${encodeURIComponent(returnTo)}`;
  const useHash = slug => `#/use${slug?'/'+encodeURIComponent(slug):''}`;
  $('.foru-skip').addEventListener('click',event=>{event.preventDefault();$('#main').focus();$('#main').scrollIntoView();});
  function keyboardTabs(list, select, vertical=false) {
    list.forEach((button,i) => button.addEventListener('keydown', event => {
      let index;
      if(event.key===(vertical?'ArrowUp':'ArrowLeft'))index=(i-1+list.length)%list.length;
      if(event.key===(vertical?'ArrowDown':'ArrowRight'))index=(i+1)%list.length;
      if(event.key==='Home')index=0;
      if(event.key==='End')index=list.length-1;
      if(index!==undefined){event.preventDefault();select(index);list[index].focus();}
    }));
  }
  function closeNav(restore=false) {
    const wasOpen=nav.classList.contains('open');
    nav.classList.remove('open');navToggle.setAttribute('aria-expanded','false');navToggle.textContent='菜单';
    document.body.style.overflow='';$('#main').inert=false;$('#footer').inert=false;
    if(wasOpen&&restore)navToggle.focus();
  }
  navToggle.addEventListener('click',()=>{
    if(nav.classList.contains('open')){closeNav(true);return;}
    nav.classList.add('open');navToggle.setAttribute('aria-expanded','true');navToggle.textContent='关闭';
    document.body.style.overflow='hidden';$('#main').inert=true;$('#footer').inert=true;nav.querySelector('a').focus();
  });
  nav.addEventListener('click',event=>{if(event.target.closest('a'))closeNav();});
  document.addEventListener('click',event=>{if(!event.target.closest('.foru-header'))closeNav();});
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'){
      if(nav.classList.contains('open'))closeNav(true);
    }
    if(event.key==='Tab'&&nav.classList.contains('open')){
      const nodes=[navToggle,...nav.querySelectorAll('a,summary')].filter(node=>node.getClientRects().length);
      const first=nodes[0],last=nodes.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    }
  });
  narrow.addEventListener('change',()=>closeNav());

  function artwork(id) {
    if(id==='industry')return `<div class="report-preview"><aside class="report-sidebar"><span>产业链</span><span>岗位人才</span><span>专业课程</span><span>就业反馈</span></aside><div class="report-page"><h3>新能源汽车专业建设报告</h3><p>分别标注事实、推断、建议和缺数，让每项关键结论都能回到来源。</p><table class="report-table"><thead><tr><th>决策主题</th><th>证据状态</th></tr></thead><tbody><tr><td>产业与岗位</td><td>来源与口径已登记</td></tr><tr><td>专业与课程</td><td>待补院校微观数据</td></tr><tr><td>建设建议</td><td>关联证据与限制</td></tr></tbody></table><span class="citation-chip">结构校验 + 语义审核</span></div></div>`;
    if(id==='teaching')return `<div class="mini-website"><div><h3>课程资料<br>变成可学内容</h3><p>答疑 · 要点 · 练习</p><span class="mini-pill">每条结论附定位引用</span></div><svg viewBox="0 0 360 310" aria-hidden="true"><use href="#foru-scene-ai"/></svg></div><div class="mini-entry-row"><span>授权资料</span><span>课堂练习</span><span>待教师清单</span></div>`;
    if(id==='interview')return `<div class="video-stage"><div><span>岗位与简历分析</span><br><strong>一次一题<br>根据回答追问</strong></div><svg viewBox="0 0 100 95" aria-hidden="true"><g fill="#76c6ff"><rect x="8" y="50" width="8" height="12" rx="4"/><rect x="23" y="38" width="8" height="24" rx="4"/><rect x="38" y="20" width="8" height="42" rx="4"/><rect x="53" y="30" width="8" height="32" rx="4"/><rect x="68" y="12" width="8" height="50" rx="4"/><rect x="83" y="25" width="8" height="37" rx="4"/></g></svg></div><div class="timeline"><div class="time-ruler"><span>开始练习</span><span>形成报告</span></div><div class="time-track"><span>能力地图</span><span>逐题问答</span><span>重答</span></div><div class="time-track audio"><span>Q1 → A1 → Q1-F1 → A1-F1</span></div><div class="time-track"><span>原话引用</span><span>待验证项</span><span>改进建议</span></div></div>`;
    return `<svg class="diagram-preview" role="img" aria-label="训练数据治理流程示例：治理数据依次经过样本构造、机器质检和专家抽检，再形成可追溯版本" viewBox="0 0 500 245"><rect x="12" y="28" width="476" height="188" rx="12" fill="#162544" stroke="#5f9eff" stroke-dasharray="5 5"/><g fill="#cde1ff" font-family="sans-serif" font-size="13"><text x="29" y="52">数据治理与验收边界</text></g><g fill="none" stroke="#69afff" stroke-width="2"><path d="M122 124h30m102 0h30m102 0h22"/></g><g fill="#223b66" stroke="#628fcc"><rect x="28" y="92" width="94" height="64" rx="8"/><rect x="152" y="92" width="102" height="64" rx="8"/><rect x="284" y="92" width="102" height="64" rx="8"/><rect x="408" y="92" width="64" height="64" rx="8"/></g><g fill="#fff" text-anchor="middle" font-size="13" font-family="sans-serif"><text x="75" y="120">治理数据</text><text x="75" y="139">与规则</text><text x="203" y="120">样本构造</text><text x="203" y="139">四类划分</text><text x="335" y="120">机器质检</text><text x="335" y="139">专家抽检</text><text x="440" y="120">封存</text><text x="440" y="139">版本</text></g><g fill="#a8c3e8" font-size="12" font-family="sans-serif"><text x="29" y="188">候选结果 ≠ 专家确认 · 全程保留来源与谱系</text></g></svg>`;
  }
  function previewMarkup(feature, detail=false) {
    return `<div class="foru-window"><span>● ● ●</span><span>产物示意 · 非真实运行结果</span></div><div class="preview-frame"><div class="preview-topline"><strong>${esc(feature.title)}</strong><span>SKILL</span></div><div class="preview-inner">${artwork(feature.id)}</div></div><div class="preview-footer"><div class="foru-tags">${feature.tags.slice(0,2).map(tag=>`<span>${esc(tag)}</span>`).join('')}</div>${detail?`<a href="${useHash(feature.slug)}">直接使用 →</a>`:`<span class="preview-links"><a href="${useHash(feature.slug)}">直接使用</a><a href="${detailHash(feature.slug)}">查看详情 →</a></span>`}</div>`;
  }
  featureTabs.innerHTML=features.map((feature,i)=>`<button type="button" id="feature-${feature.id}" role="tab" class="foru-feature${i===0?' active':''}" aria-selected="${i===0}" aria-controls="feature-preview" tabindex="${i===0?0:-1}"><svg class="foru-feature-icon" viewBox="0 0 56 56" aria-hidden="true"><use href="#foru-${feature.icon}"/></svg><strong>${esc(feature.title)}</strong><span>${esc(feature.description)}</span><small>${feature.tags.map(tag=>`<span>${esc(tag)}</span>`).join('')}</small></button>`).join('');
  const featureButtons=[...featureTabs.querySelectorAll('button')];
  function selectFeature(index) {
    activeFeature=index;elapsed=0;
    featureButtons.forEach((button,i)=>{button.classList.toggle('active',i===index);button.setAttribute('aria-selected',String(i===index));button.tabIndex=i===index?0:-1;button.style.setProperty('--progress',0);});
    const panel=$('#feature-preview');panel.setAttribute('aria-labelledby','feature-'+features[index].id);panel.dataset.feature=features[index].id;panel.innerHTML=previewMarkup(features[index]);
  }
  featureButtons.forEach((button,i)=>button.addEventListener('click',()=>selectFeature(i)));
  keyboardTabs(featureButtons,selectFeature,true);
  const area=$('#feature-area');
  const observer=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;},{threshold:.25});observer.observe(area);
  area.addEventListener('pointerenter',event=>{if(event.pointerType==='mouse')hover=true;});area.addEventListener('pointerleave',()=>hover=false);
  area.addEventListener('focusin',()=>focused=true);area.addEventListener('focusout',event=>focused=area.contains(event.relatedTarget));
  $('#feature-pause').addEventListener('click',()=>{paused=!paused;$('#feature-pause').setAttribute('aria-pressed',String(paused));$('#feature-pause').textContent=paused?'继续自动展示':'暂停自动展示';});
  function tick(time) {
    const delta=previous?Math.min(time-previous,100):0;previous=time;
    if(state.page==='home'&&visible&&!document.hidden&&!paused&&!hover&&!focused&&!reduced.matches){elapsed+=delta;if(elapsed>=5000)selectFeature((activeFeature+1)%features.length);featureButtons[activeFeature].style.setProperty('--progress',elapsed/5000);}
    frame=requestAnimationFrame(tick);
  }

  function renderCatalog() {
    const needle=state.q.trim().toLocaleLowerCase();
    const list=skills.filter(skill=>(state.category==='全部'||skill.category===state.category)&&(!needle||[skill.name,skill.identifier,skill.summary,skill.minimalInput,...skill.tags].join(' ').toLocaleLowerCase().includes(needle)));
    list.sort((a,b)=>{
      if(state.sort==='updated'){if(a.updatedAt!==b.updatedAt)return(b.updatedAt||'').localeCompare(a.updatedAt||'');}
      else if(state.sort==='featured'){if(a.featured!==b.featured)return Number(b.featured)-Number(a.featured);}
      return a.name.localeCompare(b.name,'zh-CN');
    });
    $('#result-count').textContent=list.length+' 个 SKILL';
    $('#sort-note').textContent=state.sort==='updated'?'暂无已确认日期，未标日期条目按名称排列':'4 个业务分类 · 在线运行与 API 接入';
    $('#empty-state').hidden=list.length!==0;$('#skill-grid').hidden=list.length===0;
    $('#categories').innerHTML=categories.map(category=>`<button type="button" class="${category===state.category?'active':''}" aria-pressed="${category===state.category}" data-category="${esc(category)}">${esc(category)}</button>`).join('');
    $('#skill-grid').innerHTML=list.map(skill=>`<article class="skill-card"><div class="skill-card-head"><span class="skill-card-icon">${icon(iconNames[skill.kind])}</span><div><h3>${esc(skill.name)}</h3><p>${esc(skill.identifier)}</p></div></div><div class="skill-card-body"><p class="skill-summary">${esc(skill.summary)}</p><div class="foru-tags">${skill.tags.slice(0,3).map(tag=>`<span>${esc(tag)}</span>`).join('')}</div><div class="skill-card-meta">${icon('case')}<span>在线运行 / API</span></div></div><div class="skill-card-foot"><span>${esc(skill.category)}</span><span class="skill-card-actions"><a class="use-link" href="${useHash(skill.slug)}">直接使用</a><a href="${detailHash(skill.slug)}">查看详情 →</a></span></div></article>`).join('');
  }
  function syncCatalog() {history.replaceState(null,'',catalogHash());renderCatalog();setCurrentNav('catalog');}
  $('#search-input').addEventListener('input',event=>{state.q=event.target.value;syncCatalog();});
  $('#sort-select').addEventListener('change',event=>{state.sort=event.target.value;syncCatalog();});
  $('#categories').addEventListener('click',event=>{const button=event.target.closest('[data-category]');if(button){state.category=button.dataset.category;syncCatalog();}});
  $('#clear-filters').addEventListener('click',()=>{state.q='';state.category='全部';state.sort='featured';$('#search-input').value='';$('#sort-select').value='featured';syncCatalog();$('#search-input').focus();});
  function setCurrentNav(name) {nav.querySelectorAll('[data-nav]').forEach(link=>{if(link.dataset.nav===name)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');});}
  function showPage(name) {state.page=name;document.querySelectorAll('.page-view').forEach(view=>view.hidden=view.dataset.page!==name);}
  function useSession(skill) {
    if(!useSessions.has(skill.slug))useSessions.set(skill.slug,[]);
    return useSessions.get(skill.slug);
  }
  function renderUseField(field) {
    const required=field.required?'<em>必填</em>':'';
    const help=field.help?`<small>${esc(field.help)}</small>`:'';
    const span=field.span==='full'?' field-span-full':'';
    if(field.type==='choice'||field.type==='multi'){
      const inputType=field.type==='choice'?'radio':'checkbox';
      return `<fieldset class="task-field task-choice-field${span}"><legend>${esc(field.label)} ${required}</legend><div class="choice-grid">${field.options.map(option=>`<label><input type="${inputType}" name="${esc(field.id)}" value="${esc(option)}" ${field.required&&field.type==='choice'?'required':''}><span>${esc(option)}</span></label>`).join('')}</div>${help}</fieldset>`;
    }
    if(field.type==='select'){
      return `<label class="task-field${span}"><span>${esc(field.label)} ${required}</span><select name="${esc(field.id)}" ${field.required?'required':''}><option value="" disabled selected>请选择</option>${field.options.map(option=>`<option value="${esc(option)}">${esc(option)}</option>`).join('')}</select>${help}</label>`;
    }
    if(field.type==='textarea'){
      return `<label class="task-field${span}"><span>${esc(field.label)} ${required}</span><textarea name="${esc(field.id)}" rows="4" maxlength="8000" placeholder="${esc(field.placeholder||'')}" ${field.required?'required':''}>${''}</textarea>${help}</label>`;
    }
    return `<label class="task-field${span}"><span>${esc(field.label)} ${required}</span><input type="text" name="${esc(field.id)}" maxlength="500" placeholder="${esc(field.placeholder||'')}" ${field.required?'required':''}>${help}</label>`;
  }
  function updateUseProgress() {
    const form=$('#skill-task-form');
    if(!form)return;
    const config=usePageConfigs[activeUseSkill.slug];
    const requiredFields=config.sections.flatMap(section=>section.fields).filter(field=>field.required);
    const completed=requiredFields.filter(field=>{
      const nodes=[...form.querySelectorAll(`[name="${field.id}"]`)];
      return field.type==='choice'||field.type==='multi'?nodes.some(node=>node.checked):Boolean(nodes[0]?.value.trim());
    }).length;
    const percent=Math.round(completed/requiredFields.length*100);
    const progress=$('#task-progress');
    progress?.style.setProperty('--completion',percent+'%');
    if(progress)progress.setAttribute('aria-valuenow',String(percent));
    const completion=$('#task-completion');
    if(completion)completion.textContent=`已完成 ${completed} / ${requiredFields.length} 项必填信息`;
    const kbChecked=[...document.querySelectorAll('[name="knowledge"]:checked')];
    const kbCount=$('#kb-count');
    if(kbCount)kbCount.textContent=`已选 ${kbChecked.length} 个知识库`;
    const summary=$('#task-summary');
    if(summary){
      const formData=new FormData(form);
      const rows=config.sections.flatMap(section=>section.fields).map(field=>({label:field.label,value:formData.getAll(field.id).filter(Boolean).join('、')})).filter(row=>row.value).slice(0,3);
      summary.innerHTML=rows.length?rows.map(row=>`<li><span>${esc(row.label)}</span><strong>${esc(row.value)}</strong></li>`).join(''):'<li class="summary-empty">填写任务信息后，这里会生成执行摘要。</li>';
    }
    const button=$('#use-start');
    if(button)button.disabled=!useApiReady||useBusy;
  }
  function updateUseResult() {
    const result=$('#use-result');
    if(!result)return;
    const session=useSession(activeUseSkill);
    if(!session.length&&!useBusy){result.hidden=true;return;}
    result.hidden=false;
    const recent=session.slice(-2);
    result.innerHTML=`<header><div><span>运行结果</span><h2>${useBusy?'正在调用 SKILL':'本次运行已返回'}</h2></div>${!useBusy?'<button type="button" id="result-clear">清除结果</button>':''}</header><div class="result-body">${recent.map(message=>message.role==='user'?`<details class="submitted-task"><summary>查看本次提交的结构化任务</summary><pre>${esc(message.content)}</pre></details>`:`<article class="result-answer ${message.role==='error'?'error':''}"><span>${message.role==='error'?'!':'AI'}</span><div><strong>${message.role==='error'?'请求未完成':esc(activeUseSkill.name)}</strong><p>${esc(message.content)}</p></div></article>`).join('')}${useBusy?'<div class="result-loading"><i></i><span>正在读取配置与知识库选择，生成结果…</span></div>':''}</div>`;
    $('#result-clear')?.addEventListener('click',()=>{useSessions.set(activeUseSkill.slug,[]);updateUseResult();});
  }
  async function checkUseHealth() {
    const request=++healthRequest;
    const status=$('#api-status'),setup=$('#api-setup');
    try{
      const response=await fetch('/api/health',{cache:'no-store'});
      const data=await response.json();
      if(request!==healthRequest)return;
      if(!response.ok||!data.ok)throw new Error(data.message||'API 未配置');
      useApiReady=true;status.className='api-status ready';status.innerHTML='<i></i>API 已就绪 · '+esc(data.model);setup.hidden=true;updateUseProgress();
    }catch{
      if(request!==healthRequest)return;
      useApiReady=false;status.className='api-status offline';status.innerHTML='<i></i>需要启动本地服务';setup.hidden=false;updateUseProgress();
    }
  }
  function fillUseExample(config) {
    const form=$('#skill-task-form');
    config.sections.flatMap(section=>section.fields).forEach(field=>{
      const value=config.example[field.id];
      const nodes=[...form.querySelectorAll(`[name="${field.id}"]`)];
      if(field.type==='choice')nodes.forEach(node=>node.checked=node.value===value);
      else if(field.type==='multi')nodes.forEach(node=>node.checked=Array.isArray(value)&&value.includes(node.value));
      else if(nodes[0])nodes[0].value=value||'';
    });
    updateUseProgress();
    form.querySelector('input,select,textarea')?.focus();
    notify('示例信息已填入，可继续修改。');
  }
  function collectUsePrompt(skill,config) {
    const data=new FormData($('#skill-task-form'));
    const lines=config.sections.flatMap(section=>section.fields).map(field=>{
      const value=data.getAll(field.id).filter(Boolean).join('、');
      return value?`- ${field.label}：${value}`:'';
    }).filter(Boolean);
    const selected=config.knowledge.filter(item=>data.getAll('knowledge').includes(item.id)).map(item=>item.title);
    return `使用 $${skill.identifier} 完成以下任务：\n${lines.join('\n')}\n- 可用知识库（当前为 Mock 选择）：${selected.length?selected.join('、'):'未选择'}\n\n请先复述任务边界与缺失信息，再按该 SKILL 的方法推进。`;
  }
  function renderUse(skill) {
    activeUseSkill=skill;
    useApiReady=false;
    const config=usePageConfigs[skill.slug];
    $('#use-content').innerHTML=`<a class="use-back" href="#/catalog">← 返回全部 SKILL</a><header class="use-page-header"><div class="use-title-mark">${icon(iconNames[skill.kind])}</div><div class="use-title-copy"><span>${esc(config.eyebrow)} · ${esc(skill.category)}</span><h1>${esc(skill.name)}</h1><p>${esc(config.lead)}</p></div><div class="use-header-actions"><span class="api-status checking" id="api-status"><i></i>正在检查 API</span><a href="${detailHash(skill.slug,useHash(skill.slug))}">查看能力详情 ↗</a></div></header><nav class="use-steps" aria-label="使用步骤"><span class="active"><b>1</b>配置任务</span><i></i><span><b>2</b>选择知识库</span><i></i><span><b>3</b>确认并运行</span></nav><div class="api-setup" id="api-setup" hidden><strong>直接运行需要本地代理</strong><span>在项目目录运行 <code>python3 server.py</code> 后刷新页面。表单与 Mock 知识库仍可正常预览。</span></div><div class="skill-use-layout"><main class="task-builder"><form id="skill-task-form">${config.sections.map(section=>`<section class="task-section"><header><span>${section.number}</span><div><h2>${esc(section.title)}</h2><p>${esc(section.description)}</p></div></header><div class="task-field-grid">${section.fields.map(renderUseField).join('')}</div></section>`).join('')}</form><section class="run-result" id="use-result" aria-live="polite" hidden></section></main><aside class="knowledge-panel"><section class="knowledge-card"><header><div><span>知识库</span><h2>选择参考资料</h2></div><b>MOCK</b></header><p class="knowledge-help">选择本次允许 SKILL 使用的资料范围。当前仅演示前端状态，不会上传或读取真实文档。</p><label class="knowledge-search"><span>⌕</span><input type="search" id="knowledge-search" placeholder="搜索知识库" aria-label="搜索知识库"></label><div class="knowledge-list" id="knowledge-list">${config.knowledge.map(item=>`<label class="knowledge-item" data-kb-item data-search="${esc(item.title+' '+item.meta+' '+item.tag)}"><input type="checkbox" name="knowledge" value="${esc(item.id)}" form="skill-task-form" ${item.default?'checked':''}><span class="knowledge-check">✓</span><span class="knowledge-icon">${esc(item.title.slice(0,1))}</span><span class="knowledge-copy"><strong>${esc(item.title)}</strong><small>${esc(item.meta)}</small></span><em>${esc(item.tag)}</em></label>`).join('')}</div><button type="button" class="mock-upload"><span>＋</span>添加知识库</button><p class="mock-note">演示按钮 · 后续接入真实知识库</p></section><section class="run-card"><div class="run-progress"><span id="task-completion">已完成 0 项</span><b id="kb-count">已选 0 个知识库</b></div><div class="progress-track" id="task-progress" role="progressbar" aria-label="任务信息完成度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i></i></div><h3>执行摘要</h3><ul id="task-summary"><li class="summary-empty">填写任务信息后，这里会生成执行摘要。</li></ul><div class="run-output"><span>预计产出</span><strong>${esc(config.output)}</strong></div><button type="submit" class="run-primary" id="use-start" form="skill-task-form" disabled>开始运行 SKILL <b>→</b></button><div class="run-secondary"><button type="button" id="use-example">填入示例</button><button type="button" id="use-reset">重置表单</button></div><small>提交前请确认资料授权范围，不要填写敏感个人信息。</small></section></aside></div>`;
    const form=$('#skill-task-form');
    form.addEventListener('input',updateUseProgress);
    form.addEventListener('change',updateUseProgress);
    form.addEventListener('submit',submitUseMessage);
    $('#use-example').addEventListener('click',()=>fillUseExample(config));
    $('#use-reset').addEventListener('click',()=>{form.reset();requestAnimationFrame(updateUseProgress);notify('表单已恢复为初始状态。');});
    $('#knowledge-search').addEventListener('input',event=>{
      const needle=event.target.value.trim().toLocaleLowerCase();
      document.querySelectorAll('[data-kb-item]').forEach(item=>item.hidden=Boolean(needle)&&!item.dataset.search.toLocaleLowerCase().includes(needle));
    });
    document.querySelectorAll('[name="knowledge"]').forEach(input=>input.addEventListener('change',updateUseProgress));
    $('.mock-upload').addEventListener('click',()=>notify('当前为前端 Mock，真实知识库接入将在下一阶段完成。'));
    updateUseResult();
    updateUseProgress();
    checkUseHealth();
  }
  async function submitUseMessage(event) {
    event.preventDefault();
    if(useBusy)return;
    const form=$('#skill-task-form');
    const skill=activeUseSkill,config=usePageConfigs[skill.slug];
    const missing=config.sections.flatMap(section=>section.fields).filter(field=>field.required).find(field=>{
      const nodes=[...form.querySelectorAll(`[name="${field.id}"]`)];
      return field.type==='choice'||field.type==='multi'?!nodes.some(node=>node.checked):!nodes[0]?.value.trim();
    });
    if(missing){notify(`请先填写“${missing.label}”。`);form.querySelector(`[name="${missing.id}"]`)?.focus();return;}
    if(!form.reportValidity())return;
    const session=useSession(skill);
    const value=collectUsePrompt(skill,config);
    session.push({role:'user',content:value});useBusy=true;updateUseProgress();updateUseResult();
    $('#use-result').scrollIntoView({behavior:reduced.matches?'auto':'smooth',block:'start'});
    try{
      const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill:skill.slug,messages:session.filter(message=>message.role==='user'||message.role==='assistant')})});
      const data=await response.json();
      if(!response.ok)throw new Error(data.error||'请求失败，请稍后重试。');
      session.push({role:'assistant',content:data.content});
    }catch(error){session.push({role:'error',content:error.message||'请求失败，请稍后重试。'});}
    finally{useBusy=false;if(activeUseSkill===skill){updateUseProgress();updateUseResult();}}
  }
  function route() {
    const raw=location.hash.startsWith('#/')?location.hash.slice(1):'/';const pos=raw.indexOf('?');const path=pos===-1?raw:raw.slice(0,pos);const p=new URLSearchParams(pos===-1?'':raw.slice(pos+1));
    closeNav();
    if(path==='/guide'){location.replace('http://biubiubiu.vip:14188/#/docs/guide');return;}
    if(path==='/use'||path.startsWith('/use/')){const requested=path==='/use'?'':decodeURIComponent(path.slice(5));const skill=skills.find(item=>item.slug===requested)||skills[0];if(path==='/use')history.replaceState(null,'',useHash(skill.slug));renderUse(skill);showPage('use');setCurrentNav('use');document.title='直接使用 '+skill.name+' · 智能体广场';window.scrollTo(0,0);return;}
    if(path.startsWith('/skill/')){const skill=skills.find(item=>item.slug===path.slice(7));if(skill){renderDetail(skill,p.get('return'));showPage('detail');setCurrentNav('catalog');document.title=skill.name+' · 智能体广场';window.scrollTo(0,0);return;}}
    state.q=p.get('q')||'';state.category=categories.includes(p.get('category'))?p.get('category'):'全部';state.sort=['featured','updated','name'].includes(p.get('sort'))?p.get('sort'):'featured';
    $('#search-input').value=state.q;$('#sort-select').value=state.sort;renderCatalog();showPage('home');document.title='智能体广场 · FORU 风格 Demo';
    if(path==='/catalog'||path.startsWith('/role/')){setCurrentNav('catalog');requestAnimationFrame(()=>$('#catalog').scrollIntoView());}
    else{setCurrentNav('home');window.scrollTo(0,0);}
  }
  function renderDetail(skill,returnTo) {
    const safeReturn=returnTo&&(/^(#\/catalog(?:\?|$)|#\/use(?:\/[^?]+)?$)/.test(returnTo))?returnTo:'#/catalog';
    const returnLabel=safeReturn.startsWith('#/use')?'← 返回直接使用':'← 返回 SKILL 目录';
    const feature=features.find(item=>item.slug===skill.slug);
    $('#detail-content').innerHTML=`<a class="back-link" href="${esc(safeReturn)}">${returnLabel}</a><header class="detail-header"><div><span class="detail-category">${esc(skill.category)}</span><h1>${esc(skill.name)}</h1><code>${esc(skill.identifier)}</code><p>${esc(skill.summary)}</p><div class="detail-actions"><a class="foru-primary" href="${useHash(skill.slug)}">直接使用这个 SKILL</a></div></div><div class="detail-info"><span>接入方式</span><strong>在线运行 / API</strong><a href="http://biubiubiu.vip:14188/#/docs/guide">查看接入指南 →</a></div></header><section class="detail-section"><div class="section-number">01</div><div><h2>产物与效果</h2><p>${esc(skill.output)}</p>${feature?`<div class="foru-preview">${previewMarkup(feature,true)}</div>`:`<div class="code-panel"><code>产物说明\n${esc(skill.output)}\n\n此条目尚未配置真实作品预览。</code></div>`}</div></section><section class="detail-section"><div class="section-number">02</div><div><h2>最小输入示例</h2><p>把示例中的地区、资料或附件替换成你的实际输入，再提交任务。</p><div class="code-panel"><code>${esc(skill.minimalInput)}</code><button type="button" class="copy-button" data-copy="minimalInput">复制示例</button></div></div></section><section class="detail-section"><div class="section-number">03</div><div class="split-content"><div><h2>必要依赖</h2><ul class="detail-list">${skill.dependencies.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></div><div><h2>使用限制</h2><ul class="detail-list">${skill.limitations.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></div></div></section>`;
    $('#detail-content').querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',event=>{
      copyText(skill.minimalInput,event.currentTarget,'最小输入示例已复制');
    }));
  }
  async function copyText(value,button,message) {
    let area;
    const original=button.dataset.defaultLabel||button.textContent;
    button.dataset.defaultLabel=original;
    try {
      if(navigator.clipboard&&isSecureContext)await navigator.clipboard.writeText(value);
      else{area=document.createElement('textarea');area.value=value;area.style.cssText='position:fixed;opacity:0;left:0;top:0';document.body.append(area);area.select();if(!document.execCommand('copy'))throw new Error('copy failed');}
      button.textContent='已复制';notify(message);
    }catch{button.textContent='请手动复制';notify('未能自动复制，请选择文字手动复制。');const selection=getSelection();const range=document.createRange();range.selectNodeContents(button.closest('.code-panel').querySelector('code'));selection.removeAllRanges();selection.addRange(range);}
    finally{area?.remove();button.focus();setTimeout(()=>{if(button.isConnected)button.textContent=original;},2200);}
  }
  function notify(message) {clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').hidden=false;toastTimer=setTimeout(()=>$('#toast').hidden=true,2600);}
  window.addEventListener('hashchange',route);
  selectFeature(0);route();frame=requestAnimationFrame(tick);
  window.addEventListener('pagehide',()=>{cancelAnimationFrame(frame);observer.disconnect();});
  window.addEventListener('pageshow',event=>{if(event.persisted){observer.observe(area);previous=0;frame=requestAnimationFrame(tick);}});
})();
