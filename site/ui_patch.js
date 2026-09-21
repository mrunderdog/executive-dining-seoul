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
    showcase.className='cross-showcase';
    showcase.innerHTML='<div class="cross-showcase-head"><div><div class="section-eyebrow">CROSS-ORIGIN PICKS</div><h2>기관 교차 선택</h2><p>서로 다른 공공기관·출처에서 독립적으로 반복 선택된 동일 식당입니다.</p></div><button type="button" class="cross-all-btn">전체 '+crossOrigin.length+'곳 보기 →</button></div><div class="cross-showcase-track"></div><div class="cross-pagination" aria-label="기관 교차 선택 페이지"><button type="button" class="cross-page-btn cross-prev" aria-label="이전 페이지">← 이전</button><span class="cross-page-state" aria-live="polite"></span><button type="button" class="cross-page-btn cross-next" aria-label="다음 페이지">다음 →</button></div>';
    const track=showcase.querySelector('.cross-showcase-track');
    const prevBtn=showcase.querySelector('.cross-prev');
    const nextBtn=showcase.querySelector('.cross-next');
    const pageState=showcase.querySelector('.cross-page-state');
    const pageSize=6;
    const pageCount=Math.ceil(crossOrigin.length/pageSize);
    let crossPage=0;

    function renderCrossPage(){
      const start=crossPage*pageSize;
      track.innerHTML='';
      crossOrigin.slice(start,start+pageSize).forEach(r=>{
        const e=r.evidence||{},c=r.cross_institution||{};
        const card=document.createElement('button');
        card.type='button'; card.className='cross-showcase-card';
        card.innerHTML='<span class="cross-rank">C '+(c.score||0)+'</span><strong>'+esc(r.business?.display||r.name)+'</strong><span>'+esc((r.origins||[]).join(' · '))+'</span><small>'+Number(e.visits||0).toLocaleString('ko-KR')+'회 · '+(c.institution_count||0)+'개 기관</small>';
        card.addEventListener('click',()=>{ds.value='cross_origin';sort.value='consensus';renderList(false);selectRecord(r,true,true);});
        track.appendChild(card);
      });
      pageState.textContent=(crossPage+1)+' / '+pageCount+' · '+(start+1)+'–'+Math.min(start+pageSize,crossOrigin.length)+' / '+crossOrigin.length+'곳';
      prevBtn.disabled=crossPage===0;
      nextBtn.disabled=crossPage>=pageCount-1;
    }

    prevBtn.addEventListener('click',()=>{if(crossPage>0){crossPage--;renderCrossPage();}});
    nextBtn.addEventListener('click',()=>{if(crossPage<pageCount-1){crossPage++;renderCrossPage();}});
    if(pageCount<=1) showcase.querySelector('.cross-pagination').hidden=true;
    renderCrossPage();
    showcase.querySelector('.cross-all-btn').addEventListener('click',()=>{ds.value='cross_origin';sort.value='consensus';selected=null;renderEmpty();renderList(true);document.querySelector('.workspace')?.scrollIntoView({behavior:'smooth',block:'start'});});
    topbar.insertAdjacentElement('afterend',showcase);
  }

  const workspace=document.querySelector('.workspace');
  const sidebar=document.querySelector('.sidebar');
  const filters=document.querySelector('.filters');
  if(!workspace||!sidebar||!filters) return;

  const btn=document.createElement('button');
  btn.type='button';
  btn.className='explorer-toggle';
  btn.setAttribute('aria-controls','explorer-panel');
  btn.setAttribute('aria-expanded','true');
  sidebar.id='explorer-panel';
  filters.appendChild(btn);

  function sync(){
    const collapsed=workspace.classList.contains('explorer-collapsed');
    btn.setAttribute('aria-expanded',String(!collapsed));
    btn.textContent=collapsed?'탐색 열기 →':'← 탐색 접기';
    btn.title=collapsed?'Explorer 패널 열기':'Explorer 패널 접기';
    if(collapsed){
      if(btn.parentElement!==document.body) document.body.appendChild(btn);
    }else{
      if(btn.parentElement!==filters) filters.appendChild(btn);
    }
    setTimeout(()=>{ try{ map.resize(); fitMap(); }catch(e){} },230);
  }

  btn.addEventListener('click',()=>{
    workspace.classList.toggle('explorer-collapsed');
    try{localStorage.setItem('executiveDiningExplorerCollapsed',workspace.classList.contains('explorer-collapsed')?'1':'0')}catch(e){}
    sync();
  });

  try{
    if(localStorage.getItem('executiveDiningExplorerCollapsed')==='1') workspace.classList.add('explorer-collapsed');
  }catch(e){}
  sync();
})();
