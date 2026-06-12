import { createContext, useCallback, useContext, useState } from 'react'
import { cn } from '../../utils/cn'
import './Toast.css'

const Ctx = createContext(undefined)

const toneStyles = {
  info: 'toast--info',
  success: 'toast--success',
  error: 'toast--error',
  warning: 'toast--warning',
}

const icons = {
  info: 'ℹ️',
  success: '✅',
  error: '⚠️',
  warning: '⚡',
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const push = useCallback((t) => {
    const id = Date.now() + Math.random()
    setToasts(s => [...s, { ...t, id }])
    setTimeout(() => setToasts(s => s.filter(x => x.id !== id)), 5000)
  }, [])

  const api = {
    push,
    success: (message, title) => push({ message, title, tone: 'success' }),
    error: (message, title) => push({ message, title, tone: 'error' }),
    info: (message, title) => push({ message, title, tone: 'info' }),
    warning: (message, title) => push({ message, title, tone: 'warning' }),
  }

  return (
    <Ctx.Provider value={api}>
      {children}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={cn('toast', toneStyles[t.tone] || 'toast--info')}>
            <span className="toast__icon">{icons[t.tone]}</span>
            <div className="toast__body">
              {t.title && <div className="toast__title">{t.title}</div>}
              <div className="toast__message">{t.message}</div>
            </div>
            <button
              className="toast__close"
              onClick={() => setToasts(s => s.filter(x => x.id !== t.id))}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}

export function useToast() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
