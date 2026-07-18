// === TASK:WP-500:START ===
import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { AppointmentFlow, type AppointmentBookingResponse, type AppointmentStatusResponse } from './features/appointments/AppointmentFlow'
import { EmergencyBanner, type EmergencySafetyResponse } from './features/emergency-safety/EmergencyBanner'
import { InformationResponse, type InformationAssistanceResponse } from './features/information-assistance/InformationResponse'
import { ChatClient, ChatClientError, type ChatCapability, type CapabilityResponseEnvelope, type FoundationPage } from './shared/ChatClient'
import { MicrophoneButton } from './speech/MicrophoneButton'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
const sessionId = `web-${crypto.randomUUID()}`

type Specialty = { specialty_id: string; name: string; description?: string }
type Doctor = { doctor_id: string; full_name: string; title: string; profile_summary?: string }
type AvailableSlot = { slot_id: string; date: string; time: string; room: string }
type BookingStep = 'specialty' | 'doctor' | 'slot' | 'patient'
type ChatMessage = { id: string; side: 'assistant' | 'user'; text?: string; envelope?: CapabilityResponseEnvelope }
type IconName = 'medical-cross' | 'banknote' | 'clipboard' | 'shield-check' | 'calendar-plus' | 'calendar-search' | 'alert-triangle' | 'refresh' | 'user' | 'chevron-right' | 'arrow-left' | 'sun' | 'moon'

