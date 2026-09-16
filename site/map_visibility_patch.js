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
        'circle-radius':['interpolate',['linear'],['zoom'],8,3.8,10,4.8,12,5.8,15,7.2],
        'circle-color':['match',['get','kind'],'executive','#111111','destination','#ffffff','both','#737373','#525252'],
        'circle-opacity':.92,
        'circle-stroke-color':['case',['==',['get','kind'],'destination'],'#111111','#ffffff'],
        'circle-stroke-width':['case',['==',['get','selected'],1],4,['==',['get','kind'],'destination'],2.2,1.5]
      }
    });
    map.addLayer({
      id:'place-labels',type:'symbol',source:'places',minzoom:11.5,
      layout:{
        'text-field':['get','display'],'text-size':['interpolate',['linear'],['zoom'],11.5,9.5,14,11.5],
        'text-offset':[0,1.15],'text-anchor':'top','text-allow-overlap':false,'text-optional':true
      },
      paint:{'text-color':'#171717','text-halo-color':'#ffffff','text-halo-width':1.8}
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
        .setHTML(`<b>${esc(r.business?.display||r.name)}</b><br><span style="color:#737373;font-size:12px">${esc(r.address||'주소 확인 필요')}</span>`).addTo(map);
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

  // Replace the clustered layer installer before the map load callback executes.
  addLayers=installLayers;
  bindInteractions=installInteractions;

  const oldFit=fitMap;
  fitMap=function(){
    const a=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon));
    if(!a.length) return;
    const b=new maplibregl.LngLatBounds();
    a.forEach(r=>b.extend([r.lon,r.lat]));
    // Keep a useful metro-level overview. Individual points remain visible because clustering is disabled.
    map.fitBounds(b,{padding:{top:90,bottom:45,left:45,right:45},maxZoom:12.2,duration:450});
  };

  // More explicit coverage copy: users should immediately understand that missing markers are missing coordinates.
  const oldUpdateMap=updateMap;
  updateMap=function(fit=false){
    if(!mapReady||!map.getSource('places')) return;
    map.getSource('places').setData(geojson());
    const n=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).length;
    const missing=current.length-n;
    prog.textContent=`지도 표시 ${n}/${current.length}곳${missing?` · 좌표 보강 필요 ${missing}곳`:''} · 브라우저 지오코딩 0건`;
    if(fit) fitMap();
  };
})();
