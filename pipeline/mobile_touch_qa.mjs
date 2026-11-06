#!/usr/bin/env node
import fs from 'node:fs';
const dir='reports/p0-02-mobile';fs.mkdirSync(dir,{recursive:true});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let nextId=0;const pending=new Map(),results=[],errors=[];
let endpoint;
for(let n=0;n<100;n++){try{let p=await(await fetch('http://127.0.0.1:9222/json')).json();endpoint=p.find(x=>x.type==='page'&&x.webSocketDebuggerUrl);if(endpoint)break}catch{}await sleep(150)}
if(!endpoint)throw Error('No Chromium target');
const ws=new WebSocket(endpoint.webSocketDebuggerUrl);
await new Promise((ok,bad)=>{ws.addEventListener('open',ok,{once:true});ws.addEventListener('error',bad,{once:true})});
ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){let p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails?.text)});
const cmd=(method,params={})=>new Promise((resolve,reject)=>{let id=++nextId;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
async function ev(code){let r=await cmd('Runtime.evaluate',{expression:code,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function check(name,fun,ok){try{const d=await fun();results.push({name,status:ok(d)?'PASS':'FINDING',data:d})}catch(e){results.push({name,status:'ERROR',error:String(e)})}}
async function screen(name){let r=await cmd('Page.captureScreenshot',{format:'png'});fs.writeFileSync(dir+'/'+name+'.png',Buffer.from(r.data,'base64'))}
async function size(w,h){await cmd('Emulation.setDeviceMetricsOverride',{width:w,height:h,deviceScaleFactor:1,mobile:true,screenWidth:w,screenHeight:h});await cmd('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});await sleep(250);await ev("typeof map!=='undefined'?(map.resize(),true):false")}
async function touch(selector){let ok=await ev('(()=>{let e=document.querySelector('+JSON.stringify(selector)+');if(!e)return false;e.scrollIntoView({block:"center",behavior:"instant"});return true})()');if(!ok)throw Error('missing target '+selector);await sleep(120);let p=await ev('(()=>{let r=document.querySelector('+JSON.stringify(selector)+').getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()');await cmd('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:p.x,y:p.y,id:1}]});await sleep(65);await cmd('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]})}
await cmd('Runtime.enable');await cmd('Page.enable');await size(390,844);
for(let i=0;i<90;i++){if(await ev("typeof DATA!=='undefined' && !!document.querySelector('.restaurant-card')"))break;await sleep(150)}
await check('initial-390-layout',()=>ev('({width:innerWidth,scroll:document.documentElement.scrollWidth,cards:document.querySelectorAll(".restaurant-card").length,detailTop:Math.round(detail.getBoundingClientRect().top)})'),d=>d.width===390&&d.scroll<=392&&d.cards>0);
await screen('01-initial');
await touch('#q');await cmd('Input.insertText',{text:'광화문'});await sleep(180);
await check('touch-search',()=>ev('({query:q.value,found:current.length,cards:document.querySelectorAll(".restaurant-card").length})'),d=>d.query==='광화문'&&d.found>0&&d.found===d.cards);
await screen('02-search');
await touch('.restaurant-card');await sleep(270);
await check('card-tap-detail-visible',()=>ev('(()=>{let r=detail.querySelector("h2")?.getBoundingClientRect();return {selected,hash:location.search,detailTitle:detail.querySelector("h2")?.textContent,detailTop:Math.round(detail.getBoundingClientRect().top),headingTop:r?.top,viewportHeight:innerHeight,visible:!!r&&r.top>=0&&r.top<innerHeight,scrollY,hasExternalMap:!!detail.querySelector("a[href*=google]")}})()'),d=>!!d.selected&&!!d.detailTitle&&d.visible&&d.hasExternalMap);
await screen('03-after-tap');
await check('map-and-official-evidence',()=>ev('(()=>{let a=detail.querySelector("a[href*=google]");return {mapWidth:map.getContainer().getBoundingClientRect().width,selected,official:detail.textContent.includes("원자료"),externalHref:a?.href,externalTarget:a?.target}})()'),d=>d.mapWidth>200&&!!d.selected&&d.official&&d.externalHref?.startsWith('https://')&&d.externalTarget==='_blank');
await screen('04-detail');
for(let [label,w,h] of [['small360',360,780],['tablet504',504,981]]){await size(w,h);await check(label,()=>ev('({width:innerWidth,scroll:document.documentElement.scrollWidth,mapWidth:map.getContainer().clientWidth,detailWidth:detail.clientWidth})'),d=>d.scroll<=d.width+2&&d.mapWidth>250&&d.detailWidth>250);await screen('05-'+label)}
fs.writeFileSync(dir+'/result.json',JSON.stringify({generated_at:new Date().toISOString(),scope:'isolated non-deployed Chromium mobile touch tests',results,errors},null,2)+'\n');
console.log('MOBILE_TOUCH_QA',JSON.stringify(results));console.log('MOBILE_ERRORS',JSON.stringify(errors));
ws.close();if(results.some(r=>r.status==='ERROR'))process.exitCode=1;
