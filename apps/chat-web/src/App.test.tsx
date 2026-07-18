// === TASK:WP-500:START ===
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import { BrowserSpeechRecognitionProvider } from './speech/SpeechRecognitionProvider'

function renderApp() {
  return render(<BrowserSpeechRecognitionProvider><App /></BrowserSpeechRecognitionProvider>)
}

afterEach(() => vi.unstubAllGlobals())

describe('App conversational experience', () => {
  it('welcomes the visitor and presents JTBD quick actions', async () => {
    renderApp()
    expect(screen.getByRole('heading', { name: /trợ lý bệnh viện/i })).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText(/bạn cần tôi hỗ trợ điều gì/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /giá dịch vụ/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /đặt lịch khám/i })).toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('guides appointment selection through specialty, doctor and slot buttons', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/v1/foundation/specialties')) return new Response(JSON.stringify({ items: [{ specialty_id: 'SP-01', name: 'Tim mạch', description: 'Khám tim mạch' }] }), { status: 200 })
      if (url.includes('/v1/foundation/doctors?specialty_id=SP-01')) return new Response(JSON.stringify({ items: [{ doctor_id: 'DOC-01', full_name: 'Nguyễn Văn A', title: 'BS.', profile_summary: 'Bác sĩ tim mạch' }] }), { status: 200 })
      if (url.includes('/v1/foundation/doctors/DOC-01/available-slots')) return new Response(JSON.stringify({ items: [{ slot_id: 'SL-01', date: '2026-07-20', time: '09:00', room: 'P101' }] }), { status: 200 })
      return new Response('{}', { status: 404 })
    })
    vi.stubGlobal('fetch', fetcher)
    renderApp()

    await waitFor(() => expect(screen.getByRole('button', { name: /đặt lịch khám/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /đặt lịch khám/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /tim mạch/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /tim mạch/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /nguyễn văn a/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /nguyễn văn a/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /09:00/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /09:00/i }))
    expect(screen.getByRole('heading', { name: /thông tin người khám/i })).toBeInTheDocument()
  })

  it('dictates recognized speech into the chat input', async () => {
    const instances: Array<{ lang: string; onstart: (() => void) | null; onresult: ((event: { resultIndex: number; results: Array<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null; start: () => void; stop: () => void; abort: () => void }> = []
    class MockSpeechRecognition {
      lang = ''
      continuous = true
      interimResults = true
      maxAlternatives = 0
      onstart: (() => void) | null = null
      onend: (() => void) | null = null
      onresult: ((event: { resultIndex: number; results: Array<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null = null
      onerror: (() => void) | null = null
      constructor() { instances.push(this) }
      start = vi.fn(() => this.onstart?.())
      stop = vi.fn()
      abort = vi.fn()
    }
    vi.stubGlobal('webkitSpeechRecognition', MockSpeechRecognition)
    renderApp()

    await waitFor(() => expect(screen.getByRole('button', { name: /nhập bằng giọng nói/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /nhập bằng giọng nói/i }))
    const recognition = instances[0]
    expect(recognition.lang).toBe('vi-VN')
    expect(screen.getByText(/đang nghe/i)).toBeInTheDocument()
    act(() => recognition.onresult?.({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: ' Tôi cần khám tim mạch ' } }] }))

    await waitFor(() => expect(screen.getByLabelText(/nội dung/i)).toHaveValue('Tôi cần khám tim mạch'))
  })
})
// === TASK:WP-500:END ===
