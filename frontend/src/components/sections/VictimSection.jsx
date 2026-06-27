import React from 'react'
import { Input } from '../ui/Field.jsx'
import { Button } from '../ui/Button.jsx'
import { EMPTY_VICTIM } from './formConstants.js'

function SubLabel({ icon, children }) {
  return (
    <div className="incident-sublabel">
      {icon && <span className="incident-sublabel__icon">{icon}</span>}
      <span>{children}</span>
    </div>
  )
}

export default function VictimSection({ victimsList, expandedVictims, busy, onAdd, onRemove, onToggle, onSetVictim }) {
  if (!victimsList) return null

  return (
    <div className="incident-section">
      <div className="incident-actions-row">
        <SubLabel>Сведения о пострадавших</SubLabel>
        <Button type="button" variant="secondary" size="sm" onClick={onAdd} disabled={busy}>
          + Добавить пострадавшего
        </Button>
      </div>
      {victimsList.length === 0 && (
        <div className="incident-empty">Нет добавленных пострадавших — заполните вручную или загрузите .docx</div>
      )}
      {victimsList.map((v, idx) => (
        <div key={idx} className="incident-victim-card">
          <div className="incident-victim-summary" onClick={() => onToggle(idx)}>
            <span className="incident-victim-summary__title">
              {v.full_name ? v.full_name : `Пострадавший ${idx + 1}`}
            </span>
            <div className="incident-victim-summary__actions">
              <span className="incident-victim-toggle">{expandedVictims?.[idx] ? '▲' : '▼'}</span>
              <Button type="button" variant="ghost" size="sm"
                onClick={e => { e.stopPropagation(); onRemove(idx) }} disabled={busy}>✕</Button>
            </div>
          </div>
          {expandedVictims?.[idx] && (
            <div className="incident-victim-content">
              <div className="incident-grid">
                <Input label="ФИО" type="text" value={v.full_name}
                  onChange={e => onSetVictim(idx, 'full_name', e.target.value)}
                  placeholder="Иванов Иван Иванович" disabled={busy} />
              </div>
              <div className="incident-grid incident-grid--four">
                <Input label="Дата рождения" type="date" value={v.birth_date}
                  onChange={e => onSetVictim(idx, 'birth_date', e.target.value)} disabled={busy} />
                <Input label="Возраст" type="number" min={14} max={99} value={v.age}
                  onChange={e => onSetVictim(idx, 'age', e.target.value)} disabled={busy} />
                <Input label="Семейное положение" type="text" value={v.family_status}
                  onChange={e => onSetVictim(idx, 'family_status', e.target.value)}
                  placeholder="Женат / Замужем / …" disabled={busy} />
                <Input label="Детей до 21 г." type="number" min={0} value={v.children_under_21}
                  onChange={e => onSetVictim(idx, 'children_under_21', e.target.value)} disabled={busy} />
              </div>
              <div className="incident-grid incident-grid--two">
                <Input label="Профессия / должность" type="text" value={v.profession}
                  onChange={e => onSetVictim(idx, 'profession', e.target.value)} disabled={busy} />
                <Input label="Место работы" type="text" value={v.workplace}
                  onChange={e => onSetVictim(idx, 'workplace', e.target.value)} disabled={busy} />
              </div>
              <div className="incident-grid incident-grid--three">
                <Input label="Общий стаж" type="text" value={v.total_experience}
                  onChange={e => onSetVictim(idx, 'total_experience', e.target.value)}
                  placeholder="5 лет 3 мес." disabled={busy} />
                <Input label="Стаж в организации" type="text" value={v.experience_in_organization}
                  onChange={e => onSetVictim(idx, 'experience_in_organization', e.target.value)}
                  placeholder="2 года" disabled={busy} />
                <Input label="Квалификационное удостоверение" type="text" value={v.qualification_certificate}
                  onChange={e => onSetVictim(idx, 'qualification_certificate', e.target.value)} disabled={busy} />
              </div>
              <div className="incident-grid incident-grid--two">
                <Input label="Вводный инструктаж" type="text" value={v.introductory_briefing}
                  onChange={e => onSetVictim(idx, 'introductory_briefing', e.target.value)}
                  placeholder="дд.мм.гггг / не проводился" disabled={busy} />
                <Input label="Первичный / повторный инструктаж" type="text" value={v.workplace_briefing}
                  onChange={e => onSetVictim(idx, 'workplace_briefing', e.target.value)}
                  placeholder="дд.мм.гггг / не проводился" disabled={busy} />
              </div>
              <div className="incident-grid incident-grid--three">
                <Input label="Стажировка / допуск к работе" type="text" value={v.internship}
                  onChange={e => onSetVictim(idx, 'internship', e.target.value)}
                  placeholder="дд.мм.гггг / не проводилась" disabled={busy} />
                <Input label="Проверка знаний по ОТ" type="text" value={v.safety_knowledge_test}
                  onChange={e => onSetVictim(idx, 'safety_knowledge_test', e.target.value)}
                  placeholder="дд.мм.гггг / не проводилась" disabled={busy} />
                <Input label="Медицинский осмотр" type="text" value={v.medical_examination}
                  onChange={e => onSetVictim(idx, 'medical_examination', e.target.value)}
                  placeholder="дд.мм.гггг / не проходил" disabled={busy} />
              </div>
              <div className="incident-grid">
                <Input label="Диагноз / степень тяжести" type="text" value={v.diagnosis_severity}
                  onChange={e => onSetVictim(idx, 'diagnosis_severity', e.target.value)}
                  placeholder="Перелом, лёгкая степень…" disabled={busy} />
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
