import { spawnSync } from 'node:child_process'
import assert from 'node:assert/strict'
import test from 'node:test'

for (const [name, value] of [
  ['missing', ''], ['http', 'http://api.example'],
  ['credentials', 'https://SYNTHETIC_USER:SYNTHETIC_PASSWORD@api.example'],
  ['path', 'https://api.example/api'], ['query', 'https://api.example/?SYNTHETIC_TOKEN'],
  ['fragment', 'https://api.example/#configuration'],
]) {
  test(`hosting build rejects ${name} without disclosing input`, () => {
    const result = spawnSync(process.execPath, ['scripts/check-hosted-env.mjs'], {
      cwd: new URL('..', import.meta.url), env: { ...process.env, VITE_API_BASE_URL: value }, encoding: 'utf8',
    })
    assert.equal(result.status, 1)
    assert(result.stderr.includes('VITE_API_BASE_URL'))
    assert(!result.stderr.includes('SYNTHETIC_PASSWORD') && !result.stderr.includes('SYNTHETIC_TOKEN'))
  })
}
test('hosting build accepts an HTTPS origin', () => {
  const result = spawnSync(process.execPath, ['scripts/check-hosted-env.mjs'], {
    cwd: new URL('..', import.meta.url), env: { ...process.env, VITE_API_BASE_URL: 'https://api.example' }, encoding: 'utf8',
  })
  assert.equal(result.status, 0)
})
