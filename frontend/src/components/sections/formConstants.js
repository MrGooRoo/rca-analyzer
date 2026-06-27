/* Константы формы анализа */
import { METHODOLOGIES } from '../../lib/methodologies.js'

export const SEVERITIES = [
  { value: 'critical',  label: 'Критический', hint: 'Смерть / тяжёлый вред',       color: 'rose' },
  { value: 'major',     label: 'Тяжёлый',     hint: 'Госпитализация / крупный ущерб', color: 'amber' },
  { value: 'moderate',  label: 'Средний',      hint: 'Временная нетрудоспособность',  color: 'sky' },
  { value: 'minor',     label: 'Лёгкий',       hint: 'Первая помощь / малый ущерб',   color: 'emerald' },
  { value: 'near_miss', label: 'Предпосылка',  hint: 'Без пострадавших',              color: 'slate' },
]

export const TYPES = [
  { value: 'injury',        label: 'Травма' },
  { value: 'equipment',     label: 'Оборудование' },
  { value: 'fire',          label: 'Пожар' },
  { value: 'spill',         label: 'Разлив' },
  { value: 'near_miss',     label: 'Предпосылка' },
  { value: 'process_upset', label: 'Нарушение процесса' },
  { value: 'security',      label: 'Безопасность' },
  { value: 'environmental', label: 'Экология' },
]

export const DETAIL_LEVELS = [
  { value: 1, label: 'Кратко',    hint: 'Ключевые причины и выводы' },
  { value: 2, label: 'Стандарт',  hint: 'Развёрнутый анализ с рекомендациями' },
  { value: 3, label: 'Подробно',  hint: 'Полный отчёт со всеми деталями' },
]

export const EMPTY_VICTIM = {
  full_name: '', birth_date: '', age: '', family_status: '', children_under_21: '',
  profession: '', workplace: '', total_experience: '', experience_in_organization: '',
  qualification_certificate: '', introductory_briefing: '', workplace_briefing: '',
  internship: '', safety_knowledge_test: '', medical_examination: '', diagnosis_severity: '',
}

export const DEFAULTS = {
  title: '', description: '', incident_date: '', location: '',
  incident_type: 'injury', severity: 'moderate', victims: 0,
  methodology: 'five_why', detail_level: 2,
  incident_time: '', company: '', department: '', location_detailed: '',
  injured_count: 0, fatalities_count: 0, short_description: '',
  photo_urls: [], scene_description: '', equipment_description: '',
  full_circumstances: '', established_facts: '', victims_list: [],
  mode: 'single', methodologies: ['five_why'],
}

export const STEPS = [
  { num: 1, label: 'Основное', icon: '📋' },
  { num: 2, label: 'Детали', icon: '🔍' },
  { num: 3, label: 'Анализ', icon: '⚙️' },
]

export const METHODOLOGY_OPTIONS = [
  { id: 'single', icon: '🎯', label: 'Одна методика' },
  { id: 'multi', icon: '⚖️', label: 'Сравнить методики' },
]
