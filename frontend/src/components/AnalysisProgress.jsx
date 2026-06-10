/**
 * AnalysisProgress — компонент прогресса анализа (SSE).
 *
 * Использование:
 *   <AnalysisProgress
 *     payload={multiAnalysisRequest}   // MultiAnalysisRequest для analyze-multi-stream
 *     onDone={(results) => ...}         // вызывается когда все методологии готовы
 *     onError={(message) => ...}        // вызывается при фатальной ошибке
 *   />
 *
 * Компонент сам запускает стрим при монтировании и отменяет при размонтировании.
 */

import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import './AnalysisProgress.css'

const STATUS_IDLE    = 'idle'
const STATUS_RUNNING = 'running'
const STATUS_DONE    = 'done'
const STATUS_ERROR   = 'error'

export default function AnalysisProgress({ payload, onDone, onError }) {
  const [phase, setPhase]           = useState(STATUS_IDLE)
  const [total, setTotal]           = useState(0)
  const [methodologies, setMethods] = useState([])   // ['BowTie', 'Ishikawa', ...]
  // items: { name, methodKey, state: 'pending'|'running'|'done'|'error', message? }
  const [items, setItems]           = useState([])
  const [fatalError, setFatalError] = useState(null)
  const abortRef = useRef(false)

  useEffect(() => {
    if (!payload) return
    abortRef.current = false
    setPhase(STATUS_RUNNING)
    setFatalError(null)

    api.analyzeMultiStream(payload, (event) => {
      if (abortRef.current) return

      if (event.status === 'started') {
        setTotal(event.total)
        setMethods(event.methodologies)
        setItems(
          event.methodologies.map((name, i) => ({
            name,
            methodKey: payload.methodologies[i],
            state: 'pending',
          }))
        )
      }

      if (event.status === 'progress') {
        setItems(prev =>
          prev.map(item =>
            item.name === event.name
              ? { ...item, state: 'done' }
              : item
          )
        )
      }

      if (event.status === 'error_one') {
        setItems(prev =>
          prev.map(item =>
            item.name === event.name
              ? { ...item, state: 'error', message: event.message }
              : item
          )
        )
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
  }, [payload])

  const doneCount  = items.filter(i => i.state === 'done').length
  const errorCount = items.filter(i => i.state === 'error').length
  const progress   = total > 0 ? Math.round(((doneCount + errorCount) / total) * 100) : 0

  if (phase === STATUS_IDLE) return null

  return (
    <div className="ap-root">
      <div className="ap-header">
        <span className="ap-title">
          {phase === STATUS_DONE && '✅ Анализ завершён'}
          {phase === STATUS_ERROR && '❌ Ошибка анализа'}
          {phase === STATUS_RUNNING && 'Анализ инцидента…'}
        </span>
        {phase === STATUS_RUNNING && (
          <span className="ap-counter">{doneCount + errorCount} / {total}</span>
        )}
      </div>

      {/* Прогресс-бар */}
      {phase === STATUS_RUNNING && (
        <div className="ap-bar-track">
          <div
            className="ap-bar-fill"
            style={{ width: progress + '%' }}
          />
        </div>
      )}

      {/* Список методологий */}
      {items.length > 0 && (
        <ul className="ap-list">
          {items.map((item) => (
            <li key={item.name} className={'ap-item ap-item--' + item.state}>
              <span className="ap-item-icon">
                {item.state === 'done'    && '✅'}
                {item.state === 'error'   && '❌'}
                {item.state === 'pending' && '⏳'}
                {item.state === 'running' && '⚙️'}
              </span>
              <span className="ap-item-name">{item.name}</span>
              {item.state === 'error' && item.message && (
                <span className="ap-item-error" title={item.message}>
                  — {item.message.length > 60 ? item.message.slice(0, 60) + '…' : item.message}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Фатальная ошибка */}
      {fatalError && (
        <div className="ap-fatal">{fatalError}</div>
      )}
    </div>
  )
}
