(function(){
  document.title='Executive Dining 수도권';
  const h1=document.querySelector('.brand h1');
  if(h1) h1.textContent='Executive Dining 수도권';
  const brandP=document.querySelector('.brand p');
  if(brandP) brandP.innerHTML='서울·경기·인천 기초의회 업무추진비 공개자료에서 반복 선택·고위직 방문·관외 이동 패턴을 찾아 식당 단위로 탐색합니다. 점수는 맛 평가가 아니라 <b>선택 패턴의 강도</b>입니다.';
  const originLabel=document.querySelector('label[for="origin"]');
  if(originLabel) originLabel.textContent='출발 지역';

  const workspace=document.querySelector('.workspace');
  const sidebar=document.querySelector('.sidebar');
  if(!workspace||!sidebar) return;

  const btn=document.createElement('button');
  btn.type='button';
  btn.className='explorer-toggle';
  btn.setAttribute('aria-controls','explorer-panel');
  btn.setAttribute('aria-expanded','true');
  sidebar.id='explorer-panel';
  document.body.appendChild(btn);

  function sync(){
    const collapsed=workspace.classList.contains('explorer-collapsed');
    btn.setAttribute('aria-expanded',String(!collapsed));
    btn.textContent=collapsed?'탐색 열기 →':'← 탐색 접기';
    btn.title=collapsed?'Explorer 패널 열기':'Explorer 패널 접기';
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
