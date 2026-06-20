import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { api } from '../api.js'
import { Button } from './ui/Button.jsx'
import { Badge } from './ui/Card.jsx'

const ROLE_LABELS = {
  admin: { label: 'Admin', color: 'text-amber-400', bg: 'bg-amber-500/10' },
  user:  { label: 'User',  color: 'text-indigo-400', bg: 'bg-indigo-500/10' },
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

  const inputBase = 'w-full rounded-xl bg-slate-950/60 ring-1 ring-slate-700 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-400/60 disabled:opacity-50'

  return (
    <div className="space-y-6">
      {/* LLM Conductor */}
      <section className="rounded-2xl p-5 ring-1 ring-indigo-500/30 bg-gradient-to-r from-indigo-500/10 via-slate-900/60 to-slate-900/60 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">🧠 LLM Conductor</h2>
            <p className="text-sm text-slate-400 mt-1 leading-relaxed">Черновую работу делает draft-модель, verifier подключается по выбранной схеме.</p>
          </div>
          <Button variant="secondary" size="sm" onClick={loadLlmSettings} disabled={llmLoading || llmSaving}>
            {llmLoading ? '…' : '↻ Обновить'}
          </Button>
        </div>

        {llmError && <div className="rounded-lg p-3 text-sm text-rose-300 bg-rose-500/10 ring-1 ring-rose-500/30">{llmError}</div>}
        {llmMessage && <div className="rounded-lg p-3 text-sm text-emerald-300 bg-emerald-500/10 ring-1 ring-emerald-500/30">{llmMessage}</div>}

        <form className="space-y-4" onSubmit={saveLlmSettings}>
          <div className="grid grid-cols-1 sm:grid-cols-[minmax(220px,1fr)_auto_auto] items-end gap-3">
            <label className="flex flex-col gap-2 min-w-0">
              <span className="text-sm text-white font-semibold">Поиск моделей OpenRouter</span>
              <input className={inputBase} value={modelSearch} onChange={e => setModelSearch(e.target.value)} placeholder="gpt-oss, nemotron, llama…" />
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-slate-400 pb-2">
              <input type="checkbox" checked={freeOnly} onChange={e => setFreeOnly(e.target.checked)} />
              Только бесплатные
            </label>
            <Button variant="secondary" size="sm" onClick={() => loadModels({ force_refresh: true })} disabled={modelsLoading}>
              {modelsLoading ? '…' : '↻ Каталог'}
            </Button>
          </div>

          {modelsError && <div className="rounded-lg p-3 text-sm text-amber-300 bg-amber-500/10 ring-1 ring-amber-500/30">Каталог OpenRouter недоступен: {modelsError}. Можно ввести model id вручную.</div>}

          <datalist id="openrouter-models">{models.map(m => <option key={m.id} value={m.id} label={modelLabel(m)} />)}</datalist>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="flex flex-col gap-2 min-w-0">
              <span className="text-sm text-white font-semibold">Черновая модель</span>
              <input className={inputBase} list="openrouter-models" value={llmForm.draft_model} onChange={e => updateLlmField('draft_model', e.target.value)} placeholder="nvidia/nemotron-3-super-120b-a12b:free" disabled={llmLoading || llmSaving} />
              <small className="text-xs text-slate-500">{formatPrice(selectedDraftModel)}</small>
            </label>
            <label className="flex flex-col gap-2 min-w-0">
              <span className="text-sm text-white font-semibold">Verifier-модель</span>
              <input className={inputBase} list="openrouter-models" value={llmForm.verifier_model} onChange={e => updateLlmField('verifier_model', e.target.value)} placeholder="openai/gpt-oss-20b" disabled={llmLoading || llmSaving || llmForm.verification_scheme === 'disabled'} />
              <small className="text-xs text-slate-500">{llmForm.verification_scheme === 'disabled' ? 'Не используется в схеме «Только черновик»' : formatPrice(selectedVerifierModel)}</small>
            </label>
            <label className="flex flex-col gap-2 min-w-0">
              <span className="text-sm text-white font-semibold">Схема верификации</span>
              <select className={inputBase} value={llmForm.verification_scheme} onChange={e => updateLlmField('verification_scheme', e.target.value)} disabled={llmLoading || llmSaving}>
                <option value="disabled">{SCHEME_LABELS.disabled}</option>
                <option value="threshold">{SCHEME_LABELS.threshold}</option>
                <option value="always">{SCHEME_LABELS.always}</option>
              </select>
              <small className="text-xs text-slate-500">{llmForm.verification_scheme === 'threshold' ? 'Verifier включается только ниже порога confidence_avg.' : SCHEME_LABELS[llmForm.verification_scheme]}</small>
            </label>
            <label className="flex flex-col gap-2 min-w-0">
              <span className="text-sm text-white font-semibold">Порог качества: {Math.round(Number(llmForm.quality_threshold) * 100)}%</span>
              <input type="range" min="0" max="1" step="0.01" value={llmForm.quality_threshold} onChange={e => updateLlmField('quality_threshold', e.target.value)} disabled={llmLoading || llmSaving || llmForm.verification_scheme !== 'threshold'} className="accent-indigo-500" />
              <input className={`${inputBase} max-w-[110px]`} type="number" min="0" max="1" step="0.01" value={llmForm.quality_threshold} onChange={e => updateLlmField('quality_threshold', e.target.value)} disabled={llmLoading || llmSaving || llmForm.verification_scheme !== 'threshold'} />
            </label>
          </div>

          {formInvalid && <div className="rounded-lg p-3 text-sm text-amber-300 bg-amber-500/10 ring-1 ring-amber-500/30">Укажите черновую модель{verifierRequired ? ' и verifier-модель' : ''}.</div>}

          <div className="space-y-1 rounded-xl bg-slate-950/40 ring-1 ring-white/5 p-4 text-sm text-slate-400 leading-relaxed">
            <div><strong className="text-white">Сценарий:</strong> {SCHEME_LABELS[llmForm.verification_scheme]}.</div>
            <div><strong className="text-white">Экономика:</strong> максимум токенов уходит в draft-модель; verifier получает только черновик и слабые места.</div>
          </div>

          <div className="flex justify-end">
            <button type="submit" className="rounded-xl bg-indigo-500/20 ring-1 ring-indigo-400/40 text-indigo-400 px-4 py-2.5 text-sm font-semibold hover:bg-indigo-500/30 hover:ring-indigo-400 transition disabled:opacity-50 cursor-pointer" disabled={llmSaving || llmLoading || formInvalid}>
              {llmSaving ? 'Сохранение…' : 'Сохранить LLM-настройки'}
            </button>
          </div>
        </form>
      </section>

      {/* Users */}
      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-white">👥 Управление пользователями</h2>
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            {loading ? '…' : '↻ Обновить'}
          </Button>
        </div>

        {error && <div className="rounded-lg p-3 text-sm text-rose-300 bg-rose-500/10 ring-1 ring-rose-500/30">{error}</div>}
        {!loading && !error && users.length === 0 && <div className="text-center py-16 text-slate-400 text-sm">Пользователей нет</div>}

        {users.length > 0 && (
          <div className="overflow-hidden rounded-xl ring-1 ring-slate-800">
            <div className="grid grid-cols-[1fr_1fr_90px_90px_150px] items-center bg-slate-900/60 border-b border-slate-800">
              {['Пользователь','Email','Роль','Статус','Действие'].map(h => (
                <span key={h} className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 text-center first:text-left">{h}</span>
              ))}
            </div>
            {users.map(u => {
              const r = ROLE_LABELS[u.role] || ROLE_LABELS.user
              const isSelf = u.user_id === currentUser.user_id
              return (
                <div key={u.user_id} className={`grid grid-cols-[1fr_1fr_90px_90px_150px] items-center border-b border-slate-800 last:border-0 hover:bg-slate-900/40 transition ${isSelf ? 'bg-indigo-500/5' : ''}`}>
                  <div className="px-4 py-3 text-sm text-white font-medium flex items-center gap-2 min-w-0">
                    <span className="truncate">{u.display_name}</span>
                    {isSelf && <span className="text-xs text-slate-500 shrink-0">(вы)</span>}
                  </div>
                  <div className="px-4 py-3 text-xs text-slate-500 truncate min-w-0">{u.email}</div>
                  <div className="px-4 py-3 text-center">
                    <span className={`text-xs font-semibold rounded px-2.5 py-0.5 uppercase tracking-wide ${r.bg} ${r.color}`}>{r.label}</span>
                  </div>
                  <div className="px-4 py-3 text-center">
                    <span className={`text-xs font-medium ${u.is_active ? 'text-emerald-400' : 'text-rose-400'}`}>{u.is_active ? 'Активен' : 'Отключён'}</span>
                  </div>
                  <div className="px-4 py-3 text-center">
                    {isSelf ? (
                      <span className="text-xs text-slate-500">—</span>
                    ) : (
                      <button className={`text-xs font-medium rounded-md px-3 py-1 border transition cursor-pointer ${
                        u.role === 'admin'
                          ? 'text-amber-400 border-amber-400/30 bg-amber-500/10 hover:bg-amber-500/15 hover:border-amber-400'
                          : 'text-emerald-400 border-emerald-400/30 bg-emerald-500/10 hover:bg-emerald-500/15 hover:border-emerald-400'
                      }`} onClick={() => toggleRole(u)} disabled={busy === u.user_id}>
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
