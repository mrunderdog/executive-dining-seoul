#!/usr/bin/env node
// Run against the built site in a browser started with --disable-webgl.
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let target;
for (let attempt = 0; attempt < 90; attempt++) {
  try {
    const tabs = await (await fetch('http://127.0.0.1:9222/json')).json();
    target = tabs.find(tab => tab.type === 'page' && tab.webSocketDebuggerUrl);
    if (target) break;
  } catch (_error) {}
  await sleep(200);
}
if (!target) throw new Error('Chromium debug target unavailable');

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, {once: true});
  ws.addEventListener('error', reject, {once: true});
});
let sequence = 0;
const pending = new Map();
const uncaught = [];
ws.addEventListener('message', event => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const {resolve, reject} = pending.get(message.id);
    pending.delete(message.id);
    message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result);
  }
  if (message.method === 'Runtime.exceptionThrown') {
    uncaught.push(message.params?.exceptionDetails?.text || 'Uncaught exception');
  }
});
function cdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, {resolve, reject});
    ws.send(JSON.stringify({id, method, params}));
  });
}
async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result?.value;
}
function assert(condition, message) {
  if (!condition) throw new Error(message);
}

await cdp('Runtime.enable');
let baseline;
for (let attempt = 0; attempt < 90; attempt++) {
  baseline = await evaluate(`(() => ({
    records: typeof DATA !== 'undefined' ? DATA.length : 0,
    cards: document.querySelectorAll('.restaurant-card').length,
    mapUnavailable: typeof map !== 'undefined' && map === null,
    notice: !!document.querySelector('#map .map-fallback-message[role="status"]'),
    fitDisabled: !!document.querySelector('#fit:disabled'),
    stats: document.querySelector('#statRestaurants')?.textContent
  }))()`);
  if (baseline?.records > 0 && baseline?.cards === baseline.records) break;
  await sleep(200);
}
console.log('NO_WEBGL_BASELINE', JSON.stringify(baseline));
assert(baseline?.records > 0 && baseline.cards === baseline.records, 'Restaurant list failed to initialize');
assert(baseline.mapUnavailable && baseline.notice && baseline.fitDisabled, 'Accessible map fallback missing');
assert(baseline.stats !== '-', 'Published metrics stayed in loading state');

const search = await evaluate(`(() => {
  q.value='광화문';
  q.dispatchEvent(new Event('input',{bubbles:true}));
  return {results:current.length,cards:document.querySelectorAll('.restaurant-card').length};
})()`);
console.log('NO_WEBGL_SEARCH', JSON.stringify(search));
assert(search.results > 0 && search.results < baseline.records && search.results === search.cards,
  'Search results failed with map unavailable');

const selection = await evaluate(`(() => {
  document.querySelector('.restaurant-card').click();
  return {
    selected,
    detail:detail.querySelector('h2')?.textContent,
    mapLink:detail.querySelector('a[href*="google.com/maps"]')?.href,
    deepLink:new URL(location.href).searchParams.get('restaurant')
  };
})()`);
console.log('NO_WEBGL_DETAIL', JSON.stringify(selection));
assert(selection.selected && selection.detail && selection.deepLink === selection.selected,
  'Restaurant detail/deep link failed with map unavailable');
assert(selection.mapLink?.startsWith('https://www.google.com/maps/'), 'External map fallback link missing');

const reset = await evaluate(`(() => {
  document.querySelector('.detail-drawer-close')?.click();
  document.querySelector('#reset').click();
  return {
    cards:document.querySelectorAll('.restaurant-card').length,
    selected,
    query:q.value,
    fallback:!!document.querySelector('#map .map-fallback-message')
  };
})()`);
console.log('NO_WEBGL_RESET', JSON.stringify(reset));
assert(reset.cards === baseline.records && reset.selected === null && reset.query === '' && reset.fallback,
  'List reset failed with map unavailable');
assert(!uncaught.length, 'Uncaught browser exceptions: ' + uncaught.join('; '));
ws.close();
console.log('NO_WEBGL_SMOKE PASS');
