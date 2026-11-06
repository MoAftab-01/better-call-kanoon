/** Real Chrome/CDP integration tests. No downloaded browser or test dependency.
 * Start backend/Vite first. With --mock-provider use the EXPLICIT test server.
 * Outputs screenshots/results only under ignored frontend/.qa/.
 */
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { randomUUID, createHash } from 'node:crypto'
import assert from 'node:assert/strict'

const root = resolve(import.meta.dirname, '../..')
const output = join(root, 'frontend/.qa')
const profile = join(root, 'backend/data/test-runs', 'chrome-' + randomUUID().slice(0, 8))
const binary = process.env.CHROME_BINARY || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
assert(existsSync(binary), 'Set CHROME_BINARY to an existing local Chrome/Edge installation.')
const mocked = process.argv.includes('--mock-provider')
const backendUrl = process.env.CHAT_E2E_BACKEND_URL || 'http://127.0.0.1:8000'
const frontendUrl = process.env.CHAT_E2E_FRONTEND_URL || 'http://127.0.0.1:5173'
const status = await fetch(backendUrl + '/api/chat/status').then(r => r.json())
assert(status.retrieval.passages > 0, 'Citation E2E requires the separately acquired local evidence bundle.')
await mkdir(output, { recursive: true })
await mkdir(profile, { recursive: true })
const chrome = spawn(binary, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
let socket, next = 0, session
const pending = new Map(), responses = [], failures = []
const results = { mocked_groq: mocked, live_groq: false, checks: [], citations_verified: 0 }
function rpc(method, params = {}, browser = false) {
  const id = ++next
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)) }, 15000)
    pending.set(id, { resolve: v => { clearTimeout(timer); resolve(v) }, reject: e => { clearTimeout(timer); reject(e) } })
    socket.send(JSON.stringify({ id, method, params, ...(session && !browser ? { sessionId: session } : {}) }))
  })
}
async function evaluate(expression) {
  const value = await rpc('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (value.exceptionDetails) throw new Error('Browser expression failed: ' + value.exceptionDetails.text)
  return value.result.value
}
async function until(expression, description, timeout = 15000) {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    if (await evaluate('Boolean(' + expression + ')')) return
    await pause(100)
  }
  throw new Error('Timed out: ' + description)
}
async function fill(text) {
  await evaluate(`(() => { const el=document.querySelector('#legal-question'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(el,${JSON.stringify(text)}); el.dispatchEvent(new Event('input',{bubbles:true})); el.focus(); })()`)
  await until('!document.querySelector(".send-button").disabled', 'send enabled')
}
async function ask(text, keyboard = false) {
  const before = responses.length
  await fill(text)
  if (keyboard) {
    await rpc('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await rpc('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  } else await evaluate('document.querySelector(".send-button").click()')
  await until('document.querySelector(".send-button").disabled', 'duplicate-send guard')
  for (let i = 0; i < 150 && responses.length === before; i++) await pause(100)
  assert(responses.length > before, 'real chat network response received')
  const result = responses.at(-1)
  if (result.status === 200) await until('document.querySelector(".chat-message.assistant")', 'assistant rendered')
  return result
}
async function clear() { await evaluate('document.querySelector(".clear-chat").click()'); await until('!document.querySelector(".chat-message")', 'clear conversation') }
function check(name) { results.checks.push(name); console.log('PASS', name) }
try {
  let portInfo
  for (let i = 0; i < 150; i++) {
    try { portInfo = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).trim().split('\n'); break } catch { await pause(100) }
  }
  assert(portInfo, 'Chrome debugging endpoint available')
  socket = new WebSocket('ws://127.0.0.1:' + portInfo[0].trim() + portInfo[1].trim())
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }) })
  socket.addEventListener('message', event => {
    const value = JSON.parse(event.data)
    if (value.id && pending.has(value.id)) {
      const p = pending.get(value.id); pending.delete(value.id)
      if (value.error) p.reject(new Error(value.error.message)); else p.resolve(value.result)
    }
    if (value.method === 'Network.responseReceived' && value.params.response.url.endsWith('/api/chat')) {
      const id = value.params.requestId, status = value.params.response.status
      const listener = async event => {
        const message = JSON.parse(event.data)
        if (message.method === 'Network.loadingFinished' && message.params.requestId === id) {
          socket.removeEventListener('message', listener)
          try { const body = await rpc('Network.getResponseBody', { requestId: id }); responses.push({ status, body: JSON.parse(body.body) }) }
          catch (e) { failures.push(e.message) }
        }
      }
      socket.addEventListener('message', listener)
    }
    if (value.method === 'Fetch.requestPaused') void rpc('Fetch.failRequest', { requestId: value.params.requestId, errorReason: 'Failed' })
  })
  const target = await rpc('Target.createTarget', { url: 'about:blank' }, true)
  session = (await rpc('Target.attachToTarget', { targetId: target.targetId, flatten: true }, true)).sessionId
  await rpc('Page.enable'); await rpc('Runtime.enable'); await rpc('Network.enable')
  await rpc('Emulation.setDeviceMetricsOverride', { width: 1280, height: 960, deviceScaleFactor: 1, mobile: false })
  await rpc('Page.navigate', { url: frontendUrl })
  await until('document.querySelector(".connection-connected") && document.querySelector("#answer-availability")?.textContent.includes("Extractive") || document.querySelector("#answer-availability")?.textContent.includes("Groq selects")', 'health and chat readiness')
  check('frontend load, backend health and chat readiness')
  const bns = await ask('What does the BNS commencement notification state?')
  assert.equal(bns.status, 200);assert.equal(bns.body.evidence_status, 'ARCHIVAL_UNVERIFIED')
  assert.equal(bns.body.provider.status, mocked ? 'completed' : 'not_configured')
  const citation = bns.body.citations.find(c => c.instrument === 'S.O. 850(E)')
  assert(citation && citation.quote.includes('except the provision of sub-section (2) of section 106'))
  assert.equal(createHash('sha256').update(citation.quote).digest('hex'), citation.text_sha256)
  await until('document.querySelector(".citation-card")', 'citation card')
  assert.equal(await evaluate('document.querySelector(".citation-card blockquote").textContent'), citation.quote)
  assert.equal(await evaluate('document.querySelector(".citation-card a").href'), citation.source_url + '#page=2')
  assert(!(await evaluate('document.querySelector(".message-list").textContent')).includes('VERIFIED REVIEWED'))
  results.citations_verified++;check('real POST, answer, complete BNS exception, server citation binding and official PDF link')
  const bnss = await ask('What does the BNSS commencement notification say about the First Schedule?', true)
  const schedule = bnss.body.citations.find(c => c.instrument === 'S.O. 848(E)')
  assert(schedule && schedule.quote.includes('First Schedule') && schedule.quote.includes('section 106(2)'))
  results.citations_verified++;check('Enter sends and BNSS First Schedule distinction preserved')
  await evaluate('document.querySelectorAll(".source-select")[0].click()')
  assert((await evaluate('document.querySelector(".citation-card h3").textContent')).includes('850'))
  check('selected-answer source association')
  await clear();assert.equal(await evaluate('document.querySelectorAll(".citation-card").length'), 0)
  const insufficient = await ask('What can I do about a defective consumer product?')
  assert.equal(insufficient.body.evidence_status, 'INSUFFICIENT_EVIDENCE');assert.deepEqual(insufficient.body.citations, [])
  check('clear and honest missing-evidence refusal')
  await clear()
  if (mocked) {
    await fill('BNS notification')
    await evaluate('document.querySelector(".send-button").click()')
    await until('document.querySelector(".chat-progress")', 'loading indicator')
    assert(await evaluate('document.querySelector(".send-button").disabled'))
    await clear(); await pause(900)
    assert.equal(await evaluate('document.querySelectorAll(".chat-message").length'), 0)
    check('loading indicator, duplicate-send guard and clear cancels late response')
    const retry = await ask('BNS commencement notification retry-test')
    assert.equal(retry.status, 429)
    await until('document.querySelector(".chat-error")', 'provider error')
    const count = responses.length
    await evaluate('document.querySelector(".chat-error button").click()')
    for (let i = 0; i < 150 && responses.length === count; i++) await pause(100)
    assert.equal(responses.at(-1).status, 200)
    await until('document.querySelectorAll(".chat-message.assistant").length===1', 'retry response')
    assert.equal(await evaluate('document.querySelectorAll(".chat-message.user").length'), 1)
    check('mocked Groq rate-limit error and retry without duplicate user turn')
    await clear()
  }
  await fill('What does the BSA notification state?')
  // A synthetic keyboard event checks the actual handler leaves Shift+Enter to the browser.
  assert.equal(await evaluate(`(() => { const e=new KeyboardEvent('keydown',{key:'Enter',shiftKey:true,bubbles:true,cancelable:true}); document.querySelector('#legal-question').dispatchEvent(e); return e.defaultPrevented; })()`), false)
  assert.equal(await evaluate('document.querySelectorAll(".chat-message").length'), 0)
  check('Shift+Enter does not submit')
  await ask('What does the BSA commencement notification state?')
  await rpc('Emulation.setDeviceMetricsOverride', { width: 320, height: 850, deviceScaleFactor: 1, mobile: true })
  await pause(300)
  assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'no mobile horizontal overflow')
  assert(await evaluate('document.querySelector(".mic-button").disabled && document.querySelector(".voice-button").disabled'))
  await writeFile(join(output, 'chat-mobile-' + (mocked ? 'mocked' : 'extractive') + '.png'), Buffer.from((await rpc('Page.captureScreenshot', { format: 'png' })).data, 'base64'))
  check('320px mobile layout, citation rendering and disabled voice controls')
  await rpc('Fetch.enable', { patterns: [{ urlPattern: '*api/health*', requestStage: 'Request' }] })
  await evaluate('document.querySelector(".connection-retry").click()')
  await until('document.querySelector(".connection-disconnected")', 'disconnected state')
  assert(await evaluate('document.querySelector(".send-button").disabled'))
  await rpc('Fetch.disable')
  await evaluate('document.querySelector(".connection-retry").click()')
  await until('document.querySelector(".connection-connected")', 'health recovery')
  check('connection failure, disabled send and health recovery')
  assert.deepEqual(failures, [])
  await writeFile(join(output, 'chat-browser-' + (mocked ? 'mocked' : 'extractive') + '.json'), JSON.stringify(results, null, 2))
  console.log(JSON.stringify(results))
} finally {
  if (socket?.readyState === WebSocket.OPEN) {
    try { await rpc('Browser.close', {}, true) } catch { /* process exit closes the socket */ }
    socket.close()
  }
  if (chrome.exitCode === null) chrome.kill()
}
