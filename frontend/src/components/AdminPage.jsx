import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { api } from '../api.js'
import { Button } from './ui/Button.jsx'
import { Badge } from './ui/Card.jsx'
import './AdminPage.css'

const ROLE_LABELS = {
  admin: { label: 'Admin', tone: 'amber' },
  user:  { label: 'User',  tone: 'indigo' },
}

const DEFAULT_LLM_FORM = {
  draft_model: '', verifier_model: '', quality_threshold: 0.7, verification_scheme: 'threshold',
}

const SCHEME_LABELS = {
  disabled: 'Только черновик', threshold: 'По порогу качества', always: 'Всегда верифицировать',
}

function formatPrice(model) {
  if (!model) return '—'
  if (model.is_free) return 'бесплатно'
  const input = model.prompt_price_per_1m ?? null
  const output = model.completion_price_per_1m ?? null
  if (input === null && output === null) return 'цена не указана'
  return `$${input ?? '?'} / $${output ?? '?'} за 1M токенов`
}

function modelLabel(model) {
  if (!model) return ''
  const price = formatPrice(model)
  const context = model.context_length ? ` · ${model.context_length.toLocaleString('ru-RU')} ctx` : ''
  return `${model.id} — ${model.name || 'OpenRouter model'} · ${price}${context}`
}

