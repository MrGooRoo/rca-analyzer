import React, { useState, useRef, useEffect } from 'react'
import { api } from '../api.js'
import SimilarIncidentsHint from './SimilarIncidentsHint.jsx'
import { Button } from './ui/Button.jsx'
import { Input, Textarea, Select } from './ui/Field.jsx'
import { Card, CardHeader, CardBody } from './ui/Card.jsx'
import { METHODOLOGIES } from '../lib/methodologies.js'

const SEVERITIES = [
  { value: 'critical',  label: 'Критический', hint: 'Смерть / тяжёлый вред',       color: 'rose' },
  { value: 'major',     label: 'Тяжёлый',     hint: 'Госпитализация / крупный ущерб', color: 'amber' },
  { value: 'moderate',  label: 'Средний',      hint: 'Временная нетрудоспособность',  color: 'sky' },
  { value: 'minor',     label: 'Лёгкий',       hint: 'Первая помощь / малый ущерб',   color: 'emerald' },
  { value: 'near_miss', label: 'Предпосылка',  hint: 'Без пострадавших',              color: 'slate' },
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
  full_name: '', birth_date: '', age: '', family_status: '', children_under_21: '',
  profession: '', workplace: '', total_experience: '', experience_in_organization: '',
  qualification_certificate: '', introductory_briefing: '', workplace_briefing: '',
  internship: '', safety_knowledge_test: '', medical_examination: '', diagnosis_severity: '',
}

const DEFAULTS = {
  title: '', description: '', incident_date: '', location: '',
  incident_type: 'injury', severity: 'moderate', victims: 0,
  methodology: 'five_why', detail_level: 2,
  incident_time: '', company: '', department: '', location_detailed: '',
  injured_count: 0, fatalities_count: 0, short_description: '',
  photo_urls: [], scene_description: '', equipment_description: '',
  full_circumstances: '', established_facts: '', victims_list: [],
  mode: 'single', methodologies: ['five_why'],
}

/** Заголовок блока верхнего уровня */
function BlockHeader({ number, children }) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500 text-white text-sm font-bold shrink-0">
        {number}
      </span>
      <span className="text-lg font-semibold text-white">{children}</span>
    </div>
  )
}

/** Заголовок подраздела внутри секции */
function SubLabel({ icon, children }) {
  return (
    <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-slate-400 font-semibold mt-4 mb-2">
      {icon && <span className="text-sm">{icon}</span>}
      <span>{children}</span>
    </div>
  )
}

function CardToggle(active, disabled) {
  return `relative rounded-xl p-4 ring-1 transition-all text-left cursor-pointer ${
    active
      ? 'ring-indigo-400 bg-indigo-500/10'
      : 'ring-slate-800 bg-slate-950/40 hover:ring-slate-600 hover:bg-slate-900/60'
  } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`
}

function SeverityCard(s, active, disabled) {
  return `relative rounded-xl p-3 ring-1 transition cursor-pointer ${
    active
      ? 'ring-indigo-400 bg-indigo-500/10'
      : 'ring-slate-800 bg-slate-950/40 hover:ring-slate-600'
  } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`
}

