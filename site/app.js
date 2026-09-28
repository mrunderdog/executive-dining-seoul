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
function meterDistance(a,b){
  const lat=(Number(a.lat)+Number(b.lat))*Math.PI/360;
  const dy=(Number(a.lat)-Number(b.lat))*111320;
  const dx=(Number(a.lon)-Number(b.lon))*111320*Math.cos(lat);
  return Math.hypot(dx,dy);
}
function buildDisplayCoordinateIndex(records,thresholdMeters=8){
  const pts=records.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon));
  const parent=pts.map((_,i)=>i);
  const find=i=>{while(parent[i]!==i){parent[i]=parent[parent[i]];i=parent[i]}return i};
  const union=(a,b)=>{a=find(a);b=find(b);if(a!==b)parent[b]=a};
  for(let i=0;i<pts.length;i++){
    for(let j=i+1;j<pts.length;j++){
      if(Math.abs(pts[i].lat-pts[j].lat)>.00015||Math.abs(pts[i].lon-pts[j].lon)>.00018)continue;
      if(meterDistance(pts[i],pts[j])<=thresholdMeters)union(i,j);
    }
  }
  const groups=new Map();
  pts.forEach((r,i)=>{const root=find(i);if(!groups.has(root))groups.set(root,[]);groups.get(root).push(r)});
  const out=new Map();
  let collisionGroups=0,collisionRecords=0;
  for(const group of groups.values()){
    if(group.length===1){const r=group[0];out.set(key(r),{lon:r.lon,lat:r.lat,offset:false,groupSize:1});continue}
    collisionGroups++;collisionRecords+=group.length;
    const ordered=[...group].sort((a,b)=>key(a).localeCompare(key(b),'ko-KR'));
    const n=ordered.length;
    const radius=Math.min(58,Math.max(20,20+6*(n-2)));
    const centerLat=ordered.reduce((s,r)=>s+r.lat,0)/n;
    const centerLon=ordered.reduce((s,r)=>s+r.lon,0)/n;
    ordered.forEach((r,i)=>{
      const angle=-Math.PI/2+(Math.PI*2*i/n);
      const north=Math.cos(angle)*radius;
      const east=Math.sin(angle)*radius;
      out.set(key(r),{lon:centerLon+east/(111320*Math.cos(centerLat*Math.PI/180)),lat:centerLat+north/111320,offset:true,groupSize:n});
    });
  }
  return {coordinates:out,collisionGroups,collisionRecords};
}
const DISPLAY_LAYOUT=buildDisplayCoordinateIndex(DATA);
function mapCoordinate(r){const p=DISPLAY_LAYOUT.coordinates.get(key(r));return p?[p.lon,p.lat]:[r.lon,r.lat]}
function markerWasOffset(r){return !!DISPLAY_LAYOUT.coordinates.get(key(r))?.offset}
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
function geojson(){return{type:'FeatureCollection',features:current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).map(r=>({type:'Feature',geometry:{type:'Point',coordinates:mapCoordinate(r)},properties:{id:key(r),display:r.business?.display||r.name,address:r.address||'',kind:r.type||'',selected:key(r)===selected?1:0,offset:markerWasOffset(r)?1:0}}))}}
function addLayers(){
  if(!map.isStyleLoaded())return;
  ['place-labels','places','place-halo','place-hitbox','cluster-count','clusters'].forEach(id=>{
    if(map.getLayer(id))map.removeLayer(id);
  });
  if(map.getSource('places'))map.removeSource('places');
  map.addSource('places',{
    type:'geojson',
    data:geojson()
  });
  // Soft paper halo keeps colored markers legible on both basemap tones.
  map.addLayer({
    id:'place-halo',
    type:'circle',
    source:'places',
    paint:{
      'circle-radius':['case',['==',['get','selected'],1],12,8],
      'circle-color':'#f9f5f2',
      'circle-opacity':['case',['==',['get','selected'],1],1,.9]
    }
  });
  // Invisible but generous hit target so touch/click does not depend on the visible dot size.
  map.addLayer({
    id:'place-hitbox',
    type:'circle',
    source:'places',
    paint:{
      'circle-radius':['case',['==',['get','selected'],1],18,14],
      'circle-color':'rgba(0,0,0,0.001)',
      'circle-stroke-width':0
    }
  });
  map.addLayer({
    id:'places',
    type:'circle',
    source:'places',
    paint:{
      'circle-radius':['case',['==',['get','selected'],1],9,5.5],
      'circle-color':['match',['get','kind'],
        'executive','#ac4f98',
        'destination','#f4ed36',
        'both','#c94245',
        '#61609a'
      ],
      'circle-opacity':['case',['==',['get','selected'],1],1,.94],
      'circle-stroke-color':'#1a1a1a',
      'circle-stroke-width':['case',['==',['get','selected'],1],2.6,1.15]
    }
  });
  map.addLayer({
    id:'place-labels',
    type:'symbol',
    source:'places',
    minzoom:13.5,
    layout:{
      'text-field':['get','display'],
      'text-size':11,
      'text-offset':[0,1.25],
      'text-anchor':'top',
      'text-allow-overlap':false
    },
    paint:{'text-color':'#171717','text-halo-color':'#fff','text-halo-width':1.6}
  });
  bindInteractions();
}
function bindInteractions(){
  if(bound)return;
  bound=true;
  map.on('mouseenter','place-hitbox',e=>{
    map.getCanvas().style.cursor='pointer';
    const f=e.features?.[0],r=f&&recordByKey(f.properties.id);
    if(!r)return;
    if(hoverPopup)hoverPopup.remove();
    hoverPopup=new maplibregl.Popup({closeButton:false,closeOnClick:false,offset:12})
      .setLngLat(f.geometry.coordinates)
      .setHTML(`<b>${esc(r.business?.display||r.name)}</b><br><span style="color:#61609a;font-size:12px">${esc(r.address||'주소 확인 필요')}</span>`)
      .addTo(map);
  });
  map.on('mouseleave','place-hitbox',()=>{
    map.getCanvas().style.cursor='';
    if(hoverPopup){hoverPopup.remove();hoverPopup=null}
  });
  map.on('click','place-hitbox',e=>{
    const f=e.features?.[0],r=f&&recordByKey(f.properties.id);
    if(!r)return;
    if(hoverPopup){hoverPopup.remove();hoverPopup=null}
    // Center/zoom before the detail drawer opens so the selected marker stays visible.
    selectRecord(r,true,true);
  });
}
function updateMap(fit=false){
  if(!mapReady||!map.isStyleLoaded())return;
  if(!map.getSource('places'))addLayers();
  const source=map.getSource('places');
  if(source)source.setData(geojson());
  const n=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).length;
  const missing=current.length-n;
  prog.textContent=`지도 표시 ${n}/${current.length}곳${missing?` · 좌표 보강 필요 ${missing}곳`:''} · 접속 시 지오코딩 0건`;
  if(fit)fitMap();
}
function fitMap(){const a=current.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon));if(!a.length)return;const b=new maplibregl.LngLatBounds();a.forEach(r=>b.extend([r.lon,r.lat]));map.fitBounds(b,{padding:{top:90,bottom:40,left:40,right:40},maxZoom:13.3,duration:500})}
function selectRecord(r,move=true,popup=false){selected=key(r);renderDetail(r);highlight();updateMap(false);if(selectedPopup){selectedPopup.remove();selectedPopup=null}if(Number.isFinite(r.lat)&&Number.isFinite(r.lon)){const point=mapCoordinate(r);if(move)map.flyTo({center:point,zoom:Math.max(map.getZoom(),15.2),duration:500});if(popup||move)selectedPopup=new maplibregl.Popup({offset:14}).setLngLat(point).setHTML(popupHtml(r)).addTo(map)}else prog.textContent='이 업소는 정적 좌표가 아직 없습니다. 주소 보강 후 자동 반영됩니다.'}
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


