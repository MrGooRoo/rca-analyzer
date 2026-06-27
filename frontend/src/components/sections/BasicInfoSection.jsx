import React from 'react'
import { Input, Textarea } from '../ui/Field.jsx'
import SimilarIncidentsHint from '../SimilarIncidentsHint.jsx'

function SubLabel({ icon, children }) {
  return (
    <div className="incident-sublabel">
      {icon && <span className="incident-sublabel__icon">{icon}</span>}
      <span>{children}</span>
    </div>
  )
}

export default function BasicInfoSection({ form, set, busy, showAdvanced, onOpenResult }) {
  const similarQueryText = [
    form.title, form.description, form.short_description,
    form.scene_description, form.equipment_description,
    form.full_circumstances, form.established_facts,
  ].filter(Boolean).join('\n')

  return (
    <div className="incident-section" id="step-data">
      <SubLabel icon="📝">Описание обстоятельств происшествия</SubLabel>
      <div className="incident-grid">
        <Input label="Заголовок инцидента" type="text" value={form.title}
          onChange={e => set('title', e.target.value)}
          placeholder="Кратко укажите, что произошло" required minLength={5} disabled={busy} />
      </div>
      <div className="incident-grid">
        <Textarea label="Описание" rows={4} value={form.description}
          onChange={e => set('description', e.target.value)}
          placeholder="Опишите обстоятельства: кто участвовал, что произошло, какие последствия и какие первичные меры были приняты"
          required minLength={20} disabled={busy} />
      </div>
      {similarQueryText.length >= 20 && !busy && (
        <SimilarIncidentsHint queryText={similarQueryText}
          incidentTitle={form.title} incidentDescription={form.description}
          onOpenResult={onOpenResult} />
      )}
      <div className="incident-grid incident-grid--four">
        <Input label="Дата инцидента" type="date" value={form.incident_date}
          onChange={e => set('incident_date', e.target.value)} disabled={busy} />
        <Input label="Время инцидента" type="time" value={form.incident_time}
          onChange={e => set('incident_time', e.target.value)} disabled={busy} />
        <div className="incident-grid-span-two">
          <Input label="Местоположение" type="text" value={form.location}
            onChange={e => set('location', e.target.value)}
            placeholder="Укажите площадку, участок или зону происшествия" disabled={busy} />
        </div>
      </div>
      <div className="incident-grid incident-grid--three">
        <Input label="Предприятие" type="text" value={form.company}
          onChange={e => set('company', e.target.value)}
          placeholder="Укажите организацию или производственную площадку" disabled={busy} />
        <Input label="Подразделение" type="text" value={form.department}
          onChange={e => set('department', e.target.value)}
          placeholder="Укажите подразделение, службу или подрядчика" disabled={busy} />
        <Input label="Детальное место" type="text" value={form.location_detailed}
          onChange={e => set('location_detailed', e.target.value)}
          placeholder="Уточните место: помещение, отметка, оборудование или рабочая зона" disabled={busy} />
      </div>
      <div className="incident-grid incident-grid--two">
        <Input label="Пострадавшие" type="number" min={0} value={form.injured_count}
          onChange={e => set('injured_count', e.target.value)} disabled={busy} />
        <Input label="Погибшие" type="number" min={0} value={form.fatalities_count}
          onChange={e => set('fatalities_count', e.target.value)} disabled={busy} />
        <div className="incident-grid-span-two">
          <Textarea label="Краткое описание" rows={2} value={form.short_description}
            onChange={e => set('short_description', e.target.value)}
            placeholder="Одно-два предложения для быстрого понимания события" disabled={busy} />
        </div>
      </div>
    </div>
  )
}
