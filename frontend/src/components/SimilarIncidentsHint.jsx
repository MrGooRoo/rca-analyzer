import './SimilarIncidentsHint.css'

import React, { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'

/**
 * Лёгкий индикатор количества похожих инцидентов.
 * Показывает одну строку: «🔗 Найдено 3 похожих инцидента — результат покажем после анализа»
 * Полный блок — в ResultView.
 */
export default function SimilarIncidentsHint({ queryText, incidentTitle = null, incidentDescription = null }) {
  const [count, setCount] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.similarIncidents(queryText, {
        limit: 10,
        incidentTitle,
        incidentDescription,
      })
      setCount(data?.length ?? 0)
    } catch {
      setCount(null)
    } finally {
      setLoading(false)
    }
  }, [queryText, incidentTitle, incidentDescription])

  // Автопоиск с задержкой 1 сек (чтобы не дергать API на каждый символ)
  useEffect(() => {
    if (queryText.length < 20) return
    const timer = setTimeout(load, 1000)
    return () => clearTimeout(timer)
  }, [queryText, load])

  if (loading && count === null) {
    return (
      <div className="similar-hint similar-hint--loading">
        <span className="similar-hint__spinner" />
        <span>Ищу похожие инциденты…</span>
      </div>
    )
  }

  if (count === null) return null

  if (count === 0) {
    return (
      <div className="similar-hint similar-hint--empty">
        <span className="similar-hint__icon">🔗</span>
        <span>Похожих инцидентов в истории не найдено</span>
      </div>
    )
  }

  const word = count === 1 ? 'инцидент' : count < 5 ? 'инцидента' : 'инцидентов'

  return (
    <div className="similar-hint">
      <span className="similar-hint__icon">🔗</span>
      <span>
        Найдено <strong>{count}</strong> похожих {word} —
        подробности покажем после анализа
      </span>
    </div>
  )
}
