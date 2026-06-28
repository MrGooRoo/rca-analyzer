import React from 'react'
import { Select } from '../ui/Field.jsx'
import { SEVERITIES, TYPES } from './formConstants.js'

function SubLabel({ icon, children }) {
  return (
    <div className="incident-sublabel">
      {icon && <span className="incident-sublabel__icon">{icon}</span>}
      <span>{children}</span>
    </div>
  )
}

/** Префикс CSS-класса для цвета тяжести */
const SEVERITY_CLASS = {
  rose:    'is-rose',
  amber:   'is-amber',
  sky:     'is-sky',
  emerald: 'is-emerald',
  slate:   'is-slate',
}

export default function ClassificationSection({ form, set, busy }) {
  return (
    <div className="incident-section">
      <SubLabel icon="🏷️">Классификация инцидента</SubLabel>

      <div className="incident-classification-row">
        {/* Левая колонка — тип инцидента */}
        <div className="incident-classification-type">
          <Select label="Тип инцидента" value={form.incident_type}
            onChange={e => set('incident_type', e.target.value)} disabled={busy}>
            {TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </Select>
        </div>

        {/* Правая колонка — тяжесть (цветные чипсы) */}
        <div className="incident-classification-severity">
          <div className="incident-sublabel">Тяжесть</div>
          <div className="incident-severity-chips">
            {SEVERITIES.map(s => {
              const isActive = form.severity === s.value
              const colorClass = SEVERITY_CLASS[s.color] || 'is-slate'
              return (
                <button
                  key={s.value}
                  type="button"
                  className={
                    `incident-severity-chip ${colorClass}` +
                    (isActive ? ' incident-severity-chip--active' : '')
                  }
                  onClick={() => set('severity', s.value)}
                  disabled={busy}
                  title={s.hint}
                >
                  {s.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
