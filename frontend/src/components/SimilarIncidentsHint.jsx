import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import './SimilarIncidentsHint.css'

/**
 * Вариант C — «Трансформер».
 *
 * Фазы:
 *   1) Loading skeleton — «Ищу похожие инциденты…»
 *   2) Найдены — автоматический показ списка с карточками (кликабельны)
 *   3) Свёрнуто — компактная плашка «Найдено N похожих», клик → фаза 2
 */
export default function SimilarIncidentsHint({
  queryText,
  incidentTitle = null,
  incidentDescription = null,
  onOpenResult = null,
}) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(true) // true = фаза 2 (список), false = фаза 3 (свёрнуто)
  const [hasSearched, setHasSearched] = useState(false)
  const prevQueryRef = useRef('')

  const load = useCallback(async () => {
    if (queryText.length < 20) return
    setLoading(true)
    setError(null)
    setExpanded(true)
    setHasSearched(true)
    try {
      const data = await api.similarIncidents(queryText, {
        limit: 10,
        incidentTitle,
        incidentDescription,
      })
      setItems(data || [])
    } catch (e) {
      setError(e.message)
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [queryText, incidentTitle, incidentDescription])

  // Автопоиск с debounce 1s, но только при изменении текста (не при коллапсе/экспанде)
  useEffect(() => {
    if (queryText.length < 20) {
      setItems([])
      setHasSearched(false)
      return
    }
    if (queryText === prevQueryRef.current) return
    prevQueryRef.current = queryText
    const timer = setTimeout(load, 1000)
    return () => clearTimeout(timer)
  }, [queryText, load])

  // ── Фаза 1: Loading skeleton ─────────────────────────────────
  if (loading && items.length === 0 && !error) {
    return (
      <div className="sihint sihint--loading">
        <div className="sihint__skeleton">
          <svg className="sihint__spinner" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
            <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          </svg>
          <span>Ищу похожие инциденты…</span>
          <div className="sihint__skeleton-bar" />
        </div>
      </div>
    )
  }

  // ── Нет данных ──────────────────────────────────────────────
  if (!hasSearched || (items.length === 0 && !loading && !error)) {
    if (!hasSearched) return null
    return (
      <div className="sihint sihint--empty">
        <span>🔗</span>
        <span>Похожих инцидентов в истории не найдено</span>
      </div>
    )
  }

  // ── Ошибка ──────────────────────────────────────────────────
  if (error && items.length === 0) {
    return (
      <div className="sihint sihint--error">
        <span>⚠️</span>
        <span>Ошибка поиска: {error}</span>
      </div>
    )
  }

  // ── Фаза 2/3: найдены инциденты ─────────────────────────────
  const count = items.length
  const word = count === 1 ? 'инцидент' : count < 5 ? 'инцидента' : 'инцидентов'

  async function handleOpenItem(item) {
    if (!onOpenResult) return
    try {
      const fullResult = await api.results.get(item.result_id)
      onOpenResult(fullResult)
    } catch {
      onOpenResult(item)
    }
  }

  // Фаза 3 — свёрнуто
  if (!expanded) {
    return (
      <div
        className="sihint sihint--collapsed"
        onClick={() => setExpanded(true)}
        role="button"
        tabIndex={0}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(true) } }}
      >
        <span className="sihint__icon">🔗</span>
        <span>
          Найдено <strong>{count}</strong> похожих {word}
        </span>
        <span className="sihint__expand-icon">▶</span>
      </div>
    )
  }

  // Фаза 2 — список карточек
  const slice = items.slice(0, 10)

  return (
    <div className="sihint sihint--expanded">
      <div className="sihint__header">
        <span className="sihint__icon">🔗</span>
        <span>
          Найдено <strong>{count}</strong> похожих {word}
        </span>
        <button
          className="sihint__collapse-btn"
          onClick={() => setExpanded(false)}
          title="Свернуть"
          type="button"
          aria-label="Свернуть"
        >
          ✕
        </button>
      </div>

      {loading && items.length > 0 && (
        <div className="sihint__refreshing">
          <svg className="sihint__spinner sihint__spinner--sm" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
            <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          </svg>
          <span>Обновление…</span>
        </div>
      )}

      <div className="sihint__list">
        {slice.map(item => (
          <SimilarHintCard
            key={item.result_id}
            item={item}
            onOpen={onOpenResult ? () => handleOpenItem(item) : null}
          />
        ))}
      </div>
    </div>
  )
}

function SimilarHintCard({ item, onOpen }) {
  const date = new Date(item.created_at).toLocaleDateString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  })
  const percent = Math.round((item.similarity || 0) * 100)
  const incidentDateStr = item.incident_date
    ? new Date(item.incident_date).toLocaleDateString('ru-RU', {
        day: '2-digit', month: '2-digit', year: 'numeric',
      })
    : null

  let scoreClass = 'sihint__score--amber'
  if (percent >= 75) scoreClass = 'sihint__score--green'
  else if (percent < 50) scoreClass = 'sihint__score--red'

  return (
    <div
      className={`sihint__card ${onOpen ? 'sihint__card--clickable' : ''}`}
      onClick={onOpen}
      role={onOpen ? 'button' : undefined}
      tabIndex={onOpen ? 0 : undefined}
      onKeyDown={e => {
        if (onOpen && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault(); onOpen()
        }
      }}
    >
      <span className={`sihint__score ${scoreClass}`}>{percent}%</span>

      <div className="sihint__card-body">
        <div className="sihint__card-title">
          {item.incident_title || 'Без названия'}
        </div>
        <div className="sihint__card-meta">
          {incidentDateStr && <span>{incidentDateStr}</span>}
          {item.incident_location && <span>{item.incident_location}</span>}
          <span className="sihint__card-id">#{item.result_id?.slice(0, 8)}</span>
        </div>
        {item.summary && (
          <div className="sihint__card-summary">{item.summary.slice(0, 120)}</div>
        )}
      </div>

      {onOpen && (
        <span className="sihint__card-arrow" aria-hidden="true">→</span>
      )}
    </div>
  )
}
