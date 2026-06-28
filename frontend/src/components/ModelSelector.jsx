import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Select } from './ui/Field.jsx'
import { Zap, Scale, FileText } from 'lucide-react'
import './ModelSelector.css'

const CATEGORY_META = {
  full:     { label: 'Большой контекст (≥64K)',     icon: FileText, desc: 'Сложный анализ с большим объёмом вводных данных' },
  balanced: { label: 'Средний контекст (16K–63K)', icon: Scale,    desc: 'Универсальные задачи, средний объём' },
  express:  { label: 'Малый контекст (<16K)',      icon: Zap,      desc: 'Небольшие инциденты, простые вопросы' },
}

export default function ModelSelector({ disabled, onPrefsChange }) {
  const [models, setModels] = useState({ full: [], balanced: [], express: [] })
  const [prefs, setPrefs] = useState({ full: '', balanced: '', express: '' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [modelsRes, prefsRes] = await Promise.all([
          api.fetchJson('/api/v1/user/models'),
          api.fetchJson('/api/v1/user/model-preferences'),
        ])
        if (cancelled) return

        const cats = modelsRes.categories || {}
        const byKey = {}
        for (const key of ['full', 'balanced', 'express']) {
          const cat = cats[key]
          byKey[key] = cat?.models ?? []
        }
        setModels(byKey)

        const p = {}
        if (prefsRes.full) p.full = prefsRes.full
        if (prefsRes.balanced) p.balanced = prefsRes.balanced
        if (prefsRes.express) p.express = prefsRes.express
        setPrefs(p)
        onPrefsChange?.(p)  // сообщаем родителю
      } catch (err) {
        setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  async function handleChange(category, value) {
    const next = { ...prefs, [category]: value }
    setPrefs(next)
    onPrefsChange?.(next)  // сообщаем родителю сразу
    try {
      await api.fetchJson('/api/v1/user/model-preferences', {
        method: 'PUT',
        body: JSON.stringify(next),
      })
    } catch { /* silent */ }
  }

  if (error) {
    return <div className="model-selector model-selector--error">⚠️ {error}</div>
  }

  const total = (models.full?.length ?? 0) + (models.balanced?.length ?? 0) + (models.express?.length ?? 0)
  if (!loading && total === 0) return null

  return (
    <div className="model-selector">
      <div className="model-selector__title">Модель анализа</div>
      <div className="model-selector__grid">
        {['full', 'balanced', 'express'].map(key => {
          const meta = CATEGORY_META[key]
          const Icon = meta.icon
          const list = models[key] ?? []
          const selected = prefs[key] || ''
          return (
            <div key={key} className="model-selector__item">
              <div className="model-selector__item-header">
                <Icon size={16} />
                <span>{meta.label}</span>
              </div>
              <Select
                value={selected}
                onChange={e => handleChange(key, e.target.value)}
                disabled={disabled || loading || list.length === 0}
              >
                <option value="">—</option>
                {list.map(m => {
                  const label = m.is_free
                    ? `${m.name} 🟢`
                    : `${m.name} 🟠 $${m.pricing_prompt ?? '?'}/${m.pricing_completion ?? '?'}`
                  return (
                    <option key={m.model_id} value={m.model_id}>{label}</option>
                  )
                })}
              </Select>
              <div className="model-selector__desc">{meta.desc}</div>
              {!loading && selected && (() => {
                const m = list.find(x => x.model_id === selected)
                return m && !m.is_free ? (
                  <div className="model-selector__cost">
                    🟠 Платная: ${m.pricing_prompt ?? '?'} промпт / ${m.pricing_completion ?? '?'} completion за 1K токенов
                  </div>
                ) : m?.is_free ? (
                  <div className="model-selector__cost model-selector__cost--free">🟢 Бесплатно</div>
                ) : null
              })()}
            </div>
          )
        })}
      </div>
    </div>
  )
}
