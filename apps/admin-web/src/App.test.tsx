// === TASK:WP-500:START ===
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders the operational loading state', () => {
    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent(/Đang tải bảng điều hành/i)
  })
})
// === TASK:WP-500:END ===
