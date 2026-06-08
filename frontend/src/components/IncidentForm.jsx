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

const EMPTY_VICTIM = {
  full_name: '',
  birth_date: '',
  age: '',
  family_status: '',
  children_under_21: '',
  profession: '',
  workplace: '',
  total_experience: '',
  experience_in_organization: '',
  qualification_certificate: '',
  introductory_briefing: '',
  workplace_briefing: '',
  internship: '',
  safety_knowledge_test: '',
  medical_examination: '',
  diagnosis_severity: '',
}

const DEFAULTS = {
  title: '', description: '', incident_date: '', location: '',
  incident_type: 'injury', severity: 'moderate', victims: 0,
  methodology: 'bowtie', language: 'ru', detail_level: 2,
  incident_time: '', company: '', department: '', location_detailed: '',
  injured_count: 0, fatalities_count: 0, short_description: '',
  photo_urls: [], scene_description: '', equipment_description: '',
  full_circumstances: '', established_facts: '', victims_list: [],
  mode: 'single',           // 'single' | 'multi'
  methodologies: ['bowtie'], // только для mode='multi'
}

export default function IncidentForm({ onSubmit, onSubmitMulti, loading }) {
  const [form, setForm] = useState(DEFAULTS)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadError, setUploadError] = useState(null)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [expandedVictims, setExpandedVictims] = useState({})
  const fileInputRef = useRef(null)

  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }))
  }

  // --- Mode helpers ---
  function isMulti() { return form.mode === 'multi' }

  function toggleMethodology(method) {
    setForm(f => {
      const list = f.methodologies.includes(method)
        ? f.methodologies.filter(m => m !== method)
        : [...f.methodologies, method]
      return { ...f, methodologies: list }
    })
  }

  // --- Victims list helpers ---
  function addVictim() {
    const newList = [...form.victims_list, { ...EMPTY_VICTIM }]
    setForm(f => ({ ...f, victims_list: newList }))
    setExpandedVictims(e => ({ ...e, [newList.length - 1]: true }))
  }

  function removeVictim(idx) {
    setForm(f => ({ ...f, victims_list: f.victims_list.filter((_, i) => i !== idx) }))
    setExpandedVictims(e => {
      const next = {}
      Object.keys(e).forEach(k => { if (Number(k) !== idx) next[Number(k) > idx ? k - 1 : k] = e[k] })
      return next
    })
  }

  function setVictim(idx, field, value) {
    setForm(f => {
      const list = [...f.victims_list]
      list[idx] = { ...list[idx], [field]: value }
      return { ...f, victims_list: list }
    })
  }

  function toggleVictim(idx) {
    setExpandedVictims(e => ({ ...e, [idx]: !e[idx] }))
  }

  // --- File upload ---
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
    setUploadMessage('Начинаем загрузку...')
    setUploadError(null)
    setUploadedFile(file.name)
    try {
      const fields = await api.uploadReportStream(file, (evt) => {
        if (evt.status === 'reading') setUploadMessage('Извлечение текста из DOCX...')
        else if (evt.status === 'analyzing') setUploadMessage('Анализ текста в LLM (это может занять до 1-2 минут)...')
      })
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
        equipment: fields.equipment || prev.equipment,
        conditions: fields.conditions || prev.conditions,
        actions_taken: fields.actions_taken || prev.actions_taken,
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

    const incidentPayload = {
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
      victims_list: form.victims_list.map(v => ({
        ...v,
        birth_date: v.birth_date || undefined,
        age: v.age !== '' ? Number(v.age) : undefined,
        children_under_21: v.children_under_21 !== '' ? Number(v.children_under_21) : undefined,
      })),
    }

    if (isMulti()) {
      // Multi-analysis
      onSubmitMulti({
        methodologies: form.methodologies,
        language: form.language,
        detail_level: Number(form.detail_level),
        incident: incidentPayload,
      })
    } else {
      // Single analysis
      onSubmit({
        methodology: form.methodology,
        language: form.language,
        detail_level: Number(form.detail_level),
        incident: incidentPayload,
      })
    }
  }

  return (
    <form className="incident-form" onSubmit={handleSubmit}>
      <h2 className="form-title">Новый анализ инцидента</h2>

      {/* Upload zone */}
      <div className={`upload-zone ${dragOver ? 'upload-zone--dragover' : ''} ${uploading ? 'upload-zone--uploading' : ''} ${uploadedFile ? 'upload-zone--done' : ''}`}
        onDrop={handleDrop} onDragOver={handleDragOver} onDragLeave={handleDragLeave}
        onClick={() => !uploading && fileInputRef.current?.click()}>
        <input ref={fileInputRef} type="file" accept=".docx" onChange={handleFileSelect} style={{ display: 'none' }} />
        {uploading ? (
          <div className="upload-zone__content"><span className="upload-spinner" /><span className="upload-zone__text">{uploadMessage}</span></div>
        ) : uploadedFile ? (
          <div className="upload-zone__content"><span className="upload-zone__icon">✅</span><span className="upload-zone__text">Поля заполнены из «{uploadedFile}»</span>
            <button type="button" className="upload-zone__clear" onClick={(e) => { e.stopPropagation(); clearUpload(); }}>✕ Сбросить</button></div>
        ) : (
          <div className="upload-zone__content"><span className="upload-zone__icon">📄</span><span className="upload-zone__text">Загрузите отчёт об инциденте</span></div>
        )}
      </div>

      {uploadError && <div className="upload-error"><strong>Ошибка загрузки:</strong> {uploadError}</div>}
      <div className="form-divider" />

      {/* Раздел 1: Обстоятельства */}
      <div className="form-section-label">1. Описание обстоятельств происшествия</div>

      <div className="form-row">
        <div className="form-group form-group--full"><label>Заголовок инцидента</label>
          <input type="text" value={form.title} onChange={e => set('title', e.target.value)} required minLength={5} /></div>
      </div>

      <div className="form-row">
        <div className="form-group form-group--full"><label>Описание</label>
          <textarea rows={4} value={form.description} onChange={e => set('description', e.target.value)} required minLength={20} /></div>
      </div>

      <div className="form-row">
        <div className="form-group"><label>Дата инцидента</label>
          <input type="date" value={form.incident_date} onChange={e => set('incident_date', e.target.value)} /></div>
        <div className="form-group"><label>Время инцидента</label>
          <input type="time" value={form.incident_time} onChange={e => set('incident_time', e.target.value)} /></div>
        <div className="form-group"><label>Местоположение</label>
          <input type="text" value={form.location} onChange={e => set('location', e.target.value)} placeholder="Цех №3, участок сборки" /></div>
      </div>

      <div className="form-row">
        <div className="form-group"><label>Предприятие</label>
          <input type="text" value={form.company} onChange={e => set('company', e.target.value)} placeholder="ООО «ПромБезопасность»" /></div>
        <div className="form-group"><label>Подразделение</label>
          <input type="text" value={form.department} onChange={e => set('department', e.target.value)} placeholder="Производственный цех" /></div>
        <div className="form-group"><label>Детальное место</label>
          <input type="text" value={form.location_detailed} onChange={e => set('location_detailed', e.target.value)} /></div>
      </div>

      <div className="form-row">
        <div className="form-group form-group--sm"><label>Пострадавшие</label>
          <input type="number" min={0} value={form.injured_count} onChange={e => set('injured_count', e.target.value)} /></div>
        <div className="form-group form-group--sm"><label>Погибшие</label>
          <input type="number" min={0} value={form.fatalities_count} onChange={e => set('fatalities_count', e.target.value)} /></div>
        <div className="form-group form-group--full"><label>Краткое описание</label>
          <input type="text" value={form.short_description} onChange={e => set('short_description', e.target.value)} /></div>
      </div>

      <div className="form-divider" />

      {/* Раздел 2: Фото */}
      <div className="form-section-label">2. Фото с места происшествия</div>
      <div className="form-row">
        <div className="form-group form-group--full">
          <label>Ссылки на фото (по одной на строку)</label>
          <textarea
            rows={3}
            placeholder="https://..."
            value={form.photo_urls.join('\n')}
            onChange={e => set('photo_urls', e.target.value.split('\n').map(s => s.trim()).filter(Boolean))}
          />
          {form.photo_urls.length > 0 && (
            <div className="photo-previews">
              {form.photo_urls.map((url, i) => (
                <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="photo-link">📷 Фото {i + 1}</a>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="form-divider" />

      {/* Раздел 3: Установленные факты */}
      <div className="form-section-label">3. Установленные факты</div>

      {/* 3.1 Пострадавшие */}
      <div className="victims-section">
        <div className="victims-header">
          <span className="form-subsection-label">3.1. Сведения о пострадавших</span>
          <button type="button" className="btn-add-victim" onClick={addVictim}>+ Добавить пострадавшего</button>
        </div>

        {form.victims_list.length === 0 && (
          <div className="victims-empty">Нет добавленных пострадавших — заполните вручную или загрузите .docx</div>
        )}

        {form.victims_list.map((v, idx) => (
          <div key={idx} className="victim-card">
            <div className="victim-card__header" onClick={() => toggleVictim(idx)}>
              <span className="victim-card__title">
                {v.full_name ? v.full_name : `Пострадавший ${idx + 1}`}
              </span>
              <div className="victim-card__actions">
                <span className="victim-card__toggle">{expandedVictims[idx] ? '▲' : '▼'}</span>
                <button type="button" className="victim-card__remove" onClick={e => { e.stopPropagation(); removeVictim(idx) }}>✕</button>
              </div>
            </div>

            {expandedVictims[idx] && (
              <div className="victim-card__body">
                <div className="form-row">
                  <div className="form-group form-group--full"><label>ФИО</label>
                    <input type="text" value={v.full_name} onChange={e => setVictim(idx, 'full_name', e.target.value)} placeholder="Иванов Иван Иванович" /></div>
                </div>
                <div className="form-row">
                  <div className="form-group"><label>Дата рождения</label>
                    <input type="date" value={v.birth_date} onChange={e => setVictim(idx, 'birth_date', e.target.value)} /></div>
                  <div className="form-group form-group--sm"><label>Возраст</label>
                    <input type="number" min={14} max={99} value={v.age} onChange={e => setVictim(idx, 'age', e.target.value)} /></div>
                  <div className="form-group"><label>Семейное положение</label>
                    <input type="text" value={v.family_status} onChange={e => setVictim(idx, 'family_status', e.target.value)} placeholder="Женат / Замужем / …" /></div>
                  <div className="form-group form-group--sm"><label>Детей до 21 г.</label>
                    <input type="number" min={0} value={v.children_under_21} onChange={e => setVictim(idx, 'children_under_21', e.target.value)} /></div>
                </div>
                <div className="form-row">
                  <div className="form-group"><label>Профессия / должность</label>
                    <input type="text" value={v.profession} onChange={e => setVictim(idx, 'profession', e.target.value)} /></div>
                  <div className="form-group"><label>Место работы</label>
                    <input type="text" value={v.workplace} onChange={e => setVictim(idx, 'workplace', e.target.value)} /></div>
                </div>
                <div className="form-row">
                  <div className="form-group"><label>Общий стаж</label>
                    <input type="text" value={v.total_experience} onChange={e => setVictim(idx, 'total_experience', e.target.value)} placeholder="5 лет 3 мес." /></div>
                  <div className="form-group"><label>Стаж в организации</label>
                    <input type="text" value={v.experience_in_organization} onChange={e => setVictim(idx, 'experience_in_organization', e.target.value)} placeholder="2 года" /></div>
                  <div className="form-group"><label>Квалификационное удостоверение</label>
                    <input type="text" value={v.qualification_certificate} onChange={e => setVictim(idx, 'qualification_certificate', e.target.value)} /></div>
                </div>
                <div className="form-row">
                  <div className="form-group"><label>Вводный инструктаж</label>
                    <input type="text" value={v.introductory_briefing} onChange={e => setVictim(idx, 'introductory_briefing', e.target.value)} placeholder="дд.мм.гггг / не проводился" /></div>
                  <div className="form-group"><label>Первичный / повторный инструктаж</label>
                    <input type="text" value={v.workplace_briefing} onChange={e => setVictim(idx, 'workplace_briefing', e.target.value)} placeholder="дд.мм.гггг / не проводился" /></div>
                </div>
                <div className="form-row">
                  <div className="form-group"><label>Стажировка / допуск к работе</label>
                    <input type="text" value={v.internship} onChange={e => setVictim(idx, 'internship', e.target.value)} placeholder="дд.мм.гггг / не проводилась" /></div>
                  <div className="form-group"><label>Проверка знаний по ОТ</label>
                    <input type="text" value={v.safety_knowledge_test} onChange={e => setVictim(idx, 'safety_knowledge_test', e.target.value)} placeholder="дд.мм.гггг / не проводилась" /></div>
                  <div className="form-group"><label>Медицинский осмотр</label>
                    <input type="text" value={v.medical_examination} onChange={e => setVictim(idx, 'medical_examination', e.target.value)} placeholder="дд.мм.гггг / не проходил" /></div>
                </div>
                <div className="form-row">
                  <div className="form-group form-group--full"><label>Диагноз / степень тяжести</label>
                    <input type="text" value={v.diagnosis_severity} onChange={e => setVictim(idx, 'diagnosis_severity', e.target.value)} placeholder="Перелом, лёгкая степень…" /></div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 3.2 Описание места */}
      <div className="form-subsection-label" style={{ marginTop: 8 }}>3.2. Описание места происшествия</div>
      <div className="form-row">
        <div className="form-group form-group--full">
          <textarea rows={3} value={form.scene_description} onChange={e => set('scene_description', e.target.value)} /></div>
      </div>

      {/* 3.4 Характеристика оборудования */}
      <div className="form-subsection-label">3.4. Характеристика оборудования / объекта</div>
      <div className="form-row">
        <div className="form-group form-group--full">
          <textarea rows={3} value={form.equipment_description} onChange={e => set('equipment_description', e.target.value)} /></div>
      </div>

      {/* 3.5 Полное описание */}
      <div className="form-subsection-label">3.5. Полное описание обстоятельств</div>
      <div className="form-row">
        <div className="form-group form-group--full">
          <textarea rows={4} value={form.full_circumstances} onChange={e => set('full_circumstances', e.target.value)} /></div>
      </div>

      {/* 3.6 Установленные факты */}
      <div className="form-subsection-label">3.6. Установленные факты</div>
      <div className="form-row">
        <div className="form-group form-group--full">
          <textarea rows={4} value={form.established_facts} onChange={e => set('established_facts', e.target.value)} /></div>
      </div>

      <div className="form-divider" />

      {/* Тип / тяжесть */}
      <div className="form-row">
        <div className="form-group"><label>Тип инцидента</label>
          <select value={form.incident_type} onChange={e => set('incident_type', e.target.value)}>{TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}</select>
        </div>
        <div className="form-group"><label>Тяжесть</label>
          <select value={form.severity} onChange={e => set('severity', e.target.value)}>{SEVERITIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}</select>
        </div>
      </div>

      <div className="form-divider" />

      {/* Параметры анализа */}
      <div className="form-section-label">Параметры анализа</div>

      {/* === Режим анализа: одиночный или сравнение === */}
      <div className="mode-selector">
        <label className={`mode-option ${!isMulti() ? 'mode-option--active' : ''}`}>
          <input
            type="radio"
            name="mode"
            value="single"
            checked={!isMulti()}
            onChange={() => set('mode', 'single')}
          />
          <span className="mode-option__content">
            <span className="mode-option__icon">🎯</span>
            <span className="mode-option__label">Одна методика</span>
          </span>
        </label>
        <label className={`mode-option ${isMulti() ? 'mode-option--active' : ''}`}>
          <input
            type="radio"
            name="mode"
            value="multi"
            checked={isMulti()}
            onChange={() => set('mode', 'multi')}
          />
          <span className="mode-option__content">
            <span className="mode-option__icon">⚖️</span>
            <span className="mode-option__label">Сравнить методики</span>
          </span>
        </label>
      </div>

      {/* === Одиночный режим: дропдаун === */}
      {!isMulti() && (
        <div className="form-row">
          <div className="form-group">
            <label>Методология</label>
            <select value={form.methodology} onChange={e => set('methodology', e.target.value)}>
              {METHODOLOGIES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <div className="form-group"><label>Язык</label>
            <select value={form.language} onChange={e => set('language', e.target.value)}><option value="ru">Русский</option><option value="en">English</option></select>
          </div>
          <div className="form-group form-group--sm"><label>Детализация</label>
            <select value={form.detail_level} onChange={e => set('detail_level', e.target.value)}><option value={1}>1 — кратко</option><option value={2}>2 — стандарт</option><option value={3}>3 — подробно</option></select>
          </div>
        </div>
      )}

      {/* === Мульти-режим: чекбоксы === */}
      {isMulti() && (
        <>
          <div className="checkbox-group">
            {METHODOLOGIES.map(m => (
              <label key={m.value} className={`checkbox-card ${form.methodologies.includes(m.value) ? 'checkbox-card--checked' : ''}`}>
                <input
                  type="checkbox"
                  checked={form.methodologies.includes(m.value)}
                  onChange={() => toggleMethodology(m.value)}
                  className="checkbox-card__input"
                />
                <span className="checkbox-card__check">
                  {form.methodologies.includes(m.value) ? '✓' : ''}
                </span>
                <span className="checkbox-card__label">{m.label}</span>
              </label>
            ))}
          </div>

          <div className="form-row">
            <div className="form-group"><label>Язык</label>
              <select value={form.language} onChange={e => set('language', e.target.value)}><option value="ru">Русский</option><option value="en">English</option></select>
            </div>
            <div className="form-group form-group--sm"><label>Детализация</label>
              <select value={form.detail_level} onChange={e => set('detail_level', e.target.value)}><option value={1}>1 — кратко</option><option value={2}>2 — стандарт</option><option value={3}>3 — подробно</option></select>
            </div>
          </div>

          {form.methodologies.length < 2 && (
            <div className="multi-hint">⚠️ Выберите минимум 2 методики для сравнения</div>
          )}
        </>
      )}

      {/* === Кнопка === */}
      <button
        type="submit"
        className={`btn-analyze ${isMulti() ? 'btn-analyze--multi' : ''}`}
        disabled={loading || (isMulti() && form.methodologies.length < 2)}
      >
        {loading ? (
          <><span className="spinner" /> Анализирую…</>
        ) : isMulti() ? (
          `⚖️ Сравнить (${form.methodologies.length} методик)`
        ) : (
          '▶ Запустить анализ'
        )}
      </button>
    </form>
  )
}
