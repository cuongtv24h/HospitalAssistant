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
  display_name?: string
  source_kind?: string
  source_type?: string
  url?: string
  excerpt?: string
  version?: string
  effective_date?: string
  crawled_at?: string
  publisher?: string
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

export interface ErrorEnvelopeDTO {
  trace_id?: string
  error?: {
    code?: string
    category?: string
    message?: string
  }
}

export interface InformationAssistanceResponse {
  outcome: InformationOutcome
  message: string
  citations: CitationDTO[]
  suggested_actions: SuggestedActionDTO[]
  conversation_state?: Record<string, unknown>
  explainability?: ExplainabilityDTO
  error?: ErrorEnvelopeDTO | null
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

function isSafeHttpUrl(url?: string): boolean {
  if (!url) return false
  return url.startsWith('http://') || url.startsWith('https://')
}

export function InformationResponse({ response, onSuggestedAction }: InformationResponseProps) {
  const isOutOfScopeRefusal = response.outcome === 'refused'
    && (response.error?.error?.code === 'OUT_OF_SCOPE'
      || response.message === 'Xin lỗi, tôi chỉ hỗ trợ đặt lịch khám và thông tin chính thức về khám chữa bệnh, BHYT, giá dịch vụ, giờ làm việc, bác sĩ và chuyên khoa tại Bệnh viện Tim Hà Nội.')

  if (isOutOfScopeRefusal) {
    return (
      <article className="info-response" aria-label="Information assistance response">
        <div className="markdown-answer" aria-label="Answer content">
          <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} skipHtml>
            {response.message}
          </ReactMarkdown>
        </div>
      </article>
    )
  }

  const showUncertainNotice = isUncertain(response.outcome)
  const isBooking = response.conversation_state?.mode === 'booking'
    || response.outcome === 'booking_in_progress'
    || response.outcome === 'appointment_pending'
  const visibleActions = response.suggested_actions.filter((action) => Boolean(action.label?.trim()))
  const seenSourceIds = new Set<string>()
  const visibleCitations = response.citations.filter((citation) => {
    if (!citation.source_id || seenSourceIds.has(citation.source_id)) return false
    seenSourceIds.add(citation.source_id)
    return true
  })

  return (
    <article className="info-response" aria-label="Information assistance response">
      <header>
        <p className="info-response__outcome" aria-label="Response outcome">{outcomeLabel(response.outcome)}</p>
        {showUncertainNotice ? (
          <p className="info-response__notice" role="alert">
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

      {!isBooking ? (
        <section className="info-response__citations" aria-label="Citations">
          <h3>Nguồn tham khảo</h3>
          {visibleCitations.length > 0 ? (
            <ul>
              {visibleCitations.map((citation) => {
                const label = citation.display_name || citation.title || citation.source_id
                const hasSafeLink = citation.source_kind !== 'document' && isSafeHttpUrl(citation.url)
                return (
                  <li key={citation.source_id}>
                    {hasSafeLink ? (
                      <a href={citation.url} target="_blank" rel="noreferrer">
                        {label}
                      </a>
                    ) : (
                      <span>{label}</span>
                    )}
                    {citation.effective_date ? <span> — hiệu lực {citation.effective_date}</span> : null}
                    {citation.excerpt ? (
                      <blockquote>
                        <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} skipHtml>
                          {citation.excerpt}
                        </ReactMarkdown>
                      </blockquote>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          ) : (
            <p>Không có nguồn chính thức được đính kèm.</p>
          )}
        </section>
      ) : null}

      {visibleActions.length > 0 ? (
        <section className="info-response__actions" aria-label="Suggested actions">
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
