import React, { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'

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
      <div className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm text-slate-400 border border-dashed border-indigo-500/20 bg-indigo-500/5">
        <svg className="h-3.5 w-3.5 animate-spin text-indigo-400" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25"/><path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg>
        <span>Ищу похожие инциденты…</span>
      </div>
    )
  }

  if (count === null) return null

  if (count === 0) {
    return (
      <div className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm text-slate-500 border border-slate-500/15 bg-slate-500/5">
        <span>🔗</span>
        <span>Похожих инцидентов в истории не найдено</span>
      </div>
    )
  }

  const word = count === 1 ? 'инцидент' : count < 5 ? 'инцидента' : 'инцидентов'

  return (
    <div className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm text-indigo-300 border border-indigo-500/20 bg-indigo-500/10">
      <span>🔗</span>
      <span>Найдено <strong className="text-indigo-400">{count}</strong> похожих {word} — подробности покажем после анализа</span>
    </div>
  )
}
