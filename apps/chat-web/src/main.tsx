// === TASK:WP-500:START ===
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { BrowserSpeechRecognitionProvider } from './speech/SpeechRecognitionProvider.tsx'
import './chat.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserSpeechRecognitionProvider>
      <App />
    </BrowserSpeechRecognitionProvider>
  </StrictMode>,
)
// === TASK:WP-500:END ===
