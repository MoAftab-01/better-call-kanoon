import test from 'node:test'
import assert from 'node:assert/strict'
import { requireTestProvider } from './provider-guard.mjs'

test('extractive test mode accepts an unconfigured provider', () => {
  requireTestProvider({ provider_configured: false }, null, false)
})
test('explicit mock server is accepted', () => {
  requireTestProvider({ provider_configured: true }, 'true', true)
})
test('real configured provider is refused before browser chat requests', () => {
  assert.throws(() => requireTestProvider({ provider_configured: true }, null, false))
  assert.throws(() => requireTestProvider({ provider_configured: true }, null, true))
})
