// === TASK:WP-502:START ===
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { InformationResponse, type InformationAssistanceResponse } from './InformationResponse'

const answeredResponse: InformationAssistanceResponse = {
  outcome: 'answered',
  message: 'Bệnh viện tiếp nhận khám từ 7:00 đến 16:30 các ngày làm việc.',
  citations: [
    {
      source_id: 'gio-lam-viec-2026',
      title: 'Quy định giờ làm việc',
      url: 'https://hospital.example/gio-lam-viec',
      excerpt: 'Khoa khám bệnh tiếp nhận từ 7:00.',
      effective_date: '2026-01-01',
    },
  ],
  suggested_actions: [
    {
      action_id: 'book-appointment',
      label: 'Đặt lịch khám',
      type: 'appointment_booking',
    },
  ],
  conversation_state: { topic: 'gio_lam_viec' },
  explainability: {
    grounded: true,
    confidence: 'high',
    source_count: 1,
  },
}

describe('InformationResponse', () => {
  it('renders a grounded answer with accessible citation links and next actions', () => {
    const onSuggestedAction = vi.fn()
    render(<InformationResponse response={answeredResponse} onSuggestedAction={onSuggestedAction} />)

    expect(screen.getByLabelText('Response outcome')).toHaveTextContent('Đã trả lời dựa trên nguồn chính thức')
    expect(screen.getByText(answeredResponse.message)).toBeInTheDocument()

    const citations = screen.getByLabelText('Citations')
    const citationLink = within(citations).getByRole('link', { name: 'Quy định giờ làm việc' })
    expect(citationLink).toHaveAttribute('href', 'https://hospital.example/gio-lam-viec')
    expect(citationLink).toHaveAttribute('rel', 'noreferrer')
    expect(within(citations).getByText(/hiệu lực 2026-01-01/i)).toBeInTheDocument()
    expect(within(citations).getByText('Khoa khám bệnh tiếp nhận từ 7:00.')).toBeInTheDocument()

    expect(screen.queryByLabelText('Explainability')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Đặt lịch khám' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Đặt lịch khám' }))
    expect(onSuggestedAction).toHaveBeenCalledWith(answeredResponse.suggested_actions[0])
  })

  it('marks fallback content as not certain and does not imply grounded certainty', () => {
    render(
      <InformationResponse
        response={{
          outcome: 'fallback',
          message: 'Hiện chưa đủ dữ liệu chính thức để xác nhận thông tin này.',
          citations: [],
          suggested_actions: [{ action_id: 'contact', label: 'Liên hệ bệnh viện', type: 'contact' }],
          explainability: { grounded: false, confidence: 'low', source_count: 0 },
        }}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('không được hiển thị như câu trả lời chắc chắn')
    expect(screen.getByLabelText('Response outcome')).toHaveTextContent('Chưa đủ căn cứ để trả lời chắc chắn')
    expect(screen.queryByLabelText('Explainability')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Citations')).toHaveTextContent('Không có nguồn chính thức được đính kèm.')
    expect(screen.getByRole('button', { name: 'Liên hệ bệnh viện' })).toBeInTheDocument()
  })

  it('handles clarification-required responses as uncertain UI state', () => {
    render(
      <InformationResponse
        response={{
          outcome: 'clarification_required',
          message: 'Bạn vui lòng cho biết bạn cần hỏi về BHYT hay giá dịch vụ?',
          citations: [],
          suggested_actions: [],
          explainability: { grounded: false, source_count: 0 },
        }}
      />,
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByLabelText('Response outcome')).toHaveTextContent('Cần thêm thông tin để trả lời chính xác')
    expect(screen.queryByLabelText('Suggested actions')).not.toBeInTheDocument()
  })

  it('renders an out-of-scope refusal as only the assistant message', () => {
    const message = 'Xin lỗi, tôi chỉ hỗ trợ đặt lịch khám và thông tin chính thức về khám chữa bệnh, BHYT, giá dịch vụ, giờ làm việc, bác sĩ và chuyên khoa tại Bệnh viện Tim Hà Nội.'
    render(
      <InformationResponse
        response={{
          outcome: 'refused',
          message,
          citations: [],
          suggested_actions: [],
          explainability: { grounded: false, confidence: 'low', source_count: 0 },
          error: {
            trace_id: 'scope-refusal',
            error: { code: 'OUT_OF_SCOPE', category: 'safety' },
          },
        }}
      />,
    )

    expect(screen.getByLabelText('Answer content')).toHaveTextContent(message)
    expect(screen.queryByLabelText('Response outcome')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Citations')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Suggested actions')).not.toBeInTheDocument()
    expect(screen.queryByText('Nguồn tham khảo')).not.toBeInTheDocument()
    expect(screen.queryByText('Không có nguồn chính thức được đính kèm.')).not.toBeInTheDocument()
  })

  it('renders model markdown with line breaks, emphasis, and lists', () => {
    render(
      <InformationResponse
        response={{
          outcome: 'answered',
          message: '**Quy trình khám**\nMang theo CCCD.\n- Đăng ký tại quầy\n- Xuất trình **thẻ BHYT**',
          citations: [],
          suggested_actions: [],
        }}
      />,
    )

    const answer = screen.getByLabelText('Answer content')
    expect(within(answer).getByText('Quy trình khám').tagName).toBe('STRONG')
    expect(within(answer).getByText('thẻ BHYT').tagName).toBe('STRONG')
    expect(within(answer).getAllByRole('listitem')).toHaveLength(2)
    expect(answer.querySelector('br')).toBeInTheDocument()
  })

  it('does not render raw HTML from model output', () => {
    render(
      <InformationResponse
        response={{
          outcome: 'answered',
          message: 'Nội dung an toàn <script>alert("xss")</script> <b>không tin cậy</b>',
          citations: [],
          suggested_actions: [],
        }}
      />,
    )

    const answer = screen.getByLabelText('Answer content')
    expect(answer.querySelector('script')).not.toBeInTheDocument()
    expect(answer.querySelector('b')).not.toBeInTheDocument()
  })

  it('hides internal suggested actions that have no user-facing label', () => {
    render(
      <InformationResponse
        response={{
          outcome: 'booking_in_progress',
          message: 'Vui lòng bổ sung ngày sinh.',
          citations: [],
          suggested_actions: [{ action_id: 'provide', type: 'provide', label: '' }],
          conversation_state: { mode: 'booking' },
        }}
      />,
    )

    expect(screen.queryByLabelText('Suggested actions')).not.toBeInTheDocument()
    expect(screen.queryByText('Hành động tiếp theo')).not.toBeInTheDocument()
  })

  it('renders the 22 web-source citation shape as safe links in stable order', () => {
    const citations = Array.from({ length: 22 }, (_, index) => ({
      source_id: `HHH-WEB-${String(index + 1).padStart(3, '0')}`,
      source_kind: 'web',
      title: `Nguồn web ${index + 1}`,
      url: `https://benhvientimhanoi.vn/nguon-${index + 1}`,
    }))
    render(<InformationResponse response={{ outcome: 'answered', message: 'Thông tin.', citations, suggested_actions: [] }} />)
    const links = within(screen.getByLabelText('Citations')).getAllByRole('link')
    expect(links).toHaveLength(22)
    expect(links[0]).toHaveTextContent('Nguồn web 1')
    expect(links[21]).toHaveTextContent('Nguồn web 22')
  })

  it('renders all approved local PDF labels as plain text', () => {
    const labels = [
      'Bảng giá dịch vụ kỹ thuật.pdf',
      'Quy trình đón tiếp bệnh nhân.pdf',
      'Biểu giá BHYT.pdf',
    ]
    render(<InformationResponse response={{
      outcome: 'answered',
      message: 'Thông tin.',
      citations: labels.map((label, index) => ({ source_id: `SRC-DOC-${index}`, source_kind: 'document', title: label, display_name: label })),
      suggested_actions: [],
    }} />)
    const section = screen.getByLabelText('Citations')
    labels.forEach((label) => expect(within(section).getByText(label).tagName).toBe('SPAN'))
    expect(within(section).queryByRole('link')).not.toBeInTheDocument()
  })

  it('deduplicates citations by source_id and rejects unsafe links', () => {
    render(<InformationResponse response={{
      outcome: 'answered',
      message: 'Thông tin.',
      citations: [
        { source_id: 'HHH-GEN-001', title: 'Nguồn chính', url: 'javascript:alert(1)' },
        { source_id: 'HHH-GEN-001', title: 'Nguồn trùng', url: 'https://benhvientimhanoi.vn/trung' },
      ],
      suggested_actions: [],
    }} />)
    const section = screen.getByLabelText('Citations')
    expect(within(section).getAllByRole('listitem')).toHaveLength(1)
    expect(within(section).getByText('Nguồn chính').tagName).toBe('SPAN')
    expect(within(section).queryByRole('link')).not.toBeInTheDocument()
    expect(within(section).queryByText('Nguồn trùng')).not.toBeInTheDocument()
  })

  it('suppresses the citation panel throughout booking human-in-the-loop responses', () => {
    render(<InformationResponse response={{
      outcome: 'booking_in_progress',
      message: 'Vui lòng xác nhận thông tin đặt lịch.',
      citations: [{ source_id: 'UNRELATED', title: 'Không liên quan', url: 'https://example.com' }],
      suggested_actions: [{ action_id: 'confirm', type: 'confirm_booking', label: 'Xác nhận đặt lịch' }],
      conversation_state: { mode: 'booking' },
    }} />)
    expect(screen.queryByLabelText('Citations')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Xác nhận đặt lịch' })).toBeInTheDocument()
  })
})
// === TASK:WP-502:END ===
