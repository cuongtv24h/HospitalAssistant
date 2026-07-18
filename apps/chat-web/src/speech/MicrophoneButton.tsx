import { useEffect, useMemo, useState } from 'react'
import { useSpeechRecognitionProvider, type SpeechRecognitionSession, type SpeechRecognitionState } from './SpeechRecognitionProvider'

export type MicrophoneButtonProps = {
  disabled?: boolean
  onTranscript: (text: string) => void
}

export function MicrophoneButton({ disabled = false, onTranscript }: MicrophoneButtonProps) {
  const provider = useSpeechRecognitionProvider()
  const [state, setState] = useState<SpeechRecognitionState>(provider.isSupported ? 'idle' : 'unsupported')
  const [error, setError] = useState<string | null>(provider.isSupported ? null : 'Trình duyệt của bạn chưa hỗ trợ nhập giọng nói.')

  const session = useMemo<SpeechRecognitionSession>(() => provider.createSession({
    onResult: onTranscript,
    onError: setError,
    onStateChange: setState,
  }), [onTranscript, provider])

  useEffect(() => () => session.abort(), [session])

  const isListening = state === 'listening'
  const isUnavailable = disabled || state === 'unsupported'
  const label = state === 'unsupported'
    ? 'Trình duyệt không hỗ trợ nhập giọng nói'
    : isListening
      ? 'Dừng nghe giọng nói'
      : 'Nhập bằng giọng nói'

  return <div className={`microphone-control microphone-control--${state}`}>
    <button
      type="button"
      aria-label={label}
      aria-pressed={isListening}
      className="microphone-button"
      disabled={isUnavailable}
      title={error ?? label}
      onClick={() => { if (isListening) session.stop(); else session.start() }}
    >
      <span aria-hidden="true">🎙</span>
    </button>
    <span className="microphone-status" role={state === 'error' ? 'alert' : 'status'}>
      {state === 'listening' ? 'Đang nghe…' : state === 'error' ? error : state === 'unsupported' ? 'Không hỗ trợ micro' : 'Micro sẵn sàng'}
    </span>
  </div>
}
