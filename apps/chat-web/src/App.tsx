// === TASK:WP-500:START ===
import { FormEvent, useEffect, useRef, useState } from 'react'
import { MicrophoneButton } from './speech/MicrophoneButton'
import { ChatClient, type ChatCapability } from './shared/ChatClient'

type Flow = 'appointment' | 'preparation' | 'insurance_cost' | 'doctor_info'
type FlowState = { flow?: Flow; step?: string; data: Record<string, string> }
type ChatMessage = { id: string; side: 'assistant' | 'user'; text: string; actions?: ChatAction[] }
type ChatAction = { label: string; value: string; context?: Record<string, string> }

type IconName = 'refresh' | 'user' | 'chevron-right' | 'sun' | 'moon'

const sessionId = `web-${crypto.randomUUID()}`

const actionCards = [
  { id: 'appointment', icon: '📅', title: 'Đặt hoặc tra cứu lịch hẹn', subtitle: 'Đặt lịch mới, xem lịch trống, tra mã hẹn', context: { flow: 'appointment' } },
  { id: 'preparation', icon: '🧾', title: 'Chuẩn bị đi khám / tái khám', subtitle: 'Giấy tờ, quy trình, những điều cần biết', context: { flow: 'preparation' } },
  { id: 'insurance_cost', icon: '🏥', title: 'BHYT & chi phí', subtitle: 'Quyền lợi, giấy tờ BHYT, bảng giá dịch vụ', context: { flow: 'insurance_cost' } },
  { id: 'doctor_info', icon: '👨‍⚕️', title: 'Bác sĩ, khoa & giờ làm việc', subtitle: 'Tìm bác sĩ, chuyên khoa, lịch khám', context: { flow: 'doctor_info' } },
] as const

const specialties = ['Tim mạch', 'Nội tổng hợp', 'Khám nhi', 'Cấp cứu tim mạch']
const doctors = ['BS. Nguyễn Minh Anh', 'ThS.BS. Trần Quốc Bình', 'BS.CKII. Lê Thu Hà']
const slots = ['Thứ 2, 20/07 · 08:30', 'Thứ 3, 21/07 · 14:00', 'Thứ 5, 23/07 · 09:15']
const onboardingMessages = ['Xin chào! Tôi là trợ lý AI của Bệnh viện Tim Hà Nội.', 'Bạn đang cần tôi hỗ trợ về vấn đề gì?'] as const
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

function Icon({ name }: { name: IconName }) {
  return <svg className="app-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
    {name === 'refresh' ? <><path d="M20 11a8.1 8.1 0 0 0-14.9-3L3 10" /><path d="M3 4v6h6M4 13a8.1 8.1 0 0 0 14.9 3L21 14" /><path d="M21 20v-6h-6" /></> : null}
    {name === 'user' ? <><circle cx="12" cy="8" r="3.2" /><path d="M5.5 20a6.5 6.5 0 0 1 13 0" /></> : null}
    {name === 'chevron-right' ? <path d="m9 18 6-6-6-6" /> : null}
    {name === 'sun' ? <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></> : null}
    {name === 'moon' ? <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/> : null}
  </svg>
}

