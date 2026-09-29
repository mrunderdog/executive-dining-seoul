#!/usr/bin/env node
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function waitForTarget() {
  let lastError = null;
  for (let i = 0; i < 80; i++) {
    try {
      const targets = await (await fetch('http://127.0.0.1:9222/json')).json();
      const page = targets.find(x => x.type === 'page');
      if (page?.webSocketDebuggerUrl) return page;
    } catch (err) {
      lastError = err;
    }
    await sleep(250);
  }
  throw new Error('Chrome DevTools target not ready: ' + (lastError || 'timeout'));
}

const target = await waitForTarget();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, {once:true});
  ws.addEventListener('error', reject, {once:true});
});

let seq = 0;
const pending = new Map();
const browserErrors = [];

ws.addEventListener('message', event => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const {resolve, reject} = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(JSON.stringify(msg.error)));
    else resolve(msg.result);
    return;
  }
  if (msg.method === 'Runtime.exceptionThrown') {
    browserErrors.push('EXCEPTION ' + JSON.stringify(msg.params?.exceptionDetails || {}));
  }
  if (msg.method === 'Log.entryAdded') {
    const entry = msg.params?.entry;
    if (entry && ['error','warning'].includes(entry.level)) {
      browserErrors.push('LOG ' + entry.level + ' ' + entry.text);
    }
  }
});

function cdp(method, params={}) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, {resolve, reject});
    ws.send(JSON.stringify({id, method, params}));
  });
}

async function evaluate(expression) {
  const res = await cdp('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true
  });
  if (res.exceptionDetails) {
    throw new Error('evaluate failed: ' + JSON.stringify(res.exceptionDetails));
  }
  return res.result?.value;
}

await cdp('Runtime.enable');
await cdp('Log.enable');
await cdp('Page.enable');

let ready = false;
for (let i = 0; i < 80; i++) {
  ready = await evaluate(`typeof map !== 'undefined' && typeof current !== 'undefined' && map.loaded() && map.isStyleLoaded()`);
  if (ready) break;
  await sleep(250);
}
if (!ready) {
  console.error(browserErrors.join('\n'));
  throw new Error('Map never reached loaded/style-loaded state');
}

let snapshot = null;
for (let i = 0; i < 60; i++) {
  snapshot = await evaluate(`(() => {
    const layerIds=['clusters','cluster-count','place-hitbox','places','place-labels'];
    const source=map.getSource('places');
    const rect=map.getContainer().getBoundingClientRect();
    let renderedAll=[];
    try { renderedAll=map.queryRenderedFeatures(); } catch (e) {}
    let sourceFeatures=[];
    try { sourceFeatures=source ? map.querySourceFeatures('places') : []; } catch (e) {}
    return {
      current: current.length,
      geojsonFeatures: geojson().features.length,
      source: !!source,
      sourceLoaded: source ? map.isSourceLoaded('places') : false,
      layers: Object.fromEntries(layerIds.map(id=>[id,!!map.getLayer(id)])),
      renderedAll: renderedAll.length,
      renderedLayerCounts: renderedAll.reduce((acc,f)=>{const id=f.layer?.id||'unknown';acc[id]=(acc[id]||0)+1;return acc;},{}),
      sourceFeatures: sourceFeatures.length,
      width: rect.width,
      height: rect.height,
      zoom: map.getZoom(),
      center: [map.getCenter().lng,map.getCenter().lat],
      collisionGroups: typeof DISPLAY_LAYOUT!=='undefined' ? DISPLAY_LAYOUT.collisionGroups : -1,
      collisionRecords: typeof DISPLAY_LAYOUT!=='undefined' ? DISPLAY_LAYOUT.collisionRecords : -1,
      lookupReady: !!document.querySelector('.filters #restaurantLookupBtn') && !document.querySelector('.cross-showcase #restaurantLookupBtn') && !!document.getElementById('restaurantLookupInput')
    };
  })()`);
  if (snapshot?.sourceLoaded && ((snapshot?.renderedLayerCounts?.places||0)+(snapshot?.renderedLayerCounts?.clusters||0)) > 0) break;
  await sleep(250);
}

console.log('MAP_SMOKE', JSON.stringify(snapshot));
if (browserErrors.length) console.log('BROWSER_MESSAGES\n' + browserErrors.join('\n'));

