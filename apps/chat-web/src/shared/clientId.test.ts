import { afterEach, describe, expect, it, vi } from 'vitest'
import { createClientUuid } from './clientId'

afterEach(() => vi.unstubAllGlobals())

describe('createClientUuid', () => {
  it('uses a UUID v4-shaped fallback when randomUUID is unavailable', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes: Uint8Array) => {
        bytes.fill(1)
        return bytes
      },
    })

    expect(createClientUuid()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  })
})
