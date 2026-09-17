// Stable MapLibre marker renderer.
// Restaurant markers are DOM overlays, so swapping the basemap style cannot remove them.
(function(){
  const domMarkers=new Map();

  function markerColors(r){
    if(r.type==='both') return {bg:'#c94245',border:'#1a1a1a'};
    if(r.type==='destination') return {bg:'#f4ed36',border:'#1a1a1a'};
    if(r.type==='executive') return {bg:'#ac4f98',border:'#1a1a1a'};
    return {bg:'#61609a',border:'#1a1a1a'};
  }

  function styleMarker(el,r){
    const active=key(r)===selected;
    const c=markerColors(r);
    el.style.width=active?'16px':'11px';
    el.style.height=active?'16px':'11px';
    el.style.borderRadius='999px';
    el.style.background=c.bg;
    el.style.border=`${active?3:2}px solid ${active?'#fff':c.border}`;
    el.style.boxShadow=active?'0 0 0 3px #1a1a1a,0 2px 8px rgba(0,0,0,.28)':'0 1px 5px rgba(0,0,0,.34)';
    el.style.cursor='pointer';
    el.style.padding='0';
    el.style.margin='0';
    el.style.outline='0';
  }

  function createDomMarker(r){
    const el=document.createElement('button');
    el.type='button';
    el.setAttribute('aria-label',`${r.business?.display||r.name} 지도 마커`);
    el.title=r.business?.display||r.name;
    styleMarker(el,r);

    el.addEventListener('mouseenter',()=>{
      if(hoverPopup) hoverPopup.remove();
      hoverPopup=new maplibregl.Popup({closeButton:false,closeOnClick:false,offset:12})
        .setLngLat([r.lon,r.lat])
        .setHTML(`<b>${esc(r.business?.display||r.name)}</b><br><span style="color:#61609a;font-size:12px">${esc(r.address||'주소 확인 필요')}</span>`)
        .addTo(map);
    });
    el.addEventListener('mouseleave',()=>{
      if(hoverPopup){hoverPopup.remove();hoverPopup=null;}
    });
    el.addEventListener('click',event=>{
      event.preventDefault();
      event.stopPropagation();
      selectRecord(r,false,true);
    });

    const marker=new maplibregl.Marker({element:el,anchor:'center'})
      .setLngLat([r.lon,r.lat])
      .addTo(map);
    return {marker,el};
  }

  function cleanupLegacyLayers(){
    if(!map.isStyleLoaded()) return;
    ['place-labels','places','cluster-count','clusters'].forEach(id=>{
      if(map.getLayer(id)) map.removeLayer(id);
    });
    if(map.getSource('places')) map.removeSource('places');
  }

  function renderDomMarkers(){
    const wanted=new Set();
    for(const r of current){
      if(!Number.isFinite(r.lat)||!Number.isFinite(r.lon)) continue;
      const k=key(r); wanted.add(k);
      let item=domMarkers.get(k);
      if(!item){
        item=createDomMarker(r);
        domMarkers.set(k,item);
      }else{
        item.marker.setLngLat([r.lon,r.lat]);
        styleMarker(item.el,r);
      }
    }
    for(const [k,item] of domMarkers){
      if(!wanted.has(k)){
        item.marker.remove();
        domMarkers.delete(k);
      }
    }
  }

  addLayers=function(){
    cleanupLegacyLayers();
    renderDomMarkers();
  };
  bindInteractions=function(){};

  fitMap=function(){
    const a=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon));
    if(!a.length) return;
    const b=new maplibregl.LngLatBounds();
    a.forEach(r=>b.extend([r.lon,r.lat]));
    map.fitBounds(b,{padding:{top:90,bottom:45,left:45,right:45},maxZoom:12.2,duration:450});
  };

  updateMap=function(fit=false){
    renderDomMarkers();
    const n=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).length;
    const missing=current.length-n;
    prog.textContent=`지도 표시 ${n}/${current.length}곳${missing?` · 좌표 보강 필요 ${missing}곳`:''} · 접속 시 지오코딩 0건`;
    if(fit) fitMap();
  };

  const styleButton=[...document.querySelectorAll('.map-actions .map-btn')]
    .find(btn=>btn.textContent.trim().startsWith('지도톤'));
  let styleSwitchSeq=0;

  function updateStyleButton(loading=false){
    if(!styleButton) return;
    if(loading){
      styleButton.textContent='지도톤 · 전환 중…';
      styleButton.setAttribute('aria-busy','true');
      styleButton.title='지도 스타일을 불러오는 중입니다';
      styleButton.style.cursor='wait';
      styleButton.style.opacity='.72';
      return;
    }
    const colorMode=styleMode==='liberty';
    styleButton.textContent=colorMode?'지도톤 · 컬러':'지도톤 · 라이트';
    styleButton.setAttribute('aria-pressed',colorMode?'true':'false');
    styleButton.setAttribute('aria-busy','false');
    styleButton.title='라이트/컬러 지도 전환';
    styleButton.style.cursor='pointer';
    styleButton.style.opacity='1';
  }

  // Register style.load BEFORE setStyle(). The previous implementation did the
  // opposite, so a cached/fast style could finish before the listener existed,
  // leaving the button permanently disabled after the first click.
  switchStyle=function(){
    const nextMode=styleMode==='positron'?'liberty':'positron';
    const seq=++styleSwitchSeq;
    if(hoverPopup){hoverPopup.remove();hoverPopup=null;}
    if(styleButton){
      styleButton.disabled=true;
      updateStyleButton(true);
    }

    let finished=false;
    const finish=()=>{
      if(finished||seq!==styleSwitchSeq) return;
      finished=true;
      mapReady=true;
      cleanupLegacyLayers();
      renderDomMarkers();
      updateMap(false);
      updateStyleButton(false);
      if(styleButton) styleButton.disabled=false;
    };

    map.once('style.load',finish);
    styleMode=nextMode;
    map.setStyle(STYLES[styleMode]);

    // Network/style errors must never strand the toggle in a disabled state.
    setTimeout(finish,2500);
  };

  if(styleButton){
    styleButton.onclick=event=>{
      event.preventDefault();
      if(styleButton.disabled) return;
      switchStyle();
    };
    updateStyleButton(false);
  }

  if(map.loaded()){
    mapReady=true;
    cleanupLegacyLayers();
    renderDomMarkers();
    updateMap(false);
  }
})();
