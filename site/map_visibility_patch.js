// Visibility patch for the MapLibre renderer.
// Keep all geocoded restaurants visible at overview zoom instead of hiding them in clusters.
(function(){
  function installLayers(){
    if(!map.isStyleLoaded()) return;
    ['place-labels','places','cluster-count','clusters'].forEach(id=>{ if(map.getLayer(id)) map.removeLayer(id); });
    if(map.getSource('places')) map.removeSource('places');

    map.addSource('places',{type:'geojson',data:geojson()});
    map.addLayer({
      id:'places',type:'circle',source:'places',
      paint:{
        'circle-radius':['interpolate',['linear'],['zoom'],8,4.4,10,5.3,12,6.3,15,7.8],
        'circle-color':['match',['get','kind'],'executive','#ac4f98','destination','#f4ed36','both','#c94245','#61609a'],
        'circle-opacity':.96,
        'circle-stroke-color':'#1a1a1a',
        'circle-stroke-width':['case',['==',['get','selected'],1],4,1.5]
      }
    });
    map.addLayer({
      id:'place-labels',type:'symbol',source:'places',minzoom:11.3,
      layout:{
        'text-field':['get','display'],'text-size':['interpolate',['linear'],['zoom'],11.3,9.5,14,11.8],
        'text-offset':[0,1.25],'text-anchor':'top','text-allow-overlap':false,'text-optional':true
      },
      paint:{'text-color':'#1a1a1a','text-halo-color':'#f9f5f2','text-halo-width':1.8}
    });
    installInteractions();
  }

  function installInteractions(){
    if(window.__execDiningVisibilityBound) return;
    window.__execDiningVisibilityBound=true;
    map.on('mouseenter','places',e=>{
      map.getCanvas().style.cursor='pointer';
      const f=e.features?.[0],r=f&&recordByKey(f.properties.id);
      if(!r) return;
      if(hoverPopup) hoverPopup.remove();
      hoverPopup=new maplibregl.Popup({closeButton:false,closeOnClick:false,offset:12})
        .setLngLat(f.geometry.coordinates)
        .setHTML(`<b>${esc(r.business?.display||r.name)}</b><br><span style="color:#61609a;font-size:12px">${esc(r.address||'주소 확인 필요')}</span>`).addTo(map);
    });
    map.on('mouseleave','places',()=>{
      map.getCanvas().style.cursor='';
      if(hoverPopup){hoverPopup.remove();hoverPopup=null;}
    });
    map.on('click','places',e=>{
      const f=e.features?.[0],r=f&&recordByKey(f.properties.id);
      if(r) selectRecord(r,false,true);
    });
  }

  addLayers=installLayers;
  bindInteractions=installInteractions;

  // MapLibre setStyle() destroys all custom sources/layers. Register the
  // style.load listener BEFORE changing style so a fast/cached style load
  // cannot race past the re-install callback and leave an empty map.
  switchStyle=function(){
    styleMode=styleMode==='positron'?'liberty':'positron';
    mapReady=false;
    if(hoverPopup){hoverPopup.remove();hoverPopup=null;}
    if(selectedPopup){selectedPopup.remove();selectedPopup=null;}
    map.once('style.load',()=>{
      mapReady=true;
      installLayers();
      updateMap(false);
      const r=recordByKey(selected);
      if(r&&Number.isFinite(r.lat)&&Number.isFinite(r.lon)){
        selectedPopup=new maplibregl.Popup({offset:14})
          .setLngLat([r.lon,r.lat])
          .setHTML(popupHtml(r))
          .addTo(map);
      }
    });
    map.setStyle(STYLES[styleMode]);
  };

  // IMPORTANT: maplibre.js creates the button and assigns onclick to the
  // original switchStyle function before this patch loads. Reassigning the
  // variable above does not change that stored function reference, so the
  // old buggy handler was still running in production. Rebind it explicitly.
  const styleButton=[...document.querySelectorAll('.map-actions .map-btn')]
    .find(btn=>btn.textContent.trim()==='지도톤');
  if(styleButton){
    styleButton.onclick=(event)=>{
      event.preventDefault();
      switchStyle();
    };
  }

  fitMap=function(){
    const a=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon));
    if(!a.length) return;
    const b=new maplibregl.LngLatBounds();
    a.forEach(r=>b.extend([r.lon,r.lat]));
    map.fitBounds(b,{padding:{top:90,bottom:45,left:45,right:45},maxZoom:12.2,duration:450});
  };

  updateMap=function(fit=false){
    if(!mapReady||!map.getSource('places')) return;
    map.getSource('places').setData(geojson());
    const n=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).length;
    const missing=current.length-n;
    prog.textContent=`지도 표시 ${n}/${current.length}곳${missing?` · 좌표 보강 필요 ${missing}곳`:''} · 접속 시 지오코딩 0건`;
    if(fit) fitMap();
  };
})();
