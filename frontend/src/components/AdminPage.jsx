import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { api } from '../api.js'
import './AdminPage.css'

const ROLE_LABELS = {
  admin: { label: 'Admin', color: '#f7b955', bg: 'rgba(247,185,85,0.12)' },
  user:  { label: 'User',  color: '#4f8ef7', bg: 'rgba(79,142,247,0.12)' },
}

const DEFAULT_LLM_FORM = {
  draft_model: '',
  verifier_model: '',
  quality_threshold: 0.7,
  verification_scheme: 'threshold',
}

const SCHEME_LABELS = {
  disabled: 'Только черновик',
  threshold: 'По порогу качества',
  always: 'Всегда верифицировать',
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
  const [users, setUsers]       = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [busy, setBusy]         = useState(null)

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
    setLoading(true)
    setError(null)
    try {
      const data = await api.admin.listUsers()
      setUsers(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadLlmSettings = useCallback(async () => {
    setLlmLoading(true)
    setLlmError(null)
    try {
      const data = await api.admin.getLlmSettings()
      setLlmForm({
        draft_model: data.draft_model || '',
        verifier_model: data.verifier_model || '',
        quality_threshold: data.quality_threshold ?? 0.7,
        verification_scheme: data.verification_scheme || 'threshold',
      })
    } catch (e) {
      setLlmError(e.message)
    } finally {
      setLlmLoading(false)
    }
  }, [])

  const loadModels = useCallback(async (options = {}) => {
    setModelsLoading(true)
    setModelsError(null)
    try {
      const data = await api.admin.openRouterModels({
        search: modelSearch,
        free_only: freeOnly,
        limit: 120,
        ...options,
      })
      setModels(data)
    } catch (e) {
      setModelsError(e.message)
    } finally {
      setModelsLoading(false)
    }
  }, [modelSearch, freeOnly])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadLlmSettings() }, [loadLlmSettings])
  useEffect(() => { loadModels() }, [loadModels])

  const modelById = useMemo(() => {
    const map = new Map()
    models.forEach(model => map.set(model.id, model))
    return map
  }, [models])

  const selectedDraftModel = modelById.get(llmForm.draft_model)
  const selectedVerifierModel = modelById.get(llmForm.verifier_model)
  const verifierRequired = llmForm.verification_scheme !== 'disabled'
  const formInvalid = !llmForm.draft_model.trim() || (verifierRequired && !llmForm.verifier_model.trim())

  async function toggleRole(user) {
    const newRole = user.role === 'admin' ? 'user' : 'admin'
    const action = newRole === 'admin' ? 'назначить администратором' : 'снять права администратора'
    if (!confirm(`${action} для ${user.email}?`)) return

    setBusy(user.user_id)
    setError(null)
    try {
      await api.admin.setRole(user.user_id, newRole)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  function updateLlmField(field, value) {
    setLlmMessage(null)
    setLlmError(null)
    setLlmForm(prev => ({ ...prev, [field]: value }))
  }

  async function saveLlmSettings(e) {
    e.preventDefault()
    setLlmSaving(true)
    setLlmError(null)
    setLlmMessage(null)
    try {
      const payload = {
        draft_model: llmForm.draft_model.trim(),
        verifier_model: llmForm.verifier_model.trim() || null,
        quality_threshold: Number(llmForm.quality_threshold),
        verification_scheme: llmForm.verification_scheme,
      }
      const saved = await api.admin.updateLlmSettings(payload)
      setLlmForm({
        draft_model: saved.draft_model || '',
        verifier_model: saved.verifier_model || '',
        quality_threshold: saved.quality_threshold ?? 0.7,
        verification_scheme: saved.verification_scheme || 'threshold',
      })
      setLlmMessage('Настройки LLM Conductor сохранены.')
    } catch (err) {
      setLlmError(err.message)
    } finally {
      setLlmSaving(false)
    }
  }

  return (
    <div className="admin">
      <section className="admin-section admin-section--llm">
        <div className="admin-toolbar">
          <div>
            <h2 className="admin-title">🧠 LLM Conductor</h2>
            <p className="admin-subtitle">
              Черновую работу делает draft-модель, verifier подключается по выбранной схеме.
            </p>
          </div>
          <button className="btn-refresh" onClick={loadLlmSettings} disabled={llmLoading || llmSaving}>
            {llmLoading ? '…' : '↻ Обновить'}
          </button>
        </div>

        {llmError && <div className="admin-error">{llmError}</div>}
        {llmMessage && <div className="admin-success">{llmMessage}</div>}

        <form className="llm-form" onSubmit={saveLlmSettings}>
          <div className="llm-model-tools">
            <label className="admin-field admin-field--search">
              <span>Поиск моделей OpenRouter</span>
              <input
                value={modelSearch}
                onChange={e => setModelSearch(e.target.value)}
                placeholder="gpt-oss, nemotron, llama…"
              />
            </label>
            <label className="llm-checkbox">
              <input
                type="checkbox"
                checked={freeOnly}
                onChange={e => setFreeOnly(e.target.checked)}
              />
              Только бесплатные
            </label>
            <button
              type="button"
              className="btn-refresh"
              onClick={() => loadModels({ force_refresh: true })}
              disabled={modelsLoading}
            >
              {modelsLoading ? '…' : '↻ Каталог'}
            </button>
          </div>

          {modelsError && (
            <div className="admin-warning">
              Каталог OpenRouter недоступен: {modelsError}. Можно ввести model id вручную.
            </div>
          )}

          <datalist id="openrouter-models">
            {models.map(model => (
              <option key={model.id} value={model.id} label={modelLabel(model)} />
            ))}
          </datalist>

          <div className="llm-form-grid">
            <label className="admin-field">
              <span>Черновая модель</span>
              <input
                list="openrouter-models"
                value={llmForm.draft_model}
                onChange={e => updateLlmField('draft_model', e.target.value)}
                placeholder="nvidia/nemotron-3-super-120b-a12b:free"
                disabled={llmLoading || llmSaving}
              />
              <small>{formatPrice(selectedDraftModel)}</small>
            </label>

            <label className="admin-field">
              <span>Verifier-модель</span>
              <input
                list="openrouter-models"
                value={llmForm.verifier_model}
                onChange={e => updateLlmField('verifier_model', e.target.value)}
                placeholder="openai/gpt-oss-20b"
                disabled={llmLoading || llmSaving || llmForm.verification_scheme === 'disabled'}
              />
              <small>
                {llmForm.verification_scheme === 'disabled'
                  ? 'Не используется в схеме «Только черновик»'
                  : formatPrice(selectedVerifierModel)}
              </small>
            </label>

            <label className="admin-field">
              <span>Схема верификации</span>
              <select
                value={llmForm.verification_scheme}
                onChange={e => updateLlmField('verification_scheme', e.target.value)}
                disabled={llmLoading || llmSaving}
              >
                <option value="disabled">{SCHEME_LABELS.disabled}</option>
                <option value="threshold">{SCHEME_LABELS.threshold}</option>
                <option value="always">{SCHEME_LABELS.always}</option>
              </select>
              <small>
                {llmForm.verification_scheme === 'threshold'
                  ? 'Verifier включается только ниже порога confidence_avg.'
                  : SCHEME_LABELS[llmForm.verification_scheme]}
              </small>
            </label>

            <label className="admin-field">
              <span>Порог качества: {Math.round(Number(llmForm.quality_threshold) * 100)}%</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={llmForm.quality_threshold}
                onChange={e => updateLlmField('quality_threshold', e.target.value)}
                disabled={llmLoading || llmSaving || llmForm.verification_scheme !== 'threshold'}
              />
              <input
                className="llm-threshold-number"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={llmForm.quality_threshold}
                onChange={e => updateLlmField('quality_threshold', e.target.value)}
                disabled={llmLoading || llmSaving || llmForm.verification_scheme !== 'threshold'}
              />
            </label>
          </div>

          {formInvalid && (
            <div className="admin-warning">
              Укажите черновую модель{verifierRequired ? ' и verifier-модель' : ''}.
            </div>
          )}

          <div className="llm-summary">
            <div>
              <strong>Сценарий:</strong> {SCHEME_LABELS[llmForm.verification_scheme]}.
            </div>
            <div>
              <strong>Экономика:</strong> максимум токенов уходит в draft-модель;
              verifier получает только черновик и слабые места.
            </div>
          </div>

          <div className="llm-actions">
            <button
              type="submit"
              className="admin-btn-primary"
              disabled={llmSaving || llmLoading || formInvalid}
            >
              {llmSaving ? 'Сохранение…' : 'Сохранить LLM-настройки'}
            </button>
          </div>
        </form>
      </section>

      <section className="admin-section">
        <div className="admin-toolbar">
          <h2 className="admin-title">👥 Управление пользователями</h2>
          <button className="btn-refresh" onClick={load} disabled={loading}>
            {loading ? '…' : '↻ Обновить'}
          </button>
        </div>

        {error && (
          <div className="admin-error">{error}</div>
        )}

        {!loading && !error && users.length === 0 && (
          <div className="admin-empty">Пользователей нет</div>
        )}

        {users.length > 0 && (
          <div className="admin-grid">
            <div className="admin-grid-header">
              <span>Пользователь</span>
              <span>Email</span>
              <span>Роль</span>
              <span>Статус</span>
              <span>Действие</span>
            </div>
            {users.map(u => {
              const r = ROLE_LABELS[u.role] || ROLE_LABELS.user
              const isSelf = u.user_id === currentUser.user_id
              return (
                <div key={u.user_id} className={`admin-grid-row ${isSelf ? 'admin-row--self' : ''}`}>
                  <div className="admin-cell-name">
                    <span className="admin-cell-name-text">{u.display_name}</span>
                    {isSelf && <span className="admin-you">(вы)</span>}
                  </div>
                  <div className="admin-cell-email">{u.email}</div>
                  <div>
                    <span
                      className="admin-badge"
                      style={{ background: r.bg, color: r.color }}
                    >
                      {r.label}
                    </span>
                  </div>
                  <div>
                    <span className={`admin-status ${u.is_active ? 'admin-status--active' : 'admin-status--disabled'}`}>
                      {u.is_active ? 'Активен' : 'Отключён'}
                    </span>
                  </div>
                  <div>
                    {isSelf ? (
                      <span className="admin-no-action">—</span>
                    ) : (
                      <button
                        className={`admin-btn-role ${u.role === 'admin' ? 'admin-btn-role--demote' : 'admin-btn-role--promote'}`}
                        onClick={() => toggleRole(u)}
                        disabled={busy === u.user_id}
                      >
                        {busy === u.user_id
                          ? '…'
                          : u.role === 'admin'
                            ? '↓ Снять admin'
                            : '↑ Сделать admin'
                        }
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
