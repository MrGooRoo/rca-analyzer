/**
 * AnalysisProgress — компонент прогресса multi-analysis через SSE.
 */
import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { Badge, Card } from './ui/Card.jsx'

const STATUS_IDLE = 'idle'
const STATUS_RUNNING = 'running'
const STATUS_DONE = 'done'
const STATUS_ERROR = 'error'

function updateItem(list, event, state, message = null) {
  return list.map(item =>
    item.name === event.name || item.methodKey === event.methodology
      ? { ...item, state, message: message || item.message }
      : item,
  )
}

export default function AnalysisProgress({ payload, signal, onDone, onError }) {
  const [phase, setPhase] = useState(STATUS_IDLE)
  const [total, setTotal] = useState(0)
  const [items, setItems] = useState([])
  const [fatalError, setFatalError] = useState(null)
  const abortRef = useRef(false)

  useEffect(() => {
    if (!payload) return
    abortRef.current = false
    setPhase(STATUS_RUNNING)
    setFatalError(null)
    setItems([])
    setTotal(0)

    api.analyzeMultiStream(payload, (event) => {
      if (abortRef.current) return
      if (event.status === 'started') {
        setTotal(event.total)
        setItems(event.methodologies.map((name, i) => ({
          name, methodKey: payload.methodologies[i], state: 'running',
        })))
      }
      if (event.status === 'progress') {
        setItems(prev => updateItem(prev, event, 'done'))
      }
      if (event.status === 'error_one') {
        setItems(prev => updateItem(prev, event, 'error', event.message))
      }
    }, { signal })
      .then((results) => {
        if (abortRef.current) return
        setPhase(STATUS_DONE)
        onDone?.(results)
      })
      .catch((err) => {
        if (abortRef.current) return
        if (err.name === 'AbortError') { onError?.('Анализ отменён', err); return }
        const msg = err.message || 'Ошибка анализа'
        setPhase(STATUS_ERROR)
        setFatalError(msg)
        onError?.(msg, err)
      })

    return () => { abortRef.current = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payload])

  const doneCount = items.filter(i => i.state === 'done').length
  const errorCount = items.filter(i => i.state === 'error').length
  const progress = total > 0 ? Math.round(((doneCount + errorCount) / total) * 100) : 0

  if (phase === STATUS_IDLE) return null

  const itemStateClass = {
    pending: 'opacity-50',
    running: 'border-indigo-400/40 bg-indigo-500/10',
    done: 'border-emerald-400/30',
    error: 'border-rose-400/40 bg-rose-500/10',
  }

  return (
    <Card className="my-4 p-5 ring-indigo-500/30 bg-gradient-to-r from-indigo-500/10 via-slate-900/60 to-slate-900/60">
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-indigo-400 mb-1">Сравнение методик</div>
          <div className="text-lg font-bold text-white tracking-tight">
            {phase === STATUS_DONE && '✅ Анализ завершён'}
            {phase === STATUS_ERROR && '❌ Ошибка анализа'}
            {phase === STATUS_RUNNING && 'Анализ инцидента…'}
          </div>
        </div>
        <Badge tone={phase === STATUS_ERROR ? 'rose' : phase === STATUS_DONE ? 'emerald' : 'sky'}>
          {doneCount + errorCount} / {total || payload?.methodologies?.length || 0}
        </Badge>
      </div>

      <div className="h-2 bg-slate-800 rounded-full overflow-hidden mb-4 border border-white/5" aria-label={`Прогресс ${progress}%`}>
        <div className="h-full bg-gradient-to-r from-indigo-500 to-emerald-500 rounded-full transition-[width] duration-300" style={{ width: progress + '%' }} />
      </div>

      {items.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {items.map((item) => (
            <li key={item.methodKey || item.name} className={`grid grid-cols-[24px_1fr_auto] sm:grid-cols-[24px_minmax(120px,1fr)_auto] items-center gap-2 px-2.5 py-2 rounded-lg border bg-white/[0.025] transition ${itemStateClass[item.state] || ''}`}>
              <span className="text-sm text-center leading-none" aria-hidden="true">
                {item.state === 'done' && '✅'}
                {item.state === 'error' && '❌'}
                {item.state === 'pending' && '⏳'}
                {item.state === 'running' && '⚙️'}
              </span>
              <span className="text-sm font-semibold text-white truncate">{item.name}</span>
              <span className="text-xs text-slate-400 whitespace-nowrap">
                {item.state === 'done' && 'готово'}
                {item.state === 'error' && 'ошибка'}
                {item.state === 'pending' && 'ожидает'}
                {item.state === 'running' && 'в работе'}
              </span>
              {item.state === 'error' && item.message && (
                <span className="col-span-2 sm:col-span-3 text-xs text-rose-300 truncate" title={item.message}>
                  — {item.message.length > 60 ? item.message.slice(0, 60) + '…' : item.message}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {fatalError && (
        <div className="mt-4 rounded-lg bg-rose-500/10 ring-1 ring-rose-500/30 text-rose-300 text-sm px-3 py-2.5">
          {fatalError}
        </div>
      )}
    </Card>
  )
}