function Icon({ name }: { name: IconName }) {
  return <svg className="app-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
    {name === 'medical-cross' ? <path d="M12 4v16M4 12h16" /> : null}
    {name === 'banknote' ? <><rect x="3" y="6" width="18" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /><path d="M7 9h.01M17 15h.01" /></> : null}
    {name === 'clipboard' ? <><rect x="5" y="4" width="14" height="17" rx="2" /><path d="M9 4.5h6v3H9zM9 12h6M9 16h4" /></> : null}
    {name === 'shield-check' ? <><path d="M12 3 19 6v5c0 4.6-2.8 8-7 10-4.2-2-7-5.4-7-10V6l7-3Z" /><path d="m9 12 2 2 4-4" /></> : null}
    {name === 'calendar-plus' ? <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4M17 3v4M3 10h18M12 14v4M10 16h4" /></> : null}
    {name === 'calendar-search' ? <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4M17 3v4M3 10h11" /><circle cx="15.5" cy="15.5" r="2.5" /><path d="m17.5 17.5 2 2" /></> : null}
    {name === 'alert-triangle' ? <><path d="M10.3 4.5 2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.5a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" /></> : null}
    {name === 'refresh' ? <><path d="M20 11a8.1 8.1 0 0 0-14.9-3L3 10" /><path d="M3 4v6h6M4 13a8.1 8.1 0 0 0 14.9 3L21 14" /><path d="M21 20v-6h-6" /></> : null}
    {name === 'user' ? <><circle cx="12" cy="8" r="3.2" /><path d="M5.5 20a6.5 6.5 0 0 1 13 0" /></> : null}
    {name === 'chevron-right' ? <path d="m9 18 6-6-6-6" /> : null}
    {name === 'arrow-left' ? <><path d="M19 12H5" /><path d="m11 18-6-6 6-6" /></> : null}
    {name === 'sun' ? <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></> : null}
    {name === 'moon' ? <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/> : null}
  </svg>
}

const quickActions = [
  { id: 'price', icon: 'banknote', title: 'Giá dịch vụ', prompt: 'Cho tôi biết bảng giá dịch vụ kỹ thuật.' },
  { id: 'process', icon: 'clipboard', title: 'Quy trình khám', prompt: 'Hướng dẫn quy trình tiếp đón và khám bệnh.' },
  { id: 'insurance', icon: 'shield-check', title: 'Thông tin BHYT', prompt: 'Tôi cần hướng dẫn khám chữa bệnh bằng BHYT.' },
  { id: 'booking', icon: 'calendar-plus', title: 'Đặt lịch khám', prompt: '' },
  { id: 'status', icon: 'calendar-search', title: 'Tra cứu lịch hẹn', prompt: '' },
  { id: 'emergency', icon: 'alert-triangle', title: 'Tình huống khẩn cấp', prompt: 'Tôi cần hỗ trợ khẩn cấp.' },
] as const

const onboardingMessages = [
  'Xin chào bạn, tôi là trợ lý Emy!',
  'Rất vui được hỗ trợ bạn.',
  'Bạn cần tôi hỗ trợ điều gì?',
  'Bạn có thể chọn một trong các mục dưới đây hoặc nhập câu hỏi bằng ngôn ngữ tự nhiên để được tư vấn.',
] as const

function App() {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [input, setInput] = useState('')
  const [mode, setMode] = useState<'chat' | 'booking' | 'status'>('chat')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [onboardingCycle, setOnboardingCycle] = useState(0)
  const [onboardingComplete, setOnboardingComplete] = useState(false)
  const [welcomeTyping, setWelcomeTyping] = useState(true)
  const [specialties, setSpecialties] = useState<Specialty[]>([])
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [slots, setSlots] = useState<AvailableSlot[]>([])
  const [bookingStep, setBookingStep] = useState<BookingStep>('specialty')
  const [booking, setBooking] = useState({ visit_type: 'first_visit', specialty_id: '', doctor_id: '', slot_id: '', patient_name: '', patient_phone: '', patient_dob: '', has_insurance: false, visit_reason: '' })
  const [bookingIdempotencyKey, setBookingIdempotencyKey] = useState<string | null>(null)
  const [referenceLoading, setReferenceLoading] = useState(false)
  const context = useMemo(() => ({ channel: 'web_page' as const, locale: 'vi-VN' as const }), [])
  const client = useMemo(() => new ChatClient({ baseUrl: apiBaseUrl }), [])
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    const timers: number[] = []
    const isTest = import.meta.env.TEST
    
    const typingDelay = isTest ? 0 : 1200
    const readingDelay = isTest ? 0 : 1000
    const revealDelay = isTest ? 0 : 1000
    
    const wait = (duration: number) => new Promise<void>((resolve) => {
      if (duration <= 0) resolve()
      else timers.push(window.setTimeout(resolve, duration))
    })

    async function playWelcome() {
      setMessages([])
      setOnboardingComplete(false)
      setWelcomeTyping(false)

      for (let index = 0; index < onboardingMessages.length; index += 1) {
        setWelcomeTyping(true)
        await wait(typingDelay)
        if (cancelled) return
        
        setWelcomeTyping(false)
        setMessages((current) => [...current, {
          id: `welcome-${onboardingCycle}-${index}`,
          side: 'assistant',
          text: onboardingMessages[index],
        }])
        
        if (index < onboardingMessages.length - 1) {
          await wait(readingDelay)
        } else {
          await wait(revealDelay)
        }
      }

      setOnboardingComplete(true)
    }

    void playWelcome()
    return () => {
      cancelled = true
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [onboardingCycle])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => {
    const target = endRef.current
    if (target && typeof target.scrollIntoView === 'function') {
      const isWelcome = mode === 'chat' && !onboardingComplete
      if (!isWelcome) target.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, loading, mode, bookingStep, welcomeTyping, onboardingComplete])

  useEffect(() => {
    if (mode !== 'booking' || specialties.length) return
    setReferenceLoading(true)
    void client.get<FoundationPage<Specialty>>('/v1/foundation/specialties')
      .then((page) => setSpecialties(page.items))
      .catch(() => setError('Không thể tải danh sách chuyên khoa. Vui lòng thử lại.'))
      .finally(() => setReferenceLoading(false))
  }, [client, mode, specialties.length])

  useEffect(() => {
    if (!booking.specialty_id) return
    setReferenceLoading(true)
    void client.get<FoundationPage<Doctor>>(`/v1/foundation/doctors?specialty_id=${encodeURIComponent(booking.specialty_id)}`)
      .then((page) => setDoctors(page.items))
      .catch(() => setError('Không thể tải danh sách bác sĩ. Vui lòng thử lại.'))
      .finally(() => setReferenceLoading(false))
  }, [booking.specialty_id, client])

  useEffect(() => {
    if (!booking.doctor_id) return
    setReferenceLoading(true)
    void client.get<FoundationPage<AvailableSlot>>(`/v1/foundation/doctors/${encodeURIComponent(booking.doctor_id)}/available-slots`)
      .then((page) => setSlots(page.items))
      .catch(() => setError('Không thể tải khung giờ khám. Vui lòng thử lại.'))
      .finally(() => setReferenceLoading(false))
  }, [booking.doctor_id, client])

  function addUser(text: string) { setMessages((current) => [...current, { id: crypto.randomUUID(), side: 'user', text }]) }
  function addEnvelope(envelope: CapabilityResponseEnvelope) { setMessages((current) => [...current, { id: crypto.randomUUID(), side: 'assistant', envelope }]) }

  async function execute(capability: ChatCapability, text: string, extra: Record<string, unknown> = {}) {
    setLoading(true); setError(null); addUser(text || 'Yêu cầu hỗ trợ')
    const payload = capability === 'appointment_status'
      ? { request_id: crypto.randomUUID(), session_id: sessionId, appointment_reference: { appointment_id: text.trim() }, ...extra }
      : { request_id: crypto.randomUUID(), session_id: sessionId, message: text, ...extra }
    try {
      if (capability === 'information_assistance') {
        await client.sendStream({ capability, payload, context }, (event, envelope) => { if (event === 'completed') addEnvelope(envelope) })
      } else addEnvelope(await client.send({ capability, payload, context }))
    } catch (caught) {
      setError(caught instanceof ChatClientError ? caught.message : 'Không thể kết nối tới dịch vụ. Vui lòng thử lại.')
    } finally { setLoading(false) }
  }

  async function submitChat(event: FormEvent) {
    event.preventDefault()
    if (!input.trim() || loading) return
    const value = input.trim(); setInput('')
    await execute('information_assistance', value)
  }

  async function submitBooking(confirmed = false) {
    const key = bookingIdempotencyKey ?? crypto.randomUUID()
    setBookingIdempotencyKey(key)
    const label = confirmed ? 'Xác nhận đặt lịch' : 'Kiểm tra thông tin đặt lịch'
    setLoading(true); setError(null); addUser(label)
    try {
      const envelope = await client.send({
        capability: 'appointment_booking', context, idempotencyKey: confirmed ? key : undefined,
        payload: { request_id: crypto.randomUUID(), session_id: sessionId, message: confirmed ? 'confirm' : '', form_data: { ...booking, confirmed, idempotency_key: key } },
      })
      addEnvelope(envelope)
      if ((envelope.result as Record<string, unknown>).outcome === 'created') { setBookingIdempotencyKey(null); setMode('chat') }
    } catch (caught) { setError(caught instanceof ChatClientError ? caught.message : 'Không thể xử lý đặt lịch. Vui lòng thử lại.') }
    finally { setLoading(false) }
  }

  function restartConversation() {
    setError(null)
    setInput('')
    setMode('chat')
    setMessages([])
    setOnboardingComplete(false)
    setWelcomeTyping(true)
    setOnboardingCycle((current) => current + 1)
  }

  function chooseAction(action: typeof quickActions[number]) {
    setError(null)
    if (action.id === 'booking') { setMode('booking'); setBookingStep('specialty'); return }
    if (action.id === 'status') { setMode('status'); return }
    void execute(action.id === 'emergency' ? 'emergency_safety' : 'information_assistance', action.prompt)
  }

  function appendDictatedText(text: string) {
    setInput((current) => current.trim() ? `${current.trimEnd()} ${text}` : text)
  }

  function renderEnvelope(envelope: CapabilityResponseEnvelope) {
    const data = envelope.result as Record<string, unknown>
    if (envelope.capability === 'information_assistance') return <InformationResponse response={data as unknown as InformationAssistanceResponse} />
    if (envelope.capability === 'emergency_safety') return <EmergencyBanner response={data as unknown as EmergencySafetyResponse} />
    if (envelope.capability === 'appointment_booking') return <AppointmentFlow bookingResponse={data as unknown as AppointmentBookingResponse} onConfirmBooking={() => void submitBooking(true)} onCancelBooking={() => setMode('chat')} />
    return <AppointmentFlow statusResponse={data as unknown as AppointmentStatusResponse} />
  }

  const isWelcomeExperience = mode === 'chat' && messages.every((item) => item.id.startsWith('welcome-'))

  return <main className="chat-page" aria-label="Hospital Assistant chat">
    <section className="chat-shell">
      <header className="chat-header"><div className="brand-mark"><Icon name="medical-cross" /></div><div><h1>Trợ lý Bệnh viện</h1><span><i /> Trực tuyến · Hỗ trợ 24/7</span></div><button className="new-chat" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} style={{ marginLeft: 'auto', padding: '9px', borderRadius: '50%', width: '38px', height: '38px', display: 'grid', placeItems: 'center' }} aria-label="Đổi giao diện"><Icon name={theme === 'dark' ? 'sun' : 'moon'} /></button><button className="new-chat" style={{ marginLeft: '8px' }} onClick={restartConversation}><Icon name="refresh" />Cuộc trò chuyện mới</button></header>
      <section className={`conversation ${isWelcomeExperience ? 'conversation--welcome' : ''} ${mode === 'booking' && bookingStep === 'specialty' ? 'conversation--booking' : ''} ${mode === 'status' ? 'conversation--status' : ''}`} aria-live="polite">
        {messages.map((item) => <article key={item.id} className={`message ${item.side} ${item.id.startsWith('welcome-') ? 'message--welcome' : ''}`}>{!item.id.startsWith('welcome-') ? <div className="avatar"><Icon name={item.side === 'assistant' ? 'medical-cross' : 'user'} /></div> : null}<div className="bubble">{item.text ? <p>{item.text}</p> : null}{item.envelope ? renderEnvelope(item.envelope) : null}</div></article>)}
        {isWelcomeExperience && welcomeTyping ? <div className="typing" aria-label="Emy đang nhập"><i /><i /><i /> Emy đang nhập…</div> : null}
        {isWelcomeExperience && onboardingComplete ? <div className="quick-actions-wrapper"><section className="quick-actions quick-actions--revealed" aria-label="Gợi ý hỗ trợ"><div>{quickActions.map((action) => <button key={action.id} onClick={() => chooseAction(action)}><b><Icon name={action.icon} /></b><span>{action.title}</span><small><Icon name="chevron-right" /></small></button>)}</div></section></div> : null}
        {mode === 'booking' ? <section className={`guided-card ${bookingStep === 'specialty' ? 'guided-card--specialty' : ''}`} aria-label="Đặt lịch khám"><button className="back-link" onClick={() => setMode('chat')}><Icon name="arrow-left" />Quay lại</button><p className="eyebrow">ĐẶT LỊCH KHÁM · BƯỚC {bookingStep === 'specialty' ? '1' : bookingStep === 'doctor' ? '2' : bookingStep === 'slot' ? '3' : '4'}/4</p>
          {bookingStep === 'specialty' ? <><h2>Chọn chuyên khoa</h2><div className="choice-grid">{specialties.map((x) => <button onClick={() => { setBooking({ ...booking, specialty_id: x.specialty_id, doctor_id: '', slot_id: '' }); setBookingStep('doctor') }} key={x.specialty_id}><b>{x.name}</b><span>{x.description || 'Tư vấn và khám theo chuyên khoa'}</span></button>)}</div></> : null}
          {bookingStep === 'doctor' ? <><h2>Chọn bác sĩ</h2><div className="choice-grid">{doctors.map((x) => <button onClick={() => { setBooking({ ...booking, doctor_id: x.doctor_id, slot_id: '' }); setBookingStep('slot') }} key={x.doctor_id}><b>{x.title} {x.full_name}</b><span>{x.profile_summary || 'Bác sĩ chuyên khoa'}</span></button>)}</div><button className="text-button" onClick={() => setBookingStep('specialty')}>Chọn lại chuyên khoa</button></> : null}
          {bookingStep === 'slot' ? <><h2>Chọn khung giờ còn trống</h2><div className="slot-grid">{slots.map((x) => <button onClick={() => { setBooking({ ...booking, slot_id: x.slot_id }); setBookingStep('patient') }} key={x.slot_id}><b>{x.time}</b><span>{x.date} · {x.room}</span></button>)}</div><button className="text-button" onClick={() => setBookingStep('doctor')}>Chọn lại bác sĩ</button></> : null}
          {bookingStep === 'patient' ? <form className="patient-form" onSubmit={(event) => { event.preventDefault(); void submitBooking(false) }}><h2>Thông tin người khám</h2><div className="visit-toggle"><button type="button" className={booking.visit_type === 'first_visit' ? 'selected' : ''} onClick={() => setBooking({ ...booking, visit_type: 'first_visit' })}>Khám lần đầu</button><button type="button" className={booking.visit_type === 'follow_up' ? 'selected' : ''} onClick={() => setBooking({ ...booking, visit_type: 'follow_up' })}>Tái khám</button></div><label>Họ và tên<input required value={booking.patient_name} onChange={(e) => setBooking({ ...booking, patient_name: e.target.value })} /></label><label>Số điện thoại<input required inputMode="tel" value={booking.patient_phone} onChange={(e) => setBooking({ ...booking, patient_phone: e.target.value })} /></label><label>Ngày sinh<input required type="date" value={booking.patient_dob} onChange={(e) => setBooking({ ...booking, patient_dob: e.target.value })} /></label><label>Lý do khám<input required value={booking.visit_reason} onChange={(e) => setBooking({ ...booking, visit_reason: e.target.value })} /></label><label className="check"><input type="checkbox" checked={booking.has_insurance} onChange={(e) => setBooking({ ...booking, has_insurance: e.target.checked })} /> Tôi có thẻ BHYT</label><button className="primary" disabled={loading}>Kiểm tra và xác nhận</button></form> : null}
          {referenceLoading ? <p className="loading-copy">Đang tải dữ liệu đặt lịch…</p> : null}</section> : null}
        {mode === 'status' ? <section className="guided-card status-card"><button className="back-link" onClick={() => setMode('chat')}><Icon name="arrow-left" />Quay lại</button><h2>Tra cứu lịch hẹn</h2><p>Nhập mã lịch hẹn của bạn để xem trạng thái mới nhất.</p><form onSubmit={(event) => { event.preventDefault(); const id = input.trim(); if (id) { setInput(''); setMode('chat'); void execute('appointment_status', id) } }}><input aria-label="Mã lịch hẹn" placeholder="Ví dụ: HEN-2026-0001" value={input} onChange={(e) => setInput(e.target.value)} /><button className="primary" disabled={!input.trim() || loading}>Tra cứu lịch</button></form></section> : null}
        {loading ? <div className="typing"><i /><i /><i /> Đang xử lý yêu cầu…</div> : null}
        {error ? <p className="error" role="alert">{error}</p> : null}<div ref={endRef} />
      </section>
      <footer className="composer"><form onSubmit={submitChat} style={{ minHeight: '46px', padding: '4px 4px 4px 18px' }}><textarea rows={1} aria-label="Nội dung" aria-keyshortcuts="Enter" title="Nhấn Enter để gửi, Shift + Enter để xuống dòng" placeholder={onboardingComplete ? 'Nhập câu hỏi của bạn…' : 'Emy đang chuẩn bị hỗ trợ bạn…'} value={input} onChange={(e) => { setInput(e.target.value); e.target.style.height = '26px'; e.target.style.height = e.target.scrollHeight + 'px'; }} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} disabled={loading || mode !== 'chat' || !onboardingComplete} style={{ height: '26px', minHeight: '26px', padding: '0', fontSize: '16px', lineHeight: '26px', margin: 0, overflow: 'hidden' }} /><MicrophoneButton disabled={loading || mode !== 'chat' || !onboardingComplete} onTranscript={appendDictatedText} /><button aria-label="Gửi tin nhắn" title="Gửi tin nhắn" disabled={!input.trim() || loading || mode !== 'chat' || !onboardingComplete} style={{ width: '36px', height: '36px', padding: 0 }}><svg className="send-icon" viewBox="0 0 24 24" aria-hidden="true" style={{ width: '18px', height: '18px' }}><path d="M21.4 3.6 13.8 21l-3.2-7.2L3 10.6 21.4 3.6Z" /><path d="m10.6 13.8 4.9-4.9" /></svg></button></form><p>Thông tin chỉ mang tính tham khảo, không thay thế tư vấn y tế trực tiếp.</p></footer>
    </section>
  </main>
}

export default App
// === TASK:WP-500:END ===
