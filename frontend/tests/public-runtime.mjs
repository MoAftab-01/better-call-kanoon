/** Isolated production/public integration against SYNTHETIC data only. */
import { spawn } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { randomUUID, createHash } from 'node:crypto'
import assert from 'node:assert/strict'
const root=resolve(import.meta.dirname,'../..')
const base=process.env.PUBLIC_E2E_BACKEND_URL||'http://127.0.0.1:8004'
const url=process.env.PUBLIC_E2E_FRONTEND_URL||'http://127.0.0.1:5176'
const publicationPending=process.argv.includes('--pending-publication')
const status=await fetch(base+'/api/chat/status'),data=await status.json()
if(publicationPending){
 assert.equal(status.headers.get('x-kanoon-public-website-test'),'no-corpus')
 assert.equal(data.research_state,'publication_pending');assert.equal(data.retrieval.passages,0)
}else assert.equal(status.headers.get('x-kanoon-synthetic-public-corpus'),'true')
assert.equal(data.provider_configured,false);assert.equal(data.retrieval.corpus_kind,'public')
const profile=join(root,'backend/data/test-runs','public-chrome-'+randomUUID().slice(0,8))
await mkdir(profile,{recursive:true})
const chrome=spawn(process.env.CHROME_BINARY||'C:/Program Files/Google/Chrome/Application/chrome.exe',[
 '--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'})
