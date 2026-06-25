import React, { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { Link } from 'lucide-react'
import './SimilarIncidentsHint.css'

/**
 * Лёгкий индикатор количества похожих инцидентов.
 */
export default function SimilarIncidentsHint({ queryText, incidentTitle = null, incidentDescription = null }) {
  const [count, setCount] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.similarIncidents(queryText, { limit: 10, incidentTitle, incidentDescription })
      setCount(data?.length ?? 0)
    } catch {
      setCount(null)
    } finally {
      setLoading(false)
    }
  }, [queryText, incidentTitle, incidentDescription])

  useEffect(() => {
    if (queryText.length < 20) return
    const timer = setTimeout(load, 1000)
    return () => clearTimeout(timer)
  }, [queryText, load])

  if (loading && count === null) {
    return (
      <div className="similar-incidents-hint similar-incidents-hint--loading">
        <svg className="similar-incidents-hint__spinner" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
        <span>Ищу похожие инциденты…</span>
      </div>
    )
  }

  if (count === null) return null

  if (count === 0) {
    return (
      <div className="similar-incidents-hint similar-incidents-hint--empty">
        <span><Link size={14} /></span>
        <span>Похожих инцидентов в истории не найдено</span>
      </div>
    )
  }

  const word = count === 1 ? 'инцидент' : count < 5 ? 'инцидента' : 'инцидентов'

  return (
    <div className="similar-incidents-hint similar-incidents-hint--found">
      <span><Link size={14} /></span>
      <span>
        Найдено <strong className="similar-incidents-hint__count">{count}</strong> похожих {word} — подробности покажем после анализа
      </span>
    </div>
  )
}
