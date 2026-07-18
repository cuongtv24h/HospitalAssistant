import { createContext, useContext, useMemo, type ReactNode } from 'react'

export type SpeechRecognitionState = 'idle' | 'listening' | 'error' | 'unsupported'

export type SpeechRecognitionResultHandler = (text: string) => void
export type SpeechRecognitionErrorHandler = (message: string) => void
export type SpeechRecognitionStateHandler = (state: SpeechRecognitionState) => void

export type SpeechRecognitionSession = {
  start: () => void
  stop: () => void
  abort: () => void
}

export type SpeechRecognitionOptions = {
  onResult: SpeechRecognitionResultHandler
  onError: SpeechRecognitionErrorHandler
  onStateChange: SpeechRecognitionStateHandler
}

export type SpeechRecognitionProviderValue = {
  isSupported: boolean
  createSession: (options: SpeechRecognitionOptions) => SpeechRecognitionSession
}

type WebSpeechRecognitionConstructor = new () => WebSpeechRecognition

type WebSpeechRecognitionAlternative = {
  transcript: string
}

type WebSpeechRecognitionResult = {
  isFinal: boolean
  readonly length: number
  item: (index: number) => WebSpeechRecognitionAlternative
  [index: number]: WebSpeechRecognitionAlternative
}

type WebSpeechRecognitionResultList = {
  readonly length: number
  item: (index: number) => WebSpeechRecognitionResult
  [index: number]: WebSpeechRecognitionResult
}

type WebSpeechRecognitionResultEvent = Event & {
  resultIndex: number
  results: WebSpeechRecognitionResultList
}

type WebSpeechRecognitionErrorEvent = Event & {
  error: string
  message?: string
}

type WebSpeechRecognition = EventTarget & {
  lang: string
  interimResults: boolean
  continuous: boolean
  maxAlternatives: number
  onstart: (() => void) | null
  onend: (() => void) | null
  onresult: ((event: WebSpeechRecognitionResultEvent) => void) | null
  onerror: ((event: WebSpeechRecognitionErrorEvent) => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}

declare global {
  interface Window {
    SpeechRecognition?: WebSpeechRecognitionConstructor
    webkitSpeechRecognition?: WebSpeechRecognitionConstructor
  }
}

function getSpeechRecognitionConstructor() {
  if (typeof window === 'undefined') return undefined
  return window.SpeechRecognition ?? window.webkitSpeechRecognition
}

function createBrowserSpeechRecognitionSession(options: SpeechRecognitionOptions): SpeechRecognitionSession {
  const Recognition = getSpeechRecognitionConstructor()
  if (!Recognition) {
    options.onStateChange('unsupported')
    options.onError('Trình duyệt của bạn chưa hỗ trợ nhập giọng nói.')
    return { start: () => undefined, stop: () => undefined, abort: () => undefined }
  }

  const recognition = new Recognition()
  recognition.lang = 'vi-VN'
  recognition.continuous = false
  recognition.interimResults = false
  recognition.maxAlternatives = 1
  recognition.onstart = () => options.onStateChange('listening')
  recognition.onend = () => options.onStateChange('idle')
  recognition.onerror = (event) => {
    options.onStateChange('error')
    options.onError(event.message || mapSpeechRecognitionError(event.error))
  }
  recognition.onresult = (event) => {
    let transcript = ''
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index]
      if (result?.isFinal) transcript += result[0]?.transcript ?? ''
    }
    const value = transcript.trim()
    if (value) options.onResult(value)
  }

  return {
    start: () => {
      try {
        recognition.start()
      } catch {
        options.onStateChange('error')
        options.onError('Không thể bắt đầu ghi âm. Vui lòng thử lại.')
      }
    },
    stop: () => recognition.stop(),
    abort: () => recognition.abort(),
  }
}

function mapSpeechRecognitionError(error: string) {
  if (error === 'not-allowed' || error === 'service-not-allowed') return 'Vui lòng cho phép truy cập micro để nhập bằng giọng nói.'
  if (error === 'no-speech') return 'Không nhận được giọng nói. Vui lòng thử lại.'
  if (error === 'audio-capture') return 'Không tìm thấy micro khả dụng.'
  return 'Không thể nhận dạng giọng nói. Vui lòng thử lại.'
}

const SpeechRecognitionContext = createContext<SpeechRecognitionProviderValue | null>(null)

export function BrowserSpeechRecognitionProvider({ children }: { children: ReactNode }) {
  const value = useMemo<SpeechRecognitionProviderValue>(() => ({
    isSupported: Boolean(getSpeechRecognitionConstructor()),
    createSession: createBrowserSpeechRecognitionSession,
  }), [])

  return <SpeechRecognitionContext.Provider value={value}>{children}</SpeechRecognitionContext.Provider>
}

export function useSpeechRecognitionProvider() {
  const value = useContext(SpeechRecognitionContext)
  if (!value) throw new Error('useSpeechRecognitionProvider must be used within BrowserSpeechRecognitionProvider')
  return value
}

export const speechRecognitionTestUtils = { mapSpeechRecognitionError }
