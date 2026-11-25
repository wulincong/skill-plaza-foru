(() => {
  'use strict';
  const data = window.LUMI_RESEARCH;
  if (!data) return;
  const kind = document.body.dataset.page;
  // The market brief is deliberately narrower than the full research archive:
  // it presents only the ten procurement cases selected for this version.
  const curatedCases = [
    ['B01-R02', '智能体开发实训平台', ['B01-P02']],
    ['B01-R03', '交付内容审核、学生关爱、合规检测智能体', ['B01-P03']],
    ['B04-001', '教学资源库及智能体融合建设', ['B04-S01']],
    ['B08-006', '企业级智能体应用开发平台', ['B08-S09']],
    ['B09-006', '智能体开发交付创新实训室', ['B09-S09']],
    ['B10-003', 'AI 智能体应用和开发平台', ['B10-S04']],
    ['B12-006', '含智能体编排的云计算综合平台', ['B12-S07']],
    ['B14-008', 'AI 智能体思政研学创新云平台', ['B14-S12']],
    ['B15-016', '含助学、助教、助研智能体开发平台', ['B15-S16']],
    ['B16-012', 'AI+课程改造（多智能体与工作流）', ['B16-S16']]
  ];
  const curatedIds = curatedCases.map(([id]) => id);
  const curatedById = new Map(curatedCases.map(([id, title, sourceIds]) => [id, { title, sourceIds }]));
  data.procurementRecordIds = curatedIds;
  data.counts.procurement = curatedIds.length;
  data.updated = '2026-09-11';
  data.records.forEach((record) => {
    const curated = curatedById.get(record.id);
    if (!curated) return;
    record.title = curated.title;
    record.sources = curated.sourceIds;
  });
  const curatedSourceIds = new Set(curatedCases.flatMap(([, , sourceIds]) => sourceIds));
  data.sources = data.sources.filter(source => curatedSourceIds.has(source.id));
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const records = new Map(data.records.map(r => [r.id, r]));
  const customers = new Map(data.customers.map(c => [c.id, c]));
  const sources = new Map(data.sources.map(s => [s.id, s]));
  const procurementIds = new Set(data.procurementRecordIds);
  const inProcurementScope = r => Boolean(r && procurementIds.has(r.id));
  const groups = ['大模型 / 智能体','AI 教学与实训','其他智能化','线索待核验','暂未检出相关采购'];
  const caseURL = id => `lumi-market-case.html?id=${encodeURIComponent(id)}`;
  const customerURL = id => `lumi-market-customer.html?id=${encodeURIComponent(id)}`;
  const refs = ids => `<span class="source-chips">${ids.map(id => `<a href="lumi-market-sources.html#${esc(id)}">${esc(id)}</a>`).join('')}</span>`;
  const fact = (label, value) => `<div class="fact"><dt>${label}</dt><dd>${value}</dd></div>`;
  // A field remains qualified even if other fields in its record are supported.
  const unconfirmed = value => !String(value ?? '').trim() || /待核|未|第三方|转载|候选|线索|^—$|^-$/.test(value);
  const optionalFact = (label, value) => value ? fact(label, value) : '';
  const recordedField = (r, key) => r.supported && !unconfirmed(r[key]) ? esc(r[key]) : '';
  function amountField(r, key) {
    const raw = r[key];
    if (!r.supported || unconfirmed(raw) || !/\d/.test(raw)) return '';
    return `${esc(raw)}<small class="field-note">单位：万元；原始金额及分包说明保留于研究记录。</small>`;
  }
  function stage(r) {
    if (!r.supported) return '待核验线索';
    if (r.stage.includes('意向')) return '采购意向';
    const head = r.stage.split(/\d{4}[-年]/)[0];
    if (/结果|中标|成交/.test(head)) return '结果记录';
    if (/合同/.test(head)) return '合同记录';
    if (/更正/.test(head)) return '更正公告';
    if (/失败|废标/.test(head)) return '采购未成';
    return /招标|磋商/.test(head) ? '招标记录' : '采购记录';
  }
  function summaryAmount(r) {
    if (!r.supported) return ['',''];
    if (r.id === 'B16-004') return ['48.5','包 3 成交（万元）'];
    for (const [key,label] of [['award','中标 / 成交（万元）'],['budget','采购预算（万元）']]) {
      const v = r[key];
      if (unconfirmed(v)) continue;
      if (/包\s*\d|合计|总额/.test(v)) return ['分包列示','预算与成交各包分列'];
      const m = v.match(/^([\d,.]+)/);
      if (m) return [m[1].includes('.') ? m[1].replace(/0+$/,'').replace(/\.$/,'') : m[1],key==='budget' && r.stage.includes('意向') ? '采购意向预算（万元）' : key==='budget' && v.includes('校内采购申请') ? '校内采购申请预算（万元）' : label];
    }
    return ['',''];
  }
  function projectCard(r) {
    const [value,label] = summaryAmount(r);
    return `<article class="related-project"><div><span class="procurement-status ${!r.supported?'is-budget':''}">${stage(r)}</span><span class="record-id">${esc(r.id)}</span><h3><a href="${caseURL(r.id)}">${esc(r.title)} →</a></h3><p>${esc(r.stage)}</p><div class="content-tags">${r.tags.split(/[；;、]/).slice(0,4).map(t=>`<span>${esc(t)}</span>`).join('')}</div>${refs(r.sources)}</div><div class="related-amount">${value?`<strong>${esc(value)}</strong><small>${esc(label)}</small>`:''}<a class="details-button" href="${caseURL(r.id)}">查看明细</a></div></article>`;
  }
  function detailError(title, message='这条链接没有对应的研究记录。请返回列表重新选择。') {
    document.querySelector('[data-detail]').innerHTML = `<header class="procurement-hero"><h1>${title}</h1><p>${esc(message)}</p><a class="text-link" href="lumi-market-${kind==='project'?'procurement':'customer-scale'}.html">返回列表 →</a></header>`;
  }
  function renderProject() {
    const params = new URLSearchParams(location.search);
    const requested = params.get('id') || document.querySelector('[data-default-id]')?.dataset.defaultId;
    const id = data.recordAliases[requested] || requested;
    const r = records.get(id);
    if (!r) return detailError('未找到采购记录');
    if (!inProcurementScope(r)) return detailError('该项目已移出当前采购案例','当前仅展示大模型与智能体直接相关项目。');
    const c = customers.get(r.customerId);
    const [value,label] = summaryAmount(r);
    const sourceNotes = r.sources.map(sid => sources.get(sid)).filter(Boolean);
    const notes = r.supported ? r.notes.filter(line => !/^(项目\s*\d*[:：]|\d+\.\d+\s)/.test(line) && !/未取得|未披露|未获取|未读|未见|未检|待核|待补|缺项|缺失|无法|失败|第三方|转载|仅搜索|尚未/.test(line)) : [];
    const financialFacts = optionalFact('采购预算',amountField(r,'budget')) + optionalFact('中标 / 成交',amountField(r,'award')) + optionalFact('供应商',recordedField(r,'supplier'));
    const duplicate = r.aliases.length ? `<p class="notice">已合并重复记录 ${r.aliases.map(esc).join('、')}，同一公告不重复计数。若研究记录存在早期失败或结果线索，以本页较完整的已读记录为准。</p>` : '';
    document.title = `${r.title} | 采购明细 · Lumi LLM`;
    document.querySelector('[data-detail]').innerHTML = `<header class="procurement-hero detail-heading"><div class="detail-kicker"><span class="procurement-status ${!r.supported?'is-budget':''}">${stage(r)}</span><span>${esc(r.id)} · ${esc(r.category)}</span></div><h1>${esc(r.title)}</h1><p class="lead"><a class="text-link" href="${customerURL(r.customerId)}">${esc(r.school)} →</a></p></header><div class="record-layout"><div><section class="record-section"><h2>项目概况</h2><dl class="facts">${fact('名单客户',esc(r.school))}${fact('地区 / 分类',`${esc(r.region)} · ${esc(c.categories.join('；'))}<small class="field-note">沿用 XLSX 原值；采购主体对应关系以研究备注为准。</small>`)}${optionalFact('官方项目编号',unconfirmed(r.officialId)?'':esc(r.officialId))}${fact('公告与日期',`${esc(r.stage)}<small class="field-note">已检索公告记录；计划采购月份、签约与验收日期不替代公告日期。</small>`)}${fact('项目类别',esc(r.category))}${fact('核心内容',esc(r.tags))}${optionalFact('分包范围',recordedField(r,'package'))}</dl>${r.id==='B16-004'?'<p class="notice">本条包含 4 个包；与大模型直接相关的是包 3，预算 48.6 万元、成交 48.5 万元。项目总预算 230.4 万元不能作为大模型套件单项价格。</p>':''}${duplicate}</section>${financialFacts?`<section class="record-section"><h2>金额与供应商</h2><dl class="facts">${financialFacts}</dl></section>`:''}${notes.length?`<section class="record-section"><h2>项目补充记录</h2><div class="research-notes">${notes.map(line=>`<p>${esc(line)}</p>`).join('')}</div></section>`:''}<section class="record-section"><h2>引用依据</h2><p>原文与来源说明见数据来源页。</p>${sourceNotes.map(s=>`<div class="evidence-source"><a class="text-link" href="lumi-market-sources.html#${s.id}">${s.id} · ${esc(s.title)} →</a><p>${esc(s.org)} · ${esc(s.date)}</p></div>`).join('')}</section></div><aside class="record-side">${value?`<div class="stat-panel"><span class="stat-label">${esc(label)}</span><div class="stat-number ${/^[0-9]/.test(value)?'':'text-stat'}"><strong>${esc(value)}</strong></div><p>市场采购参考，非本平台业绩。</p></div>`:''}<nav class="side-links" aria-label="明细导航"><a class="text-link" href="lumi-market-procurement.html?customer=${r.customerId}">查看该客户采购案例 →</a><a class="text-link" href="${customerURL(r.customerId)}">客户需求详情 →</a><a class="text-link" href="lumi-market-procurement.html">返回采购案例 →</a></nav></aside></div>`;
  }
  function renderCustomer() {
    const requested = new URLSearchParams(location.search).get('id');
    const id = data.customerAliases[requested] || requested;
    const c = customers.get(id);
    if (!c) return detailError('未找到客户记录');
    const rs = c.records.map(id=>records.get(id)).filter(inProcurementScope);
    const supported=rs.filter(r=>r.supported), leads=rs.filter(r=>!r.supported);
    const schoolNotes=[...new Set(c.names.flatMap(n=>n.notes))];
    document.title=`${c.name} | 客户需求 · Lumi LLM`;
    document.querySelector('[data-detail]').innerHTML=`<header class="procurement-hero detail-heading"><p class="procurement-eyebrow">客户需求 · ${esc(c.id)}</p><h1>${esc(c.name)}</h1><div class="detail-kicker"><span class="evidence-badge tone-${c.group}">${groups[c.group]}</span>${c.intention?'<span class="procurement-status is-budget">曾发布采购意向</span>':''}</div><p class="lead">${esc(c.categories.join(' · '))} · 分类沿用 XLSX</p></header><div class="record-layout"><div><section class="record-section"><h2>客户信息</h2><p>${c.group===0?'已取得大模型或智能体直接相关采购依据，可作为潜在客户跟进。':'相关采购记录见下方项目列表。'}与本平台的合作意向尚未确认。</p>${c.intention?'<p>曾发布公开采购意向，表示历史采购需求；不表示当前仍在采购或已与本平台接洽。</p>':''}<dl class="facts">${c.names.map(n=>fact(`名单第 ${n.customer_index} 条`,`${esc(n.name)}<small class="field-note">${esc(n.region)} · ${esc(n.xlsx_category)} · Excel 第 ${n.excel_row} 行</small>`)).join('')}</dl>${c.names.length>1?'<p class="notice">这两个 XLSX 原名已确认对应同一学校，客户总数计 1 家；名称与原分类全部保留。</p>':''}</section><section class="record-section"><h2>相关采购 · ${supported.length} 条</h2>${supported.length?supported.map(projectCard).join(''):'<p>暂无大模型或智能体直接相关采购记录。</p>'}</section>${leads.length?`<section class="record-section"><h2>待核验线索 · ${leads.length} 条</h2><p>这些记录仍有正文、主体或内容依据缺口，不计入有依据的采购案例。</p>${leads.map(projectCard).join('')}</section>`:''}${schoolNotes.length?`<section class="record-section"><h2>检索范围与限制</h2><div class="research-notes">${schoolNotes.map(n=>`<p>${esc(n)}</p>`).join('')}</div></section>`:''}</div><aside class="record-side"><div class="stat-panel"><span class="stat-label">有依据的采购记录</span><div class="stat-number"><strong>${supported.length}</strong><span>条</span></div><p>重复公告已合并；不同分包保留。</p></div><nav class="side-links" aria-label="客户导航"><a class="text-link" href="lumi-market-procurement.html?customer=${id}">在采购表中查看 →</a><a class="text-link" href="lumi-market-customer-scale.html">返回客户名单 →</a></nav></aside></div>`;
  }
  function updateStaticSummaries() {
    if (kind === 'procurement') {
      const overview = document.querySelector('.procurement-overview');
      if (overview) {
        const eyebrow = overview.querySelector('.procurement-eyebrow');
        const lead = overview.querySelector('.lead');
        const caption = overview.querySelector('#procurement-trend-caption');
        const chart = overview.querySelector('.procurement-trend > div');
        if (eyebrow) eyebrow.textContent = '项目清单 · 更新于 2026-09-11';
        if (lead) lead.innerHTML = '10 条采购记录，按学校、项目与分包查阅。<br>项目内容、金额与引用依据逐条关联。';
        if (caption) caption.textContent = '采购案例年度趋势：2024 年 1 条；2025 年 4 条；2026 年截至 09-11 5 条。按本页全部 10 条记录汇总。';
        if (chart) chart.innerHTML = `<span class="trend-y-title">案例数量（条）</span><div class="trend-plot"><span class="trend-grid-line" style="bottom:0%"><span class="trend-tick">0</span></span><span class="trend-grid-line" style="bottom:33.3333%"><span class="trend-tick">2</span></span><span class="trend-grid-line" style="bottom:66.6667%"><span class="trend-tick">4</span></span><span class="trend-grid-line" style="bottom:100%"><span class="trend-tick">6</span></span><div class="trend-bars" style="--trend-years:3"><div class="trend-year-column" data-trend-year="2024" data-trend-count="1" style="--trend-share:16.6667%"><span class="trend-bar"></span><span class="trend-value">1</span><span class="trend-year">2024</span></div><div class="trend-year-column" data-trend-year="2025" data-trend-count="4" style="--trend-share:66.6667%"><span class="trend-bar"></span><span class="trend-value">4</span><span class="trend-year">2025</span></div><div class="trend-year-column is-partial" data-trend-year="2026" data-trend-count="5" style="--trend-share:83.3333%"><span class="trend-bar"></span><span class="trend-value">5</span><span class="trend-year">2026</span><span class="trend-cutoff">截至 09-11</span></div></div></div><span class="trend-x-title">年份</span>`;
      }
      curatedCases.forEach(([id, title]) => {
        const link = document.querySelector(`[data-item="${id}"] .project > a`);
        if (link) link.innerHTML = `${esc(title)} <span aria-hidden="true">→</span>`;
      });
    }
    if (kind === 'sources') {
      const eyebrow = document.querySelector('.procurement-hero .procurement-eyebrow');
      const lead = document.querySelector('.procurement-hero .lead');
      if (eyebrow) eyebrow.textContent = '证据索引 · 更新于 2026-09-11';
      if (lead) lead.textContent = '仅收录本版 10 条采购案例的公告原文与引用字段。每条记录保留实际读取状态，详情页通过来源编号关联。';
    }
  }
  updateStaticSummaries();
  if(kind==='project')return renderProject();
  if(kind==='customer')return renderCustomer();

  const form=document.querySelector('[data-filters]');
  if(!form)return;
  form.addEventListener('submit',e=>e.preventDefault());
  const rowNodes=Array.from(document.querySelectorAll('[data-rows] > [data-item]'));
  const items=rowNodes.map(node=>({node,item:(kind==='customers'?customers:kind==='sources'?sources:records).get(node.dataset.item)})).filter(({node,item})=>{
    if(item)return true;
    node.hidden=true;
    return false;
  });
  const search=form.querySelector('[data-search]');
  const filters=Array.from(form.querySelectorAll('[data-filter]'));
  const prev=document.querySelector('[data-prev]'),next=document.querySelector('[data-next]');
  let currentPage=1,selectedCustomer=null,filtered=[];
  const pageSize=kind==='sources'?12:kind==='customers'?20:12;
  const normalize=s=>String(s).toLowerCase().replace(/\s/g,'');
  const state={};
  function readURL(){
    const params=new URLSearchParams(location.search);
    search.value=params.get('q')||'';
    filters.forEach(f=>{const key=f.dataset.filter;const value=params.get(key);f.value=Array.from(f.options).some(o=>o.value===value)?value:f.options[0].value;state[key]=f.value;});
    currentPage=Math.max(1,Number.parseInt(params.get('page')||'1',10)||1);
    const customerID=params.get('customer');
    selectedCustomer=data.customerAliases[customerID]||customerID;
  }
  function syncURL(){
    const params=new URLSearchParams();
    if(search.value)params.set('q',search.value);
    filters.forEach(f=>{if(f.value!==f.options[0].value)params.set(f.dataset.filter,f.value);});
    if(selectedCustomer)params.set('customer',selectedCustomer);
    if(currentPage>1)params.set('page',String(currentPage));
    const query=params.toString();
    try{history.replaceState(null,'',location.pathname+(query?'?'+query:'')+location.hash);}catch(_){}
  }
  function matches(item){
    const q=normalize(search.value);
    if(kind==='customers'){
      const group=state.group;
      if(group==='potential' && item.group!==0 || /^\d$/.test(group) && item.group!==Number(group) || group==='intention' && (item.group!==0 || !item.intention) || group==='intention2026' && (item.group!==0 || !item.intention2026))return false;
      if(state.category!=='all'&&!item.categories.includes(state.category))return false;
      return !q || normalize(item.names.map(n=>n.name).join(' ')+item.records.map(id=>records.get(id)?.title||'').join(' ')).includes(q);
    }
    if(kind==='procurement'){
      if(selectedCustomer&&!customers.get(selectedCustomer)?.records.includes(item.id))return false;
      if(!inProcurementScope(item))return false;
      if(state.stage==='intention'&&!item.stage.includes('意向')||state.stage==='result'&&stage(item)!=='结果记录'||state.stage==='tender'&&stage(item)!=='招标记录')return false;
      return !q||normalize(item.school+item.title+item.officialId+item.id+item.tags).includes(q);
    }
    if(state.batch!=='all'&&String(item.batch)!==state.batch)return false;
    return !q||normalize(item.id+item.org+item.title+item.cited).includes(q);
  }
  function render({scroll=false,write=true}={}){
    filters.forEach(f=>state[f.dataset.filter]=f.value);
    filtered=items.filter(({item})=>matches(item));
    const pages=Math.max(1,Math.ceil(filtered.length/pageSize));
    currentPage=Math.min(currentPage,pages);
    const visible=new Set(filtered.slice((currentPage-1)*pageSize,currentPage*pageSize).map(x=>x.node));
    items.forEach(({node})=>{node.hidden=!visible.has(node);});
    document.querySelector('[data-result-count]').textContent=filtered.length;
    document.querySelector('[data-empty]').hidden=filtered.length>0;
    document.querySelector('[data-page-count]').textContent=filtered.length?`第 ${(currentPage-1)*pageSize+1}–${Math.min(currentPage*pageSize,filtered.length)} 条 / 共 ${filtered.length} 条 · ${currentPage} / ${pages} 页`:'0 条记录';
    prev.disabled=currentPage===1;next.disabled=currentPage===pages;
    if(write)syncURL();
    if(scroll)form.scrollIntoView({block:'start',behavior:'instant'});
  }
  function revealHash(scroll=true){
    let hash='';try{hash=decodeURIComponent(location.hash.slice(1));}catch(_){return;}
    if(!hash)return;
    const legacyCases={'case-teaching':'B14-008','case-platform':'B08-006'};
    hash=legacyCases[hash]||data.recordAliases[hash]||hash;
    const target=items.find(x=>x.node.id===hash);
    if(!target)return;
    const wasFiltered=!matches(target.item);
    if(wasFiltered){search.value='';filters.forEach(f=>{f.value=Array.from(f.options).some(o=>o.value==='all')?'all':f.options[0].value;});selectedCustomer=null;}
    render({write:false});
    currentPage=Math.floor(filtered.indexOf(target)/pageSize)+1;
    render();
    if(scroll)requestAnimationFrame(()=>target.node.scrollIntoView({block:'start',behavior:'instant'}));
  }
  readURL();
  if(kind==='procurement'&&selectedCustomer){
    const c=customers.get(selectedCustomer);
    if(c){const banner=document.createElement('p');banner.className='notice customer-filter-note';banner.innerHTML=`当前客户：<a class="text-link" href="${customerURL(c.id)}">${esc(c.name)}</a> · <a class="text-link" href="lumi-market-procurement.html">查看全部客户</a>`;form.before(banner);}
  }
  form.addEventListener('input',()=>{currentPage=1;render();});
  form.addEventListener('change',()=>{currentPage=1;render();});
  form.addEventListener('reset',e=>{e.preventDefault();search.value='';filters.forEach(f=>f.value=f.options[0].value);currentPage=1;render();});
  prev.addEventListener('click',()=>{currentPage--;render({scroll:true});});
  next.addEventListener('click',()=>{currentPage++;render({scroll:true});});
  window.addEventListener('hashchange',()=>revealHash());
  window.addEventListener('popstate',()=>{readURL();render({write:false});revealHash();});
  document.addEventListener('click',e=>{
    const a=e.target.closest('a[href^="#"]');
    if(!a||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
    const id=a.getAttribute('href').slice(1);
    if(!items.some(x=>x.node.id===id))return;
    e.preventDefault();e.stopImmediatePropagation();
    history.pushState(null,'','#'+id);revealHash();
  },true);
  render({write:false});revealHash();
})();
