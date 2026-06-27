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

function SeverityCard(s, active, disabled) {
  return `incident-severity-card ${
    active ? 'incident-choice--active' : 'incident-severity-card--hoverable'
  } ${disabled ? 'is-disabled' : ''}`
}

export default function ClassificationSection({ form, set, busy }) {
  return (
    <div className="incident-section">
      <SubLabel icon="🏷️">Классификация инцидента</SubLabel>

      <Select label="Тип инцидента" value={form.incident_type}
        onChange={e => set('incident_type', e.target.value)} disabled={busy}>
        {TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
      </Select>

      <SubLabel>Тяжесть инцидента</SubLabel>
      <div className="incident-severity-grid">
        {SEVERITIES.map(s => (
          <label key={s.value} className={SeverityCard(s, form.severity === s.value, busy)}>
            <input type="radio" name="severity" value={s.value}
              checked={form.severity === s.value}
              onChange={() => set('severity', s.value)}
              disabled={busy} className="incident-sr-only" />
            <div className="incident-severity-card__title">{s.label}</div>
            <div className="incident-severity-card__hint">{s.hint}</div>
          </label>
        ))}
      </div>
    </div>
  )
}
