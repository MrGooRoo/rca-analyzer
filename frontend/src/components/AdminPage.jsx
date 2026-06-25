import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { api } from '../api.js'
import { Button } from './ui/Button.jsx'
import { Badge } from './ui/Card.jsx'
import { Brain, Users, FileText, Server, Package, Database } from 'lucide-react'
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

  const [docxCache, setDocxCache] = useState([])
  const [docxCacheLoading, setDocxCacheLoading] = useState(false)
  const [docxCacheError, setDocxCacheError] = useState(null)
  const [docxCacheDeleting, setDocxCacheDeleting] = useState(null)

  const [providers, setProviders] = useState([])
  const [providersLoading, setProvidersLoading] = useState(false)
  const [providersError, setProvidersError] = useState(null)
  const [providerForm, setProviderForm] = useState(null)
  const [providerSaving, setProviderSaving] = useState(false)
  const [scanningProvider, setScanningProvider] = useState(null)
  const [providerModels, setProviderModels] = useState([])
  const [showModelsFor, setShowModelsFor] = useState(null)

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

  const loadDocxCache = useCallback(async () => {
    setDocxCacheLoading(true); setDocxCacheError(null)
    try { const data = await api.admin.listDocxCache(); setDocxCache(data) } catch (e) { setDocxCacheError(e.message) } finally { setDocxCacheLoading(false) }
  }, [])

  const loadProviders = useCallback(async () => {
    setProvidersLoading(true); setProvidersError(null)
    try { const data = await api.admin.listProviders(); setProviders(data) } catch (e) { setProvidersError(e.message) } finally { setProvidersLoading(false) }
  }, [])

  async function saveProvider() {
    if (!providerForm.name.trim()) return
    setProviderSaving(true); setProvidersError(null)
    try {
      if (providerForm.id) {
        await api.admin.updateProvider(providerForm.id, { name: providerForm.name, api_key: providerForm.api_key || null, base_url: providerForm.base_url || null, is_active: providerForm.is_active })
      } else {
        await api.admin.createProvider({ name: providerForm.name, api_key: providerForm.api_key || null, base_url: providerForm.base_url || null, is_active: true })
      }
      setProviderForm(null)
      await loadProviders()
    } catch (e) { setProvidersError(e.message) } finally { setProviderSaving(false) }
  }

  async function deleteProvider(id, name) {
    if (!confirm(`Удалить провайдера «${name}»?`)) return
    setProvidersError(null)
    try { await api.admin.deleteProvider(id); await loadProviders() } catch (e) { setProvidersError(e.message) }
  }

  async function scanProvider(id, name) {
    setScanningProvider(id); setProvidersError(null); setProviderModels([])
    try {
      const models = await api.admin.scanProvider(id)
      setProviderModels(models)
      setShowModelsFor({ id, name, fresh: true })
    } catch (e) { setProvidersError(`Ошибка сканирования ${name}: ${e.message}`) } finally { setScanningProvider(null) }
  }

  async function showModels(id, name) {
    setProvidersError(null)
    try {
      const models = await api.admin.listProviderModels(id)
      setProviderModels(models)
      setShowModelsFor({ id, name, fresh: false })
    } catch (e) { setProvidersError(`Ошибка загрузки моделей ${name}: ${e.message}`) }
  }

  async function deleteDocxCacheEntry(fileHash) {
    if (!confirm(`Удалить запись кэша ${fileHash.slice(0, 16)}…? Данные инцидента не удаляются, только кэш LLM-извлечения.`)) return
    setDocxCacheDeleting(fileHash); setDocxCacheError(null)
    try { await api.admin.deleteDocxCache(fileHash); await loadDocxCache() } catch (e) { setDocxCacheError(e.message) } finally { setDocxCacheDeleting(null) }
  }

  useEffect(() => { load() }, [load])
  useEffect(() => { loadLlmSettings() }, [loadLlmSettings])
  useEffect(() => { loadModels() }, [loadModels])
  useEffect(() => { loadDocxCache() }, [loadDocxCache])
  useEffect(() => { loadProviders() }, [loadProviders])

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
            <h2 className="admin-section__title"><Brain size={18} /> LLM Conductor</h2>
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
          <h2 className="admin-section__title"><Users size={18} /> Управление пользователями</h2>
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            {loading ? '…' : '↻ Обновить'}
          </Button>
        </div>

        {error && <div className="admin-alert admin-alert--error">{error}</div>}
        {!loading && !error && users.length === 0 && (
          <div className="admin-empty">
            <div className="admin-empty__icon"><Users size={20} /></div>
            Пользователей нет
          </div>
        )}

        {users.length > 0 && (
          <div className="admin-table">
            <div className="admin-table__header">
              {['Пользователь','Email','Роль','Статус','Баланс','Действие'].map(h => (
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
                  <div className="admin-table__cell admin-table__cell--balance">
                    <span className="admin-balance">${(u.balance ?? 0).toFixed(2)}</span>
                    <button className="admin-topup-btn" title="Пополнить баланс" onClick={() => {
                      const amt = prompt('Сумма пополнения ($):', '10')
                      if (amt && !isNaN(amt) && Number(amt) > 0) {
                        const idx = users.findIndex(x => x.user_id === u.user_id)
                        const newUsers = [...users]
                        newUsers[idx] = { ...newUsers[idx], balance: (newUsers[idx].balance ?? 0) + Number(amt) }
                        setUsers(newUsers)
                        api.wallet.topUp(u.user_id, Number(amt))
                          .then(r => load())
                          .catch(e => load())
                      }
                    }}>+</button>
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

      {/* DOCX Cache */}
      <section className="admin-section">
        <div className="admin-section__header">
          <h2 className="admin-section__title"><FileText size={18} /> Кэш DOCX-извлечений</h2>
          <Button variant="secondary" size="sm" onClick={loadDocxCache} disabled={docxCacheLoading}>
            {docxCacheLoading ? '…' : '↻ Обновить'}
          </Button>
        </div>

        {docxCacheError && <div className="admin-alert admin-alert--error">{docxCacheError}</div>}
        {!docxCacheLoading && !docxCacheError && docxCache.length === 0 && (
          <div className="admin-empty">
            <div className="admin-empty__icon"><Database size={20} /></div>
            Кэш пуст — записи появятся после загрузки .docx файлов
          </div>
        )}

        {docxCache.length > 0 && (
          <div className="admin-table">
            <div className="admin-table__header">
              {['File Hash', 'Дата создания', 'Попаданий', 'Действие'].map(h => (
                <span key={h} className="admin-table__head-cell">{h}</span>
              ))}
            </div>
            {docxCache.map(c => (
              <div key={c.file_hash} className="admin-table__row">
                <div className="admin-table__cell">
                  <code title={c.incident_hash ? `incident_hash: ${c.incident_hash.slice(0, 16)}…` : 'без incident_hash'}>
                    {c.file_hash.slice(0, 16)}…
                  </code>
                </div>
                <div className="admin-table__cell admin-table__cell--date">
                  {c.created_at ? new Date(c.created_at).toLocaleString('ru-RU') : '—'}
                </div>
                <div className="admin-table__cell admin-table__cell--center">{c.hit_count}</div>
                <div className="admin-table__cell admin-table__cell--center">
                  <button
                    className="admin-role-button admin-role-button--user"
                    onClick={() => deleteDocxCacheEntry(c.file_hash)}
                    disabled={docxCacheDeleting === c.file_hash}
                  >
                    {docxCacheDeleting === c.file_hash ? '…' : 'Удалить'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* LLM Providers */}
      <section className="admin-section">
        <div className="admin-section__header">
          <h2 className="admin-section__title"><Server size={18} /> Провайдеры LLM</h2>
          <div className="admin-section__actions">
            <Button variant="secondary" size="sm" onClick={loadProviders} disabled={providersLoading}>
              {providersLoading ? '…' : '↻ Обновить'}
            </Button>
            <Button variant="primary" size="sm" onClick={() => setProviderForm({ id: null, name: '', api_key: '', base_url: '', is_active: true })}>
              + Добавить
            </Button>
          </div>
        </div>

        {providersError && <div className="admin-alert admin-alert--error">{providersError}</div>}

        {/* Модальное окно добавления/редактирования */}
        {providerForm && (
          <div className="admin-overlay" onClick={() => setProviderForm(null)}>
            <div className="admin-modal" onClick={e => e.stopPropagation()}>
              <h3 className="admin-modal__title">{providerForm.id ? 'Редактировать провайдера' : 'Добавить провайдера'}</h3>
              <div className="admin-form">
                <label className="admin-field">
                  <span className="admin-field__label">Название</span>
                  <input className="admin-input" value={providerForm.name} onChange={e => setProviderForm(f => ({ ...f, name: e.target.value }))} placeholder="OpenRouter" />
                </label>
                <label className="admin-field">
                  <span className="admin-field__label">API-ключ</span>
                  <input className="admin-input" value={providerForm.api_key || ''} onChange={e => setProviderForm(f => ({ ...f, api_key: e.target.value }))} placeholder="sk-or-…" type="password" />
                  <small className="admin-field__hint">Показывается только в маскированном виде после сохранения</small>
                </label>
                <label className="admin-field">
                  <span className="admin-field__label">Base URL (опционально)</span>
                  <input className="admin-input" value={providerForm.base_url || ''} onChange={e => setProviderForm(f => ({ ...f, base_url: e.target.value }))} placeholder="https://openrouter.ai/api/v1" />
                </label>
                <label className="admin-checkbox">
                  <input type="checkbox" checked={providerForm.is_active !== false} onChange={e => setProviderForm(f => ({ ...f, is_active: e.target.checked }))} />
                  Активен
                </label>
                <div className="admin-actions">
                  <button className="admin-save-button" onClick={saveProvider} disabled={providerSaving || !providerForm.name.trim()}>
                    {providerSaving ? 'Сохранение…' : providerForm.id ? 'Сохранить изменения' : 'Добавить'}
                  </button>
                  <button className="admin-cancel-button" onClick={() => setProviderForm(null)} disabled={providerSaving}>
                    Отмена
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {!providersLoading && !providersError && providers.length === 0 && (
          <div className="admin-empty">
            <div className="admin-empty__icon"><Package size={20} /></div>
            Провайдеров нет. Нажмите «+ Добавить», чтобы подключить LLM-провайдера.
          </div>
        )}

        {providers.length > 0 && (
          <div className="admin-table">
            <div className="admin-table__header admin-table__header--providers">
              {['Название', 'API-ключ', 'Base URL', 'Статус', 'Дата создания', 'Действие'].map(h => (
                <span key={h} className="admin-table__head-cell">{h}</span>
              ))}
            </div>
            {providers.map(p => (
              <div key={p.id} className="admin-table__row admin-table__row--providers">
                <div className="admin-table__cell admin-table__cell--name"><strong>{p.name}</strong></div>
                <div className="admin-table__cell"><code>{p.api_key_masked || '—'}</code></div>
                <div className="admin-table__cell admin-table__cell--url">{p.base_url || '—'}</div>
                <div className="admin-table__cell admin-table__cell--center">
                  <span className={`admin-status admin-status--${p.is_active ? 'active' : 'inactive'}`}>
                    {p.is_active ? 'Активен' : 'Отключён'}
                  </span>
                </div>
                <div className="admin-table__cell admin-table__cell--date">
                  {p.created_at ? new Date(p.created_at).toLocaleString('ru-RU') : '—'}
                </div>
                <div className="admin-table__cell admin-table__cell--actions">
                  <button className="admin-role-button admin-role-button--user" title="Сканировать" onClick={() => scanProvider(p.id, p.name)} disabled={scanningProvider === p.id}>
                    {scanningProvider === p.id ? '…' : '🔍 Scan'}
                  </button>
                  <button className="admin-role-button admin-role-button--user" title="Модели" onClick={() => showModels(p.id, p.name)}>
                    📋
                  </button>
                  <button className="admin-role-button admin-role-button--user" onClick={() => setProviderForm({ id: p.id, name: p.name, api_key: '', base_url: p.base_url || '', is_active: p.is_active })} disabled={providerSaving}>
                    ✎
                  </button>
                  <button className="admin-role-button admin-role-button--user" onClick={() => deleteProvider(p.id, p.name)} disabled={providerSaving}>
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Модальное окно моделей провайдера */}
        {showModelsFor && (
          <div className="admin-overlay" onClick={() => setShowModelsFor(null)}>
            <div className="admin-modal admin-modal--wide" onClick={e => e.stopPropagation()}>
              <h3 className="admin-modal__title">
                Модели {showModelsFor.name}
                <span className="admin-modal__count">{providerModels.length}</span>
              </h3>
              {showModelsFor.fresh && (
                <div className="admin-alert admin-alert--success">Каталог отсканирован. Загружено {providerModels.length} моделей.</div>
              )}
              {providerModels.length === 0 ? (
                <div className="admin-empty">Моделей не найдено</div>
              ) : (
                <div className="admin-table" style={{ maxHeight: '50vh', overflowY: 'auto' }}>
                  <div className="admin-table__header admin-table__header--models">
                    {['ID модели', 'Название', 'Контекст', 'Бесплатно', 'Цена prompt/1M', 'Цена completion/1M'].map(h => (
                      <span key={h} className="admin-table__head-cell">{h}</span>
                    ))}
                  </div>
                  {providerModels.map(m => (
                    <div key={m.id} className="admin-table__row admin-table__row--models">
                      <div className="admin-table__cell"><code>{m.model_id}</code></div>
                      <div className="admin-table__cell admin-table__cell--name">{m.name}</div>
                      <div className="admin-table__cell admin-table__cell--center">{m.context_length > 0 ? `${(m.context_length / 1000).toFixed(0)}K` : '—'}</div>
                      <div className="admin-table__cell admin-table__cell--center">
                        <span className={`admin-status admin-status--${m.is_free ? 'active' : 'inactive'}`}>
                          {m.is_free ? 'Да' : 'Нет'}
                        </span>
                      </div>
                      <div className="admin-table__cell admin-table__cell--right">{m.pricing_prompt != null ? `$${m.pricing_prompt}` : '—'}</div>
                      <div className="admin-table__cell admin-table__cell--right">{m.pricing_completion != null ? `$${m.pricing_completion}` : '—'}</div>
                    </div>
                  ))}
                </div>
              )}
              <div className="admin-actions">
                <button className="admin-cancel-button" onClick={() => setShowModelsFor(null)}>Закрыть</button>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
