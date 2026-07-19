// === TASK:WP-500:START ===
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import { BrowserSpeechRecognitionProvider } from './speech/SpeechRecognitionProvider'

function renderApp() {
  return render(<BrowserSpeechRecognitionProvider><App /></BrowserSpeechRecognitionProvider>)
}

afterEach(() => vi.unstubAllGlobals())

function mockBackendResponse(message = 'Phản hồi từ AI/backend') {
  const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({
    trace_id: 'trace-1',
    capability: 'information_assistance',
    outcome: 'answered',
    result: { message, suggested_actions: [{ label: 'Trở lại', value: 'start_over' }] },
    warnings: [],
    errors: [],
    timestamp: new Date().toISOString(),
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

describe('App conversational experience', () => {
  it('welcomes the visitor and presents exactly four Vietnamese hospital action cards', async () => {
    renderApp()
    expect(screen.getByRole('heading', { name: /trợ lý bệnh viện/i })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/bạn đang cần tôi hỗ trợ về vấn đề gì/i)).toBeInTheDocument())

    expect(screen.getByRole('button', { name: /đặt hoặc tra cứu lịch hẹn/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /chuẩn bị đi khám \/ tái khám/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /bhyt & chi phí/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /bác sĩ, khoa & giờ làm việc/i })).toBeInTheDocument()
    expect(screen.getAllByRole('button').filter((button) => button.getAttribute('data-flow')).map((button) => button.getAttribute('data-flow'))).toEqual(['appointment', 'preparation', 'insurance_cost', 'doctor_info'])
  })

  it('guides appointment booking through visit type, specialty, doctor, slot, patient validation and confirmation', async () => {
    renderApp()

    await waitFor(() => expect(screen.getByRole('button', { name: /đặt hoặc tra cứu lịch hẹn/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /đặt hoặc tra cứu lịch hẹn/i }))
    expect(screen.getByText(/đặt lịch mới hay tra cứu/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /đặt lịch mới/i }))
    fireEvent.click(screen.getByRole('button', { name: /khám lần đầu/i }))
    fireEvent.click(screen.getByRole('button', { name: /^tim mạch$/i }))
    fireEvent.click(screen.getByRole('button', { name: /nguyễn minh anh/i }))
    fireEvent.click(screen.getByRole('button', { name: /08:30/i }))

    const input = screen.getByLabelText(/nội dung/i)
    fireEvent.change(input, { target: { value: 'Nguyễn Văn A, 123, 1985' } })
    fireEvent.click(screen.getByRole('button', { name: /gửi tin nhắn/i }))
    expect(screen.getByText(/số điện thoại chưa hợp lệ/i)).toBeInTheDocument()

    fireEvent.change(input, { target: { value: 'Nguyễn Văn A, 0912345678, 1985' } })
    fireEvent.click(screen.getByRole('button', { name: /gửi tin nhắn/i }))
    expect(screen.getByText(/vui lòng kiểm tra/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /xác nhận đặt lịch/i }))
    expect(screen.getByText(/đặt lịch thành công/i)).toBeInTheDocument()
    expect(screen.getByText(/HEN-2026-0420/i)).toBeInTheDocument()
  })

  it('routes free text "tôi muốn đặt chỗ" to structured appointment actions without backend demo completion', async () => {
    const fetcher = mockBackendResponse('Yêu cầu đặt lịch hẹn của bạn đã được ghi nhận ở chế độ thử nghiệm. Đây là hệ thống demo.')
    renderApp()
    await waitFor(() => expect(screen.getByLabelText(/nội dung/i)).toBeInTheDocument())

    const input = screen.getByLabelText(/nội dung/i)
    fireEvent.change(input, { target: { value: 'tôi muốn đặt chỗ' } })
    fireEvent.click(screen.getByRole('button', { name: /gửi tin nhắn/i }))

    expect(screen.getByText(/bạn muốn đặt lịch mới hay tra cứu lịch hẹn đã có/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /📅 đặt lịch mới/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /🔍 tra cứu lịch hẹn/i })).toBeInTheDocument()
    expect(fetcher).not.toHaveBeenCalled()
    expect(screen.queryByText(/chế độ thử nghiệm|demo|mô phỏng/i)).not.toBeInTheDocument()
  })

  it('calls the real backend/LLM capability endpoint for ambiguous free text', async () => {
    const fetcher = mockBackendResponse('AI đã hiểu yêu cầu tự do')
    renderApp()
    await waitFor(() => expect(screen.getByLabelText(/nội dung/i)).toBeInTheDocument())

    const input = screen.getByLabelText(/nội dung/i)
    fireEvent.change(input, { target: { value: 'Tôi chưa biết nên hỏi gì, tư vấn giúp tôi' } })
    fireEvent.click(screen.getByRole('button', { name: /gửi tin nhắn/i }))

    await waitFor(() => expect(fetcher).toHaveBeenCalledWith('/v1/capabilities/information-assistance:execute', expect.objectContaining({ method: 'POST' })))
    const body = JSON.parse(String((fetcher.mock.calls[0] as [RequestInfo | URL, RequestInit?])[1]?.body))
    expect(body.message).toBe('Tôi chưa biết nên hỏi gì, tư vấn giúp tôi')
    expect(body.session_id).toMatch(/^web-/)
    expect(body.button_context).toEqual({})
    expect(screen.getByText(/AI đã hiểu yêu cầu tự do/i)).toBeInTheDocument()
  })

  it('calls appointment backend/LLM fallback when specialty text cannot be deterministically inferred', async () => {
    const fetcher = mockBackendResponse('AI cần hỏi thêm để xác định chuyên khoa')
    renderApp()
    await waitFor(() => expect(screen.getByRole('button', { name: /đặt hoặc tra cứu lịch hẹn/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /đặt hoặc tra cứu lịch hẹn/i }))
    fireEvent.click(screen.getByRole('button', { name: /đặt lịch mới/i }))
    fireEvent.click(screen.getByRole('button', { name: /khám lần đầu/i }))

    const input = screen.getByLabelText(/nội dung/i)
    fireEvent.change(input, { target: { value: 'Tôi thấy người hơi mệt không rõ khám gì' } })
    fireEvent.click(screen.getByRole('button', { name: /gửi tin nhắn/i }))

    await waitFor(() => expect(fetcher).toHaveBeenCalledWith('/v1/capabilities/appointment-booking:execute', expect.objectContaining({ method: 'POST' })))
    const body = JSON.parse(String((fetcher.mock.calls[0] as [RequestInfo | URL, RequestInit?])[1]?.body))
    expect(body.message).toBe('Tôi thấy người hơi mệt không rõ khám gì')
    expect(body.form_data.visit_type).toBe('first_visit')
    expect(screen.getByText(/AI cần hỏi thêm để xác định chuyên khoa/i)).toBeInTheDocument()
  })

  it('switches from appointment flow to BHYT and cost flow for clear insurance text', async () => {
    renderApp()
    await waitFor(() => expect(screen.getByRole('button', { name: /đặt hoặc tra cứu lịch hẹn/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /đặt hoặc tra cứu lịch hẹn/i }))

    expect(screen.getByText(/bạn muốn đặt lịch mới hay tra cứu lịch hẹn đã có/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /📅 đặt lịch mới/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /🔍 tra cứu lịch hẹn/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /bảo hiểm y tế|bhyt|quyền lợi bhyt/i })).not.toBeInTheDocument()

    const input = screen.getByLabelText(/nội dung/i)
    fireEvent.change(input, { target: { value: 'tôi muốn tìm thông tin về chính sách bảo hiểm y tế' } })
    fireEvent.click(screen.getByRole('button', { name: /gửi tin nhắn/i }))

    expect(screen.getByText(/bạn muốn hỏi về vấn đề nào/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /quyền lợi bhyt/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /giấy chuyển tuyến/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /giấy tờ cần mang/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^giá khám$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /giá xét nghiệm \/ dịch vụ/i })).toBeInTheDocument()
    expect(screen.queryByText(/bạn muốn đặt lịch khám lần đầu hay tái khám/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^tiếp tục$/i })).not.toBeInTheDocument()
  })

  it('calls backend/RAG information assistance when clicking Giá khám and does not invent frontend prices', async () => {
    const officialAnswer = 'Theo dữ liệu chính thức từ backend/RAG: vui lòng chọn loại khám để tra cứu bảng giá phù hợp.'
    const fetcher = mockBackendResponse(officialAnswer)
    renderApp()
    await waitFor(() => expect(screen.getByRole('button', { name: /bhyt & chi phí/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /bhyt & chi phí/i }))
    fireEvent.click(screen.getByRole('button', { name: /^giá khám$/i }))

    await waitFor(() => expect(fetcher).toHaveBeenCalledWith('/v1/capabilities/information-assistance:execute', expect.objectContaining({ method: 'POST' })))
    const body = JSON.parse(String((fetcher.mock.calls[0] as [RequestInfo | URL, RequestInit?])[1]?.body))
    expect(body.message).toMatch(/giá khám chuyên khoa/i)
    expect(body.button_context).toMatchObject({ flow: 'insurance_cost', selected_action: 'exam_price', requires_official_source: 'true', source_requirement: 'rag_or_backend_citations' })
    expect(screen.queryByText(/mô phỏng/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/\b\d{1,3}(?:\.\d{3})+\s*đ\b/i)).not.toBeInTheDocument()
    expect(await screen.findByText(officialAnswer)).toBeInTheDocument()
  })

  it('shows safe official-data retrieval failure for Giá khám without fake amounts', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({
      trace_id: 'trace-fail',
      capability: 'information_assistance',
      outcome: 'failed',
      result: {},
      warnings: [],
      errors: [{ code: 'backend_unavailable', message: 'Backend unavailable' }],
      timestamp: new Date().toISOString(),
    }), { status: 503, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetcher)
    renderApp()
    await waitFor(() => expect(screen.getByRole('button', { name: /bhyt & chi phí/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /bhyt & chi phí/i }))
    fireEvent.click(screen.getByRole('button', { name: /^giá khám$/i }))

    await waitFor(() => expect(screen.getByText(/chưa truy xuất được dữ liệu chính thức/i)).toBeInTheDocument())
    expect(screen.getByText(/quầy viện phí/i)).toBeInTheDocument()
    expect(screen.queryByText(/mô phỏng/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/\b\d{1,3}(?:\.\d{3})+\s*đ\b/i)).not.toBeInTheDocument()
  })

  it('supports a representative preparation branch', async () => {
    renderApp()
    await waitFor(() => expect(screen.getByRole('button', { name: /chuẩn bị đi khám \/ tái khám/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /chuẩn bị đi khám \/ tái khám/i }))
    fireEvent.click(screen.getByRole('button', { name: /^tái khám$/i }))
    expect(screen.getByText(/mang sổ\/phiếu hẹn tái khám/i)).toBeInTheDocument()
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
