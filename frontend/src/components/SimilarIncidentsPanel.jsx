import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import './SimilarIncidentsPanel.css'

const METHODOLOGY_LABELS = {
  ishikawa:     'Ishikawa',
  five_why:     '5 Почему',
  fta:          'FTA',
  rca_systemic: 'RCA',
  bowtie:       'Bowtie',
}

function normalizeQuery(text) {
  return String(text || '').replace(/\s+/g, ' ').trim().slice(0, 5000)
}

export default function SimilarIncidentsPanel({
  queryText,
  excludeResultId = null,
  excludeIncidentId = null,
  auto = false,
  title = 'Похожие инциденты',
  compact = false,
}) {
  const query = useMemo(() => normalizeQuery(queryText), [queryText])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searched, setSearched] = useState(false)

  const canSearch = query.length >= 20

  const load = useCallback(async () => {
    if (!canSearch) return
    setLoading(true)
    setError(null)
    setSearched(true)
    try {
      const data = await api.similarIncidents(query, {
        limit: 5,
        threshold: 0.15,
        excludeResultId,
        excludeIncidentId,
      })
      setItems(data || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [canSearch, query, excludeResultId, excludeIncidentId])

  useEffect(() => {
    if (auto && canSearch) load()
  }, [auto, canSearch, load])

  if (!auto && !canSearch) {
    return (
      <section className={`similar-panel ${compact ? 'similar-panel--compact' : ''}`}>
        <div className="similar-panel__header">
          <div>
            <h3>{title}</h3>
            <p>Заполните описание — затем можно найти похожие случаи в истории.</p>
          </div>
          <button type="button" className="similar-panel__btn" disabled>Найти</button>
        </div>
      </section>
    )
  }

  return (
    <section className={`similar-panel ${compact ? 'similar-panel--compact' : ''}`}>
      <div className="similar-panel__header">
        <div>
          <h3>{title}</h3>
          <p>Поиск идёт по summary, причинам и рекомендациям ранее сохранённых RCA-результатов.</p>
        </div>
        {!auto && (
          <button
            type="button"
            className="similar-panel__btn"
            onClick={load}
            disabled={loading || !canSearch}
          >
            {loading ? 'Ищу…' : 'Найти похожие'}
          </button>
        )}
      </div>

      {loading && <div className="similar-panel__status">Поиск похожих инцидентов…</div>}
      {error && <div className="similar-panel__error">Ошибка поиска: {error}</div>}

      {!loading && !error && searched && items.length === 0 && (
        <div className="similar-panel__empty">Похожих инцидентов пока не найдено.</div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="similar-panel__list">
          {items.map(item => (
            <SimilarCard key={item.result_id} item={item} />
          ))}
        </div>
      )}
    </section>
  )
}

function SimilarCard({ item }) {
  const date = new Date(item.created_at).toLocaleDateString('ru-RU')
  const percent = Math.round((item.similarity || 0) * 100)
  const author = item.user_display_name || item.user_email || null

  return (
    <div className="similar-card">
      <div className="similar-card__top">
        <span className="similar-card__score">{percent}% похоже</span>
        <span className="similar-card__method">
          {METHODOLOGY_LABELS[item.methodology] || item.methodology}
        </span>
        <span className="similar-card__date">{date}</span>
        {author && <span className="similar-card__author">👤 {author}</span>}
      </div>
      <p className="similar-card__summary">{item.summary}</p>
      {item.root_causes_preview?.length > 0 && (
        <div className="similar-card__section">
          <strong>Корневые причины:</strong>
          <ul>
            {item.root_causes_preview.map((text, idx) => <li key={idx}>{text}</li>)}
          </ul>
        </div>
      )}
      {item.recommendations_preview?.length > 0 && (
        <div className="similar-card__section">
          <strong>Рекомендации:</strong>
          <ul>
            {item.recommendations_preview.map((text, idx) => <li key={idx}>{text}</li>)}
          </ul>
        </div>
      )}
      <div className="similar-card__footer">
        <span>result #{item.result_id.slice(0, 8)}</span>
        <span>incident #{item.incident_id.slice(0, 8)}</span>
      </div>
    </div>
  )
}
