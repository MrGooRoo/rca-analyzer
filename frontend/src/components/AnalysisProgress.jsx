/**
 * AnalysisProgress — компонент прогресса multi-analysis через SSE.
 *
 * Компонент запускает /analyze-multi-stream при монтировании, показывает
 * прогресс по методикам и сообщает родителю results через onDone.
 */

import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { Badge, Card } from './ui/Card.jsx'
import './AnalysisProgress.css'

const STATUS_IDLE    = 'idle'
const STATUS_RUNNING = 'running'
const STATUS_DONE    = 'done'
const STATUS_ERROR   = 'error'

function markNextRunning(list) {
  let activated = false
  return list.map(item => {
    if (!activated && item.state === 'pending') {
      activated = true
      return { ...item, state: 'running' }
    }
    return item
  })
}

function updateItem(list, event, state, message = null) {
  const updated = list.map(item =>
    item.name === event.name || item.methodKey === event.methodology
      ? { ...item, state, message: message || item.message }
      : item,
  )
  return state === 'done' || state === 'error' ? markNextRunning(updated) : updated
}

export default function AnalysisProgress({ payload, onDone, onError }) {
  const [phase, setPhase]           = useState(STATUS_IDLE)
  const [total, setTotal]           = useState(0)
  // items: { name, methodKey, state: 'pending'|'running'|'done'|'error', message? }
  const [items, setItems]           = useState([])
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
        setItems(markNextRunning(
          event.methodologies.map((name, i) => ({
            name,
            methodKey: payload.methodologies[i],
            state: 'pending',
          })),
        ))
      }

      if (event.status === 'progress') {
        setItems(prev => updateItem(prev, event, 'done'))
      }

      if (event.status === 'error_one') {
        setItems(prev => updateItem(prev, event, 'error', event.message))
      }
    })
      .then((results) => {
        if (abortRef.current) return
        setPhase(STATUS_DONE)
        onDone?.(results)
      })
      .catch((err) => {
        if (abortRef.current) return
        const msg = err.message || 'Ошибка анализа'
        setPhase(STATUS_ERROR)
        setFatalError(msg)
        onError?.(msg)
      })

    return () => {
      abortRef.current = true
    }
    // Важно: поток должен стартовать только при смене payload.
    // onDone/onError в App.jsx пересоздаются на рендере, их не добавляем в deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payload])

  const doneCount  = items.filter(i => i.state === 'done').length
  const errorCount = items.filter(i => i.state === 'error').length
  const progress   = total > 0 ? Math.round(((doneCount + errorCount) / total) * 100) : 0

  if (phase === STATUS_IDLE) return null

  return (
    <Card className="ap-root">
      <div className="ap-header">
        <div>
          <div className="ap-eyebrow">Сравнение методик</div>
          <div className="ap-title">
            {phase === STATUS_DONE && '✅ Анализ завершён'}
            {phase === STATUS_ERROR && '❌ Ошибка анализа'}
            {phase === STATUS_RUNNING && 'Анализ инцидента…'}
          </div>
        </div>
        <Badge tone={phase === STATUS_ERROR ? 'rose' : phase === STATUS_DONE ? 'emerald' : 'sky'}>
          {doneCount + errorCount} / {total || payload?.methodologies?.length || 0}
        </Badge>
      </div>

      <div className="ap-bar-track" aria-label={`Прогресс ${progress}%`}>
        <div className="ap-bar-fill" style={{ width: progress + '%' }} />
      </div>

      {items.length > 0 && (
        <ul className="ap-list">
          {items.map((item) => (
            <li key={item.methodKey || item.name} className={'ap-item ap-item--' + item.state}>
              <span className="ap-item-icon" aria-hidden="true">
                {item.state === 'done'    && '✅'}
                {item.state === 'error'   && '❌'}
                {item.state === 'pending' && '⏳'}
                {item.state === 'running' && '⚙️'}
              </span>
              <span className="ap-item-name">{item.name}</span>
              <span className="ap-item-state">
                {item.state === 'done' && 'готово'}
                {item.state === 'error' && 'ошибка'}
                {item.state === 'pending' && 'ожидает'}
                {item.state === 'running' && 'в работе'}
              </span>
              {item.state === 'error' && item.message && (
                <span className="ap-item-error" title={item.message}>
                  — {item.message.length > 60 ? item.message.slice(0, 60) + '…' : item.message}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {fatalError && <div className="ap-fatal">{fatalError}</div>}
    </Card>
  )
}