export default function AdminPage({ currentUser }) {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)

  const [llmForm, setLlmForm] = useState(DEFAULT_LLM_FORM)
  const [llmLoading, setLlmLoading] = useState(false)
  const [llmSaving, setLlmSaving] = useState(false)
  const [llmError, setLlmError] = useState(null)
  const [llmMessage, setLlmMessage] = useState(null)

  const [models, setModels] = useState([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [modelsError, setModelsError] = useState(null)
  const [modelSearch, setModelSearch] = useState('')
  const [freeOnly, setFreeOnly] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try { const data = await api.admin.listUsers(); setUsers(data) } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [])

  const loadLlmSettings = useCallback(async () => {
    setLlmLoading(true); setLlmError(null)
    try {
      const data = await api.admin.getLlmSettings()
      setLlmForm({ draft_model: data.draft_model || '', verifier_model: data.verifier_model || '', quality_threshold: data.quality_threshold ?? 0.7, verification_scheme: data.verification_scheme || 'threshold' })
    } catch (e) { setLlmError(e.message) } finally { setLlmLoading(false) }
  }, [])

  const loadModels = useCallback(async (options = {}) => {
    setModelsLoading(true); setModelsError(null)
    try {
      const data = await api.admin.openRouterModels({ search: modelSearch, free_only: freeOnly, limit: 120, ...options })
      setModels(data)
    } catch (e) { setModelsError(e.message) } finally { setModelsLoading(false) }
  }, [modelSearch, freeOnly])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadLlmSettings() }, [loadLlmSettings])
  useEffect(() => { loadModels() }, [loadModels])

  const modelById = useMemo(() => { const m = new Map(); models.forEach(x => m.set(x.id, x)); return m }, [models])
  const selectedDraftModel = modelById.get(llmForm.draft_model)
  const selectedVerifierModel = modelById.get(llmForm.verifier_model)
  const verifierRequired = llmForm.verification_scheme !== 'disabled'
  const formInvalid = !llmForm.draft_model.trim() || (verifierRequired && !llmForm.verifier_model.trim())

  async function toggleRole(user) {
    const newRole = user.role === 'admin' ? 'user' : 'admin'
    const action = newRole === 'admin' ? 'назначить администратором' : 'снять права администратора'
    if (!confirm(`${action} для ${user.email}?`)) return
    setBusy(user.user_id); setError(null)
    try { await api.admin.setRole(user.user_id, newRole); await load() } catch (e) { setError(e.message) } finally { setBusy(null) }
  }

  function updateLlmField(field, value) { setLlmMessage(null); setLlmError(null); setLlmForm(prev => ({ ...prev, [field]: value })) }

  async function saveLlmSettings(e) {
    e.preventDefault()
    setLlmSaving(true); setLlmError(null); setLlmMessage(null)
    try {
      const saved = await api.admin.updateLlmSettings({
        draft_model: llmForm.draft_model.trim(), verifier_model: llmForm.verifier_model.trim() || null,
        quality_threshold: Number(llmForm.quality_threshold), verification_scheme: llmForm.verification_scheme,
      })
      setLlmForm({ draft_model: saved.draft_model || '', verifier_model: saved.verifier_model || '', quality_threshold: saved.quality_threshold ?? 0.7, verification_scheme: saved.verification_scheme || 'threshold' })
      setLlmMessage('Настройки LLM Conductor сохранены.')
    } catch (err) { setLlmError(err.message) } finally { setLlmSaving(false) }
  }

  const inputBase = 'admin-input'

  return (
    <div className="admin-page">
      {/* LLM Conductor */}
      <section className="admin-section admin-section--llm">
        <div className="admin-section__header">
          <div>
            <h2 className="admin-section__title">🧠 LLM Conductor</h2>
            <p className="admin-section__description">Черновую работу делает draft-модель, verifier подключается по выбранной схеме.</p>
          </div>
          <Button variant="secondary" size="sm" onClick={loadLlmSettings} disabled={llmLoading || llmSaving}>
            {llmLoading ? '…' : '↻ Обновить'}
          </Button>
        </div>

        {llmError && <div className="admin-alert admin-alert--error">{llmError}</div>}
        {llmMessage && <div className="admin-alert admin-alert--success">{llmMessage}</div>}

        <form className="admin-form" onSubmit={saveLlmSettings}>
          <div className="admin-grid admin-grid--model-search">
            <label className="admin-field">
              <span className="admin-field__label">Поиск моделей OpenRouter</span>
              <input className={inputBase} value={modelSearch} onChange={e => setModelSearch(e.target.value)} placeholder="gpt-oss, nemotron, llama…" />
            </label>
            <label className="admin-checkbox">
              <input type="checkbox" checked={freeOnly} onChange={e => setFreeOnly(e.target.checked)} />
              Только бесплатные
            </label>
            <Button variant="secondary" size="sm" onClick={() => loadModels({ force_refresh: true })} disabled={modelsLoading}>
              {modelsLoading ? '…' : '↻ Каталог'}
            </Button>
          </div>

          {modelsError && <div className="admin-alert admin-alert--warning">Каталог OpenRouter недоступен: {modelsError}. Можно ввести model id вручную.</div>}

          <datalist id="openrouter-models">{models.map(m => <option key={m.id} value={m.id} label={modelLabel(m)} />)}</datalist>

          <div className="admin-grid admin-grid--two">
            <label className="admin-field">
              <span className="admin-field__label">Черновая модель</span>
              <input className={inputBase} list="openrouter-models" value={llmForm.draft_model} onChange={e => updateLlmField('draft_model', e.target.value)} placeholder="nvidia/nemotron-3-super-120b-a12b:free" disabled={llmLoading || llmSaving} />
              <small className="admin-field__hint">{formatPrice(selectedDraftModel)}</small>
            </label>
            <label className="admin-field">
              <span className="admin-field__label">Verifier-модель</span>
              <input className={inputBase} list="openrouter-models" value={llmForm.verifier_model} onChange={e => updateLlmField('verifier_model', e.target.value)} placeholder="openai/gpt-oss-20b" disabled={llmLoading || llmSaving || llmForm.verification_scheme === 'disabled'} />
              <small className="admin-field__hint">{llmForm.verification_scheme === 'disabled' ? 'Не используется в схеме «Только черновик»' : formatPrice(selectedVerifierModel)}</small>
            </label>
            <label className="admin-field">
              <span className="admin-field__label">Схема верификации</span>
              <select className={inputBase} value={llmForm.verification_scheme} onChange={e => updateLlmField('verification_scheme', e.target.value)} disabled={llmLoading || llmSaving}>
                <option value="disabled">{SCHEME_LABELS.disabled}</option>
                <option value="threshold">{SCHEME_LABELS.threshold}</option>
                <option value="always">{SCHEME_LABELS.always}</option>
              </select>
              <small className="admin-field__hint">{llmForm.verification_scheme === 'threshold' ? 'Verifier включается только ниже порога confidence_avg.' : SCHEME_LABELS[llmForm.verification_scheme]}</small>
            </label>
            <label className="admin-field">
              <span className="admin-field__label">Порог качества: {Math.round(Number(llmForm.quality_threshold) * 100)}%</span>
              <input type="range" min="0" max="1" step="0.01" value={llmForm.quality_threshold} onChange={e => updateLlmField('quality_threshold', e.target.value)} disabled={llmLoading || llmSaving || llmForm.verification_scheme !== 'threshold'} className="admin-range" />
              <input className="admin-input admin-input--narrow" type="number" min="0" max="1" step="0.01" value={llmForm.quality_threshold} onChange={e => updateLlmField('quality_threshold', e.target.value)} disabled={llmLoading || llmSaving || llmForm.verification_scheme !== 'threshold'} />
            </label>
          </div>

          {formInvalid && <div className="admin-alert admin-alert--warning">Укажите черновую модель{verifierRequired ? ' и verifier-модель' : ''}.</div>}

          <div className="admin-summary">
            <div><strong>Сценарий:</strong> {SCHEME_LABELS[llmForm.verification_scheme]}.</div>
            <div><strong>Экономика:</strong> максимум токенов уходит в draft-модель; verifier получает только черновик и слабые места.</div>
          </div>

          <div className="admin-actions">
            <button type="submit" className="admin-save-button" disabled={llmSaving || llmLoading || formInvalid}>
              {llmSaving ? 'Сохранение…' : 'Сохранить LLM-настройки'}
            </button>
          </div>
        </form>
      </section>

      {/* Users */}
      <section className="admin-section">
        <div className="admin-section__header">
          <h2 className="admin-section__title">👥 Управление пользователями</h2>
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            {loading ? '…' : '↻ Обновить'}
          </Button>
        </div>

        {error && <div className="admin-alert admin-alert--error">{error}</div>}
        {!loading && !error && users.length === 0 && <div className="admin-empty">Пользователей нет</div>}

        {users.length > 0 && (
          <div className="admin-table">
            <div className="admin-table__header">
              {['Пользователь','Email','Роль','Статус','Действие'].map(h => (
                <span key={h} className="admin-table__head-cell">{h}</span>
              ))}
            </div>
            {users.map(u => {
              const r = ROLE_LABELS[u.role] || ROLE_LABELS.user
              const isSelf = u.user_id === currentUser.user_id
              return (
                <div key={u.user_id} className={`admin-table__row ${isSelf ? 'admin-table__row--self' : ''}`}>
                  <div className="admin-table__cell admin-table__cell--user">
                    <span className="admin-table__truncate">{u.display_name}</span>
                    {isSelf && <span className="admin-table__self">(вы)</span>}
                  </div>
                  <div className="admin-table__cell admin-table__cell--email">{u.email}</div>
                  <div className="admin-table__cell admin-table__cell--center">
                    <Badge tone={r.tone}>{r.label}</Badge>
                  </div>
                  <div className="admin-table__cell admin-table__cell--center">
                    <span className={`admin-status admin-status--${u.is_active ? 'active' : 'inactive'}`}>{u.is_active ? 'Активен' : 'Отключён'}</span>
                  </div>
                  <div className="admin-table__cell admin-table__cell--center">
                    {isSelf ? (
                      <span className="admin-table__dash">—</span>
                    ) : (
                      <button className={`admin-role-button admin-role-button--${u.role === 'admin' ? 'admin' : 'user'}`} onClick={() => toggleRole(u)} disabled={busy === u.user_id}>
                        {busy === u.user_id ? '…' : u.role === 'admin' ? '↓ Снять admin' : '↑ Сделать admin'}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
