/* Independent example implementation; no FORU services or dependencies. */
(() => {
  let dispose;
  function mount() {
    const abort = new AbortController();
    const on = (node, event, fn) => node.addEventListener(event, fn, {signal:abort.signal});
    const roles = {
      personal:[['学习课堂','learning'],['能力测评','assessment'],['招聘广场','jobs'],['项目广场','projects']],
      enterprise:[['人才甄选','team'],['项目众包','case'],['成果转化','building']],
      college:[['院校工作台','building'],['产业研究','case'],['教学实训','book']],
      partner:[['产业共同体','team'],['专家协作','case'],['师资共建','book']]
    };
    const tabs=[...document.querySelectorAll('[data-role]')];
    const panel=document.getElementById('products');
    function selectRole(id) {
      if (!roles[id]) return;
      tabs.forEach(tab => {const active=tab.dataset.role===id; tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;});
      panel.setAttribute('aria-labelledby','role-'+id);
      panel.style.setProperty('--product-count',roles[id].length);
      panel.replaceChildren(...roles[id].map(([label,icon],index) => {
        const link=document.createElement('a');link.className='foru-product';link.href='#resources';
        const wrapper=document.createElement('span');wrapper.className='foru-product-icon';
        wrapper.style.setProperty('--icon-color',['#165dff','#8470ec','#20b994','#41b5ee'][index]);
        const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('aria-hidden','true');
        const use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#foru-'+icon);svg.append(use);wrapper.append(svg);
        const text=document.createElement('span');text.textContent=label;link.append(wrapper,text);return link;
      }));
    }
    function keyboardTabs(list, select, orientation='horizontal') {
      list.forEach((button,index) => on(button,'keydown',event => {
        const previous=orientation==='vertical'?'ArrowUp':'ArrowLeft';
        const next=orientation==='vertical'?'ArrowDown':'ArrowRight';
        let target;
        if (event.key===previous) target=(index-1+list.length)%list.length;
        if (event.key===next) target=(index+1)%list.length;
        if (event.key==='Home') target=0;
        if (event.key==='End') target=list.length-1;
        if (target!==undefined){event.preventDefault();select(target);list[target].focus();}
      }));
    }
    tabs.forEach(tab=>on(tab,'click',()=>selectRole(tab.dataset.role)));
    keyboardTabs(tabs,index=>selectRole(tabs[index].dataset.role));selectRole('personal');
    const nav=document.getElementById('foru-nav');
    const toggle=document.querySelector('.foru-nav-toggle');
    function closeNav(){nav.classList.remove('open');toggle.setAttribute('aria-expanded','false');nav.querySelectorAll('details').forEach(d=>d.open=false);}
    on(toggle,'click',()=>{const open=toggle.getAttribute('aria-expanded')!=='true';toggle.setAttribute('aria-expanded',String(open));nav.classList.toggle('open',open);});
    nav.querySelectorAll('a').forEach(link=>on(link,'click',()=>{if(link.dataset.roleLink) selectRole(link.dataset.roleLink);closeNav();}));
    on(document,'keydown',event=>{if(event.key==='Escape'){const focused=nav.contains(document.activeElement);const summary=nav.querySelector('details[open]>summary');closeNav();if(focused)(getComputedStyle(toggle).display!=='none'?toggle:summary)?.focus();}});
    on(document,'click',event=>{if(!document.querySelector('.foru-header').contains(event.target)) closeNav();});
    const solutions=[...document.querySelectorAll('.foru-solution')];
    function selectSolution(index){solutions.forEach((card,i)=>{const active=i===index;card.classList.toggle('active',active);const button=card.querySelector('button');button.setAttribute('aria-expanded',String(active));if(button.dataset.title)button.textContent=active?button.dataset.expandedTitle:button.dataset.title;});}
    solutions.forEach((card,index)=>{on(card.querySelector('button'),'click',()=>selectSolution(index));on(card,'pointerenter',event=>{if(event.pointerType==='mouse')selectSolution(index);});on(card,'focusin',()=>selectSolution(index));});
    const area=document.querySelector('.foru-features');
    const features=[...document.querySelectorAll('.foru-feature')];
    const preview=document.getElementById('feature-preview');
    const pause=document.getElementById('foru-pause');
    const reduced=matchMedia('(prefers-reduced-motion: reduce)');
    let active=0,elapsed=0,previousTime=0,frame,visible=false,manualPause=false,hover=false,focused=false;
    function selectFeature(index){
      active=index;elapsed=0;
      features.forEach((button,i)=>{button.classList.toggle('active',i===index);button.setAttribute('aria-selected',String(i===index));button.tabIndex=i===index?0:-1;button.style.setProperty('--progress',0);});
      preview.setAttribute('aria-labelledby','feature-'+index);preview.dataset.feature=String(index);
      document.getElementById('preview-title').textContent=features[index].querySelector('strong').textContent;
      document.getElementById('preview-description').textContent=features[index].querySelector('span').textContent;
      document.getElementById('preview-tags').replaceChildren(...features[index].querySelector('small').textContent.split(/\s+/).filter(Boolean).map(label=>{const tag=document.createElement('span');tag.textContent=label;return tag;}));
    }
    features.forEach((button,index)=>on(button,'click',()=>selectFeature(index)));
    keyboardTabs(features,selectFeature,'vertical');selectFeature(0);
    on(pause,'click',()=>{manualPause=!manualPause;pause.setAttribute('aria-pressed',String(manualPause));pause.textContent=manualPause?'继续自动展示':'暂停自动展示';});
    on(area,'pointerenter',event=>{if(event.pointerType==='mouse')hover=true;});on(area,'pointerleave',()=>hover=false);
    on(area,'focusin',()=>focused=true);on(area,'focusout',event=>focused=area.contains(event.relatedTarget));
    const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;},{threshold:0.25});observer.observe(area);
    function tick(time){
      const delta=previousTime?Math.min(time-previousTime,100):0;previousTime=time;
      if(visible&&!document.hidden&&!manualPause&&!hover&&!focused&&!reduced.matches){elapsed+=delta;if(elapsed>=5000)selectFeature((active+1)%features.length);features[active].style.setProperty('--progress',elapsed/5000);}
      frame=requestAnimationFrame(tick);
    }
    frame=requestAnimationFrame(tick);
    return ()=>{abort.abort();observer.disconnect();cancelAnimationFrame(frame);};
  }
  dispose=mount();
  addEventListener('pagehide',()=>dispose?.());
  addEventListener('pageshow',event=>{if(event.persisted)dispose=mount();});
})();
