import assert from 'node:assert/strict'

export function requireTestProvider(status, syntheticHeader, mocked) {
  assert.equal(status.provider_configured, mocked,
    'Browser automation refuses live Groq: use an unconfigured extractive backend or the explicit synthetic test server.')
  if (mocked) assert.equal(syntheticHeader, 'true',
    'Mocked browser automation requires the explicit synthetic-transport server marker.')
}
