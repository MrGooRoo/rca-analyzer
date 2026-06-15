import React, { useState, useRef } from 'react'
import { api } from '../api.js'
import SimilarIncidentsHint from './SimilarIncidentsHint.jsx'
import { Button } from './ui/Button.jsx'
import { Input, Textarea, Select } from './ui/Field.jsx'
import { METHODOLOGIES } from '../lib/methodologies.js'
import './IncidentForm.css'

const SEVERITIES = [
  { value: 'critical',  label: 'Критический', hint: 'Смерть / тяжёлый вред',       color: 'critical' },
  { value: 'major',     label: 'Тяжёлый',     hint: 'Госпитализация / крупный ущерб', color: 'major' },
  { value: 'moderate',  label: 'Средний',      hint: 'Временная нетрудоспособность',  color: 'moderate' },
  { value: 'minor',     label: 'Лёгкий',       hint: 'Первая помощь / малый ущерб',   color: 'minor' },
  { value: 'near_miss', label: 'Предпосылка',  hint: 'Без пострадавших',              color: 'near_miss' },
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

const DETAIL_LEVELS = [
  { value: 1, label: 'Кратко',    hint: 'Ключевые причины и выводы' },
  { value: 2, label: 'Стандарт',  hint: 'Развёрнутый анализ с рекомендациями' },
  { value: 3, label: 'Подробно',  hint: 'Полный отчёт со всеми деталями' },
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
  methodology: 'five_why', detail_level: 2,
  incident_time: '', company: '', department: '', location_detailed: '',
  injured_count: 0, fatalities_count: 0, short_description: '',
  photo_urls: [], scene_description: '', equipment_description: '',
  full_circumstances: '', established_facts: '', victims_list: [],
  mode: 'single',
  methodologies: ['five_why'],
}

/** Заголовок блока верхнего уровня (1 / 2) */
function BlockHeader({ number, children }) {
  return (
    <div className="form-block-header">
      <span className="form-block-header__num">{number}</span>
      <span className="form-block-header__title">{children}</span>
    </div>
  )
}

/** Заголовок подраздела внутри секции */
function SubLabel({ icon, children }) {
  return (
    <div className="form-sublabel">
      {icon && <span className="form-sublabel__icon">{icon}</span>}
      <span className="form-sublabel__text">{children}</span>
    </div>
  )
}

export default function IncidentForm({ onSubmit, onSubmitMulti, loading }) {
  const [form, setForm] = useState(DEFAULTS)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadError, setUploadError] = useState(null)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [inputMode, setInputMode] = useState('manual')
  const [dragOver, setDragOver] = useState(false)
  const [expandedVictims, setExpandedVictims] = useState({})
  const fileInputRef = useRef(null)

  const busy = loading || uploading

  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }))
  }

  function isMulti() { return form.mode === 'multi' }

  function toggleMethodology(method) {
    setForm(f => {
      const list = f.methodologies.includes(method)
        ? f.methodologies.filter(m => m !== method)
        : [...f.methodologies, method]
      return { ...f, methodologies: list }
    })
  }

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
    setInputMode('docx')
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
        victims_list: fields.victims_list?.length > 0 ? fields.victims_list : prev.victims_list,
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
  function clearUpload() { setUploadedFile(null); setUploadError(null); setUploadMessage('') }

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
      onSubmitMulti({ methodologies: form.methodologies, language: 'ru', detail_level: Number(form.detail_level), incident: incidentPayload })
    } else {
      onSubmit({ methodology: form.methodology, language: 'ru', detail_level: Number(form.detail_level), incident: incidentPayload })
    }
  }

  const similarQueryText = [
    form.title, form.description, form.short_description,
    form.scene_description, form.equipment_description,
    form.full_circumstances, form.established_facts,
  ].filter(Boolean).join('\n')

  return (
    <form className="incident-form" onSubmit={handleSubmit}>
      <h2 className="form-title">Новый анализ инцидента</h2>

      {/* ══════════ БЛОК 1: Данные инцидента ══════════ */}
      <div className="form-block">
        <BlockHeader number="1">Данные инцидента</BlockHeader>

        {/* Способ заполнения */}
        <div className="input-source">
          <div className="input-source__header">
            <div className="input-source__eyebrow">Способ заполнения</div>
            <div className="input-source__title">Выберите, с чего начать ввод исходных данных</div>
          </div>
          <div className="input-source__options" role="tablist" aria-label="Способ заполнения исходных данных">
            <button type="button" className={`input-source-card ${inputMode === 'manual' ? 'input-source-card--active' : ''}`} onClick={() => setInputMode('manual')} disabled={busy} aria-pressed={inputMode === 'manual'}>
              <span className="input-source-card__icon">⌨️</span>
              <span className="input-source-card__body">
                <span className="input-source-card__title">Вручную</span>
                <span className="input-source-card__text">Сразу заполнить поля формы самостоятельно.</span>
              </span>
            </button>
            <button type="button" className={`input-source-card ${inputMode === 'docx' ? 'input-source-card--active' : ''}`} onClick={() => setInputMode('docx')} disabled={busy} aria-pressed={inputMode === 'docx'}>
              <span className="input-source-card__icon">📄</span>
              <span className="input-source-card__body">
                <span className="input-source-card__title">Из DOCX-отчёта</span>
                <span className="input-source-card__text">Подставить найденные поля из файла и дозаполнить недостающее вручную.</span>
              </span>
            </button>
          </div>
        </div>

        {inputMode === 'docx' && (
          <div className={`upload-zone ${dragOver ? 'upload-zone--dragover' : ''} ${uploading ? 'upload-zone--uploading' : ''} ${uploadedFile ? 'upload-zone--done' : ''}`}
            onDrop={handleDrop} onDragOver={handleDragOver} onDragLeave={handleDragLeave}
            onClick={() => !busy && fileInputRef.current?.click()}>
            <input ref={fileInputRef} type="file" accept=".docx" onChange={handleFileSelect} style={{ display: 'none' }} disabled={busy} />
            {uploading ? (
              <div className="upload-zone__content"><span className="upload-spinner" /><span className="upload-zone__text">{uploadMessage}</span></div>
            ) : uploadedFile ? (
              <div className="upload-zone__content">
                <span className="upload-zone__icon">✅</span>
                <span className="upload-zone__text">Данные загружены из «{uploadedFile}»</span>
                <span className="upload-zone__hint">Проверьте заполненные поля ниже. Если в файле не было части сведений, дозаполните их вручную перед запуском анализа.</span>
                <Button type="button" variant="ghost" size="sm" className="upload-zone__clear" onClick={(e) => { e.stopPropagation(); clearUpload(); }} disabled={busy}>✕ Сбросить файл</Button>
              </div>
            ) : (
              <div className="upload-zone__content">
                <span className="upload-zone__icon">📄</span>
                <span className="upload-zone__text">Загрузите отчёт DOCX</span>
                <span className="upload-zone__hint">Найденные в файле поля подставятся в форму. Если часть данных отсутствует, заполните их вручную ниже.</span>
              </div>
            )}
          </div>
        )}

        {inputMode === 'docx' && uploadError && (
          <div className="upload-error"><strong>Ошибка загрузки:</strong> {uploadError}</div>
        )}

        {/* 1.1 Описание обстоятельств */}
        <div className="form-section" id="step-data">
          <SubLabel icon="📝">Описание обстоятельств происшествия</SubLabel>
          <div className="form-row">
            <div className="form-group form-group--full">
              <Input label="Заголовок инцидента" type="text" value={form.title} onChange={e => set('title', e.target.value)} placeholder="Кратко укажите, что произошло" required minLength={5} disabled={busy} />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group form-group--full">
              <Textarea label="Описание" rows={4} value={form.description} onChange={e => set('description', e.target.value)} placeholder="Опишите обстоятельства: кто участвовал, что произошло, какие последствия и какие первичные меры были приняты" required minLength={20} disabled={busy} />
            </div>
          </div>
          {similarQueryText.length >= 20 && !busy && (
            <SimilarIncidentsHint queryText={similarQueryText} incidentTitle={form.title} incidentDescription={form.description} />
          )}
          <div className="form-row">
            <div className="form-group"><Input label="Дата инцидента" type="date" value={form.incident_date} onChange={e => set('incident_date', e.target.value)} disabled={busy} /></div>
            <div className="form-group"><Input label="Время инцидента" type="time" value={form.incident_time} onChange={e => set('incident_time', e.target.value)} disabled={busy} /></div>
            <div className="form-group"><Input label="Местоположение" type="text" value={form.location} onChange={e => set('location', e.target.value)} placeholder="Укажите площадку, участок или зону происшествия" disabled={busy} /></div>
          </div>
          <div className="form-row">
            <div className="form-group"><Input label="Предприятие" type="text" value={form.company} onChange={e => set('company', e.target.value)} placeholder="Укажите организацию или производственную площадку" disabled={busy} /></div>
            <div className="form-group"><Input label="Подразделение" type="text" value={form.department} onChange={e => set('department', e.target.value)} placeholder="Укажите подразделение, службу или подрядчика" disabled={busy} /></div>
            <div className="form-group"><Input label="Детальное место" type="text" value={form.location_detailed} onChange={e => set('location_detailed', e.target.value)} placeholder="Уточните место: помещение, отметка, оборудование или рабочая зона" disabled={busy} /></div>
          </div>
          <div className="form-row">
            <div className="form-group form-group--sm"><Input label="Пострадавшие" type="number" min={0} value={form.injured_count} onChange={e => set('injured_count', e.target.value)} disabled={busy} /></div>
            <div className="form-group form-group--sm"><Input label="Погибшие" type="number" min={0} value={form.fatalities_count} onChange={e => set('fatalities_count', e.target.value)} disabled={busy} /></div>
            <div className="form-group form-group--full"><Input label="Краткое описание" type="text" value={form.short_description} onChange={e => set('short_description', e.target.value)} placeholder="Одно-два предложения для быстрого понимания события" disabled={busy} /></div>
          </div>
        </div>

        {/* 1.2 Фото */}
        <div className="form-section">
          <SubLabel icon="📷">Фото с места происшествия</SubLabel>
          <div className="form-row">
            <div className="form-group form-group--full">
              <Textarea label="Ссылки на фото (по одной на строку)" rows={3} placeholder="https://..." value={form.photo_urls.join('\n')} onChange={e => set('photo_urls', e.target.value.split('\n').map(s => s.trim()).filter(Boolean))} disabled={busy} />
              {form.photo_urls.length > 0 && (
                <div className="photo-previews">
                  {form.photo_urls.map((url, i) => <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="photo-link">📷 Фото {i + 1}</a>)}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 1.3 Установленные факты */}
        <div className="form-section">
          <SubLabel icon="🔍">Установленные факты</SubLabel>

          <div className="victims-section">
            <div className="victims-header">
              <SubLabel>Сведения о пострадавших</SubLabel>
              <Button type="button" variant="secondary" size="sm" className="btn-add-victim" onClick={addVictim} disabled={busy}>+ Добавить пострадавшего</Button>
            </div>
            {form.victims_list.length === 0 && <div className="victims-empty">Нет добавленных пострадавших — заполните вручную или загрузите .docx</div>}
            {form.victims_list.map((v, idx) => (
              <div key={idx} className="victim-card">
                <div className="victim-card__header" onClick={() => toggleVictim(idx)} disabled={busy}>
                  <span className="victim-card__title">{v.full_name ? v.full_name : `Пострадавший ${idx + 1}`}</span>
                  <div className="victim-card__actions">
                    <span className="victim-card__toggle">{expandedVictims[idx] ? '▲' : '▼'}</span>
                    <Button type="button" variant="ghost" size="sm" className="victim-card__remove" onClick={e => { e.stopPropagation(); removeVictim(idx) }} disabled={busy}>✕</Button>
                  </div>
                </div>
                {expandedVictims[idx] && (
                  <div className="victim-card__body">
                    <div className="form-row"><div className="form-group form-group--full"><Input label="ФИО" type="text" value={v.full_name} onChange={e => setVictim(idx, 'full_name', e.target.value)} placeholder="Иванов Иван Иванович" disabled={busy} /></div></div>
                    <div className="form-row">
                      <div className="form-group"><Input label="Дата рождения" type="date" value={v.birth_date} onChange={e => setVictim(idx, 'birth_date', e.target.value)} disabled={busy} /></div>
                      <div className="form-group form-group--sm"><Input label="Возраст" type="number" min={14} max={99} value={v.age} onChange={e => setVictim(idx, 'age', e.target.value)} disabled={busy} /></div>
                      <div className="form-group"><Input label="Семейное положение" type="text" value={v.family_status} onChange={e => setVictim(idx, 'family_status', e.target.value)} placeholder="Женат / Замужем / …" disabled={busy} /></div>
                      <div className="form-group form-group--sm"><Input label="Детей до 21 г." type="number" min={0} value={v.children_under_21} onChange={e => setVictim(idx, 'children_under_21', e.target.value)} disabled={busy} /></div>
                    </div>
                    <div className="form-row">
                      <div className="form-group"><Input label="Профессия / должность" type="text" value={v.profession} onChange={e => setVictim(idx, 'profession', e.target.value)} disabled={busy} /></div>
                      <div className="form-group"><Input label="Место работы" type="text" value={v.workplace} onChange={e => setVictim(idx, 'workplace', e.target.value)} disabled={busy} /></div>
                    </div>
                    <div className="form-row">
                      <div className="form-group"><Input label="Общий стаж" type="text" value={v.total_experience} onChange={e => setVictim(idx, 'total_experience', e.target.value)} placeholder="5 лет 3 мес." disabled={busy} /></div>
                      <div className="form-group"><Input label="Стаж в организации" type="text" value={v.experience_in_organization} onChange={e => setVictim(idx, 'experience_in_organization', e.target.value)} placeholder="2 года" disabled={busy} /></div>
                      <div className="form-group"><Input label="Квалификационное удостоверение" type="text" value={v.qualification_certificate} onChange={e => setVictim(idx, 'qualification_certificate', e.target.value)} disabled={busy} /></div>
                    </div>
                    <div className="form-row">
                      <div className="form-group"><Input label="Вводный инструктаж" type="text" value={v.introductory_briefing} onChange={e => setVictim(idx, 'introductory_briefing', e.target.value)} placeholder="дд.мм.гггг / не проводился" disabled={busy} /></div>
                      <div className="form-group"><Input label="Первичный / повторный инструктаж" type="text" value={v.workplace_briefing} onChange={e => setVictim(idx, 'workplace_briefing', e.target.value)} placeholder="дд.мм.гггг / не проводился" disabled={busy} /></div>
                    </div>
                    <div className="form-row">
                      <div className="form-group"><Input label="Стажировка / допуск к работе" type="text" value={v.internship} onChange={e => setVictim(idx, 'internship', e.target.value)} placeholder="дд.мм.гггг / не проводилась" disabled={busy} /></div>
                      <div className="form-group"><Input label="Проверка знаний по ОТ" type="text" value={v.safety_knowledge_test} onChange={e => setVictim(idx, 'safety_knowledge_test', e.target.value)} placeholder="дд.мм.гггг / не проводилась" disabled={busy} /></div>
                      <div className="form-group"><Input label="Медицинский осмотр" type="text" value={v.medical_examination} onChange={e => setVictim(idx, 'medical_examination', e.target.value)} placeholder="дд.мм.гггг / не проходил" disabled={busy} /></div>
                    </div>
                    <div className="form-row"><div className="form-group form-group--full"><Input label="Диагноз / степень тяжести" type="text" value={v.diagnosis_severity} onChange={e => setVictim(idx, 'diagnosis_severity', e.target.value)} placeholder="Перелом, лёгкая степень…" disabled={busy} /></div></div>
                  </div>
                )}
              </div>
            ))}
          </div>

          <SubLabel>Описание места происшествия</SubLabel>
          <div className="form-row"><div className="form-group form-group--full"><Textarea label="Описание места происшествия" rows={3} value={form.scene_description} onChange={e => set('scene_description', e.target.value)} placeholder="Опишите состояние места, доступ, освещение, ограждения, проходы, погодные или производственные условия" disabled={busy} /></div></div>

          <SubLabel>Характеристика оборудования / объекта</SubLabel>
          <div className="form-row"><div className="form-group form-group--full"><Textarea label="Характеристика оборудования / объекта" rows={3} value={form.equipment_description} onChange={e => set('equipment_description', e.target.value)} placeholder="Укажите оборудование, инструмент, объект работ, их состояние и особенности эксплуатации" disabled={busy} /></div></div>

          <SubLabel>Полное описание обстоятельств</SubLabel>
          <div className="form-row"><div className="form-group form-group--full"><Textarea label="Полное описание обстоятельств" rows={4} value={form.full_circumstances} onChange={e => set('full_circumstances', e.target.value)} placeholder="Опишите последовательность событий до, во время и после происшествия" disabled={busy} /></div></div>

          <SubLabel>Установленные факты</SubLabel>
          <div className="form-row"><div className="form-group form-group--full"><Textarea label="Установленные факты" rows={4} value={form.established_facts} onChange={e => set('established_facts', e.target.value)} placeholder="Перечислите подтверждённые факты, выявленные нарушения, документы, показания или замеры" disabled={busy} /></div></div>
        </div>

        {/* 1.4 Классификация */}
        <div className="form-section">
          <SubLabel icon="🏷️">Классификация инцидента</SubLabel>
          <div className="form-row">
            <div className="form-group">
              <Select label="Тип инцидента" value={form.incident_type} onChange={e => set('incident_type', e.target.value)} disabled={busy}>
                {TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </Select>
            </div>
          </div>

          <SubLabel>Тяжесть инцидента</SubLabel>
          <div className="severity-selector">
            {SEVERITIES.map(s => (
              <label
                key={s.value}
                className={[
                  'severity-option',
                  `severity-option--${s.color}`,
                  form.severity === s.value ? 'severity-option--active' : '',
                  busy ? 'severity-option--disabled' : '',
                ].filter(Boolean).join(' ')}
              >
                <input
                  type="radio"
                  name="severity"
                  value={s.value}
                  checked={form.severity === s.value}
                  onChange={() => set('severity', s.value)}
                  disabled={busy}
                />
                <span className="severity-option__label">{s.label}</span>
                <span className="severity-option__hint">{s.hint}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* ══════════ БЛОК 2: Параметры анализа ══════════ */}
      <div className="form-block" id="step-method">
        <BlockHeader number="2">Параметры анализа</BlockHeader>

        <div className="form-section">
          <SubLabel icon="⚙️">Методология</SubLabel>
          <div className="mode-selector">
            <label className={`mode-option ${!isMulti() ? 'mode-option--active' : ''}`}>
              <input type="radio" name="mode" value="single" checked={!isMulti()} onChange={() => set('mode', 'single')} disabled={busy} />
              <span className="mode-option__content"><span className="mode-option__icon">🎯</span><span className="mode-option__label">Одна методика</span></span>
            </label>
            <label className={`mode-option ${isMulti() ? 'mode-option--active' : ''}`}>
              <input type="radio" name="mode" value="multi" checked={isMulti()} onChange={() => set('mode', 'multi')} disabled={busy} />
              <span className="mode-option__content"><span className="mode-option__icon">⚖️</span><span className="mode-option__label">Сравнить методики</span></span>
            </label>
          </div>

          {!isMulti() && (
            <div className="form-row">
              <div className="form-group">
                <Select label="Методология" value={form.methodology} onChange={e => set('methodology', e.target.value)} disabled={busy}>
                  {METHODOLOGIES.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.icon} {m.name}{m.short !== m.name ? ` — ${m.short}` : ''}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          )}

          {isMulti() && (
            <div className="checkbox-group">
              {METHODOLOGIES.map(m => (
                <label key={m.id} className={`checkbox-card ${form.methodologies.includes(m.id) ? 'checkbox-card--checked' : ''}`}>
                  <input type="checkbox" checked={form.methodologies.includes(m.id)} onChange={() => toggleMethodology(m.id)} className="checkbox-card__input" disabled={busy} />
                  <span className="checkbox-card__check">{form.methodologies.includes(m.id) ? '✓' : ''}</span>
                  <span className="checkbox-card__label">{m.icon} {m.name}{m.short !== m.name ? ` — ${m.short}` : ''}</span>
                </label>
              ))}
            </div>
          )}

          <div
            className="multi-hint"
            aria-live="polite"
            style={{ visibility: isMulti() && form.methodologies.length < 2 ? 'visible' : 'hidden' }}
          >
            ⚠️ Выберите минимум 2 методики для сравнения
          </div>

          <SubLabel>Уровень детализации</SubLabel>
          <div className="detail-selector">
            {DETAIL_LEVELS.map(lvl => (
              <label
                key={lvl.value}
                className={`detail-option ${Number(form.detail_level) === lvl.value ? 'detail-option--active' : ''} ${busy ? 'detail-option--disabled' : ''}`}
              >
                <input
                  type="radio"
                  name="detail_level"
                  value={lvl.value}
                  checked={Number(form.detail_level) === lvl.value}
                  onChange={() => set('detail_level', lvl.value)}
                  disabled={busy}
                />
                <span className="detail-option__label">{lvl.label}</span>
                <span className="detail-option__hint">{lvl.hint}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      <Button
        type="submit"
        variant="primary"
        size="lg"
        className={`btn-analyze ${isMulti() ? 'btn-analyze--multi' : ''}`}
        disabled={busy || (isMulti() && form.methodologies.length < 2)}
        loading={loading}
      >
        {loading ? 'Анализирую…' : isMulti() ? `⚖️ Сравнить (${form.methodologies.length} методик)` : '▶ Запустить анализ'}
      </Button>
    </form>
  )
}
