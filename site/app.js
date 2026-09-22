/* app.js — consolidated runtime. Generated from the former map + visibility + UI layers. */
/* Core map/application */
const DATA=__DATA__,STATS=__STATS__,ORIGINS=__ORIGINS__;
const $=id=>document.getElementById(id),ds=$('ds'),ori=$('origin'),q=$('q'),sort=$('sort'),list=$('list'),detail=$('detail'),sum=$('sum'),prog=$('prog');
['전체',...ORIGINS].forEach(o=>{const x=document.createElement('option');x.value=o==='전체'?'all':o;x.textContent=o;ori.appendChild(x)});
let current=[],selected=null,mapReady=false,hoverPopup=null,selectedPopup=null,styleMode='positron',bound=false;
const STYLES={positron:'https://tiles.openfreemap.org/styles/positron',liberty:'https://tiles.openfreemap.org/styles/liberty'};
const map=new maplibregl.Map({container:'map',style:STYLES[styleMode],center:[126.98,37.53],zoom:9.1,attributionControl:true});
map.addControl(new maplibregl.NavigationControl(),'bottom-right');
map.addControl(new maplibregl.FullscreenControl(),'bottom-right');
function esc(s){return(s??'').toString().replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')}
function won(n){return Number(n||0).toLocaleString('ko-KR')+'원'}
function shortWon(n){n=Number(n||0);if(n>=1e8)return(n/1e8).toFixed(1).replace('.0','')+'억';if(n>=1e4)return Math.round(n/1e4).toLocaleString('ko-KR')+'만';return n.toLocaleString('ko-KR')}
function pct(v){return Math.round(Number(v||0)*100)+'%'}function key(r){return r.entity_id||r.name+'|'+r.origin}function sourceLabel(r){const a=r.origins||[r.origin];return a.filter(Boolean).join(' · ')}function googleUrl(r){return'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(r.search_query)}
function signalScore(r){return Math.max(r.destination?.score||0,r.executive?.score||0,r.cross_institution?.score||0)}
function scoreLabel(r){const p=[];if(r.destination)p.push(`목적지 ${r.destination.score}`);if(r.executive)p.push(`반복 ${r.executive.score}`);if(r.cross_institution?.is_cross)p.push(`교차 ${r.cross_institution.score||0}`);return p.join(' · ')||'-'}
function pass(r){const d=ds.value,o=ori.value,s=q.value.trim().toLowerCase();if(d==='both'&&r.type!=='both')return false;if(d==='destination'&&!r.destination)return false;if(d==='executive'&&!r.executive)return false;if(d==='consensus'&&!r.cross_institution?.is_cross)return false;if(d==='cross_origin'&&!(r.cross_institution?.is_cross&&(r.cross_institution?.source_count||0)>=2))return false;if(d==='top_official'&&!(r.executive?.top_official_visits>0))return false;if(d==='regional_head'&&!(((r.executive?.mayor_visits||0)+(r.executive?.vice_mayor_visits||0))>0))return false;const origins=r.origins||[r.origin];if(o!=='all'&&!origins.includes(o))return false;return !s||[r.name,r.business?.display,r.address,...origins,...(r.institutions||[]),r.business?.category,r.why].join(' ').toLowerCase().includes(s)}
function institutionCount(r){return Number(r.cross_institution?.institution_count||r.institutions?.length||0)}
function displayName(r){return String(r.business?.display||r.name||'')}
function sortRecords(a){return a.sort((x,y)=>{
  if(sort.value==='visits')return(y.evidence?.visits||0)-(x.evidence?.visits||0)||displayName(x).localeCompare(displayName(y),'ko-KR');
  if(sort.value==='spend')return(y.evidence?.spend||0)-(x.evidence?.spend||0)||displayName(x).localeCompare(displayName(y),'ko-KR');
  if(sort.value==='name')return displayName(x).localeCompare(displayName(y),'ko-KR',{sensitivity:'base'});
  if(sort.value==='institutions')return institutionCount(y)-institutionCount(x)||(y.evidence?.visits||0)-(x.evidence?.visits||0)||displayName(x).localeCompare(displayName(y),'ko-KR');
  if(sort.value==='recent')return String(y.evidence?.date_max||'').localeCompare(String(x.evidence?.date_max||''))||displayName(x).localeCompare(displayName(y),'ko-KR');
  if(sort.value==='consensus')return(y.cross_institution?.score||0)-(x.cross_institution?.score||0)||institutionCount(y)-institutionCount(x);
  if(sort.value==='top_official')return(y.executive?.top_official_visits||0)-(x.executive?.top_official_visits||0)||signalScore(y)-signalScore(x);
  if(sort.value==='regional_head')return((y.executive?.mayor_visits||0)+(y.executive?.vice_mayor_visits||0))-((x.executive?.mayor_visits||0)+(x.executive?.vice_mayor_visits||0))||signalScore(y)-signalScore(x);
  return signalScore(y)-signalScore(x)||(y.evidence?.visits||0)-(x.evidence?.visits||0);
})}
function popupHtml(r){const e=r.evidence||{},roles=(e.roles||[]).slice(0,3).map(x=>`${esc(x.role)} ${x.visits}회`).join(' · ');return`<div class="popup"><h3>${esc(r.business?.display||r.name)}</h3><div class="muted">${esc(r.business?.category||'업종 확인 필요')} · ${esc(r.address||'주소 확인 필요')}</div><div class="why"><b>왜 선정됐나</b><br>${esc(r.why||'-')}</div><b>원자료</b> ${e.visits||0}회 · ${won(e.spend||0)}<br><b>직책</b> ${roles||'-'}<br><a href="${googleUrl(r)}" target="_blank" rel="noopener">Google Maps에서 확인</a></div>`}
function renderEmpty(){detail.innerHTML='<div class="empty-detail"><div><strong>식당을 선택하세요</strong>왼쪽 목록이나 지도 마커를 누르면 업체 정보와 선정 근거를 표시합니다.</div></div>'}
function renderDetail(r){if(!r){renderEmpty();return}const e=r.evidence||{},b=r.business||{},cross=r.cross_institution||{},roles=(e.roles||[]).map(x=>`<div class="role-row"><span><b>${esc(x.role)}</b><br><span style="color:var(--muted)">${x.visits}회 · ${x.people}명</span></span><span>${won(x.spend)}</span></div>`).join(''),pur=(e.purposes||[]).map(x=>`<div class="visit-row"><div class="date">${esc(x.text)}</div><div class="meta">${x.count}회 확인</div></div>`).join(''),vis=(e.recent||[]).map(x=>`<div class="visit-row"><div class="date">${esc(x.date)} ${esc(x.time)}</div><div class="meta">${esc(x.role)} · ${x.people}명 · ${won(x.amount)}<br>${esc(x.purpose)}${x.source?`<br><a href="${esc(x.source)}" target="_blank" rel="noopener">공식 원자료 보기</a>`:''}</div></div>`).join('');detail.innerHTML=`<div class="detail-top"><div><h2>${esc(b.display||r.name)}</h2><div class="detail-category">${esc(b.category||'업종 확인 필요')} · ${esc(sourceLabel(r))}</div></div><div class="detail-score">${esc(scoreLabel(r))}<br>${r.type==='both'?'Destination + Executive':r.type==='destination'?'Destination VIP':'Executive Repeat'}</div></div><div class="why-card"><div class="why-title">Why selected</div><div class="why-text">${esc(r.why||'선정 근거 요약 없음')}</div></div><div class="action-row"><a class="btn primary" href="${googleUrl(r)}" target="_blank" rel="noopener">Google Maps</a>${b.url?`<a class="btn ghost" href="${esc(b.url)}" target="_blank" rel="noopener">업체 정보 출처</a>`:''}</div>${cross.is_cross?`<div class="detail-section"><h3>교차기관 선택</h3><div class="cross-grid">${(cross.by_origin||[]).map(x=>`<div class="cross-row"><span><b>${esc(x.origin)}</b></span><span>${Number(x.visits||0).toLocaleString('ko-KR')}회 · ${shortWon(x.spend||0)}원</span></div>`).join('')}</div><div class="method-note">Consensus ${cross.score||0} · ${cross.institution_count||0}개 기관 · ${cross.source_count||0}개 출처 · ${cross.cohort_count||0}개 계층에서 동일 물리 식당으로 통합되었습니다.</div></div>`:''}<div class="detail-section"><h3>업체 정보</h3><div class="detail-grid"><div class="k">위치 검증</div><div class="v">${esc((r.location_verification||{}).label||'미분류')}</div><div class="k">주소</div><div class="v">${esc(r.address||'확인 필요')}</div><div class="k">전화</div><div class="v">${esc(b.phone||'-')}</div><div class="k">현재 업소</div><div class="v">${esc(b.status||'자동 확인 미실시')}</div><div class="k">업체정보 확인</div><div class="v">${b.verified_at?esc(b.verified_at+(b.verification_confidence?' · '+b.verification_confidence:'')):'별도 검증 기록 없음'}</div><div class="k">평점 정보</div><div class="v">${esc(b.rating||'-')}</div><div class="k">메모</div><div class="v">${esc(b.note||'-')}</div></div></div><div class="detail-section"><h3>업무추진비 원자료</h3><div class="metric-grid"><div class="metric-card"><div class="label">Visits</div><div class="value">${e.visits||0}회</div></div><div class="metric-card"><div class="label">Spend</div><div class="value">${shortWon(e.spend||0)}원</div></div><div class="metric-card"><div class="label">People</div><div class="value">${Number(e.people||0).toLocaleString('ko-KR')}명</div></div><div class="metric-card"><div class="label">Evening</div><div class="value">${pct(e.evening_ratio||0)}</div></div></div><div class="detail-grid" style="margin-top:12px"><div class="k">방문 기간</div><div class="v">${esc(e.date_min||'-')} ~ ${esc(e.date_max||'-')}</div><div class="k">방문 월</div><div class="v">${e.months||0}개월</div><div class="k">가중 1인당</div><div class="v">${won(e.ppc||0)}</div></div></div><div class="detail-section"><h3>어떤 공무원들이 갔나</h3>${roles||'<div class="method-note">원자료 매칭 정보 없음</div>'}</div><div class="detail-section"><h3>주요 집행 목적</h3>${pur||'<div class="method-note">목적 정보 없음</div>'}</div><div class="detail-section"><h3>최근 방문 원자료</h3>${vis||'<div class="method-note">방문내역 없음</div>'}</div><div class="method-note">※ 이 서비스의 점수는 식당의 맛이나 품질을 평가하는 평점이 아닙니다.</div>`}
function badges(r){const a=[];const vg=r.location_verification||{};if(vg.grade)a.push(`<span class="badge ${vg.grade==='A'?'soft':'outline'}" title="A=주소와 좌표 확인 · B=좌표만 확인 · C=원자료 사용처만 확인">위치 ${esc(vg.grade)}</span>`);a.push(r.type==='both'?'<span class="badge solid">Destination + Executive</span>':r.type==='destination'?'<span class="badge outline">Destination VIP</span>':'<span class="badge solid">Executive Repeat</span>');if(r.cross_institution?.is_cross)a.push(`<span class="badge cross">기관 교차 ${r.cross_institution.institution_count}</span>`);if((r.executive?.top_official_visits||0)>0)a.push(`<span class="badge outline">${esc(r.executive.top_role_label||'장·차관급')} ${r.executive.top_official_visits}회</span>`);if((r.executive?.mayor_visits||0)+(r.executive?.vice_mayor_visits||0)>0)a.push(`<span class="badge outline">시장·부시장 ${(r.executive.mayor_visits||0)+(r.executive.vice_mayor_visits||0)}회</span>`);a.push(`<span class="badge soft">${esc(r.business?.category||'업종 확인 필요')}</span>`);return a.join('')}
function cardHtml(r){const e=r.evidence||{},miss=Number.isFinite(r.lat)&&Number.isFinite(r.lon)?'':' · 좌표 미확인';return`<div class="card-head"><div class="card-title">${esc(r.business?.display||r.name)}</div><div class="score" title="맛 평점이 아닌 공개 지출기록 기반 신호 점수입니다. 반복=반복·고위직 사용, 교차=복수 기관 선택, 목적지=관외·목적지 선택">${esc(scoreLabel(r))}</div></div><div class="badge-row">${badges(r)}</div><div class="card-meta">${esc(r.address||'주소 확인 필요')}<br>${esc(sourceLabel(r))}${r.cross_institution?.is_cross?' · 기관 교차 선택':''}${miss}</div><div class="card-metrics"><div class="mini-metric"><div class="mini-label">방문</div><div class="mini-value">${e.visits||0}회</div></div><div class="mini-metric"><div class="mini-label">집행액</div><div class="mini-value">${shortWon(e.spend||0)}원</div></div><div class="mini-metric"><div class="mini-label">저녁</div><div class="mini-value">${pct(e.evening_ratio||0)}</div></div></div>`}
function highlight(){for(const c of list.querySelectorAll('.restaurant-card'))c.classList.toggle('active',c.dataset.key===selected)}
function recordByKey(k){return DATA.find(r=>key(r)===k)}
function geojson(){return{type:'FeatureCollection',features:current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).map(r=>({type:'Feature',geometry:{type:'Point',coordinates:[r.lon,r.lat]},properties:{id:key(r),display:r.business?.display||r.name,address:r.address||'',kind:r.type||'',selected:key(r)===selected?1:0}}))}}
function addLayers(){if(!map.isStyleLoaded())return;['place-labels','places','cluster-count','clusters'].forEach(id=>{if(map.getLayer(id))map.removeLayer(id)});if(map.getSource('places'))map.removeSource('places');map.addSource('places',{type:'geojson',data:geojson(),cluster:true,clusterMaxZoom:14,clusterRadius:42});map.addLayer({id:'clusters',type:'circle',source:'places',filter:['has','point_count'],paint:{'circle-color':'#171717','circle-opacity':.88,'circle-stroke-color':'#fff','circle-stroke-width':2,'circle-radius':['step',['get','point_count'],15,10,19,30,23,80,28]}});map.addLayer({id:'cluster-count',type:'symbol',source:'places',filter:['has','point_count'],layout:{'text-field':['get','point_count_abbreviated'],'text-size':12},paint:{'text-color':'#fff'}});map.addLayer({id:'places',type:'circle',source:'places',filter:['!',['has','point_count']],paint:{'circle-radius':['case',['==',['get','selected'],1],10,6.5],'circle-color':['match',['get','kind'],'executive','#0a0a0a','destination','#fff','both','#737373','#525252'],'circle-stroke-color':'#0a0a0a','circle-stroke-width':['case',['==',['get','selected'],1],4,['==',['get','kind'],'destination'],2.5,2]}});map.addLayer({id:'place-labels',type:'symbol',source:'places',filter:['!',['has','point_count']],minzoom:13.5,layout:{'text-field':['get','display'],'text-size':11,'text-offset':[0,1.25],'text-anchor':'top','text-allow-overlap':false},paint:{'text-color':'#171717','text-halo-color':'#fff','text-halo-width':1.6}});bindInteractions()}
function bindInteractions(){if(bound)return;bound=true;map.on('click','clusters',async e=>{const f=e.features?.[0];if(!f)return;map.easeTo({center:f.geometry.coordinates,zoom:await map.getSource('places').getClusterExpansionZoom(f.properties.cluster_id)})});map.on('mouseenter','places',e=>{map.getCanvas().style.cursor='pointer';const f=e.features?.[0],r=f&&recordByKey(f.properties.id);if(!r)return;if(hoverPopup)hoverPopup.remove();hoverPopup=new maplibregl.Popup({closeButton:false,closeOnClick:false,offset:12}).setLngLat(f.geometry.coordinates).setHTML(`<b>${esc(r.business?.display||r.name)}</b><br><span style="color:#737373;font-size:12px">${esc(r.address||'주소 확인 필요')}</span>`).addTo(map)});map.on('mouseleave','places',()=>{map.getCanvas().style.cursor='';if(hoverPopup){hoverPopup.remove();hoverPopup=null}});map.on('click','places',e=>{const f=e.features?.[0],r=f&&recordByKey(f.properties.id);if(r)selectRecord(r,false,true)})}
function updateMap(fit=false){if(!mapReady||!map.getSource('places'))return;map.getSource('places').setData(geojson());const n=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).length;prog.textContent=`정적 좌표 ${n}/${current.length} · 브라우저 지오코딩 0건`;if(fit)fitMap()}
function fitMap(){const a=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon));if(!a.length)return;const b=new maplibregl.LngLatBounds();a.forEach(r=>b.extend([r.lon,r.lat]));map.fitBounds(b,{padding:{top:90,bottom:40,left:40,right:40},maxZoom:13.3,duration:500})}
function selectRecord(r,move=true,popup=false){selected=key(r);renderDetail(r);highlight();updateMap(false);if(selectedPopup){selectedPopup.remove();selectedPopup=null}if(Number.isFinite(r.lat)&&Number.isFinite(r.lon)){if(move)map.flyTo({center:[r.lon,r.lat],zoom:Math.max(map.getZoom(),15.2),duration:500});if(popup||move)selectedPopup=new maplibregl.Popup({offset:14}).setLngLat([r.lon,r.lat]).setHTML(popupHtml(r)).addTo(map)}else prog.textContent='이 업소는 정적 좌표가 아직 없습니다. 주소 보강 후 자동 반영됩니다.'}
function renderList(fit=true){current=sortRecords(DATA.filter(pass));const mapped=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).length;const unmapped=current.length-mapped;sum.innerHTML=`목록 <strong>${current.length}</strong>곳 · 지도표시 <strong>${mapped}</strong>곳${unmapped?` · 위치미확인 <strong>${unmapped}</strong>곳`:''}`;list.innerHTML='';for(const r of current){const c=document.createElement('article');c.className='restaurant-card'+(key(r)===selected?' active':'');c.dataset.key=key(r);c.innerHTML=cardHtml(r);c.onclick=()=>selectRecord(r,true,true);list.appendChild(c)}if(!current.length)list.innerHTML='<div style="padding:28px 16px;text-align:center;color:var(--muted)">조건에 맞는 식당이 없습니다.</div>';updateMap(fit)}
function updateStats(){const visits=DATA.reduce((s,r)=>s+Number(r.evidence?.visits||0),0),spend=DATA.reduce((s,r)=>s+Number(r.evidence?.spend||0),0),exec=DATA.filter(r=>!!r.executive).length;$('statRestaurants').textContent=(STATS.total||DATA.length).toLocaleString('ko-KR');$('statVisits').textContent=visits.toLocaleString('ko-KR');$('statSpend').textContent=shortWon(spend)+'원';$('statExec').textContent=exec.toLocaleString('ko-KR')}
function clearSelection(){
  selected=null;
  if(selectedPopup){selectedPopup.remove();selectedPopup=null}
  if(hoverPopup){hoverPopup.remove();hoverPopup=null}
  renderEmpty();
}
function resetFilters(){ds.value='all';ori.value='all';q.value='';sort.value='signal';clearSelection();renderList(true)}
function switchStyle(){styleMode=styleMode==='positron'?'liberty':'positron';mapReady=false;map.setStyle(STYLES[styleMode]);map.once('style.load',()=>{mapReady=true;addLayers();updateMap(false)})}
map.on('load',()=>{mapReady=true;addLayers();updateMap(true)});ds.onchange=ori.onchange=()=>{clearSelection();renderList(true)};q.oninput=()=>{clearSelection();renderList(true)};sort.onchange=()=>renderList(false);$('reset').onclick=resetFilters;$('fit').onclick=fitMap;
const styleBtn=document.createElement('button');styleBtn.className='map-btn';styleBtn.textContent='지도톤';styleBtn.onclick=switchStyle;document.querySelector('.map-actions')?.prepend(styleBtn);
updateStats();renderList(false);prog.textContent=`정적 좌표 ${STATS.coordinates||DATA.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).length}/${DATA.length} · 첫 접속 추가 지오코딩 없음`;


/* Stable marker renderer */
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


/* UI enhancements */
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
