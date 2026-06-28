import React, { useEffect, useState } from 'react'
import { Input } from '../ui/Field.jsx'
import { EMPTY_VICTIM } from './formConstants.js'

function SubLabel({ icon, children }) {
  return (
    <div className="incident-sublabel">
      {icon && <span className="incident-sublabel__icon">{icon}</span>}
      <span>{children}</span>
    </div>
  )
}

/**
 * Секция «Сведения о пострадавших».
 *
 * Содержит счётчики «Пострадавшие» / «Погибшие» и автоматически
 * синхронизирует список victims_list.
 *
 * Каждый victim в списке имеет поле status: 'injured' | 'fatal'.
 */
export default function VictimSection({ form, set, busy }) {
  const victims = form.victims_list || []
  const [expanded, setExpanded] = useState({})

  const injuredCount = form.injured_count || 0
  const fatalitiesCount = form.fatalities_count || 0

  // ── Синхронизация victims_list с injured_count + fatalities_count ──
  useEffect(() => {
    const injured = victims.filter(v => v.status === 'injured')
    const fatal = victims.filter(v => v.status === 'fatal')
    let changed = false

    // Корректируем пострадавших
    while (injured.length < injuredCount) {
      injured.push({ ...EMPTY_VICTIM, status: 'injured' })
      changed = true
    }
    while (injured.length > injuredCount) {
      injured.pop()
      changed = true
    }

    // Корректируем погибших
    while (fatal.length < fatalitiesCount) {
      fatal.push({ ...EMPTY_VICTIM, status: 'fatal' })
      changed = true
    }
    while (fatal.length > fatalitiesCount) {
      fatal.pop()
      changed = true
    }

    if (changed) {
      set('victims_list', [...injured, ...fatal])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [injuredCount, fatalitiesCount])

  // ── Хелперы ──────────────────────────────────────────────────────
  function setVictimField(idx, field, value) {
    const list = [...victims]
    list[idx] = { ...list[idx], [field]: value }
    set('victims_list', list)
  }

  function toggleExpand(idx) {
    setExpanded(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  // ── Рендер ───────────────────────────────────────────────────────

  // Разбиваем на две группы
  const injuredList = victims.filter(v => v.status === 'injured')
  const fatalList = victims.filter(v => v.status === 'fatal')

  const total = injuredCount + fatalitiesCount
  if (total === 0) {
    return (
      <div className="incident-section">
        <SubLabel icon="👤">Сведения о пострадавших</SubLabel>
        <div className="incident-grid incident-grid--two">
          <Input label="Пострадавшие" type="number" min={0} value={form.injured_count ?? 0}
            onChange={e => set('injured_count', Number(e.target.value))} disabled={busy} />
          <Input label="Погибшие" type="number" min={0} value={form.fatalities_count ?? 0}
            onChange={e => set('fatalities_count', Number(e.target.value))} disabled={busy} />
        </div>
        <div className="incident-empty">
          Укажите количество — появятся поля для заполнения данных
        </div>
      </div>
    )
  }

  // Находим глобальный индекс по номеру в группе
  function globalIndex(group, localIdx) {
    if (group === 'injured') return localIdx
    return injuredList.length + localIdx
  }

  function renderGroup(list, groupLabel, groupKey, count) {
    if (count === 0) return null
    const label = groupKey === 'injured' ? 'Пострадавший' : 'Погибший'
    return (
      <div className="incident-victim-group">
        <div className="incident-victim-group__header">
          {groupLabel}: {count}
        </div>
        {list.map((v, localIdx) => {
          const gi = globalIndex(groupKey, localIdx)
          const isOpen = expanded[gi]
          return (
            <div key={gi} className="incident-victim-card">
              <div className="incident-victim-summary" onClick={() => toggleExpand(gi)}>
                <span className="incident-victim-summary__title">
                  {v.full_name
                    ? `${label} #${localIdx + 1} — ${v.full_name}`
                    : `${label} #${localIdx + 1}`}
                </span>
                <span className="incident-victim-toggle">{isOpen ? '▲' : '▼'}</span>
              </div>
              {isOpen && (
                <div className="incident-victim-content">
                  <div className="incident-grid">
                    <Input label="ФИО" type="text" value={v.full_name}
                      onChange={e => setVictimField(gi, 'full_name', e.target.value)}
                      placeholder="Иванов Иван Иванович" disabled={busy} required />
                  </div>
                  <div className="incident-grid incident-grid--four">
                    <Input label="Дата рождения" type="date" value={v.birth_date}
                      onChange={e => setVictimField(gi, 'birth_date', e.target.value)} disabled={busy} />
                    <Input label="Возраст" type="number" min={14} max={99} value={v.age}
                      onChange={e => setVictimField(gi, 'age', e.target.value)} disabled={busy} />
                    <Input label="Семейное положение" type="text" value={v.family_status}
                      onChange={e => setVictimField(gi, 'family_status', e.target.value)}
                      placeholder="Женат / Замужем / …" disabled={busy} />
                    <Input label="Детей до 21 г." type="number" min={0} value={v.children_under_21}
                      onChange={e => setVictimField(gi, 'children_under_21', e.target.value)} disabled={busy} />
                  </div>
                  <div className="incident-grid incident-grid--two">
                    <Input label="Профессия / должность" type="text" value={v.profession}
                      onChange={e => setVictimField(gi, 'profession', e.target.value)} disabled={busy} />
                    <Input label="Место работы" type="text" value={v.workplace}
                      onChange={e => setVictimField(gi, 'workplace', e.target.value)} disabled={busy} />
                  </div>
                  <div className="incident-grid incident-grid--three">
                    <Input label="Общий стаж" type="text" value={v.total_experience}
                      onChange={e => setVictimField(gi, 'total_experience', e.target.value)}
                      placeholder="5 лет 3 мес." disabled={busy} />
                    <Input label="Стаж в организации" type="text" value={v.experience_in_organization}
                      onChange={e => setVictimField(gi, 'experience_in_organization', e.target.value)}
                      placeholder="2 года" disabled={busy} />
                    <Input label="Квалификационное удостоверение" type="text" value={v.qualification_certificate}
                      onChange={e => setVictimField(gi, 'qualification_certificate', e.target.value)} disabled={busy} />
                  </div>
                  <div className="incident-grid incident-grid--two">
                    <Input label="Вводный инструктаж" type="text" value={v.introductory_briefing}
                      onChange={e => setVictimField(gi, 'introductory_briefing', e.target.value)}
                      placeholder="дд.мм.гггг / не проводился" disabled={busy} />
                    <Input label="Первичный / повторный инструктаж" type="text" value={v.workplace_briefing}
                      onChange={e => setVictimField(gi, 'workplace_briefing', e.target.value)}
                      placeholder="дд.мм.гггг / не проводился" disabled={busy} />
                  </div>
                  <div className="incident-grid incident-grid--three">
                    <Input label="Стажировка / допуск к работе" type="text" value={v.internship}
                      onChange={e => setVictimField(gi, 'internship', e.target.value)}
                      placeholder="дд.мм.гггг / не проводилась" disabled={busy} />
                    <Input label="Проверка знаний по ОТ" type="text" value={v.safety_knowledge_test}
                      onChange={e => setVictimField(gi, 'safety_knowledge_test', e.target.value)}
                      placeholder="дд.мм.гггг / не проводилась" disabled={busy} />
                    <Input label="Медицинский осмотр" type="text" value={v.medical_examination}
                      onChange={e => setVictimField(gi, 'medical_examination', e.target.value)}
                      placeholder="дд.мм.гггг / не проходил" disabled={busy} />
                  </div>
                  <div className="incident-grid">
                    <Input label="Диагноз / степень тяжести" type="text" value={v.diagnosis_severity}
                      onChange={e => setVictimField(gi, 'diagnosis_severity', e.target.value)}
                      placeholder="Перелом, лёгкая степень…" disabled={busy} />
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="incident-section">
      <SubLabel icon="👤">Сведения о пострадавших</SubLabel>

      {/* Счётчики — всегда видны */}
      <div className="incident-grid incident-grid--two">
        <Input label="Пострадавшие" type="number" min={0} value={form.injured_count ?? 0}
          onChange={e => set('injured_count', Number(e.target.value))} disabled={busy} />
        <Input label="Погибшие" type="number" min={0} value={form.fatalities_count ?? 0}
          onChange={e => set('fatalities_count', Number(e.target.value))} disabled={busy} />
      </div>

      {/* Карточки пострадавших */}
      {injuredCount > 0 && renderGroup(injuredList, 'Пострадавшие', 'injured', injuredCount)}
      {fatalitiesCount > 0 && renderGroup(fatalList, 'Погибшие', 'fatal', fatalitiesCount)}
    </div>
  )
}
