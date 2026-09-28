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
    let rendered=[];
    let renderedAll=[];
    try { rendered=map.queryRenderedFeatures(undefined,{layers:['clusters','places']}); } catch (e) {}
    try { renderedAll=map.queryRenderedFeatures(); } catch (e) {}
    let sourceFeatures=[];
    try { sourceFeatures=source ? map.querySourceFeatures('places') : []; } catch (e) {}
    return {
      current: current.length,
      geojsonFeatures: geojson().features.length,
      source: !!source,
      sourceLoaded: source ? map.isSourceLoaded('places') : false,
      layers: Object.fromEntries(layerIds.map(id=>[id,!!map.getLayer(id)])),
      rendered: rendered.length,
      renderedAll: renderedAll.length,
      renderedLayerCounts: renderedAll.reduce((acc,f)=>{const id=f.layer?.id||'unknown';acc[id]=(acc[id]||0)+1;return acc;},{}),
      sourceFeatures: sourceFeatures.length,
      width: rect.width,
      height: rect.height,
      zoom: map.getZoom(),
      center: [map.getCenter().lng,map.getCenter().lat]
    };
  })()`);
  if (snapshot?.sourceLoaded && snapshot?.rendered > 0) break;
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
if (snapshot.rendered < 1) {
  throw new Error('zero rendered restaurant markers');
}

ws.close();
