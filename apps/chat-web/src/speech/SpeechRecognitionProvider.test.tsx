import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BrowserSpeechRecognitionProvider, speechRecognitionTestUtils, useSpeechRecognitionProvider } from './SpeechRecognitionProvider'

function Probe() {
  const provider = useSpeechRecognitionProvider()
  return <output>{provider.isSupported ? 'supported' : 'unsupported'}</output>
}

afterEach(() => vi.unstubAllGlobals())

describe('BrowserSpeechRecognitionProvider', () => {
  it('detects native SpeechRecognition support', () => {
    class MockSpeechRecognition {
      lang = ''
      continuous = false
      interimResults = false
      maxAlternatives = 1
      onstart = null
      onend = null
      onresult = null
      onerror = null
      start = vi.fn()
      stop = vi.fn()
      abort = vi.fn()
    }
    vi.stubGlobal('SpeechRecognition', MockSpeechRecognition)

    render(<BrowserSpeechRecognitionProvider><Probe /></BrowserSpeechRecognitionProvider>)

    expect(screen.getByText('supported')).toBeInTheDocument()
  })

  it('reports unsupported without a browser recognition constructor', () => {
    render(<BrowserSpeechRecognitionProvider><Probe /></BrowserSpeechRecognitionProvider>)

    expect(screen.getByText('unsupported')).toBeInTheDocument()
  })

  it('maps browser errors to Vietnamese user-facing messages', () => {
    expect(speechRecognitionTestUtils.mapSpeechRecognitionError('not-allowed')).toMatch(/cho phép truy cập micro/i)
    expect(speechRecognitionTestUtils.mapSpeechRecognitionError('no-speech')).toMatch(/không nhận được giọng nói/i)
    expect(speechRecognitionTestUtils.mapSpeechRecognitionError('audio-capture')).toMatch(/không tìm thấy micro/i)
  })
})
