/**
 * Метаданные методологий анализа — для карточек выбора, бейджей, описаний.
 * Единый источник правды вместо разбросанных METHODOLOGY_LABELS.
 */

export const METHODOLOGIES = [
  {
    id: 'five_why',
    name: '5 Почему',
    short: '5 Почему',
    description: 'Последовательный поиск корневой причины через цепочку вопросов «Почему?». Быстро и эффективно для простых инцидентов.',
    icon: '❓',
    color: 'from-sky-500 to-blue-600',
    badgeTone: 'sky',
  },
  {
    id: 'ishikawa',
    name: 'Ishikawa',
    short: 'Диаграмма Исикавы',
    description: 'Категоризация причин по 6M: люди, методы, машины, материалы, измерения, среда. Подходит для системного разбора.',
    icon: '🐟',
    color: 'from-emerald-500 to-teal-600',
    badgeTone: 'emerald',
  },
  {
    id: 'fta',
    name: 'FTA',
    short: 'Fault Tree Analysis',
    description: 'Дедуктивный анализ: от верхнего нежелательного события вниз через логические связки к базовым причинам.',
    icon: '🌳',
    color: 'from-amber-500 to-orange-600',
    badgeTone: 'amber',
  },
  {
    id: 'rca_systemic',
    name: 'RCA Системный',
    short: 'Системный RCA',
    description: 'Глубокий анализ организационных, технических и человеческих факторов с учётом взаимосвязей в системе.',
    icon: '⚙️',
    color: 'from-violet-500 to-purple-600',
    badgeTone: 'violet',
  },
  {
    id: 'bowtie',
    name: 'Bowtie',
    short: 'Диаграмма «Галстук-бабочка»',
    description: 'Угрозы → барьеры → топ-событие → барьеры → последствия. Визуализирует риски и эффективность контролей.',
    icon: '🎀',
    color: 'from-rose-500 to-pink-600',
    badgeTone: 'rose',
  },
]

/** Получить метаданные методологии по id */
export function methodologyMeta(id) {
  return METHODOLOGIES.find(m => m.id === id) ?? METHODOLOGIES[0]
}

/** Простая мапа id → название (для обратной совместимости) */
export const METHODOLOGY_LABELS = Object.fromEntries(
  METHODOLOGIES.map(m => [m.id, m.name])
)