const pause=ms=>new Promise(r=>setTimeout(r,ms));let socket,session,id=0
const pending=new Map(),checks=[];let chatPosts=0
function rpc(method,params={},browser=false){const key=++id;return new Promise((resolve,reject)=>{
 const timer=setTimeout(()=>reject(Error('CDP timeout '+method)),15000)
 pending.set(key,{resolve:v=>{clearTimeout(timer);resolve(v)},reject})
 socket.send(JSON.stringify({id:key,method,params,...(session&&!browser?{sessionId:session}:{})}))
})}
async function evaluate(expression){const r=await rpc('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails);return r.result.value}
async function until(expression){for(let n=0;n<150;n++){if(await evaluate('Boolean('+expression+')'))return;await pause(100)}throw Error('Timed out: '+expression)}
async function input(selector,value){await evaluate(`(()=>{let e=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(e instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`)}
try{
 let info;for(let n=0;n<150;n++){try{info=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).trim().split('\n');break}catch{await pause(100)}}
 assert(info);socket=new WebSocket('ws://127.0.0.1:'+info[0].trim()+info[1].trim())
 await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true})})
 socket.addEventListener('message',e=>{
  const r=JSON.parse(e.data)
  if(pending.has(r.id)){const p=pending.get(r.id);pending.delete(r.id);r.error?p.reject(Error(r.error.message)):p.resolve(r.result)}
  if(r.method==='Network.requestWillBeSent'&&r.params.request.method==='POST'&&r.params.request.url.endsWith('/api/chat'))chatPosts++
  if(r.method==='Fetch.requestPaused')void rpc('Fetch.failRequest',{requestId:r.params.requestId,errorReason:'Failed'})
 })
 const target=await rpc('Target.createTarget',{url:'about:blank'},true)
 session=(await rpc('Target.attachToTarget',{targetId:target.targetId,flatten:true},true)).sessionId
 await rpc('Page.enable');await rpc('Runtime.enable');await rpc('Network.enable')
 if(publicationPending)await rpc('Page.addScriptToEvaluateOnNewDocument',{source:"Object.defineProperty(window,'SpeechRecognition',{value:undefined});Object.defineProperty(window,'webkitSpeechRecognition',{value:undefined});"})
 await rpc('Page.navigate',{url})
 await until('document.querySelector(".brand")')
 assert((await evaluate('document.title')).startsWith('Better Call AI |'))
 assert.equal(await evaluate('document.querySelector(".brand").getAttribute("aria-label")'),'Better Call AI home')
 assert.equal(await evaluate('document.querySelector(".brand-name strong").textContent'),'AI.')
 if(publicationPending){
  const health=await fetch(base+'/api/health'),ready=await fetch(base+'/api/ready')
  assert.equal(health.status,200);assert.equal(ready.status,503);assert.equal((await ready.json()).research_ready,false)
  checks.push('healthy infrastructure and accurately blocked research readiness')
  await until('document.querySelector(".connection-connected") && document.querySelector(".publication-notice")')
  const text=await evaluate('document.body.textContent')
  assert(text.includes('Source publication pending')&&text.includes('Legal research is not available yet'))
  assert(text.includes('Sources are not available yet.')&&!text.includes('555'))
  assert.equal(await evaluate('document.querySelectorAll(".starter-button,.access-token,.citation-card,.chat-message").length'),0)
  checks.push('explicit pending publication, no source suggestions, fabricated conversations or citations')
  await input('#legal-question','BNS section 15')
  assert(await evaluate('document.querySelector(".send-button").disabled'))
  await evaluate('document.querySelector("#legal-question").dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",bubbles:true,cancelable:true}))')
  await pause(300);assert.equal(chatPosts,0)
  assert.equal(await evaluate('document.querySelectorAll(".chat-message").length'),0)
  checks.push('draft typing allowed; Enter and disabled submission send zero chat requests')
  assert((await evaluate('document.querySelector(".browser-voice").textContent')).includes('You can type a draft instead.'))
  assert(await evaluate('document.querySelector(".voice-button").disabled'))
  checks.push('unsupported speech fallback and unavailable telephone call are honest')
  await rpc('Emulation.setDeviceMetricsOverride',{width:320,height:850,deviceScaleFactor:1,mobile:true});await pause(200)
  assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'))
  await mkdir(join(root,'frontend/.qa'),{recursive:true})
  await writeFile(join(root,'frontend/.qa/public-no-corpus-mobile.png'),Buffer.from((await rpc('Page.captureScreenshot',{format:'png'})).data,'base64'))
  checks.push('320px pending-publication layout without overflow')
  await rpc('Fetch.enable',{patterns:[{urlPattern:'*api/health*',requestStage:'Request'}]})
  await evaluate('document.querySelector(".connection-retry").click()');await until('document.querySelector(".connection-disconnected")')
  assert(await evaluate('document.querySelector(".send-button").disabled'))
  await rpc('Fetch.disable');await evaluate('document.querySelector(".connection-retry").click()')
  await until('document.querySelector(".connection-connected")');assert.equal(chatPosts,0)
  checks.push('connection failure/recovery keeps publication gating and zero chat submissions')
 }else{
 await until('document.querySelector(".connection-connected") && document.querySelector(".access-token input")')
 checks.push('public production readiness and runtime access field')
 await input('#legal-question','BNS section 15');await until('!document.querySelector(".send-button").disabled')
 await evaluate('document.querySelector(".send-button").click()');await until('document.querySelector(".chat-error")')
 assert((await evaluate('document.querySelector(".chat-error").textContent')).includes('private demo access token'))
 checks.push('unauthorized request rejected visibly')
 await input('.access-token input','SYNTHETIC_PUBLIC_BROWSER_ACCESS_NOT_REAL_2026')
 await evaluate('document.querySelector(".chat-error button").click()');await until('document.querySelector(".citation-card")')
 const quote=await evaluate('document.querySelector(".citation-card blockquote").textContent')
 assert(quote.includes('SYNTHETIC SOFTWARE FIXTURE - NOT LAW'))
 const sample=await (await fetch(base+'/api/chat',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer SYNTHETIC_PUBLIC_BROWSER_ACCESS_NOT_REAL_2026'},body:JSON.stringify({message:'BNS section 15'})})).json()
 assert.equal(createHash('sha256').update(quote).digest('hex'),sample.citations[0].text_sha256)
 const text=await evaluate('document.querySelector(".citation-card").textContent')
 assert(text.includes('SYNTHETIC SOFTWARE TEST COMMENTARY'));assert(text.includes('Publication manifest SHA-256'))
 assert(!text.includes('Processed SHA-256'));assert(!text.includes('VERIFIED REVIEWED'))
 checks.push('authorized public answer, exact quotation, editorial note and manifest citation without private hashes')
 await rpc('Emulation.setDeviceMetricsOverride',{width:320,height:850,deviceScaleFactor:1,mobile:true});await pause(200)
 assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'))
 checks.push('320px public citation layout without overflow')
 await evaluate('document.querySelector(".clear-chat").click()');await until('!document.querySelector(".chat-message")')
 checks.push('clear removes displayed conversation and sources')
 }
 await mkdir(join(root,'frontend/.qa'),{recursive:true})
 const report={synthetic_only:true,publication_pending:publicationPending,branding_verified:true,live_groq:false,checks,...(publicationPending?{chat_posts:chatPosts}:{})}
 await writeFile(join(root,'frontend/.qa/'+(publicationPending?'public-no-corpus':'public-runtime')+'.json'),JSON.stringify(report,null,2))
 console.log(JSON.stringify(report))
}finally{
 if(socket?.readyState===WebSocket.OPEN){try{await rpc('Browser.close',{},true)}catch{}socket.close()}
 if(chrome.exitCode===null)chrome.kill()
}
