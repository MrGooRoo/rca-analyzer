import { createContext, useCallback, useContext, useState } from 'react'
import { cn } from '../../utils/cn'

const Ctx = createContext(undefined)

const toneStyles = {
  info: 'bg-slate-800 ring-slate-700 text-slate-100',
  success: 'bg-emerald-600/90 ring-emerald-400/40 text-white',
  error: 'bg-rose-600/90 ring-rose-400/40 text-white',
  warning: 'bg-amber-600/90 ring-amber-400/40 text-white',
}

const icons = {
  info: 'ℹ️',
  success: '✓',
  error: '✕',
  warning: '⚠',
}

export function ToastProvider({ children }) {
  const [items, setItems] = useState([])

  const push = useCallback((t) => {
    const id = Date.now() + Math.random()
    setItems(s => [...s, { ...t, id }])
    setTimeout(() => setItems(s => s.filter(x => x.id !== id)), 5000)
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
      <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col gap-2">
        {items.map(t => (
          <div
            key={t.id}
            className={cn(
              'pointer-events-auto flex items-center gap-3 rounded-xl px-4 py-3 shadow-xl ring-1 animate-slideIn',
              toneStyles[t.tone] || toneStyles.info,
            )}
            style={{ minWidth: 240 }}
          >
            <span className="text-lg">{icons[t.tone] || icons.info}</span>
            <div className="text-sm">
              {t.title && <div className="font-semibold">{t.title}</div>}
              <div>{t.message}</div>
            </div>
            <button
              className="ml-auto text-slate-400 hover:text-white transition"
              onClick={() => setItems(s => s.filter(x => x.id !== t.id))}
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
