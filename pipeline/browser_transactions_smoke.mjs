#!/usr/bin/env node
/* Exercise the newly deployed official transaction explorer in headless Chrome. */
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
let target;
for (let i = 0; i < 50; i++) {
  try {
    const targets = await (await fetch('http://127.0.0.1:9222/json')).json();
    target = targets.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
    if (target) break;
  } catch (_) { /* Chrome may still be attaching. */ }
  await delay(250);
}
if (!target) throw new Error('No Chrome CDP page');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, {once:true});
  ws.addEventListener('error', reject, {once:true});
});
let serial = 0;
const pending = new Map();
const exceptions = [];
ws.addEventListener('message', event => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const {resolve,reject} = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(JSON.stringify(msg.error)));
    else resolve(msg.result);
  } else if (msg.method === 'Runtime.exceptionThrown') {
    exceptions.push(JSON.stringify(msg.params?.exceptionDetails || {}));
  }
});
function call(method, params={}) {
  return new Promise((resolve,reject) => {
    const id = ++serial;
    pending.set(id, {resolve,reject});
    ws.send(JSON.stringify({id,method,params}));
  });
}
async function evalOnPage(expression) {
  const result = await call('Runtime.evaluate', {expression, awaitPromise:true, returnByValue:true});
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result?.value;
}
await call('Page.enable');
await call('Runtime.enable');
await call('Page.navigate', {url:'http://127.0.0.1:8765/transactions.html'});
let initial;
for (let i = 0; i < 60; i++) {
  initial = await evalOnPage(`(() => ({
    title: document.title,
    total: document.getElementById('verifiedCount')?.textContent,
    rows: document.querySelectorAll('#transactionRows tr').length,
    firstLink: document.querySelector('#transactionRows .source-links a')?.href,
    options: document.querySelectorAll('#institution option').length,
    result: document.getElementById('resultCount')?.textContent
  }))()`);
  if (initial?.options > 1 && initial?.firstLink) break;
  await delay(250);
}
console.log('OFFICIAL_LEDGER_INITIAL', JSON.stringify(initial));
if (!initial?.firstLink?.startsWith('http') || initial.rows !== 50 || initial.options < 2) {
  throw new Error('Verified source rows/links did not render');
}
const filtered = await evalOnPage(`(() => {
  const select=document.getElementById('institution');
  select.selectedIndex=1;
  select.dispatchEvent(new Event('change',{bubbles:true}));
  const institution=select.value;
  const cells=[...document.querySelectorAll('#transactionRows td.institution span:first-child')].map(x=>x.textContent);
  return {institution,allSame:cells.length>0&&cells.every(x=>x===institution),count:cells.length};
})()`);
console.log('OFFICIAL_LEDGER_FILTER',JSON.stringify(filtered));
if (!filtered.allSame || filtered.count < 1) throw new Error('Institution filter returned unrelated transactions');
const search = await evalOnPage(`(() => {
  document.getElementById('reset').click();
  const input=document.getElementById('query');
  input.value='no_such_merchant_9fe3abc281';
  input.dispatchEvent(new Event('input',{bubbles:true}));
  const none=document.getElementById('resultCount').textContent;
  document.getElementById('reset').click();
  return {none,restored:document.querySelectorAll('#transactionRows .source-links a').length>0};
})()`);
console.log('OFFICIAL_LEDGER_SEARCH',JSON.stringify(search));
if (!search.none.includes('조회 0건') || !search.restored) throw new Error('Search/reset behavior failed');
await call('Emulation.setDeviceMetricsOverride', {width:390,height:844,deviceScaleFactor:1,mobile:true});
const mobile = await evalOnPage(`(() => ({
  width:innerWidth,
  overhang:document.documentElement.scrollWidth-innerWidth,
  rowWidth:document.querySelector('#transactionRows tr')?.getBoundingClientRect().width,
  tableWidth:document.querySelector('table')?.getBoundingClientRect().width
}))()`);
console.log('OFFICIAL_LEDGER_MOBILE', JSON.stringify(mobile));
if (mobile.overhang > 2 || mobile.rowWidth > mobile.width) {
  throw new Error('Mobile ledger has horizontal overflow');
}
if (exceptions.length) throw new Error('Browser exceptions: ' + exceptions.join('\n'));
await call('Emulation.clearDeviceMetricsOverride');
ws.close();
