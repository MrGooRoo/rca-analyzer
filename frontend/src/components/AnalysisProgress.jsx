/**
 * AnalysisProgress — компонент прогресса multi-analysis через SSE.
 */
import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { Badge, Card } from './ui/Card.jsx'
import { CheckCircle, XCircle, Clock, Cog } from 'lucide-react'
import './AnalysisProgress.css'

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

function stateIcon(state) {
  if (state === 'done') return <CheckCircle size={14} />
  if (state === 'error') return <XCircle size={14} />
  if (state === 'pending') return <Clock size={14} />
  return <Cog size={14} />
}

function stateLabel(state) {
  if (state === 'done') return 'готово'
  if (state === 'error') return 'ошибка'
  if (state === 'pending') return 'ожидает'
  return 'в работе'
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
  const phaseClass = phase === STATUS_ERROR ? 'analysis-progress--error' : 'analysis-progress--indigo'

  if (phase === STATUS_IDLE) return null

  return (
    <Card className={`analysis-progress ${phaseClass}`}>
      <div className="analysis-progress__header">
        <div className="analysis-progress__title-group">
          <div className="analysis-progress__eyebrow">Сравнение методик</div>
          <div className="analysis-progress__title">
            {phase === STATUS_DONE && <><CheckCircle size={16} /> Анализ завершён</>}
            {phase === STATUS_ERROR && <><XCircle size={16} /> Ошибка анализа</>}
            {phase === STATUS_RUNNING && <>Анализ инцидента…</>}
          </div>
        </div>
        <Badge tone={phase === STATUS_ERROR ? 'rose' : phase === STATUS_DONE ? 'emerald' : 'sky'} className="analysis-progress__badge">
          {doneCount + errorCount} / {total || payload?.methodologies?.length || 0}
        </Badge>
      </div>

      <div className="analysis-progress__bar" aria-label={`Прогресс ${progress}%`}>
        <div className="analysis-progress__bar-fill" style={{ width: progress + '%' }} />
      </div>

      {items.length > 0 && (
        <ul className="analysis-progress__list">
          {items.map((item) => (
            <li key={item.methodKey || item.name} className={`analysis-progress__item analysis-progress__item--${item.state}`}>
              <span className="analysis-progress__status-icon" aria-hidden="true">
                {stateIcon(item.state)}
              </span>
              <span className="analysis-progress__name">{item.name}</span>
              <span className="analysis-progress__status-label">{stateLabel(item.state)}</span>
              {item.state === 'error' && item.message && (
                <span className="analysis-progress__error-message" title={item.message}>
                  — {item.message.length > 60 ? item.message.slice(0, 60) + '…' : item.message}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {fatalError && (
        <div className="analysis-progress__fatal-error">
          {fatalError}
        </div>
      )}
    </Card>
  )
}