if (!snapshot) throw new Error('No map snapshot');
if (snapshot.current < 1 || snapshot.geojsonFeatures < 1) throw new Error('Published map data is empty');
if (!snapshot.source) throw new Error('places source missing');
for (const id of ['place-hitbox','places']) {
  if (!snapshot.layers?.[id]) throw new Error('required map layer missing: ' + id);
}
if (snapshot.width < 400 || snapshot.height < 300) {
  throw new Error('map container collapsed: ' + snapshot.width + 'x' + snapshot.height);
}
const renderedMarkers=(snapshot.renderedLayerCounts?.places||0)+(snapshot.renderedLayerCounts?.clusters||0);
if (renderedMarkers < 1) {
  throw new Error('zero rendered restaurant markers/clusters');
}
if (snapshot.collisionGroups < 1 || snapshot.collisionRecords < 2) {
  throw new Error('collision-safe display layout did not detect overlapping markers');
}
if (!snapshot.lookupReady) {
  throw new Error('restaurant lookup UI is missing');
}

const pointerState=await evaluate(`(() => {
  const backdrop=document.getElementById('restaurantLookupBackdrop');
  const rect=map.getContainer().getBoundingClientRect();
  const x=rect.left+rect.width/2,y=rect.top+rect.height/2;
  const top=document.elementFromPoint(x,y);
  return {
    lookupHidden: backdrop?.hidden,
    lookupDisplay: backdrop ? getComputedStyle(backdrop).display : null,
    lookupPointer: backdrop ? getComputedStyle(backdrop).pointerEvents : null,
    topTag: top?.tagName||'',
    topClass: top?.className?.toString?.()||'',
    scrollZoom: map.scrollZoom.isEnabled(),
    dragPan: map.dragPan.isEnabled(),
    zoom: map.getZoom(),
    x,y
  };
})()`);
console.log('POINTER_STATE',JSON.stringify(pointerState));
if (!pointerState.lookupHidden || pointerState.lookupDisplay !== 'none' || pointerState.lookupPointer !== 'none') {
  throw new Error('closed restaurant lookup overlay is intercepting pointer events');
}
if (!pointerState.scrollZoom || !pointerState.dragPan) {
  throw new Error('MapLibre zoom/pan interactions are disabled');
}

const zoomBefore=pointerState.zoom;
await cdp('Input.dispatchMouseEvent',{type:'mouseWheel',x:pointerState.x,y:pointerState.y,deltaX:0,deltaY:-420});
await sleep(700);
const zoomAfter=await evaluate('map.getZoom()');
console.log('ZOOM_SMOKE',JSON.stringify({before:zoomBefore,after:zoomAfter}));
if (!(zoomAfter > zoomBefore + 0.05)) {
  throw new Error('mouse wheel did not zoom the map');
}

const markerTarget=await evaluate(`(() => {
  const rect=map.getContainer().getBoundingClientRect();
  const all=map.queryRenderedFeatures();
  const f=all.find(x=>x.layer?.id==='places');
  if(!f)return null;
  const p=map.project(f.geometry.coordinates);
  return {id:String(f.properties.id),x:rect.left+p.x,y:rect.top+p.y};
})()`);
if(!markerTarget) throw new Error('no rendered marker available for click smoke');
await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:markerTarget.x,y:markerTarget.y,button:'left',clickCount:1});
await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:markerTarget.x,y:markerTarget.y,button:'left',clickCount:1});
await sleep(500);
const selectedAfterClick=await evaluate('selected');
console.log('MARKER_CLICK_SMOKE',JSON.stringify({target:markerTarget.id,selected:selectedAfterClick}));
if (!selectedAfterClick) {
  throw new Error('marker click did not select a restaurant');
}

const lookupCheck=await evaluate(`(() => {
  const btn=document.getElementById('restaurantLookupBtn');
  btn.click();
  const input=document.getElementById('restaurantLookupInput');
  input.value='싱카이';
  input.dispatchEvent(new Event('input',{bubbles:true}));
  const names=[...document.querySelectorAll('.restaurant-lookup-result .restaurant-lookup-name')].map(x=>x.textContent.trim());
  const target=DATA.filter(r=>String(r.name||'').includes('싱카이')||String(r.business?.display||'').includes('싱카이'));
  const coords=target.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lon)).map(r=>mapCoordinate(r).map(v=>Number(v).toFixed(7)).join(','));
  return {names, targetCount:target.length, uniqueTargetCoords:new Set(coords).size};
})()`);
console.log('LOOKUP_SMOKE',JSON.stringify(lookupCheck));
if (!lookupCheck.names.some(n=>n.includes('싱카이'))) {
  throw new Error('restaurant lookup failed to return 싱카이');
}
if (lookupCheck.targetCount > 1 && lookupCheck.uniqueTargetCoords < 2) {
  throw new Error('overlapping 싱카이 markers were not separated');
}

