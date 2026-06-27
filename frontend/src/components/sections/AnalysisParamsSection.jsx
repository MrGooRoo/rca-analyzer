import React from 'react'
import { Select } from '../ui/Field.jsx'
import { Button } from '../ui/Button.jsx'
import { Card, CardHeader, CardBody } from '../ui/Card.jsx'
import { METHODOLOGIES } from '../../lib/methodologies.js'
import { DETAIL_LEVELS, METHODOLOGY_OPTIONS } from './formConstants.js'

function CardToggle(active, disabled) {
  return `incident-choice ${
    active ? 'incident-choice--active' : 'incident-choice--hoverable'
  } ${disabled ? 'is-disabled' : ''}`
}

function SubLabel({ icon, children }) {
  return (
    <div className="incident-sublabel">
      {icon && <span className="incident-sublabel__icon">{icon}</span>}
      <span>{children}</span>
    </div>
  )
}

function BlockHeader({ number, children }) {
  return (
    <div className="incident-block-header">
      <span className="incident-block-number">{number}</span>
      <span className="incident-block-title">{children}</span>
    </div>
  )
}

export default function AnalysisParamsSection({ form, set, toggleMethodology, isMulti, busy, loading, onSubmit }) {
  return (
    <>
      <Card>
        <CardHeader><BlockHeader number="2">Параметры анализа</BlockHeader></CardHeader>
        <CardBody className="incident-card-body--stack">
          <div className="incident-section" id="step-method">
            <SubLabel icon="⚙️">Методология</SubLabel>

            <div className="incident-method-grid">
              {METHODOLOGY_OPTIONS.map(m => (
                <label key={m.id} className={CardToggle(form.mode === m.id, busy)}>
                  <input type="radio" name="mode" value={m.id}
                    checked={form.mode === m.id}
                    onChange={() => set('mode', m.id)}
                    disabled={busy} className="incident-sr-only" />
                  <div className="incident-choice__content">
                    <span className="incident-choice__icon">{m.icon}</span>
                    <span className="incident-choice__title">{m.label}</span>
                  </div>
                </label>
              ))}
            </div>

            {!isMulti && (
              <Select label="Методология" value={form.methodology}
                onChange={e => set('methodology', e.target.value)} disabled={busy}>
                {METHODOLOGIES.map(m =>
                  <option key={m.id} value={m.id}>
                    {m.icon} {m.name}{m.short !== m.name ? ` — ${m.short}` : ''}
                  </option>
                )}
              </Select>
            )}

            {isMulti && (
              <div className="incident-method-grid">
                {METHODOLOGIES.map(m => (
                  <label key={m.id} className={CardToggle(form.methodologies?.includes(m.id), busy)}>
                    <input type="checkbox" checked={form.methodologies?.includes(m.id)}
                      onChange={() => toggleMethodology(m.id)}
                      className="incident-sr-only" disabled={busy} />
                    <div className="incident-choice__content">
                      <div className={`incident-method-check ${form.methodologies?.includes(m.id) ? 'incident-method-check--active' : ''}`}>
                        {form.methodologies?.includes(m.id) ? '✓' : ''}
                      </div>
                      <span className="incident-choice__title">{m.icon} {m.name}</span>
                    </div>
                  </label>
                ))}
              </div>
            )}

            <div className="incident-warning" style={{
              visibility: isMulti && (form.methodologies?.length || 0) < 2 ? 'visible' : 'hidden'
            }}>
              ⚠️ Выберите минимум 2 методики для сравнения
            </div>

            <SubLabel>Уровень детализации</SubLabel>
            <div className="incident-method-grid incident-method-grid--three">
              {DETAIL_LEVELS.map(lvl => (
                <label key={lvl.value} className={CardToggle(Number(form.detail_level) === lvl.value, busy)}>
                  <input type="radio" name="detail_level" value={lvl.value}
                    checked={Number(form.detail_level) === lvl.value}
                    onChange={() => set('detail_level', lvl.value)}
                    disabled={busy} className="incident-sr-only" />
                  <div className="incident-choice__title">{lvl.label}</div>
                  <div className="incident-choice__text">{lvl.hint}</div>
                </label>
              ))}
            </div>
          </div>
        </CardBody>
      </Card>

      <Button type="submit" variant="primary" size="lg" className="incident-submit"
        disabled={busy || (isMulti && (form.methodologies?.length || 0) < 2)} loading={loading}>
        {loading
          ? 'Анализирую…'
          : isMulti
            ? `⚖️ Сравнить (${form.methodologies?.length || 0} методик)`
            : '▶ Запустить анализ'}
      </Button>
    </>
  )
}
