import React, { useState, useRef, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import { Button } from './ui/Button.jsx'
import { Card, CardHeader, CardBody } from './ui/Card.jsx'
import { DEFAULTS, EMPTY_VICTIM } from './sections/formConstants.js'
import StepIndicator from './sections/StepIndicator.jsx'
import InputModeSelector from './sections/InputModeSelector.jsx'
import BasicInfoSection from './sections/BasicInfoSection.jsx'
import VictimSection from './sections/VictimSection.jsx'
import AdvancedFieldsSection from './sections/AdvancedFieldsSection.jsx'
import ClassificationSection from './sections/ClassificationSection.jsx'
import AnalysisParamsSection from './sections/AnalysisParamsSection.jsx'
import ModelSelector from './ModelSelector.jsx'
import FormSkeleton from './sections/FormSkeleton.jsx'
import './IncidentForm.css'

export default function IncidentForm({ onSubmit, onSubmitMulti, loading, initialValues, onDraftChange, onOpenResult }) {
  const [form, setForm] = useState(() => initialValues ? { ...DEFAULTS, ...initialValues } : DEFAULTS)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadError, setUploadError] = useState(null)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [inputMode, setInputMode] = useState('manual')
  const [dragOver, setDragOver] = useState(false)
  const [expandedVictims, setExpandedVictims] = useState({})
  const [step, setStep] = useState(1)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)
  const [modelPrefs, setModelPrefs] = useState({})
  const fileInputRef = useRef(null)

  // Draft change callback
  const onDraftChangeRef = useRef(onDraftChange)
  useEffect(() => { onDraftChangeRef.current = onDraftChange }, [onDraftChange])
  useEffect(() => { onDraftChangeRef.current?.(form) }, [form])

  // Simulate initialization for skeleton
  useEffect(() => {
    const timer = setTimeout(() => setIsInitializing(false), 300)
    return () => clearTimeout(timer)
  }, [])

  const busy = loading || uploading
  const isMulti = form.mode === 'multi'

  // --- Field helpers ---
  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }))
  }

  function toggleMethodology(method) {
    setForm(f => {
      const list = f.methodologies?.includes(method)
        ? f.methodologies.filter(m => m !== method)
        : [...(f.methodologies || []), method]
      return { ...f, methodologies: list }
    })
  }

  // --- Step validation ---
  function canProceed() {
    if (step === 1) return form.title.trim().length >= 5 && form.description.trim().length >= 20
    if (step === 2) return true
    if (step === 3) return isMulti ? (form.methodologies?.length || 0) >= 2 : true
    return false
  }

  function nextStep() { if (canProceed()) setStep(s => Math.min(s + 1, 3)) }
  function prevStep() { setStep(s => Math.max(s - 1, 1)) }

  // --- Keyboard shortcuts ---
  function handleFormKeyDown(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      if (step < 3 && canProceed()) { nextStep(); return }
      if (step === 3) document.querySelector('.incident-submit')?.click()
    }
  }

  // --- File upload ---
  async function processFile(file) {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.docx')) { setUploadError('Допустимы только файлы формата .docx'); return }
    if (file.size > 10 * 1024 * 1024) { setUploadError('Файл слишком большой (макс. 10 МБ)'); return }
    setUploading(true)
    setUploadMessage('Начинаем загрузку...')
    setUploadError(null)
    setUploadedFile(file.name)
    setInputMode('docx')
    try {
      const fields = await api.uploadReportStream(file, (evt) => {
        if (evt.status === 'reading') setUploadMessage('Извлечение текста из DOCX...')
        else if (evt.status === 'analyzing') setUploadMessage('Анализ текста в LLM...')
      })
      setForm(prev => ({ ...prev, ...fields }))
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

  function clearUpload() {
    setUploadedFile(null); setUploadError(null); setUploadMessage('')
    setForm({ ...DEFAULTS })
    setInputMode('manual')
  }

  // --- Submit ---
  function buildIncidentPayload() {
    return {
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
      equipment_description: form.equipment_description || undefined,
      full_circumstances: form.full_circumstances || undefined,
      established_facts: form.established_facts || undefined,
      victims_list: (form.victims_list || []).map(v => ({
        ...v, birth_date: v.birth_date || undefined,
        age: v.age !== '' ? Number(v.age) : undefined,
        children_under_21: v.children_under_21 !== '' ? Number(v.children_under_21) : undefined,
      })),
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    const incidentPayload = buildIncidentPayload()
    const base = {
      model_prefs: modelPrefs,
      detail_level: Number(form.detail_level),
      incident: incidentPayload,
    }
    if (isMulti) {
      onSubmitMulti({ methodologies: form.methodologies, ...base })
    } else {
      onSubmit({ methodology: form.methodology, ...base })
    }
  }

  // --- Victims helpers ---
  function addVictim() {
    const newList = [...(form.victims_list || []), { ...EMPTY_VICTIM }]
    setForm(f => ({ ...f, victims_list: newList }))
    setExpandedVictims(e => ({ ...e, [newList.length - 1]: true }))
  }

  function removeVictim(idx) {
    setForm(f => ({ ...f, victims_list: f.victims_list?.filter((_, i) => i !== idx) }))
    setExpandedVictims(e => {
      const next = {}
      Object.keys(e).forEach(k => {
        if (Number(k) !== idx) next[Number(k) > idx ? Number(k) - 1 : Number(k)] = e[k]
      })
      return next
    })
  }

  function setVictim(idx, field, value) {
    setForm(f => {
      const list = [...(f.victims_list || [])]
      list[idx] = { ...list[idx], [field]: value }
      return { ...f, victims_list: list }
    })
  }

  function toggleVictim(idx) {
    setExpandedVictims(e => ({ ...e, [idx]: !e[idx] }))
  }

  // --- Render ---
  if (isInitializing) return <FormSkeleton />

  return (
    <form className="incident-form" onSubmit={handleSubmit} onKeyDown={handleFormKeyDown}>
      <StepIndicator step={step} busy={busy} onGoTo={setStep} />

      <h2 className="incident-form__title">Новый анализ инцидента</h2>

      {/* Step 1-2: Data entry */}
      {(step === 1 || step === 2) && (
        <Card>
          <CardHeader>
            <div className="incident-block-header">
              <span className="incident-block-number">1</span>
              <span className="incident-block-title">Данные инцидента</span>
            </div>
          </CardHeader>
          <CardBody className="incident-card-body--stack">
            <InputModeSelector
              inputMode={inputMode} uploadedFile={uploadedFile}
              uploading={uploading} uploadMessage={uploadMessage}
              uploadError={uploadError} busy={busy} dragOver={dragOver}
              onModeChange={setInputMode} onFileSelect={handleFileSelect}
              onDrop={handleDrop} onDragOver={handleDragOver}
              onDragLeave={handleDragLeave} onClear={clearUpload}
              fileInputRef={fileInputRef}
            />

            {inputMode === 'docx' && uploadError && (
              <div className="incident-error">
                <strong>Ошибка загрузки:</strong> {uploadError}
              </div>
            )}

            <BasicInfoSection form={form} set={set} busy={busy} showAdvanced={showAdvanced} onOpenResult={onOpenResult} />

            <div className="incident-advanced-toggle">
              <label className="incident-toggle">
                <input type="checkbox" checked={showAdvanced || step === 2}
                  onChange={e => setShowAdvanced(e.target.checked)}
                  disabled={busy || step === 2} />
                <span className="incident-toggle__slider" />
                <span className="incident-toggle__label">Показать расширенные поля</span>
              </label>
            </div>

            {(step === 2 || showAdvanced) && (
              <>
                <AdvancedFieldsSection form={form} set={set} busy={busy} />
                <VictimSection
                  victimsList={form.victims_list}
                  expandedVictims={expandedVictims}
                  busy={busy}
                  onAdd={addVictim}
                  onRemove={removeVictim}
                  onToggle={toggleVictim}
                  onSetVictim={setVictim}
                />
                <ClassificationSection form={form} set={set} busy={busy} />
              </>
            )}
          </CardBody>
        </Card>
      )}

      {/* Step 3: Analysis params */}
      {step === 3 && (
        <>
          <AnalysisParamsSection
            form={form} set={set}
            toggleMethodology={toggleMethodology}
            isMulti={isMulti} busy={busy} loading={loading}
          />
          <ModelSelector disabled={busy} onPrefsChange={setModelPrefs} />
          {step === 3 && <span className="incident-submit-hint"><code>⌘⏎</code></span>}
        </>
      )}

      {/* Step navigation */}
      {!loading && (
        <div className="incident-nav">
          {step > 1 && (
            <Button type="button" variant="secondary" onClick={prevStep} disabled={busy}>
              ← Назад
            </Button>
          )}
          {step < 3 && (
            <Button type="button" variant="primary" onClick={nextStep}
              disabled={busy || !canProceed()}>
              {step === 1 ? 'Детали →' : 'Параметры анализа →'}
            </Button>
          )}
        </div>
      )}
    </form>
  )
}
