import React, { useState, useRef } from 'react'
import { api } from '../api.js'
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
  title: '', description: '', incident_date: '', location: '',
  incident_type: 'injury', severity: 'moderate', victims: 0,
  methodology: 'bowtie', language: 'ru', detail_level: 2,
  incident_time: '', company: '', department: '', location_detailed: '',
  injured_count: 0, fatalities_count: 0, short_description: '',
  photo_urls: [], scene_description: '', equipment_description: '',
  full_circumstances: '', established_facts: '', victims_list: [],
}

export default function IncidentForm({ onSubmit, loading }) {
  const [form, setForm] = useState(DEFAULTS)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)

  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }))
  }

  async function processFile(file) {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setUploadError('Допустимы только файлы формата .docx')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError('Файл слишком большой (макс. 10 МБ)')
      return
    }

    setUploading(true)
    setUploadError(null)
    setUploadedFile(file.name)

    try {
      const fields = await api.uploadReport(file)
      setForm(prev => ({
        ...prev,
        title: fields.title || prev.title,
        description: fields.description || prev.description,
        incident_date: fields.incident_date ? fields.incident_date.slice(0, 10) : prev.incident_date,
        incident_time: fields.incident_time || prev.incident_time,
        company: fields.company || prev.company,
        department: fields.department || prev.department,
        location: fields.location || prev.location,
        injured_count: fields.injured_count ?? prev.injured_count,
        fatalities_count: fields.fatalities_count ?? prev.fatalities_count,
        short_description: fields.short_description || prev.short_description,
        incident_type: fields.incident_type || prev.incident_type,
        severity: fields.severity || prev.severity,
        scene_description: fields.scene_description || prev.scene_description,
        equipment_description: fields.equipment_description || prev.equipment_description,
        full_circumstances: fields.full_circumstances || prev.full_circumstances,
        established_facts: fields.established_facts || prev.established_facts,
        victims_list: fields.victims_list || prev.victims_list,
      }))
    } catch (e) {
      setUploadError(e.message)
      setUploadedFile(null)
    } finally {
      setUploading(false)
    }
  }

  function handleFileSelect(e) {
    const file = e.target.files?.[0]
    if (file) processFile(file)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function handleDrop(e) { e.preventDefault(); setDragOver(false); const file = e.dataTransfer.files?.[0]; if (file) processFile(file) }
  function handleDragOver(e) { e.preventDefault(); setDragOver(true) }
  function handleDragLeave(e) { e.preventDefault(); setDragOver(false) }
  function clearUpload() { setUploadedFile(null); setUploadError(null) }

  function handleSubmit(e) {
    e.preventDefault()
    onSubmit({
      methodology: form.methodology,
      language: form.language,
      detail_level: Number(form.detail_level),
      incident: {
        title: form.title,
        description: form.description,
        incident_date: form.incident_date ? form.incident_date + 'T00:00:00' : null,
        location: form.location,
        incident_type: form.incident_type,
        severity: form.severity,
        victims: form.victims ? Number(form.victims) : undefined,
        equipment: form.equipment || undefined,
        conditions: form.conditions || undefined,
        actions_taken: form.actions_taken || undefined,
        incident_time: form.incident_time || undefined,
        company: form.company || undefined,
        department: form.department || undefined,
        location_detailed: form.location_detailed || undefined,
        injured_count: form.injured_count || undefined,
        fatalities_count: form.fatalities_count || undefined,
        short_description: form.short_description || undefined,
        photo_urls: form.photo_urls || [],
        scene_description: form.scene_description || undefined,
        equipment_description: form.equipment_description || undefined,
        full_circumstances: form.full_circumstances || undefined,
        established_facts: form.established_facts || undefined,
        victims_list: form.victims_list || [],
      },
    })
  }

  return (
    <form className="incident-form" onSubmit={handleSubmit}>
      <h2 className="form-title">Новый анализ инцидента</h2>

      <div className={`upload-zone ${dragOver ? 'upload-zone--dragover' : ''} ${uploading ? 'upload-zone--uploading' : ''} ${uploadedFile ? 'upload-zone--done' : ''}`}
        onDrop={handleDrop} onDragOver={handleDragOver} onDragLeave={handleDragLeave}
        onClick={() => !uploading && fileInputRef.current?.click()}>
        <input ref={fileInputRef} type="file" accept=".docx" onChange={handleFileSelect} style={{ display: 'none' }} />
        {uploading ? (
          <div className="upload-zone__content"><span className="upload-spinner" /><span className="upload-zone__text">ИИ анализирует отчёт…</span></div>
        ) : uploadedFile ? (
          <div className="upload-zone__content"><span className="upload-zone__icon">✅</span><span className="upload-zone__text">Поля заполнены из «{uploadedFile}»</span>
            <button type="button" className="upload-zone__clear" onClick={(e) => { e.stopPropagation(); clearUpload(); }}>✕ Сбросить</button></div>
        ) : (
          <div className="upload-zone__content"><span className="upload-zone__icon">📄</span><span className="upload-zone__text">Загрузите отчёт об инциденте</span></div>
        )}
      </div>

      {uploadError && <div className="upload-error"><strong>Ошибка загрузки:</strong> {uploadError}</div>}
      <div className="form-divider" />

      <div className="form-row">
        <div className="form-group form-group--full"><label>Заголовок инцидента</label>
          <input type="text" value={form.title} onChange={e => set('title', e.target.value)} required minLength={5} /></div>
      </div>

      <div className="form-row">
        <div className="form-group form-group--full"><label>Описание</label>
          <textarea rows={4} value={form.description} onChange={e => set('description', e.target.value)} required minLength={20} /></div>
      </div>

      <div className="form-row">
        <div className="form-group"><label>Дата</label><input type="date" value={form.incident_date} onChange={e => set('incident_date', e.target.value)} /></div>
        <div className="form-group"><label>Время</label><input type="time" value={form.incident_time} onChange={e => set('incident_time', e.target.value)} /></div>
        <div className="form-group"><label>Компания</label><input type="text" value={form.company} onChange={e => set('company', e.target.value)} /></div>
      </div>

      <div className="form-row">
        <div className="form-group"><label>Подразделение</label><input type="text" value={form.department} onChange={e => set('department', e.target.value)} /></div>
        <div className="form-group"><label>Место происшествия</label><input type="text" value={form.location} onChange={e => set('location', e.target.value)} required /></div>
      </div>

      <div className="form-row">
        <div className="form-group form-group--sm"><label>Пострадавших</label><input type="number" min={0} value={form.injured_count} onChange={e => set('injured_count', e.target.value)} /></div>
        <div className="form-group form-group--sm"><label>Погибших</label><input type="number" min={0} value={form.fatalities_count} onChange={e => set('fatalities_count', e.target.value)} /></div>
        <div className="form-group"><label>Краткое описание</label><input type="text" value={form.short_description} onChange={e => set('short_description', e.target.value)} /></div>
      </div>

      <div className="form-divider" />

      <div className="form-row">
        <div className="form-group"><label>Тип инцидента</label>
          <select value={form.incident_type} onChange={e => set('incident_type', e.target.value)}>{TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}</select>
        </div>
        <div className="form-group"><label>Тяжесть</label>
          <select value={form.severity} onChange={e => set('severity', e.target.value)}>{SEVERITIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}</select>
        </div>
      </div>

      <div className="form-divider" />

      <div className="form-row">
        <div className="form-group form-group--full"><label>Описание места происшествия</label>
          <textarea rows={3} value={form.scene_description} onChange={e => set('scene_description', e.target.value)} /></div>
      </div>

      <div className="form-row">
        <div className="form-group form-group--full"><label>Характеристика оборудования / объекта</label>
          <textarea rows={3} value={form.equipment_description} onChange={e => set('equipment_description', e.target.value)} /></div>
      </div>

      <div className="form-row">
        <div className="form-group form-group--full"><label>Полное описание обстоятельств</label>
          <textarea rows={4} value={form.full_circumstances} onChange={e => set('full_circumstances', e.target.value)} /></div>
      </div>

      <div className="form-row">
        <div className="form-group form-group--full"><label>Установленные факты</label>
          <textarea rows={4} value={form.established_facts} onChange={e => set('established_facts', e.target.value)} /></div>
      </div>

      <div className="form-divider" />

      <div className="form-row">
        <div className="form-group"><label>Методология</label>
          <select value={form.methodology} onChange={e => set('methodology', e.target.value)}>{METHODOLOGIES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}</select>
        </div>
        <div className="form-group"><label>Язык</label>
          <select value={form.language} onChange={e => set('language', e.target.value)}><option value="ru">Русский</option><option value="en">English</option></select>
        </div>
        <div className="form-group form-group--sm"><label>Детализация</label>
          <select value={form.detail_level} onChange={e => set('detail_level', e.target.value)}><option value={1}>1 — кратко</option><option value={2}>2 — стандарт</option><option value={3}>3 — подробно</option></select>
        </div>
      </div>

      <button type="submit" className="btn-analyze" disabled={loading}>
        {loading ? (<><span className="spinner" /> Анализирую…</>) : ('▶ Запустить анализ')}
      </button>
    </form>
  )
}