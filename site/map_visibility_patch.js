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

  // Replace the old custom style-layer renderer with DOM markers.
  // These are outside MapLibre's style graph and survive setStyle().
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

  // Now the tone button can perform a real basemap switch again.
  // DOM markers remain mounted while Positron/Liberty is replaced underneath them.
  switchStyle=function(){
    styleMode=styleMode==='positron'?'liberty':'positron';
    if(hoverPopup){hoverPopup.remove();hoverPopup=null;}
    map.setStyle(STYLES[styleMode]);
    if(styleButton){
      styleButton.disabled=true;
      styleButton.textContent=styleMode==='liberty'?'지도톤 · 컬러':'지도톤 · 라이트';
      styleButton.setAttribute('aria-pressed',styleMode==='liberty'?'true':'false');
    }
    map.once('style.load',()=>{
      mapReady=true;
      cleanupLegacyLayers();
      renderDomMarkers();
      updateMap(false);
      if(styleButton) styleButton.disabled=false;
    });
  };

  // maplibre.js creates the button before this patch executes; replace its handler directly.
  const styleButton=[...document.querySelectorAll('.map-actions .map-btn')]
    .find(btn=>btn.textContent.trim().startsWith('지도톤'));
  if(styleButton){
    styleButton.onclick=event=>{
      event.preventDefault();
      switchStyle();
    };
    styleButton.textContent='지도톤 · 라이트';
    styleButton.title='라이트/컬러 지도 전환';
    styleButton.setAttribute('aria-pressed','false');
  }

  // If the map has already loaded before this patch executes, migrate immediately.
  if(map.loaded()){
    mapReady=true;
    cleanupLegacyLayers();
    renderDomMarkers();
    updateMap(false);
  }
})();
