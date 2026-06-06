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
  title: '',
  description: '',
  incident_date: '',
  location: '',
  incident_type: 'injury',
  severity: 'moderate',
  victims: 0,
  methodology: 'bowtie',
  language: 'ru',
  detail_level: 2,
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

  // --- DOCX Upload ---

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

      // Заполняем форму извлечёнными данными
      setForm(prev => ({
        ...prev,
        title: fields.title || prev.title,
        description: fields.description || prev.description,
        incident_date: fields.incident_date
          ? fields.incident_date.slice(0, 16)  // datetime-local формат
          : prev.incident_date,
        location: fields.location || prev.location,
        incident_type: fields.incident_type || prev.incident_type,
        severity: fields.severity || prev.severity,
        victims: fields.victims ?? prev.victims,
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
    // Сброс input чтобы можно было загрузить тот же файл повторно
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) processFile(file)
  }

  function handleDragOver(e) {
    e.preventDefault()
    setDragOver(true)
  }

  function handleDragLeave(e) {
    e.preventDefault()
    setDragOver(false)
  }

  function clearUpload() {
    setUploadedFile(null)
    setUploadError(null)
  }

  // --- Submit ---

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

      {/* --- Зона загрузки DOCX --- */}
      <div
        className={`upload-zone ${dragOver ? 'upload-zone--dragover' : ''} ${uploading ? 'upload-zone--uploading' : ''} ${uploadedFile ? 'upload-zone--done' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !uploading && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".docx"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />

        {uploading ? (
          <div className="upload-zone__content">
            <span className="upload-spinner" />
            <span className="upload-zone__text">ИИ анализирует отчёт…</span>
            <span className="upload-zone__hint">Извлекаю данные из «{uploadedFile}»</span>
          </div>
        ) : uploadedFile ? (
          <div className="upload-zone__content">
            <span className="upload-zone__icon">✅</span>
            <span className="upload-zone__text">Поля заполнены из «{uploadedFile}»</span>
            <span className="upload-zone__hint">Проверьте и отредактируйте данные ниже, затем запустите анализ</span>
            <button type="button" className="upload-zone__clear" onClick={(e) => { e.stopPropagation(); clearUpload(); }}>
              ✕ Сбросить
            </button>
          </div>
        ) : (
          <div className="upload-zone__content">
            <span className="upload-zone__icon">📄</span>
            <span className="upload-zone__text">Загрузите отчёт об инциденте</span>
            <span className="upload-zone__hint">
              Перетащите DOCX-файл сюда или нажмите для выбора.
              ИИ извлечёт данные и заполнит форму автоматически.
            </span>
          </div>
        )}
      </div>

      {uploadError && (
        <div className="upload-error">
          <strong>Ошибка загрузки:</strong> {uploadError}
        </div>
      )}

      <div className="form-divider" />

      {/* --- Ручной ввод / редактирование --- */}

      <div className="form-row">
        <div className="form-group form-group--full">
          <label>Заголовок инцидента</label>
          <input
            type="text"
            value={form.title}
            onChange={e => set('title', e.target.value)}
            required
            minLength={5}
            placeholder="Введите заголовок или загрузите отчёт"
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group form-group--full">
          <label>Описание</label>
          <textarea
            rows={4}
            value={form.description}
            onChange={e => set('description', e.target.value)}
            required
            minLength={20}
            placeholder="Подробное описание инцидента"
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
            placeholder="Место инцидента"
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