const lookupReturnCheck=await evaluate(`(() => {
  const first=document.querySelector('.restaurant-lookup-result');
  if(!first)return {error:'lookup result missing'};
  first.click();
  return {
    query:q.value,
    mode:ds.value,
    origin:ori.value,
    sort:sort.value,
    current:current.length,
    total:DATA.length,
    selected
  };
})()`);
console.log('LOOKUP_RETURN_SMOKE',JSON.stringify(lookupReturnCheck));
if (lookupReturnCheck.error || lookupReturnCheck.query!=='' || lookupReturnCheck.mode!=='all' || lookupReturnCheck.origin!=='all' || lookupReturnCheck.current!==lookupReturnCheck.total || !lookupReturnCheck.selected) {
  throw new Error('lookup selection did not return to the full restaurant set');
}

const crossResetCheck=await evaluate(`(() => {
  document.getElementById('restaurantLookupClose')?.click();
  const all=document.querySelector('#crossShowcase .cross-all-btn');
  if(!all)return {error:'cross all button missing'};
  const initialLabel=all.textContent.trim();
  all.click();
  const during={mode:ds.value,count:current.length,label:all.textContent.trim()};
  all.click();
  const after={mode:ds.value,origin:ori.value,query:q.value,sort:sort.value,count:current.length,total:DATA.length,label:all.textContent.trim()};
  return {initialLabel,during,after};
})()`);
console.log('CROSS_RESET_SMOKE',JSON.stringify(crossResetCheck));
if (crossResetCheck.error || crossResetCheck.during.mode!=='cross_origin' || crossResetCheck.during.label!=='전체 식당 보기') {
  throw new Error('cross-origin toggle did not switch into all-restaurants return state');
}
if (crossResetCheck.after.mode!=='all' || crossResetCheck.after.origin!=='all' || crossResetCheck.after.query!=='' || crossResetCheck.after.count!==crossResetCheck.after.total || !crossResetCheck.after.label.startsWith('기관교차 전체 ')) {
  throw new Error('cross-origin toggle did not restore the full dataset');
}



await cdp('Emulation.setDeviceMetricsOverride',{width:504,height:981,deviceScaleFactor:1,mobile:false});
await sleep(500);
await evaluate(`(() => { try{map.resize()}catch(e){} document.querySelector('.sidebar')?.scrollIntoView({block:'start'}); return true; })()`);
await sleep(300);

const narrowUi=await evaluate(`(() => {
  const fits=el=>!el || el.scrollWidth<=el.clientWidth+2;
  const rect=el=>el?.getBoundingClientRect();
  const filters=document.querySelector('.filters');
  const summary=document.querySelector('.summary');
  const sidebar=document.querySelector('.sidebar');
  const fields=[...document.querySelectorAll('.filters .field')];
  const controls=[...document.querySelectorAll('.filters .control')];
  const labelsAbove=fields.every(f=>{
    const l=f.querySelector('label'),c=f.querySelector('.control');
    if(!l||!c)return true;
    return rect(c).top>=rect(l).bottom-1;
  });
  const controlFits=controls.every(c=>{
    const cr=rect(c),fr=rect(c.closest('.filters'));
    return cr.left>=fr.left-1 && cr.right<=fr.right+1;
  });
  const summaryButtons=[...summary.querySelectorAll('.score-help,.explorer-toggle')];
  const buttonHeights=summaryButtons.map(b=>Math.round(rect(b).height));
  const badges=[...document.querySelectorAll('.restaurant-card .badge')].slice(0,20);
  const metrics=document.querySelector('.restaurant-card .card-metrics');
  const metricCols=metrics?getComputedStyle(metrics).gridTemplateColumns.split(' ').filter(Boolean).length:0;
  return {
    viewport:innerWidth,
    bodyOverflow:document.documentElement.scrollWidth-innerWidth,
    sidebarOverflow:sidebar.scrollWidth-sidebar.clientWidth,
    filtersFit:fits(filters),
    summaryFit:fits(summary),
    labelsAbove,
    controlFits,
    buttonHeights,
    buttonsNowrap:summaryButtons.every(b=>getComputedStyle(b).whiteSpace==='nowrap'),
    badgesNowrap:badges.every(b=>getComputedStyle(b).whiteSpace==='nowrap'),
    metricCols
  };
})()`);
console.log('NARROW_UI_SMOKE',JSON.stringify(narrowUi));
if (narrowUi.viewport!==504 || narrowUi.bodyOverflow>2 || narrowUi.sidebarOverflow>2 || !narrowUi.filtersFit || !narrowUi.summaryFit || !narrowUi.labelsAbove || !narrowUi.controlFits) {
  throw new Error('narrow explorer layout overflows or fields are misaligned');
}
if (narrowUi.buttonHeights.some(h=>h>30) || !narrowUi.buttonsNowrap || !narrowUi.badgesNowrap || narrowUi.metricCols!==3) {
  throw new Error('narrow explorer buttons/badges/metrics are visually unstable');
}

ws.close();
