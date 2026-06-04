import React, { useState } from 'react'
import './IncidentForm.css'

const METHODOLOGIES = [
  { value: 'ishikawa',     label: 'Ishikawa (Рыбья кость)' },
  { value: 'five_why',     label: '5 Почему' },
  { value: 'fta',          label: 'FTA (Дерево отказов)' },
  { value: 'rca_systemic', label: 'RCA Системный' },
  { value: 'bowtie',       label: 'Bowtie (Бабочка)' },
]

const SEVERITIES = [
  { value: 'critical',  label: 'Критический' },
  { value: 'major',     label: 'Тяжёлый' },
  { value: 'moderate',  label: 'Средний' },
  { value: 'minor',     label: 'Лёгкий' },
  { value: 'near_miss', label: 'Предпосылка' },
]

const TYPES = [
  { value: 'injury',        label: 'Травма' },
  { value: 'equipment',     label: 'Оборудование' },
  { value: 'fire',          label: 'Пожар' },
  { value: 'spill',         label: 'Разлив' },
  { value: 'near_miss',     label: 'Предпосылка' },
  { value: 'process_upset', label: 'Нарушение процесса' },
  { value: 'security',      label: 'Безопасность' },
  { value: 'environmental', label: 'Экология' },
]

const DEFAULTS = {
  title: 'Падение работника с лестницы',
  description: 'Работник поскользнулся на мокрой ступени и упал с высоты 2 м.',
  incident_date: '2026-06-01T09:30',
  location: 'Цех №3, отметка +6м',
  incident_type: 'injury',
  severity: 'moderate',
  victims: 1,
  methodology: 'bowtie',
  language: 'ru',
  detail_level: 2,
}

export default function IncidentForm({ onSubmit, loading }) {
  const [form, setForm] = useState(DEFAULTS)

  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    onSubmit({
      methodology: form.methodology,
      language: form.language,
      detail_level: Number(form.detail_level),
      incident: {
        title: form.title,
        description: form.description,
        incident_date: form.incident_date + ':00',
        location: form.location,
        incident_type: form.incident_type,
        severity: form.severity,
        victims: form.victims ? Number(form.victims) : undefined,
      },
    })
  }

  return (
    <form className="incident-form" onSubmit={handleSubmit}>
      <h2 className="form-title">Новый анализ инцидента</h2>

      <div className="form-row">
        <div className="form-group form-group--full">
          <label>Заголовок инцидента</label>
          <input
            type="text"
            value={form.title}
            onChange={e => set('title', e.target.value)}
            required
            minLength={5}
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group form-group--full">
          <label>Описание</label>
          <textarea
            rows={3}
            value={form.description}
            onChange={e => set('description', e.target.value)}
            required
            minLength={20}
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Дата и время</label>
          <input
            type="datetime-local"
            value={form.incident_date}
            onChange={e => set('incident_date', e.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <label>Место</label>
          <input
            type="text"
            value={form.location}
            onChange={e => set('location', e.target.value)}
            required
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Тип инцидента</label>
          <select value={form.incident_type} onChange={e => set('incident_type', e.target.value)}>
            {TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Тяжесть</label>
          <select value={form.severity} onChange={e => set('severity', e.target.value)}>
            {SEVERITIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        <div className="form-group form-group--sm">
          <label>Пострадавших</label>
          <input
            type="number"
            min={0}
            value={form.victims}
            onChange={e => set('victims', e.target.value)}
          />
        </div>
      </div>

      <div className="form-divider" />

      <div className="form-row">
        <div className="form-group">
          <label>Методология</label>
          <select value={form.methodology} onChange={e => set('methodology', e.target.value)}>
            {METHODOLOGIES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Язык отчёта</label>
          <select value={form.language} onChange={e => set('language', e.target.value)}>
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
        </div>
        <div className="form-group form-group--sm">
          <label>Детализация</label>
          <select value={form.detail_level} onChange={e => set('detail_level', e.target.value)}>
            <option value={1}>1 — кратко</option>
            <option value={2}>2 — стандарт</option>
            <option value={3}>3 — подробно</option>
          </select>
        </div>
      </div>

      <button type="submit" className="btn-analyze" disabled={loading}>
        {loading ? (
          <><span className="spinner" /> Анализирую…</>
        ) : (
          '▶ Запустить анализ'
        )}
      </button>
    </form>
  )
}
