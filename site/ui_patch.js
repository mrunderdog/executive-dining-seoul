(function(){
  const workspace=document.querySelector('.workspace');
  const sidebar=document.querySelector('.sidebar');
  if(!workspace||!sidebar) return;

  const btn=document.createElement('button');
  btn.type='button';
  btn.className='explorer-toggle';
  btn.setAttribute('aria-controls','explorer-panel');
  btn.setAttribute('aria-expanded','true');
  btn.innerHTML='<span class="state-open">← 탐색 접기</span><span class="state-closed">탐색 열기 →</span>';
  sidebar.id='explorer-panel';
  document.body.appendChild(btn);

  function sync(){
    const collapsed=workspace.classList.contains('explorer-collapsed');
    btn.setAttribute('aria-expanded',String(!collapsed));
    setTimeout(()=>{ try{ map.resize(); fitMap(); }catch(e){} },230);
  }

  btn.addEventListener('click',()=>{
    workspace.classList.toggle('explorer-collapsed');
    sync();
  });

  // Remember the user's choice on this browser, but default to open on first visit.
  try{
    const saved=localStorage.getItem('executiveDiningExplorerCollapsed');
    if(saved==='1') workspace.classList.add('explorer-collapsed');
    btn.addEventListener('click',()=>localStorage.setItem('executiveDiningExplorerCollapsed',workspace.classList.contains('explorer-collapsed')?'1':'0'));
  }catch(e){}
  sync();
})();