function normalize(text: string) { return text.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd') }
function isClearAppointmentIntent(text: string) {
  const plain = normalize(text)
  return /\b(dat\s+(cho|lich|kham|hen)|book\s+(lich|kham|hen)|dang\s+ky\s+kham|muon\s+dat\s+(cho|lich|kham|hen)|can\s+dat\s+(cho|lich|kham|hen)|hen\s+kham|lich\s+kham)\b/.test(plain)
}
function detectIntentFlow(text: string): Flow | undefined {
  const plain = normalize(text)
  if (isClearAppointmentIntent(text)) return 'appointment'
  if (/\b(bhyt|bao hiem|vien phi|chi phi|chi phí|bang gia|gia kham|gia xet nghiem|gia dich vu|chuyen tuyen|the bhyt|vssid)\b/.test(plain)) return 'insurance_cost'
  if (/\b(bac si|bác sĩ|chuyen khoa|khoa nao|gio lam|gio kham|lich bac si|phong kham)\b/.test(plain)) return 'doctor_info'
  if (/\b(chuan bi|giay to|tai kham|nhap vien|can mang)\b/.test(plain)) return 'preparation'
  return undefined
}
function inferSpecialty(text: string) {
  const plain = normalize(text)
  if (/tim|nguc|mach|huyet ap|hoi hop|kho tho/.test(plain)) return 'Tim mạch'
  if (/tre|nhi|be|con toi/.test(plain)) return 'Khám nhi'
  if (/cap cuu|dau nguc du doi|ngat/.test(plain)) return 'Cấp cứu tim mạch'
  return ''
}
function validatePhone(value: string) { return /^(0|\+84)\d{8,10}$/.test(value.replace(/\s/g, '')) }
function validateYear(value: string) { const year = Number(value); return year >= 1900 && year <= new Date().getFullYear() }
function hasExplicitBookingConfirmation(state: FlowState) { return state.flow === 'appointment' && (state.step === 'confirm' || state.step === 'done') && Boolean(state.data.patient_name && state.data.patient_phone && state.data.birth_year && state.data.specialty && state.data.slot) }
function isUnsafeAppointmentCompletionText(text: string, state: FlowState) {
  if (hasExplicitBookingConfirmation(state)) return false
  const plain = normalize(text)
  return /(che do thu nghiem|\bdemo\b|mo phong|dat lich thanh cong|ghi nhan.*(dat lich|lich hen|yeu cau dat)|ma hen|hen-\d{4})/.test(plain)
}

type BackendAction = string | { label?: string; title?: string; value?: string; action?: string; context?: Record<string, string> }
type BackendResult = {
  message?: string
  prompt?: string
  answer?: string
  suggested_actions?: BackendAction[]
  actions?: BackendAction[]
  conversation_state?: Record<string, unknown>
}

function App() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => (globalThis.localStorage?.getItem('app-theme') as 'dark' | 'light') || 'light')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [flowState, setFlowState] = useState<FlowState>({ data: {} })
  const [onboardingComplete, setOnboardingComplete] = useState(false)
  const [welcomeTyping, setWelcomeTyping] = useState(true)
  const [onboardingCycle, setOnboardingCycle] = useState(0)
  const [backendThinking, setBackendThinking] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    async function playWelcome() {
      setMessages([]); setOnboardingComplete(false); setWelcomeTyping(false)
      for (let index = 0; index < onboardingMessages.length; index += 1) {
        setWelcomeTyping(true); await new Promise((resolve) => setTimeout(resolve, import.meta.env.TEST ? 0 : 350))
        if (cancelled) return
        setWelcomeTyping(false)
        setMessages((current) => [...current, { id: `welcome-${onboardingCycle}-${index}`, side: 'assistant', text: onboardingMessages[index] }])
      }
      setOnboardingComplete(true)
    }
    void playWelcome()
    return () => { cancelled = true }
  }, [onboardingCycle])

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); globalThis.localStorage?.setItem('app-theme', theme) }, [theme])
  useEffect(() => { endRef.current?.scrollIntoView?.({ behavior: 'smooth' }) }, [messages, welcomeTyping, backendThinking])

  function addAssistant(text: string, actions: ChatAction[] = []) { setMessages((current) => [...current, { id: crypto.randomUUID(), side: 'assistant', text, actions }]) }
  function addUser(text: string) { setMessages((current) => [...current, { id: crypto.randomUUID(), side: 'user', text }]) }

  function startFlow(flow: Flow) {
    const hidden = { flow }
    setFlowState({ flow, step: flow === 'appointment' ? 'intent' : 'menu', data: { session_id: sessionId } })
    if (flow === 'appointment') addAssistant('Bạn muốn đặt lịch mới hay tra cứu lịch hẹn đã có?', [
      { label: '📅 Đặt lịch mới', value: 'booking_new', context: hidden }, { label: '🔍 Tra cứu lịch hẹn', value: 'lookup', context: hidden },
    ])
    if (flow === 'preparation') addAssistant('Bạn thuộc trường hợp nào để tôi hướng dẫn chuẩn bị đi khám?', [
      { label: 'Khám lần đầu', value: 'first_visit', context: hidden }, { label: 'Tái khám', value: 'revisit', context: hidden }, { label: 'Nhập viện', value: 'admission', context: hidden }, { label: 'Chưa rõ cần chuẩn bị gì', value: 'unclear', context: hidden },
    ])
    if (flow === 'insurance_cost') addAssistant('Bạn muốn hỏi về vấn đề nào?', [
      { label: 'Quyền lợi BHYT', value: 'benefits', context: hidden }, { label: 'Giấy chuyển tuyến', value: 'referral', context: hidden }, { label: 'Giấy tờ cần mang', value: 'documents', context: hidden }, { label: 'Giá khám', value: 'exam_price', context: hidden }, { label: 'Giá xét nghiệm / dịch vụ', value: 'service_price', context: hidden },
    ])
    if (flow === 'doctor_info') addAssistant('Bạn muốn tìm thông tin bác sĩ, chuyên khoa hay giờ làm việc?', [
      { label: 'Tìm bác sĩ', value: 'doctor_search', context: hidden }, { label: 'Danh sách chuyên khoa', value: 'specialty_list', context: hidden }, { label: 'Giờ làm việc', value: 'work_hours', context: hidden }, { label: 'Vị trí phòng khám', value: 'clinic_location', context: hidden },
    ])
  }

  function handleAction(action: ChatAction) {
    addUser(action.label)
    const contextFlow = action.context?.flow
    if ((contextFlow === 'insurance_cost' || contextFlow === 'preparation' || contextFlow === 'doctor_info' || contextFlow === 'appointment') && contextFlow !== flowState.flow) return startFlow(contextFlow)
    route(action.value)
  }

  function route(value: string) {
    const flow = flowState.flow
    if (value === 'start_over') return restartConversation()
    if (value.startsWith('backend:')) return callBackendFallback(value.split(':').slice(2).join(':') || value, 'information_assistance')
    if (flow === 'appointment') return routeAppointment(value)
    if (flow === 'preparation') return addAssistant(preparationResponse(value), followUps())
    if (flow === 'insurance_cost') return routeInsuranceCost(value)
    if (flow === 'doctor_info') return addAssistant(doctorInfoResponse(value), followUps())
  }

  function routeAppointment(value: string) {
    const data = { ...flowState.data }
    if (value === 'booking_new') { setFlowState({ flow: 'appointment', step: 'visit_type', data }); return addAssistant('Bạn đặt lịch cho loại lượt khám nào?', [{ label: 'Khám lần đầu', value: 'first_visit' }, { label: 'Tái khám', value: 'follow_up' }]) }
    if (value === 'lookup') { setFlowState({ flow: 'appointment', step: 'lookup', data }); return addAssistant('Vui lòng nhập mã hẹn, ví dụ HEN-2026-0001. Nếu chưa nhớ mã, hãy nhập số điện thoại để tôi tra cứu theo thông tin bạn cung cấp.') }
    if (['first_visit', 'follow_up'].includes(value)) { data.visit_type = value; setFlowState({ flow: 'appointment', step: 'specialty', data }); return addAssistant('Bạn muốn khám chuyên khoa nào? Nếu chưa rõ, hãy mô tả triệu chứng.', specialties.map((item) => ({ label: item, value: `specialty:${item}` }))) }
    if (value.startsWith('specialty:')) { data.specialty = value.split(':')[1]; setFlowState({ flow: 'appointment', step: 'doctor', data }); return addAssistant(`Đã chọn ${data.specialty}. Bạn muốn chọn bác sĩ nào?`, [...doctors.map((item) => ({ label: item, value: `doctor:${item}` })), { label: 'Bất kỳ bác sĩ phù hợp', value: 'doctor:any' }]) }
    if (value.startsWith('doctor:')) { data.doctor = value.split(':')[1] === 'any' ? 'Bác sĩ phù hợp sớm nhất' : value.split(':')[1]; setFlowState({ flow: 'appointment', step: 'slot', data }); return addAssistant(`Đã chọn ${data.doctor}. Các khung giờ còn trống:`, slots.map((item) => ({ label: item, value: `slot:${item}` }))) }
    if (value.startsWith('slot:')) { data.slot = value.split(':').slice(1).join(':'); setFlowState({ flow: 'appointment', step: 'patient', data }); return addAssistant('Vui lòng nhập: Họ tên, số điện thoại, năm sinh. Ví dụ: Nguyễn Văn A, 0912345678, 1985') }
    if (value === 'confirm_booking') { setFlowState({ flow: 'appointment', step: 'done', data }); return addAssistant(`Đặt lịch thành công. Mã hẹn: HEN-2026-0420. ${data.patient_name || 'Người bệnh'} khám ${data.specialty} lúc ${data.slot}. Vui lòng đến trước 15 phút và mang giấy tờ tùy thân/BHYT nếu có.`, followUps()) }
    if (value === 'edit_booking') { setFlowState({ flow: 'appointment', step: 'specialty', data }); return addAssistant('Bạn muốn chỉnh lại chuyên khoa trước khi xác nhận?', specialties.map((item) => ({ label: item, value: `specialty:${item}` }))) }
    if (value === 'cancel_booking') { setFlowState({ flow: 'appointment', step: 'cancelled', data }); return addAssistant('Tôi đã hủy thao tác đặt lịch trong phiên này. Bạn có thể bắt đầu lại khi cần.', followUps()) }
  }

  async function handleFreeText(text: string) {
    addUser(text)
    const plain = normalize(text)
    const intentFlow = detectIntentFlow(text)
    if (!flowState.flow) {
      if (intentFlow) return startFlow(intentFlow)
      if (/\b(lich|hen|dat)\b/.test(plain)) return startFlow('appointment')
      return callBackendFallback(text, 'information_assistance')
    }
    if (intentFlow && intentFlow !== flowState.flow) return startFlow(intentFlow)
    if (flowState.flow === 'appointment') return handleAppointmentText(text)
    return callBackendFallback(text, 'information_assistance')
  }

  function backendActionsToChatActions(actions: BackendAction[] = []): ChatAction[] {
    const knownValues = new Set(['start_over', 'booking_new', 'lookup', 'first_visit', 'follow_up', 'benefits', 'referral', 'documents', 'exam_price', 'service_price', 'doctor_search', 'specialty_list', 'work_hours', 'clinic_location', 'revisit', 'admission', 'unclear'])
    return actions.map((action, index): ChatAction | undefined => {
      if (typeof action === 'string') return { label: action, value: `backend:${index}:${action}` }
      const label = action.label || action.title || action.value || action.action || ''
      const value = action.value || action.action || ''
      const contextFlow = action.context?.flow
      if (contextFlow === 'insurance_cost' || contextFlow === 'preparation' || contextFlow === 'doctor_info' || contextFlow === 'appointment') return { label: label || 'Mở luồng phù hợp', value: value || `backend:${index}:${label}`, context: action.context }
      if (value && (knownValues.has(value) || value.startsWith('specialty:') || value.startsWith('doctor:') || value.startsWith('slot:'))) return { label, value, context: action.context }
      if (label.trim()) return { label, value: `backend:${index}:${label}` }
      return undefined
    }).filter((action): action is ChatAction => Boolean(action?.label.trim()))
  }

  async function callBackendFallback(text: string, capability: ChatCapability, extraContext: Record<string, string> = {}) {
    setBackendThinking(true)
    try {
      const client = new ChatClient({ baseUrl: apiBaseUrl })
      const envelope = await client.send<Record<string, unknown>, BackendResult>({
        capability,
        payload: {
          request_id: crypto.randomUUID(),
          session_id: sessionId,
          message: text,
          conversation_history: messages.slice(-12).map((item) => ({ role: item.side === 'assistant' ? 'assistant' : 'user', content: item.text })),
          response_mode: 'sync',
          ...(capability === 'appointment_booking' ? { form_data: flowState.data } : { button_context: { ...flowState.data, ...extraContext, flow: flowState.flow, step: flowState.step } }),
        },
        context: { channel: 'web_page', locale: 'vi-VN', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone },
      })
      const result = envelope.result || {}
      const backendState = result.conversation_state || {}
      const backendFlow = typeof backendState.flow === 'string' ? backendState.flow : undefined
      const actionFlow = [...(result.suggested_actions || []), ...(result.actions || [])].find((action) => typeof action !== 'string' && typeof action.context?.flow === 'string')
      const switchedFlow = backendFlow || (typeof actionFlow !== 'string' ? actionFlow?.context?.flow : undefined)
      if (switchedFlow === 'insurance_cost' || switchedFlow === 'preparation' || switchedFlow === 'doctor_info' || switchedFlow === 'appointment') return startFlow(switchedFlow)
      const textToShow = result.message || result.prompt || result.answer || 'Tôi đã nhận thông tin. Bạn có thể mô tả thêm nhu cầu để tôi hỗ trợ đúng luồng.'
      if (capability === 'appointment_booking' && isUnsafeAppointmentCompletionText(textToShow, flowState)) return startFlow('appointment')
      const actions = backendActionsToChatActions(result.suggested_actions || result.actions)
      addAssistant(textToShow, actions)
      if (result.conversation_state) setFlowState((current) => ({ ...current, data: { ...current.data, backend_context: JSON.stringify(result.conversation_state) } }))
    } catch {
      const isOfficialCostPolicyRequest = flowState.flow === 'insurance_cost' || extraContext.requires_official_source === 'true'
      addAssistant(isOfficialCostPolicyRequest
        ? 'Hiện tôi chưa truy xuất được dữ liệu chính thức từ hệ thống/RAG cho thông tin BHYT, viện phí hoặc bảng giá dịch vụ. Vui lòng kiểm tra tại quầy viện phí, quầy BHYT hoặc kênh liên hệ chính thức của bệnh viện; tôi sẽ không tự đưa số tiền hay quyền lợi khi chưa có nguồn chính thức.'
        : 'Hiện tôi chưa kết nối được hệ thống AI/backend để xử lý nội dung tự do. Bạn có thể chọn một nút gợi ý bên dưới hoặc thử lại sau.', followUps())
    } finally {
      setBackendThinking(false)
    }
  }

  function handleAppointmentText(text: string) {
    const intentFlow = detectIntentFlow(text)
    if (intentFlow && intentFlow !== 'appointment') return startFlow(intentFlow)
    const data = { ...flowState.data }
    if (flowState.step === 'lookup') return addAssistant(text.toUpperCase().includes('HEN-') ? `Kết quả tra cứu: mã ${text.trim()} đang ở trạng thái đã xác nhận, lịch khám dự kiến 20/07/2026 lúc 08:30 tại quầy khám Tim mạch.` : 'Tôi chưa tìm thấy mã hẹn khớp với thông tin bạn cung cấp. Vui lòng nhập mã hẹn hoặc số điện thoại chính xác hơn.', followUps())
    if (flowState.step === 'specialty') {
      const inferred = inferSpecialty(text)
      if (inferred) { data.specialty = inferred; setFlowState({ flow: 'appointment', step: 'doctor', data }); return addAssistant(`Dựa trên mô tả, tôi gợi ý chuyên khoa ${inferred}. Bạn muốn chọn bác sĩ nào?`, [...doctors.map((item) => ({ label: item, value: `doctor:${item}` })), { label: 'Bất kỳ bác sĩ phù hợp', value: 'doctor:any' }]) }
      return callBackendFallback(text, 'appointment_booking')
    }
    if (flowState.step === 'patient') {
      const parts = text.split(',').map((part) => part.trim())
      const phone = parts.find((part) => /^(0|\+84)\d[\d\s]{7,11}$/.test(part)) || ''
      const year = parts.find((part) => /^\d{4}$/.test(part)) || ''
      if (!phone || !validatePhone(phone)) return addAssistant('Số điện thoại chưa hợp lệ. Vui lòng nhập lại theo mẫu: Nguyễn Văn A, 0912345678, 1985')
      if (!year || !validateYear(year)) return addAssistant('Năm sinh chưa hợp lệ. Vui lòng nhập năm sinh từ 1900 đến năm hiện tại, ví dụ: Nguyễn Văn A, 0912345678, 1985')
      data.patient_name = parts[0] || 'Người bệnh'; data.patient_phone = phone; data.birth_year = year
      setFlowState({ flow: 'appointment', step: 'confirm', data })
      return addAssistant(`Vui lòng kiểm tra: ${data.patient_name}, SĐT ${data.patient_phone}, năm sinh ${data.birth_year}, ${data.visit_type === 'follow_up' ? 'tái khám' : 'khám lần đầu'}, chuyên khoa ${data.specialty}, bác sĩ ${data.doctor}, khung giờ ${data.slot}.`, [{ label: 'Xác nhận đặt lịch', value: 'confirm_booking' }, { label: 'Chỉnh sửa', value: 'edit_booking' }, { label: 'Hủy', value: 'cancel_booking' }])
    }
    void callBackendFallback(text, 'appointment_booking')
  }

  function followUps(): ChatAction[] { return [{ label: 'Trở lại', value: 'start_over' }] }
  function preparationResponse(value: string) {
    const map: Record<string, string> = {
      first_visit: 'Khám lần đầu: vui lòng mang CCCD/hộ chiếu, thẻ BHYT nếu có, giấy chuyển tuyến nếu cần, hồ sơ bệnh án/cận lâm sàng cũ. Nên đến trước giờ hẹn 15–30 phút để làm thủ tục.',
      revisit: 'Tái khám: mang sổ/phiếu hẹn tái khám, đơn thuốc đang dùng, kết quả xét nghiệm/cận lâm sàng gần nhất, giấy tờ tùy thân và BHYT nếu có.',
      admission: 'Nhập viện: chuẩn bị giấy nhập viện, CCCD, BHYT, giấy chuyển tuyến nếu có, đồ dùng cá nhân cơ bản và thông tin người nhà liên hệ.',
      unclear: 'Nếu chưa rõ trường hợp, hãy cho biết bạn đi khám lần đầu, tái khám theo hẹn, hay được chỉ định nhập viện. Trước mắt nên chuẩn bị CCCD, BHYT và hồ sơ y tế cũ.',
    }
    return map[value] || map.unclear
  }
  function routeInsuranceCost(value: string) {
    const queryByAction: Record<string, string> = {
      benefits: 'Quyền lợi BHYT tại Bệnh viện Tim Hà Nội, điều kiện hưởng, phạm vi thanh toán và lưu ý khi không có BHYT',
      referral: 'Quy định giấy chuyển tuyến và điều kiện hưởng BHYT đúng tuyến tại Bệnh viện Tim Hà Nội',
      documents: 'Giấy tờ cần mang để làm thủ tục BHYT tại Bệnh viện Tim Hà Nội',
      exam_price: 'Giá khám chuyên khoa, khám Giáo sư Phó Giáo sư và bảng giá khám Bệnh viện Tim Hà Nội',
      service_price: 'Bảng giá xét nghiệm, cận lâm sàng và dịch vụ kỹ thuật Bệnh viện Tim Hà Nội',
    }
    const query = queryByAction[value]
    if (!query) return addAssistant('Bạn vui lòng chọn một nhóm thông tin BHYT hoặc chi phí để tôi truy xuất từ nguồn chính thức.', followUps())
    void callBackendFallback(query, 'information_assistance', { selected_action: value, requires_official_source: 'true', source_requirement: 'rag_or_backend_citations' })
  }
  function doctorInfoResponse(value: string) {
    const map: Record<string, string> = {
      doctor_search: `Danh sách bác sĩ tham khảo: ${doctors.join('; ')}. Bạn có thể nhập tên bác sĩ hoặc chọn chuyên khoa để lọc lịch khám.`,
      specialty_list: `Các chuyên khoa phổ biến: ${specialties.join(', ')}. Nếu có triệu chứng, tôi có thể gợi ý chuyên khoa phù hợp.`,
      work_hours: 'Giờ làm việc tham khảo: khám ngoại trú từ Thứ 2–Thứ 6 07:30–16:30, Thứ 7 07:30–11:30. Cấp cứu tiếp nhận 24/7.',
      clinic_location: 'Vị trí phòng khám tham khảo: khu khám ngoại trú tầng 1; quầy tiếp đón hướng dẫn phân luồng theo chuyên khoa và mã hẹn.',
    }
    return map[value] || 'Bạn vui lòng chọn tìm bác sĩ, chuyên khoa, giờ làm việc hoặc vị trí phòng khám.'
  }

  function submitChat(event: FormEvent) { event.preventDefault(); if (!input.trim() || backendThinking) return; const value = input.trim(); setInput(''); void handleFreeText(value) }
  function restartConversation() { setInput(''); setFlowState({ data: {} }); setMessages([]); setWelcomeTyping(true); setOnboardingComplete(false); setOnboardingCycle((current) => current + 1) }
  function appendDictatedText(text: string) { setInput((current) => current.trim() ? `${current.trimEnd()} ${text.trim()}` : text.trim()) }
  const isWelcomeExperience = messages.every((item) => item.id.startsWith('welcome-'))

  return <main className="chat-page" aria-label="Hospital Assistant chat">
    <section className="chat-shell">
      <header className="chat-header"><div className="brand-mark" style={{ padding: 0, overflow: 'hidden' }}><img src="/agent-avatar.png" alt="Hospital Assistant" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /></div><div><h1>Trợ lý Bệnh viện</h1><span><i /> Trực tuyến · Hỗ trợ 24/7</span></div><button className="new-chat" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} style={{ marginLeft: 'auto', padding: '9px', borderRadius: '50%', width: '38px', height: '38px', display: 'grid', placeItems: 'center' }} aria-label="Đổi giao diện"><Icon name={theme === 'dark' ? 'sun' : 'moon'} /></button><button className="new-chat" style={{ marginLeft: '8px' }} onClick={restartConversation}><Icon name="refresh" />Cuộc trò chuyện mới</button></header>
      <section className={`conversation ${isWelcomeExperience ? 'conversation--welcome' : ''}`} aria-live="polite">
        {messages.map((item) => <article key={item.id} className={`message ${item.side} ${item.id.startsWith('welcome-') ? 'message--welcome' : ''}`}>{!item.id.startsWith('welcome-') ? <div className="avatar" style={item.side === 'assistant' ? { padding: 0, overflow: 'hidden' } : undefined}>{item.side === 'assistant' ? <img src="/agent-avatar.png" alt="AI" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <Icon name="user" />}</div> : null}<div className="bubble"><p>{item.text}</p>{item.actions?.length ? <div className="message-actions">{item.actions.map((action) => <button key={action.value + action.label} onClick={() => handleAction(action)}>{action.label}</button>)}</div> : null}</div></article>)}
        {isWelcomeExperience && onboardingComplete ? <div className="quick-actions-wrapper"><section className="quick-actions quick-actions--revealed" aria-label="Gợi ý hỗ trợ"><div>{actionCards.map((action) => <button key={action.id} onClick={() => { addUser(action.title); startFlow(action.id) }} data-flow={action.context.flow}><b className="emoji-icon">{action.icon}</b><span><strong>{action.title}</strong><br/><em>{action.subtitle}</em></span><small><Icon name="chevron-right" /></small></button>)}</div></section></div> : null}
        {welcomeTyping || backendThinking ? <div className="typing"><i /><i /><i /> {backendThinking ? 'Vui lòng chờ tôi tra cứu…' : 'Đang soạn tin…'}</div> : null}
        <div ref={endRef} />
      </section>
      <footer className="composer"><form onSubmit={submitChat} style={{ minHeight: '46px', padding: '4px 4px 4px 18px' }}><textarea rows={1} aria-label="Nội dung" aria-keyshortcuts="Enter" title="Nhấn Enter để gửi, Shift + Enter để xuống dòng" placeholder="Nhập câu hỏi của bạn…" value={input} onChange={(e) => { setInput(e.target.value); e.target.style.height = '26px'; e.target.style.height = e.target.scrollHeight + 'px' }} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} style={{ height: '26px', minHeight: '26px', padding: '0', fontSize: '16px', lineHeight: '26px', margin: 0, overflow: 'hidden' }} /><MicrophoneButton onTranscript={appendDictatedText} /><button className="send-button" aria-label="Gửi tin nhắn" title="Gửi tin nhắn" disabled={!input.trim() || backendThinking} style={{ width: '36px', height: '36px', padding: 0 }}><svg className="send-icon" viewBox="0 0 24 24" aria-hidden="true" style={{ width: '18px', height: '18px' }}><path d="M21.4 3.6 13.8 21l-3.2-7.2L3 10.6 21.4 3.6Z" /><path d="m10.6 13.8 4.9-4.9" /></svg></button></form><p>Thông tin chỉ mang tính tham khảo, không thay thế tư vấn y tế trực tiếp.</p></footer>
    </section>
  </main>
}

export default App
// === TASK:WP-500:END ===
