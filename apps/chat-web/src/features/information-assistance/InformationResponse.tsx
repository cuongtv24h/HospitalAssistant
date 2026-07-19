// === TASK:WP-502:START ===
export type InformationOutcome =
  | 'answered'
  | 'clarification_required'
  | 'fallback'
  | 'refused'
  | 'emergency_rerouted'
  | (string & {})

export interface CitationDTO {
  source_id: string
  title: string
  source_type?: string
  url?: string
  excerpt?: string
  version?: string
  effective_date?: string
}

export interface SuggestedActionDTO {
  action_id: string
  label: string
  type: string
  payload?: Record<string, unknown>
}

export interface ExplainabilityDTO {
  grounded: boolean
  confidence?: 'low' | 'medium' | 'high' | string
  rationale?: string
  source_count?: number
}

export interface InformationAssistanceResponse {
  outcome: InformationOutcome
  message: string
  citations: CitationDTO[]
  suggested_actions: SuggestedActionDTO[]
  conversation_state?: Record<string, unknown>
  explainability?: ExplainabilityDTO
}

export interface InformationResponseProps {
  response: InformationAssistanceResponse
  onSuggestedAction?: (action: SuggestedActionDTO) => void
}

const uncertainOutcomes: InformationOutcome[] = ['clarification_required', 'fallback', 'refused', 'emergency_rerouted']

function outcomeLabel(outcome: InformationOutcome): string {
  switch (outcome) {
    case 'answered':
      return 'Đã trả lời dựa trên nguồn chính thức'
    case 'clarification_required':
      return 'Cần thêm thông tin để trả lời chính xác'
    case 'fallback':
      return 'Chưa đủ căn cứ để trả lời chắc chắn'
    case 'refused':
      return 'Không thể trả lời nội dung này'
    case 'emergency_rerouted':
      return 'Đã chuyển sang hướng dẫn an toàn khẩn cấp'
    case 'booking_in_progress':
      return 'Đang hỗ trợ đặt lịch khám'
    case 'appointment_pending':
      return 'Lịch hẹn đã được ghi nhận và đang chờ xác nhận'
    default:
      return `Trạng thái: ${outcome}`
  }
}

function isUncertain(outcome: InformationOutcome): boolean {
  return uncertainOutcomes.includes(outcome)
}

export function InformationResponse({ response, onSuggestedAction }: InformationResponseProps) {
  const showUncertainNotice = isUncertain(response.outcome)
  const isBooking = response.conversation_state?.mode === 'booking'
    || response.outcome === 'booking_in_progress'
    || response.outcome === 'appointment_pending'
  const visibleActions = response.suggested_actions.filter((action) => Boolean(action.label?.trim()))

  return (
    <article aria-label="Information assistance response">
      <header>
        <p aria-label="Response outcome">{outcomeLabel(response.outcome)}</p>
        {showUncertainNotice ? (
          <p role="alert">
            Nội dung này không được hiển thị như câu trả lời chắc chắn. Vui lòng xem hướng dẫn tiếp theo hoặc cung cấp
            thêm thông tin.
          </p>
        ) : null}
      </header>

      <div className="markdown-answer" aria-label="Answer content">
        <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} skipHtml>
          {response.message}
        </ReactMarkdown>
      </div>

      {!isBooking ? <section aria-label="Citations">
        <h3>Nguồn tham khảo</h3>
        {response.citations.length > 0 ? (
          <ul>
            {response.citations.map((citation) => (
              <li key={citation.source_id}>
                {citation.url ? (
                  <a href={citation.url} target="_blank" rel="noreferrer">
                    {citation.title}
                  </a>
                ) : (
                  <span>{citation.title}</span>
                )}
                {citation.effective_date ? <span> — hiệu lực {citation.effective_date}</span> : null}
                {citation.excerpt ? <blockquote>{citation.excerpt}</blockquote> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p>Không có nguồn chính thức được đính kèm.</p>
        )}
      </section> : null}

      {visibleActions.length > 0 ? (
        <section aria-label="Suggested actions">
          <h3>Hành động tiếp theo</h3>
          <ul>
            {visibleActions.map((action) => (
              <li key={action.action_id}>
                <button type="button" onClick={() => onSuggestedAction?.(action)}>{action.label}</button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  )
}
// === TASK:WP-502:END ===
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