/* Restaurant lookup: global existence search, independent from Explore filters. */
(function(){
  const openBtn=$('restaurantLookupBtn'),backdrop=$('restaurantLookupBackdrop'),closeBtn=$('restaurantLookupClose');
  const input=$('restaurantLookupInput'),results=$('restaurantLookupResults'),count=$('restaurantLookupCount');
  if(!openBtn||!backdrop||!closeBtn||!input||!results||!count)return;
  function normalizeLookup(v){return String(v||'').normalize('NFKC').toLowerCase().replace(/[\\s\\-_.·,()\\[\\]{}'\"]/g,'')}
  function namesFor(r){return [r.name,r.business?.display,...(r.aliases||[]),...(r.business?.aliases||[])].filter(Boolean)}
  function matchLookup(r,query){
    const qn=normalizeLookup(query);if(!qn)return null;
    const normalized=namesFor(r).map(normalizeLookup);
    let rank=0,label='';
    if(normalized.some(v=>v===qn)){rank=400;label='정확 일치'}
    else if(normalized.some(v=>v.startsWith(qn))){rank=320;label='이름 앞부분'}
    else if(normalized.some(v=>v.includes(qn))){rank=260;label='이름 포함'}
    else{
      const meta=normalizeLookup([r.address,r.business?.category,sourceLabel(r),...(r.institutions||[])].filter(Boolean).join(' '));
      if(meta.includes(qn)){rank=140;label='주소·업종·기관'}
    }
    return rank?{r,rank,label}:null;
  }
  function renderLookup(){
    const raw=input.value.trim(),qn=normalizeLookup(raw);
    if(!qn){
      count.textContent='식당명을 입력하세요';
      results.innerHTML='<div class="restaurant-lookup-empty">알고 있는 식당 이름을 입력하면 현재 수집 데이터 전체에서 찾습니다.</div>';
      return;
    }
    const matches=DATA.map(r=>matchLookup(r,raw)).filter(Boolean).sort((a,b)=>b.rank-a.rank||signalScore(b.r)-signalScore(a.r)||(b.r.evidence?.visits||0)-(a.r.evidence?.visits||0)||displayName(a.r).localeCompare(displayName(b.r),'ko-KR'));
    count.textContent=matches.length?(matches.length.toLocaleString('ko-KR')+'개 결과 · 상위 '+Math.min(matches.length,10)+'개 표시'):'현재 수집 데이터에는 없음';
    if(!matches.length){
      results.innerHTML='<div class="restaurant-lookup-empty"><strong>“'+esc(raw)+'”</strong>과 일치하는 식당을 찾지 못했습니다.<br><span>띄어쓰기나 지점명을 줄여 다시 검색해보세요.</span></div>';
      return;
    }
    results.innerHTML=matches.slice(0,10).map(({r,label})=>'<button type="button" class="restaurant-lookup-result" data-key="'+esc(key(r))+'"><span class="restaurant-lookup-name">'+esc(displayName(r))+'</span><span class="restaurant-lookup-match">'+esc(label)+'</span><span class="restaurant-lookup-address">'+esc(r.address||'주소 확인 필요')+'</span><span class="restaurant-lookup-source">'+esc(sourceLabel(r))+' · '+Number(r.evidence?.visits||0).toLocaleString('ko-KR')+'회</span></button>').join('');
    results.querySelectorAll('.restaurant-lookup-result').forEach(btn=>{btn.onclick=()=>{
      const r=recordByKey(btn.dataset.key);if(!r)return;
      ds.value='all';ori.value='all';q.value=displayName(r);
      clearSelection();renderList(false);selectRecord(r,true,true);closeLookup();
      requestAnimationFrame(()=>list.querySelector('.restaurant-card.active')?.scrollIntoView({block:'nearest',behavior:'smooth'}));
    }});
  }
  function openLookup(){backdrop.hidden=false;requestAnimationFrame(()=>backdrop.classList.add('is-open'));input.value='';renderLookup();setTimeout(()=>input.focus(),20)}
  function closeLookup(){backdrop.classList.remove('is-open');setTimeout(()=>{backdrop.hidden=true},120)}
  openBtn.onclick=openLookup;closeBtn.onclick=closeLookup;
  backdrop.addEventListener('click',e=>{if(e.target===backdrop)closeLookup()});
  input.addEventListener('input',renderLookup);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!backdrop.hidden)closeLookup()});
})();
/* Stable map layer lifecycle */
// Keep a single MapLibre source/layer renderer. Basemap style swaps destroy custom
// sources/layers, so restore them only after style.load.
(function(){
  const styleButton=[...document.querySelectorAll('.map-actions .map-btn')]
    .find(btn=>btn.textContent.trim().startsWith('지도톤'));
  let styleSwitchSeq=0;

  function updateStyleButton(loading=false){
    if(!styleButton)return;
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

  switchStyle=function(){
    const previousMode=styleMode;
    const nextMode=styleMode==='positron'?'liberty':'positron';
    const seq=++styleSwitchSeq;
    if(hoverPopup){hoverPopup.remove();hoverPopup=null}
    if(styleButton){
      styleButton.disabled=true;
      updateStyleButton(true);
    }

    let finished=false;
    let recoveryStarted=false;
    const finish=()=>{
      if(finished||seq!==styleSwitchSeq)return;
      finished=true;
      mapReady=true;
      addLayers();
      updateMap(false);
      updateStyleButton(false);
      if(styleButton)styleButton.disabled=false;
    };
    const recover=()=>{
      if(finished||seq!==styleSwitchSeq)return;
      if(map.isStyleLoaded()){finish();return}
      if(recoveryStarted){
        // Do not strand the control if both external styles are unavailable.
        styleMode=previousMode;
        updateStyleButton(false);
        if(styleButton)styleButton.disabled=false;
        return;
      }
      recoveryStarted=true;
      styleMode=previousMode;
      map.setStyle(STYLES[previousMode]);
      setTimeout(recover,3500);
    };

    map.once('style.load',finish);
    mapReady=false;
    styleMode=nextMode;
    map.setStyle(STYLES[nextMode]);
    setTimeout(recover,5000);
  };

  if(styleButton){
    styleButton.onclick=event=>{
      event.preventDefault();
      if(styleButton.disabled)return;
      switchStyle();
    };
    updateStyleButton(false);
  }

  // Rebuild the custom source/layers after any style reload, including external
  // calls not initiated by the toggle above.
  map.on('style.load',()=>{
    if(!mapReady)return;
    if(!map.getSource('places')){
      addLayers();
      updateMap(false);
    }
  });
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
