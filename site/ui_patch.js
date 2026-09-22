(function(){
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

  const practicalSorts=[
    ['visits','방문횟수 많은 순'],
    ['spend','집행금액 큰 순'],
    ['name','가나다순'],
    ['institutions','방문기관 많은 순']
  ];
  practicalSorts.forEach(([value,label])=>{
    let opt=sortSelect?.querySelector('option[value="'+value+'"]');
    if(opt) opt.textContent=label;
    else if(sortSelect){
      opt=document.createElement('option');
      opt.value=value;
      opt.textContent=label;
      sortSelect.appendChild(opt);
    }
  });
  const signalOpt=sortSelect?.querySelector('option[value="signal"]');
  if(signalOpt) signalOpt.textContent='신호 강도 순';

  const crossOrigin=DATA.filter(r=>r.cross_institution?.is_cross&&(r.cross_institution?.source_count||0)>=2)
    .sort((a,b)=>(b.cross_institution?.score||0)-(a.cross_institution?.score||0)||(b.evidence?.visits||0)-(a.evidence?.visits||0));
  const topbar=document.querySelector('.topbar');
  if(topbar && crossOrigin.length){
    let showcase=document.getElementById('crossShowcase');
    if(!showcase){
      showcase=document.createElement('section');
      showcase.id='crossShowcase';
      showcase.className='cross-showcase cross-showcase-v2';
      topbar.insertAdjacentElement('afterend',showcase);
    }
    showcase.innerHTML='<div class="cross-showcase-head"><div class="cross-title-wrap"><div class="section-eyebrow">CROSS-ORIGIN PICKS</div><h2>기관 교차 선택</h2><p>여러 기관에서 반복해서 등장한 식당</p></div><div class="cross-head-actions"><button type="button" class="cross-nav cross-prev" aria-label="이전 식당">←</button><button type="button" class="cross-nav cross-next" aria-label="다음 식당">→</button><button type="button" class="cross-all-btn">전체 '+crossOrigin.length+'곳</button></div></div><div class="cross-showcase-track" tabindex="0" aria-label="기관 교차 선택 식당 목록"></div>';
    const track=showcase.querySelector('.cross-showcase-track');

    crossOrigin.forEach(r=>{
      const e=r.evidence||{},ci=r.cross_institution||{};
      const card=document.createElement('button');
      card.type='button';
      card.className='cross-showcase-card';
      card.innerHTML='<span class="cross-rank">교차 '+(ci.score||0)+'</span><strong>'+esc(r.business?.display||r.name)+'</strong><span>'+esc((r.origins||[]).join(' · '))+'</span><small>'+Number(e.visits||0).toLocaleString('ko-KR')+'회 · '+(ci.institution_count||0)+'개 기관</small>';
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
    showcase.querySelector('.cross-all-btn').addEventListener('click',()=>{ds.value='cross_origin';sort.value='consensus';if(typeof clearSelection==='function')clearSelection();else{selected=null;renderEmpty();}renderList(true);document.querySelector('.workspace')?.scrollIntoView({behavior:'smooth',block:'start'});});
  }else{
    const showcase=document.getElementById('crossShowcase');
    if(showcase) showcase.hidden=true;
  }

  const workspace=document.querySelector('.workspace');
  const sidebar=document.querySelector('.sidebar');
  const filters=document.querySelector('.filters');
  const summary=document.querySelector('.summary');
  if(!workspace||!sidebar||!filters||!summary) return;

  const scoreHelp=document.createElement('button');
  scoreHelp.type='button';
  scoreHelp.className='score-help';
  scoreHelp.textContent='점수 뜻 ?';
  scoreHelp.title='반복=반복·고위직 사용 신호 · 교차=복수 기관의 동일 식당 선택 신호 · 목적지=관외/목적지 선택 신호. 맛 평점이 아닙니다.';
  scoreHelp.addEventListener('click',()=>{
    alert('점수는 맛 평점이 아닙니다.\n\n반복: 반복 방문·사용기간·직책 다양성·저녁 비중·집행액 등을 반영한 신호\n교차: 여러 기관·출처에서 같은 식당이 선택된 정도를 반영한 신호\n목적지: 관외 이동·목적지성 선택 패턴을 반영한 신호');
  });
  summary.appendChild(scoreHelp);

  const dataHelp=document.createElement('button');
  dataHelp.type='button';
  dataHelp.className='score-help';
  dataHelp.textContent='데이터 현황';
  dataHelp.title='현재 공개 데이터의 위치 검증·기관별 수집 상태';

  const SOURCE_LABELS={
    goyang:'고양시의회',suwon:'수원시의회',hwaseong:'화성시의회',seongnam:'성남시의회',
    bucheon:'부천시의회',namyangju:'남양주시의회',uijeongbu:'의정부시의회',gwangmyeong:'광명시의회',
    gimpo:'김포시의회',ansan:'안산시의회',paju:'파주시의회',anseong:'안성시의회',icheon:'이천시의회',
    osan:'오산시의회',pocheon:'포천시의회',yangpyeong:'양평군의회',yongin:'용인시의회',gwangju:'광주시의회',
    guri:'구리시의회',uiwang:'의왕시의회',gunpo:'군포시의회',dongducheon:'동두천시의회',gwacheon:'과천시의회',
    gapyeong:'가평군의회',siheung:'시흥시의회',yeoju:'여주시의회',yangju:'양주시의회',hanam:'하남시의회',
    yeoncheon:'연천군의회',michuhol:'미추홀구의회',bupyeong:'부평구의회',jemulpo:'제물포구의회',
    yeongjong:'영종구의회',seohae:'서해구의회',yeonsu:'연수구의회',gyeyang:'계양구의회',ganghwa:'강화군의회',
    ongjin:'옹진군의회',gyeonggi_council:'경기도의회',incheon_council:'인천시의회'
  };
  const STATUS_LABELS={
    PUBLISHED:'게시 중',INGESTION_REVIEW:'수집·인입 점검',ROLE_OR_SOURCE_SCOPE_REVIEW:'파서/역할 점검',
    NO_CANDIDATES:'파서/역할 점검',DISCOVERY_REVIEW:'소스 탐색',BELOW_PUBLICATION_THRESHOLDS:'게시 기준 미달',
    CANDIDATE_BUILD_REVIEW:'후보 생성 점검',PUBLISH_PIPELINE_REVIEW:'게시 파이프라인 점검',NO_DATA:'자료 없음'
  };
  const STATUS_ORDER={
    PUBLISHED:0,BELOW_PUBLICATION_THRESHOLDS:1,PUBLISH_PIPELINE_REVIEW:2,CANDIDATE_BUILD_REVIEW:3,
    ROLE_OR_SOURCE_SCOPE_REVIEW:4,NO_CANDIDATES:5,INGESTION_REVIEW:6,DISCOVERY_REVIEW:7,NO_DATA:8
  };

  function closeDataStatus(){
    document.querySelector('.data-status-backdrop')?.remove();
  }
  function showDataStatus(){
    closeDataStatus();
    const total=Number(STATS.total||DATA.length);
    const mapped=Number(STATS.coordinates||DATA.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).length);
    const a=Number(STATS.location_grade_a||0),b=Number(STATS.location_grade_b||0),c=Number(STATS.location_grade_c||Math.max(0,total-mapped));
    const sourceHealth=STATS.source_health||{};
    const rows=Object.entries(sourceHealth).sort((x,y)=>{
      const ax=STATUS_ORDER[x[1]?.diagnosis]??99, ay=STATUS_ORDER[y[1]?.diagnosis]??99;
      return ax-ay||(SOURCE_LABELS[x[0]]||x[0]).localeCompare(SOURCE_LABELS[y[0]]||y[0],'ko-KR');
    });
    const tableRows=rows.map(([source,row])=>{
      const state=String(row?.diagnosis||'NO_DATA');
      return '<tr><td><strong>'+esc(SOURCE_LABELS[source]||source)+'</strong></td>'+
        '<td><span class="data-status-pill state-'+esc(state.toLowerCase())+'">'+esc(STATUS_LABELS[state]||state)+'</span></td>'+
        '<td>'+Number(row?.raw_rows||0).toLocaleString('ko-KR')+'</td>'+
        '<td>'+Number(row?.candidate_count||0).toLocaleString('ko-KR')+'</td>'+
        '<td>'+Number(row?.published_count||0).toLocaleString('ko-KR')+'</td></tr>';
    }).join('');
    const backdrop=document.createElement('div');
    backdrop.className='data-status-backdrop';
    backdrop.innerHTML='<section class="data-status-modal" role="dialog" aria-modal="true" aria-label="데이터 현황">'+
      '<div class="data-status-head"><div><div class="section-eyebrow">DATA STATUS</div><h2>데이터 현황</h2><p>공개 식당의 위치 검증 수준과 기관별 수집·게시 상태입니다.</p></div><button type="button" class="data-status-close" aria-label="닫기">×</button></div>'+
      '<div class="data-status-metrics">'+
        '<div><span>공개 식당</span><strong>'+total.toLocaleString('ko-KR')+'</strong></div>'+
        '<div><span>지도 표시</span><strong>'+mapped.toLocaleString('ko-KR')+'</strong></div>'+
        '<div><span>A 주소·위치 확인</span><strong>'+a.toLocaleString('ko-KR')+'</strong></div>'+
        '<div><span>B 위치만 확인</span><strong>'+b.toLocaleString('ko-KR')+'</strong></div>'+
        '<div><span>C 위치 미확인</span><strong>'+c.toLocaleString('ko-KR')+'</strong></div>'+
      '</div>'+
      '<div class="data-status-note">위치 미확인 식당은 오배치를 막기 위해 지도에 표시하지 않습니다. 목록과 원자료 증거는 유지됩니다.</div>'+
      (rows.length?'<div class="data-status-table-wrap"><table class="data-status-table"><thead><tr><th>기관</th><th>상태</th><th>원자료</th><th>후보</th><th>게시</th></tr></thead><tbody>'+tableRows+'</tbody></table></div>':'<div class="data-status-note">기관별 상태 데이터가 아직 생성되지 않았습니다.</div>')+
      '</section>';
    backdrop.addEventListener('click',e=>{if(e.target===backdrop)closeDataStatus();});
    backdrop.querySelector('.data-status-close').addEventListener('click',closeDataStatus);
    document.body.appendChild(backdrop);
    requestAnimationFrame(()=>backdrop.classList.add('is-open'));
  }
  dataHelp.addEventListener('click',showDataStatus);
  summary.appendChild(dataHelp);

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
    btn.textContent=collapsed?'☰ 목록 열기':'목록 접기';
    btn.title=collapsed?'식당 목록 열기':'식당 목록 접기';
    btn.classList.toggle('is-floating',collapsed);
    if(collapsed){
      if(btn.parentElement!==document.body) document.body.appendChild(btn);
    }else{
      if(btn.parentElement!==summary) summary.appendChild(btn);
    }
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
