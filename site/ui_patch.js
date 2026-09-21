(function(){
  document.title='그들이 먹는 세상 | 공개 지출기록으로 보는 식당 선택 지도';
  const h1=document.querySelector('.brand h1');
  if(h1) h1.textContent='그들이 먹는 세상';
  const brandP=document.querySelector('.brand p');
  if(brandP) brandP.innerHTML='서울·경기·인천의 지방정부와 의회, 중앙정부, 국회의원 공개 지출자료를 모아 여러 기관이 반복해서 찾은 식당과 선택 패턴을 보여줍니다. 맛집 평점이 아니라 <b>실제 공개 기록에 남은 선택의 흔적</b>을 탐색합니다.<br><span class="brand-tagline">누가 어디서, 얼마나 자주 먹었는지는 기록에 남습니다.</span>';
  const kicker=document.querySelector('.brand-kicker');
  if(kicker) kicker.textContent='공개 지출기록으로 보는 공공부문의 식당 선택 지도';
  const originLabel=document.querySelector('label[for="origin"]');
  if(originLabel) originLabel.textContent='기관 / 출처';

  const signalSelect=document.getElementById('ds');
  if(signalSelect && !signalSelect.querySelector('option[value="consensus"]')){
    const opt=document.createElement('option');
    opt.value='consensus';
    opt.textContent='기관 교차 선택';
    signalSelect.appendChild(opt);
  }
  if(signalSelect && !signalSelect.querySelector('option[value="top_official"]')){
    const opt=document.createElement('option');
    opt.value='top_official';
    opt.textContent='장·차관급 사용';
    signalSelect.appendChild(opt);
  }
  if(signalSelect && !signalSelect.querySelector('option[value="regional_head"]')){
    const opt=document.createElement('option');
    opt.value='regional_head';
    opt.textContent='시장·부시장급 사용';
    signalSelect.appendChild(opt);
  }
  if(signalSelect && !signalSelect.querySelector('option[value="cross_origin"]')){
    const opt=document.createElement('option');
    opt.value='cross_origin';
    opt.textContent='지역 간 교차 선택';
    signalSelect.appendChild(opt);
  }
  const sortSelect=document.getElementById('sort');
  if(sortSelect && !sortSelect.querySelector('option[value="consensus"]')){
    const opt=document.createElement('option');
    opt.value='consensus';
    opt.textContent='기관 교차 신호';
    sortSelect.appendChild(opt);
  }
  if(sortSelect && !sortSelect.querySelector('option[value="top_official"]')){
    const opt=document.createElement('option');
    opt.value='top_official';
    opt.textContent='장·차관급 반복';
    sortSelect.appendChild(opt);
  }
  if(sortSelect && !sortSelect.querySelector('option[value="regional_head"]')){
    const opt=document.createElement('option');
    opt.value='regional_head';
    opt.textContent='시장·부시장급 반복';
    sortSelect.appendChild(opt);
  }

  const crossOrigin=DATA.filter(r=>r.cross_institution?.is_cross&&(r.cross_institution?.source_count||0)>=2)
    .sort((a,b)=>(b.cross_institution?.score||0)-(a.cross_institution?.score||0)||(b.evidence?.visits||0)-(a.evidence?.visits||0));
  const topbar=document.querySelector('.topbar');
  if(topbar && crossOrigin.length){
    const showcase=document.createElement('section');
    showcase.className='cross-showcase cross-showcase-v2';
    showcase.innerHTML='<div class="cross-showcase-head"><div class="cross-title-wrap"><div class="section-eyebrow">CROSS-ORIGIN PICKS</div><h2>기관 교차 선택</h2><p>여러 기관에서 반복해서 등장한 식당</p></div><div class="cross-head-actions"><button type="button" class="cross-nav cross-prev" aria-label="이전 식당">←</button><button type="button" class="cross-nav cross-next" aria-label="다음 식당">→</button><button type="button" class="cross-all-btn">전체 '+crossOrigin.length+'곳</button></div></div><div class="cross-showcase-track" tabindex="0" aria-label="기관 교차 선택 식당 목록"></div>';
    const track=showcase.querySelector('.cross-showcase-track');

    crossOrigin.forEach(r=>{
      const e=r.evidence||{},ci=r.cross_institution||{};
      const card=document.createElement('button');
      card.type='button';
      card.className='cross-showcase-card';
      card.innerHTML='<span class="cross-rank">C '+(ci.score||0)+'</span><strong>'+esc(r.business?.display||r.name)+'</strong><span>'+esc((r.origins||[]).join(' · '))+'</span><small>'+Number(e.visits||0).toLocaleString('ko-KR')+'회 · '+(ci.institution_count||0)+'개 기관</small>';
      card.addEventListener('click',()=>{ds.value='cross_origin';sort.value='consensus';renderList(false);selectRecord(r,true,true);document.querySelector('.workspace')?.scrollIntoView({behavior:'smooth',block:'nearest'});});
      track.appendChild(card);
    });

    const scrollCards=dir=>{
      const card=track.querySelector('.cross-showcase-card');
      const step=(card?.getBoundingClientRect().width||240)+10;
      track.scrollBy({left:dir*step*2,behavior:'smooth'});
    };
    showcase.querySelector('.cross-prev').addEventListener('click',()=>scrollCards(-1));
    showcase.querySelector('.cross-next').addEventListener('click',()=>scrollCards(1));
    showcase.querySelector('.cross-all-btn').addEventListener('click',()=>{ds.value='cross_origin';sort.value='consensus';selected=null;renderEmpty();renderList(true);document.querySelector('.workspace')?.scrollIntoView({behavior:'smooth',block:'start'});});
    topbar.insertAdjacentElement('afterend',showcase);
  }

  const workspace=document.querySelector('.workspace');
  const sidebar=document.querySelector('.sidebar');
  const filters=document.querySelector('.filters');
  const summary=document.querySelector('.summary');
  if(!workspace||!sidebar||!filters||!summary) return;

  document.body.classList.add('ui-v2');
  sidebar.id='explorer-panel';

  const btn=document.createElement('button');
  btn.type='button';
  btn.className='explorer-toggle';
  btn.setAttribute('aria-controls','explorer-panel');
  btn.setAttribute('aria-expanded','true');
  summary.appendChild(btn);

  function sync(){
    const collapsed=workspace.classList.contains('explorer-collapsed');
    btn.setAttribute('aria-expanded',String(!collapsed));
    btn.textContent=collapsed?'목록 열기':'목록 접기';
    btn.title=collapsed?'식당 목록 열기':'식당 목록 접기';
    setTimeout(()=>{ try{ map.resize(); }catch(e){} },240);
  }

  btn.addEventListener('click',()=>{
    workspace.classList.toggle('explorer-collapsed');
    try{localStorage.setItem('executiveDiningExplorerCollapsed',workspace.classList.contains('explorer-collapsed')?'1':'0')}catch(e){}
    sync();
  });

  try{
    if(localStorage.getItem('executiveDiningExplorerCollapsed')==='1') workspace.classList.add('explorer-collapsed');
  }catch(e){}

  const baseRenderDetail=renderDetail;
  const baseRenderEmpty=renderEmpty;

  function addDrawerChrome(){
    if(detail.querySelector('.detail-drawer-close')) return;
    const close=document.createElement('button');
    close.type='button';
    close.className='detail-drawer-close';
    close.setAttribute('aria-label','상세 닫기');
    close.textContent='×';
    close.addEventListener('click',()=>{
      selected=null;
      if(selectedPopup){selectedPopup.remove();selectedPopup=null;}
      baseRenderEmpty();
      workspace.classList.remove('detail-open');
      highlight();
      updateMap(false);
      setTimeout(()=>{try{map.resize()}catch(e){}},180);
    });
    detail.prepend(close);
  }

  renderDetail=function(r){
    baseRenderDetail(r);
    if(!r){
      workspace.classList.remove('detail-open');
      return;
    }
    addDrawerChrome();
    workspace.classList.add('detail-open');
    setTimeout(()=>{try{map.resize()}catch(e){}},180);
  };

  renderEmpty=function(){
    baseRenderEmpty();
    workspace.classList.remove('detail-open');
  };

  // Initial empty detail is now hidden off-canvas rather than reserving a third column.
  workspace.classList.remove('detail-open');
  sync();
})();
