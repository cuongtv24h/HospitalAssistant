import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MicrophoneButton } from './MicrophoneButton'
import { BrowserSpeechRecognitionProvider, type SpeechRecognitionOptions } from './SpeechRecognitionProvider'

function renderWithSpeechProvider(element: React.ReactElement) {
  return render(<BrowserSpeechRecognitionProvider>{element}</BrowserSpeechRecognitionProvider>)
}

afterEach(() => vi.unstubAllGlobals())

describe('MicrophoneButton', () => {
  it('shows unsupported state when Web Speech API is unavailable', () => {
    renderWithSpeechProvider(<MicrophoneButton onTranscript={vi.fn()} />)

    expect(screen.getByRole('button', { name: /không hỗ trợ/i })).toBeDisabled()
    expect(screen.getByText(/không hỗ trợ micro/i)).toBeInTheDocument()
  })

  it('starts and stops a Vietnamese speech recognition session', () => {
    const instances: MockSpeechRecognition[] = []
    class MockSpeechRecognition {
      lang = ''
      continuous = true
      interimResults = true
      maxAlternatives = 0
      onstart: (() => void) | null = null
      onend: (() => void) | null = null
      onresult: SpeechRecognitionOptions['onResult'] | null = null
      onerror: (() => void) | null = null
      start = vi.fn(() => this.onstart?.())
      stop = vi.fn(() => this.onend?.())
      abort = vi.fn()
      constructor() { instances.push(this) }
    }
    vi.stubGlobal('SpeechRecognition', MockSpeechRecognition)
    renderWithSpeechProvider(<MicrophoneButton onTranscript={vi.fn()} />)

    const button = screen.getByRole('button', { name: /nhập bằng giọng nói/i })
    fireEvent.click(button)
    const recognition = instances[0]
    expect(recognition.lang).toBe('vi-VN')
    expect(recognition.continuous).toBe(false)
    expect(recognition.interimResults).toBe(false)
    expect(button).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(screen.getByRole('button', { name: /dừng nghe/i }))
    expect(recognition.stop).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /nhập bằng giọng nói/i })).toHaveAttribute('aria-pressed', 'false')
  })

  it('returns final recognized text to the caller', () => {
    const onTranscript = vi.fn()
    const instances: Array<{ onresult: ((event: { resultIndex: number; results: Array<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null }> = []
    class MockSpeechRecognition {
      lang = ''
      continuous = false
      interimResults = false
      maxAlternatives = 1
      onstart = null
      onend = null
      onerror = null
      onresult: ((event: { resultIndex: number; results: Array<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null = null
      start = vi.fn()
      stop = vi.fn()
      abort = vi.fn()
      constructor() { instances.push(this) }
    }
    vi.stubGlobal('webkitSpeechRecognition', MockSpeechRecognition)
    renderWithSpeechProvider(<MicrophoneButton onTranscript={onTranscript} />)
    fireEvent.click(screen.getByRole('button', { name: /nhập bằng giọng nói/i }))

    const recognition = instances[0]
    recognition.onresult?.({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: ' đặt lịch khám ' } }] })

    expect(onTranscript).toHaveBeenCalledWith('đặt lịch khám')
  })
})
