import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../components/ui/Toast'
import App from '../App'

// Mock fetch for auth check
beforeEach(() => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ user: null }),
    })
  )
})

describe('App', () => {
  it('renders without crashing', async () => {
    render(
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    )

    // App should render auth page initially (no user)
    const loginButton = await screen.findByRole('button', { name: /войти|вход|login/i })
    expect(loginButton).toBeDefined()
  })
})
