import React from 'react'
import { Input, Textarea } from '../ui/Field.jsx'

function SubLabel({ icon, children }) {
  return (
    <div className="incident-sublabel">
      {icon && <span className="incident-sublabel__icon">{icon}</span>}
      <span>{children}</span>
    </div>
  )
}

export default function AdvancedFieldsSection({ form, set, busy }) {
  return (
    <>
      {/* Фото — временно скрыто (экономия места на сервере и токенов) */}
      {/*<div className="incident-section">
        <SubLabel icon="📷">Фото с места происшествия</SubLabel>
        <Textarea label="Ссылки на фото (по одной на строку)" rows={3}
          placeholder="https://..."
          value={form.photo_urls?.join('\n') || ''}
          onChange={e => set('photo_urls', e.target.value.split('\n').map(s => s.trim()).filter(Boolean))}
          disabled={busy} />
        {form.photo_urls?.length > 0 && (
          <div className="incident-photo-links">
            {form.photo_urls.map((url, i) => (
              <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="incident-photo-link">
                📷 Фото {i + 1}
              </a>
            ))}
          </div>
        )}
      </div>*/}

      {/* Установленные факты */}
      <div className="incident-section">
        <SubLabel icon="🔍">Установленные факты</SubLabel>

        <SubLabel>Описание места происшествия</SubLabel>
        <Textarea label="Описание места происшествия" rows={3} value={form.scene_description}
          onChange={e => set('scene_description', e.target.value)}
          placeholder="Опишите состояние места, доступ, освещение, ограждения, проходы, погодные или производственные условия"
          disabled={busy} />

        <SubLabel>Характеристика оборудования / объекта</SubLabel>
        <Textarea label="Характеристика оборудования / объекта" rows={3} value={form.equipment_description}
          onChange={e => set('equipment_description', e.target.value)}
          placeholder="Укажите оборудование, инструмент, объект работ, их состояние и особенности эксплуатации"
          disabled={busy} />

        <SubLabel>Полное описание обстоятельств</SubLabel>
        <Textarea label="Полное описание обстоятельств" rows={4} value={form.full_circumstances}
          onChange={e => set('full_circumstances', e.target.value)}
          placeholder="Опишите последовательность событий до, во время и после происшествия"
          disabled={busy} />

        <SubLabel>Установленные факты</SubLabel>
        <Textarea label="Установленные факты" rows={4} value={form.established_facts}
          onChange={e => set('established_facts', e.target.value)}
          placeholder="Перечислите подтверждённые факты, выявленные нарушения, документы, показания или замеры"
          disabled={busy} />
      </div>
    </>
  )
}