export default function IncidentForm({ onSubmit, onSubmitMulti, loading, initialValues, onDraftChange }) {
  const [form, setForm] = useState(() => initialValues ? { ...DEFAULTS, ...initialValues } : DEFAULTS)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadError, setUploadError] = useState(null)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [inputMode, setInputMode] = useState('manual')
  const [dragOver, setDragOver] = useState(false)
  const [expandedVictims, setExpandedVictims] = useState({})
  const fileInputRef = useRef(null)

  const onDraftChangeRef = useRef(onDraftChange)
  useEffect(() => { onDraftChangeRef.current = onDraftChange }, [onDraftChange])
  useEffect(() => { onDraftChangeRef.current?.(form) }, [form])

  const busy = loading || uploading

  function set(field, value) { setForm(f => ({ ...f, [field]: value })) }
  function isMulti() { return form.mode === 'multi' }

  function toggleMethodology(method) {
    setForm(f => {
      const list = f.methodologies.includes(method) ? f.methodologies.filter(m => m !== method) : [...f.methodologies, method]
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
      Object.keys(e).forEach(k => { if (Number(k) !== idx) next[Number(k) > idx ? Number(k) - 1 : Number(k)] = e[k] })
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

  function toggleVictim(idx) { setExpandedVictims(e => ({ ...e, [idx]: !e[idx] })) }

  async function processFile(file) {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.docx')) { setUploadError('Допустимы только файлы формата .docx'); return }
    if (file.size > 10 * 1024 * 1024) { setUploadError('Файл слишком большой (макс. 10 МБ)'); return }
    setUploading(true); setUploadMessage('Начинаем загрузку...'); setUploadError(null); setUploadedFile(file.name); setInputMode('docx')
    try {
      const fields = await api.uploadReportStream(file, (evt) => {
        if (evt.status === 'reading') setUploadMessage('Извлечение текста из DOCX...')
        else if (evt.status === 'analyzing') setUploadMessage('Анализ текста в LLM...')
      })
      setForm(prev => ({ ...prev, ...fields }))
    } catch (e) { setUploadError(e.message); setUploadedFile(null) }
    finally { setUploading(false) }
  }

  function handleFileSelect(e) { const file = e.target.files?.[0]; if (file) processFile(file); if (fileInputRef.current) fileInputRef.current.value = '' }
  function handleDrop(e) { e.preventDefault(); setDragOver(false); const file = e.dataTransfer.files?.[0]; if (file) processFile(file) }
  function handleDragOver(e) { e.preventDefault(); setDragOver(true) }
  function handleDragLeave(e) { e.preventDefault(); setDragOver(false) }
  function clearUpload() { setUploadedFile(null); setUploadError(null); setUploadMessage('') }

  function handleSubmit(e) {
    e.preventDefault()
    const incidentPayload = {
      title: form.title, description: form.description,
      incident_date: form.incident_date ? form.incident_date + 'T00:00:00' : null,
      location: form.location, incident_type: form.incident_type, severity: form.severity,
      victims: form.victims ? Number(form.victims) : undefined,
      equipment: form.equipment || undefined, conditions: form.conditions || undefined,
      actions_taken: form.actions_taken || undefined, incident_time: form.incident_time || undefined,
      company: form.company || undefined, department: form.department || undefined,
      location_detailed: form.location_detailed || undefined, injured_count: form.injured_count || undefined,
      fatalities_count: form.fatalities_count || undefined, short_description: form.short_description || undefined,
      photo_urls: form.photo_urls || [], scene_description: form.scene_description || undefined,
      equipment_description: form.equipment_description || undefined, full_circumstances: form.full_circumstances || undefined,
      established_facts: form.established_facts || undefined,
      victims_list: form.victims_list.map(v => ({
        ...v, birth_date: v.birth_date || undefined, age: v.age !== '' ? Number(v.age) : undefined,
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
    <form className="space-y-6 animate-fadeIn" onSubmit={handleSubmit}>
      <h2 className="text-2xl font-bold text-white tracking-tight">Новый анализ инцидента</h2>

      {/* ══════════ БЛОК 1: Данные инцидента ══════════ */}
      <Card>
        <CardHeader><BlockHeader number="1">Данные инцидента</BlockHeader></CardHeader>
        <CardBody className="space-y-4">

          {/* Способ заполнения */}
          <div className="space-y-3">
            <div className="space-y-1">
              <div className="text-xs uppercase tracking-wider text-indigo-400 font-bold">Способ заполнения</div>
              <div className="text-sm text-slate-300">Выберите, с чего начать ввод исходных данных</div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2" role="tablist" aria-label="Способ заполнения исходных данных">
              {[
                { id: 'manual', icon: '⌨️', title: 'Вручную', text: 'Сразу заполнить поля формы самостоятельно.' },
                { id: 'docx', icon: '📄', title: 'Из DOCX-отчёта', text: 'Подставить найденные поля из файла и дозаполнить недостающее вручную.' },
              ].map(opt => (
                <button key={opt.id} type="button" disabled={busy}
                  className={CardToggle(inputMode === opt.id, busy)}
                  onClick={() => setInputMode(opt.id)} aria-pressed={inputMode === opt.id}>
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{opt.icon}</span>
                    <div className="min-w-0">
                      <div className="font-semibold text-white">{opt.title}</div>
                      <div className="text-xs text-slate-400 mt-0.5">{opt.text}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Upload zone */}
          {inputMode === 'docx' && (
            <div className={`rounded-xl p-4 cursor-pointer transition-all ${
              dragOver ? 'ring-1 ring-indigo-400 bg-indigo-500/10' : uploadedFile ? 'ring-1 ring-emerald-500/30 bg-emerald-500/10' : 'ring-1 ring-slate-800 bg-slate-950/60 hover:ring-indigo-500/30'
            } ${uploading ? 'opacity-75 cursor-wait' : ''}`}
              onDrop={handleDrop} onDragOver={handleDragOver} onDragLeave={handleDragLeave}
              onClick={() => !busy && fileInputRef.current?.click()}>
              <input ref={fileInputRef} type="file" accept=".docx" onChange={handleFileSelect} className="hidden" disabled={busy} />
              <div className="flex flex-col items-center gap-2 text-center">
                {uploading ? (
                  <>
                    <svg className="h-5 w-5 animate-spin text-indigo-400" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25"/><path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg>
                    <span className="text-sm text-slate-300">{uploadMessage}</span>
                  </>
                ) : uploadedFile ? (
                  <>
                    <span className="text-2xl">✅</span>
                    <span className="text-sm text-slate-300">Данные загружены из «{uploadedFile}»</span>
                    <span className="text-xs text-slate-500">Проверьте заполненные поля ниже. Если в файле не было части сведений, дозаполните их вручную перед запуском анализа.</span>
                    <Button type="button" variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); clearUpload() }} disabled={busy}>✕ Сбросить файл</Button>
                  </>
                ) : (
                  <>
                    <span className="text-2xl">📄</span>
                    <span className="text-sm text-slate-300">Загрузите отчёт DOCX</span>
                    <span className="text-xs text-slate-500">Найденные в файле поля подставятся в форму. Если часть данных отсутствует, заполните их вручную ниже.</span>
                  </>
                )}
              </div>
            </div>
          )}

          {inputMode === 'docx' && uploadError && (
            <div className="rounded-lg bg-rose-500/10 ring-1 ring-rose-500/30 text-rose-300 text-sm px-3 py-2.5">
              <strong>Ошибка загрузки:</strong> {uploadError}
            </div>
          )}

          {/* 1.1 Описание обстоятельств */}
          <div className="space-y-4" id="step-data">
            <SubLabel icon="📝">Описание обстоятельств происшествия</SubLabel>
            <div className="grid gap-4">
              <Input label="Заголовок инцидента" type="text" value={form.title} onChange={e => set('title', e.target.value)} placeholder="Кратко укажите, что произошло" required minLength={5} disabled={busy} />
            </div>
            <div className="grid gap-4">
              <Textarea label="Описание" rows={4} value={form.description} onChange={e => set('description', e.target.value)} placeholder="Опишите обстоятельства: кто участвовал, что произошло, какие последствия и какие первичные меры были приняты" required minLength={20} disabled={busy} />
            </div>
            {similarQueryText.length >= 20 && !busy && (
              <SimilarIncidentsHint queryText={similarQueryText} incidentTitle={form.title} incidentDescription={form.description} />
            )}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <Input label="Дата инцидента" type="date" value={form.incident_date} onChange={e => set('incident_date', e.target.value)} disabled={busy} />
              <Input label="Время инцидента" type="time" value={form.incident_time} onChange={e => set('incident_time', e.target.value)} disabled={busy} />
              <div className="lg:col-span-2"><Input label="Местоположение" type="text" value={form.location} onChange={e => set('location', e.target.value)} placeholder="Укажите площадку, участок или зону происшествия" disabled={busy} /></div>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <Input label="Предприятие" type="text" value={form.company} onChange={e => set('company', e.target.value)} placeholder="Укажите организацию или производственную площадку" disabled={busy} />
              <Input label="Подразделение" type="text" value={form.department} onChange={e => set('department', e.target.value)} placeholder="Укажите подразделение, службу или подрядчика" disabled={busy} />
              <Input label="Детальное место" type="text" value={form.location_detailed} onChange={e => set('location_detailed', e.target.value)} placeholder="Уточните место: помещение, отметка, оборудование или рабочая зона" disabled={busy} />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Input label="Пострадавшие" type="number" min={0} value={form.injured_count} onChange={e => set('injured_count', e.target.value)} disabled={busy} />
              <Input label="Погибшие" type="number" min={0} value={form.fatalities_count} onChange={e => set('fatalities_count', e.target.value)} disabled={busy} />
              <div className="md:col-span-2"><Input label="Краткое описание" type="text" value={form.short_description} onChange={e => set('short_description', e.target.value)} placeholder="Одно-два предложения для быстрого понимания события" disabled={busy} /></div>
            </div>
          </div>

          {/* 1.2 Фото */}
          <div className="space-y-4">
            <SubLabel icon="📷">Фото с места происшествия</SubLabel>
            <Textarea label="Ссылки на фото (по одной на строку)" rows={3} placeholder="https://..." value={form.photo_urls.join('\n')} onChange={e => set('photo_urls', e.target.value.split('\n').map(s => s.trim()).filter(Boolean))} disabled={busy} />
            {form.photo_urls.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {form.photo_urls.map((url, i) => (
                  <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="text-sm text-indigo-400 hover:text-indigo-300 transition">📷 Фото {i + 1}</a>
                ))}
              </div>
            )}
          </div>

          {/* 1.3 Установленные факты */}
          <div className="space-y-4">
            <SubLabel icon="🔍">Установленные факты</SubLabel>

            <div className="space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <SubLabel>Сведения о пострадавших</SubLabel>
                <Button type="button" variant="secondary" size="sm" onClick={addVictim} disabled={busy}>+ Добавить пострадавшего</Button>
              </div>
              {form.victims_list.length === 0 && <div className="text-sm text-slate-500 text-center py-4">Нет добавленных пострадавших — заполните вручную или загрузите .docx</div>}
              {form.victims_list.map((v, idx) => (
                <div key={idx} className="rounded-xl bg-slate-950/60 ring-1 ring-slate-800 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-800/40 transition" onClick={() => toggleVictim(idx)}>
                    <span className="text-sm font-medium text-white">{v.full_name ? v.full_name : `Пострадавший ${idx + 1}`}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-400">{expandedVictims[idx] ? '▲' : '▼'}</span>
                      <Button type="button" variant="ghost" size="sm" onClick={e => { e.stopPropagation(); removeVictim(idx) }} disabled={busy}>✕</Button>
                    </div>
                  </div>
                  {expandedVictims[idx] && (
                    <div className="px-4 pb-4 space-y-4">
                      <div className="grid gap-4"><Input label="ФИО" type="text" value={v.full_name} onChange={e => setVictim(idx, 'full_name', e.target.value)} placeholder="Иванов Иван Иванович" disabled={busy} /></div>
                      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                        <Input label="Дата рождения" type="date" value={v.birth_date} onChange={e => setVictim(idx, 'birth_date', e.target.value)} disabled={busy} />
                        <Input label="Возраст" type="number" min={14} max={99} value={v.age} onChange={e => setVictim(idx, 'age', e.target.value)} disabled={busy} />
                        <Input label="Семейное положение" type="text" value={v.family_status} onChange={e => setVictim(idx, 'family_status', e.target.value)} placeholder="Женат / Замужем / …" disabled={busy} />
                        <Input label="Детей до 21 г." type="number" min={0} value={v.children_under_21} onChange={e => setVictim(idx, 'children_under_21', e.target.value)} disabled={busy} />
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        <Input label="Профессия / должность" type="text" value={v.profession} onChange={e => setVictim(idx, 'profession', e.target.value)} disabled={busy} />
                        <Input label="Место работы" type="text" value={v.workplace} onChange={e => setVictim(idx, 'workplace', e.target.value)} disabled={busy} />
                      </div>
                      <div className="grid gap-4 md:grid-cols-3">
                        <Input label="Общий стаж" type="text" value={v.total_experience} onChange={e => setVictim(idx, 'total_experience', e.target.value)} placeholder="5 лет 3 мес." disabled={busy} />
                        <Input label="Стаж в организации" type="text" value={v.experience_in_organization} onChange={e => setVictim(idx, 'experience_in_organization', e.target.value)} placeholder="2 года" disabled={busy} />
                        <Input label="Квалификационное удостоверение" type="text" value={v.qualification_certificate} onChange={e => setVictim(idx, 'qualification_certificate', e.target.value)} disabled={busy} />
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        <Input label="Вводный инструктаж" type="text" value={v.introductory_briefing} onChange={e => setVictim(idx, 'introductory_briefing', e.target.value)} placeholder="дд.мм.гггг / не проводился" disabled={busy} />
                        <Input label="Первичный / повторный инструктаж" type="text" value={v.workplace_briefing} onChange={e => setVictim(idx, 'workplace_briefing', e.target.value)} placeholder="дд.мм.гггг / не проводился" disabled={busy} />
                      </div>
                      <div className="grid gap-4 md:grid-cols-3">
                        <Input label="Стажировка / допуск к работе" type="text" value={v.internship} onChange={e => setVictim(idx, 'internship', e.target.value)} placeholder="дд.мм.гггг / не проводилась" disabled={busy} />
                        <Input label="Проверка знаний по ОТ" type="text" value={v.safety_knowledge_test} onChange={e => setVictim(idx, 'safety_knowledge_test', e.target.value)} placeholder="дд.мм.гггг / не проводилась" disabled={busy} />
                        <Input label="Медицинский осмотр" type="text" value={v.medical_examination} onChange={e => setVictim(idx, 'medical_examination', e.target.value)} placeholder="дд.мм.гггг / не проходил" disabled={busy} />
                      </div>
                      <div className="grid gap-4"><Input label="Диагноз / степень тяжести" type="text" value={v.diagnosis_severity} onChange={e => setVictim(idx, 'diagnosis_severity', e.target.value)} placeholder="Перелом, лёгкая степень…" disabled={busy} /></div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <SubLabel>Описание места происшествия</SubLabel>
            <Textarea label="Описание места происшествия" rows={3} value={form.scene_description} onChange={e => set('scene_description', e.target.value)} placeholder="Опишите состояние места, доступ, освещение, ограждения, проходы, погодные или производственные условия" disabled={busy} />

            <SubLabel>Характеристика оборудования / объекта</SubLabel>
            <Textarea label="Характеристика оборудования / объекта" rows={3} value={form.equipment_description} onChange={e => set('equipment_description', e.target.value)} placeholder="Укажите оборудование, инструмент, объект работ, их состояние и особенности эксплуатации" disabled={busy} />

            <SubLabel>Полное описание обстоятельств</SubLabel>
            <Textarea label="Полное описание обстоятельств" rows={4} value={form.full_circumstances} onChange={e => set('full_circumstances', e.target.value)} placeholder="Опишите последовательность событий до, во время и после происшествия" disabled={busy} />

            <SubLabel>Установленные факты</SubLabel>
            <Textarea label="Установленные факты" rows={4} value={form.established_facts} onChange={e => set('established_facts', e.target.value)} placeholder="Перечислите подтверждённые факты, выявленные нарушения, документы, показания или замеры" disabled={busy} />
          </div>

          {/* 1.4 Классификация */}
          <div className="space-y-4">
            <SubLabel icon="🏷️">Классификация инцидента</SubLabel>
            <Select label="Тип инцидента" value={form.incident_type} onChange={e => set('incident_type', e.target.value)} disabled={busy}>
              {TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </Select>

            <SubLabel>Тяжесть инцидента</SubLabel>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {SEVERITIES.map(s => (
                <label key={s.value} className={SeverityCard(s, form.severity === s.value, busy)}>
                  <input type="radio" name="severity" value={s.value} checked={form.severity === s.value} onChange={() => set('severity', s.value)} disabled={busy} className="sr-only" />
                  <div className="font-semibold text-white">{s.label}</div>
                  <div className="text-xs text-slate-400">{s.hint}</div>
                </label>
              ))}
            </div>
          </div>
        </CardBody>
      </Card>

      {/* ══════════ БЛОК 2: Параметры анализа ══════════ */}
      <Card>
        <CardHeader><BlockHeader number="2">Параметры анализа</BlockHeader></CardHeader>
        <CardBody className="space-y-4">
          <div className="space-y-4" id="step-method">
            <SubLabel icon="⚙️">Методология</SubLabel>

            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { id: 'single', icon: '🎯', label: 'Одна методика' },
                { id: 'multi', icon: '⚖️', label: 'Сравнить методики' },
              ].map(m => (
                <label key={m.id} className={CardToggle(form.mode === m.id, busy)}>
                  <input type="radio" name="mode" value={m.id} checked={form.mode === m.id} onChange={() => set('mode', m.id)} disabled={busy} className="sr-only" />
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{m.icon}</span>
                    <span className="font-semibold text-white">{m.label}</span>
                  </div>
                </label>
              ))}
            </div>

            {!isMulti() && (
              <Select label="Методология" value={form.methodology} onChange={e => set('methodology', e.target.value)} disabled={busy}>
                {METHODOLOGIES.map(m => <option key={m.id} value={m.id}>{m.icon} {m.name}{m.short !== m.name ? ` — ${m.short}` : ''}</option>)}
              </Select>
            )}

            {isMulti() && (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {METHODOLOGIES.map(m => (
                  <label key={m.id} className={CardToggle(form.methodologies.includes(m.id), busy)}>
                    <input type="checkbox" checked={form.methodologies.includes(m.id)} onChange={() => toggleMethodology(m.id)} className="sr-only" disabled={busy} />
                    <div className="flex items-center gap-3">
                      <div className={`h-5 w-5 flex items-center justify-center rounded-md text-xs ${form.methodologies.includes(m.id) ? 'bg-indigo-500/20 text-indigo-300 ring-1 ring-indigo-500/30' : 'ring-1 ring-slate-600 text-slate-500'}`}>
                        {form.methodologies.includes(m.id) ? '✓' : ''}
                      </div>
                      <span className="font-semibold text-white">{m.icon} {m.name}</span>
                    </div>
                  </label>
                ))}
              </div>
            )}

            <div className="text-sm text-amber-300" style={{ visibility: isMulti() && form.methodologies.length < 2 ? 'visible' : 'hidden' }}>
              ⚠️ Выберите минимум 2 методики для сравнения
            </div>

            <SubLabel>Уровень детализации</SubLabel>
            <div className="grid gap-3 sm:grid-cols-3">
              {DETAIL_LEVELS.map(lvl => (
                <label key={lvl.value} className={CardToggle(Number(form.detail_level) === lvl.value, busy)}>
                  <input type="radio" name="detail_level" value={lvl.value} checked={Number(form.detail_level) === lvl.value} onChange={() => set('detail_level', lvl.value)} disabled={busy} className="sr-only" />
                  <div className="font-semibold text-white">{lvl.label}</div>
                  <div className="text-xs text-slate-400">{lvl.hint}</div>
                </label>
              ))}
            </div>
          </div>
        </CardBody>
      </Card>

      <Button type="submit" variant="primary" size="lg" className="w-full" disabled={busy || (isMulti() && form.methodologies.length < 2)} loading={loading}>
        {loading ? 'Анализирую…' : isMulti() ? `⚖️ Сравнить (${form.methodologies.length} методик)` : '▶ Запустить анализ'}
      </Button>
    </form>
  )
}
