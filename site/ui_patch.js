(function(){
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
