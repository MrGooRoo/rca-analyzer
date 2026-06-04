/**
 * BowtieDiagram — Apple-style redesign.
 *
 * Визуальный язык: стеклянные карточки, 5-колоночный grid,
 * тонкие SVG bezier-связи, приглушённая палитра, без вертикального текста.
 *
 * Структура causal_tree по category:
 *   BOWTIE:HAZARD       — источник опасности
 *   BOWTIE:TOP_EVENT    — центральное событие
 *   BOWTIE:THREAT       — угрозы (левое крыло)
 *   BOWTIE:PREVENTION   — барьеры предотвращения
 *   BOWTIE:CONSEQUENCE  — последствия (правое крыло)
 *   BOWTIE:MITIGATION   — барьеры смягчения
 */

import React, { useRef, useState, useLayoutEffect, useCallback } from 'react'
import './BowtieDiagram.css'

// ── Палитра (приглушённая, iOS-стиль) ─────────────────────────────────────────
const PALETTE = {
  hazard:      { bg: 'rgba(167,139,250,0.18)', border: 'rgba(167,139,250,0.45)', dot: '#a78bfa', text: '#ede9fe' },
  topEvent:    { bg: 'rgba(248,113,113,0.22)', border: 'rgba(248,113,113,0.55)', dot: '#f87171', text: '#fff1f2' },
  threat:      { bg: 'rgba(251,146,60,0.18)',  border: 'rgba(251,146,60,0.45)',  dot: '#fb923c', text: '#fff7ed' },
  prevention:  { bg: 'rgba(250,204,21,0.15)',  border: 'rgba(250,204,21,0.40)',  dot: '#facc15', text: '#fefce8' },
  mitigation:  { bg: 'rgba(52,211,153,0.15)',  border: 'rgba(52,211,153,0.40)',  dot: '#34d399', text: '#ecfdf5' },
  consequence: { bg: 'rgba(96,165,250,0.16)',  border: 'rgba(96,165,250,0.42)',  dot: '#60a5fa', text: '#eff6ff' },
}

const LEGEND = [
  { key: 'threat',      label: 'Угрозы' },
  { key: 'prevention',  label: 'Барьеры предотвр.' },
  { key: 'topEvent',    label: 'Топ-событие' },
  { key: 'mitigation',  label: 'Барьеры смягч.' },
  { key: 'consequence', label: 'Последствия' },
  { key: 'hazard',      label: 'Опасный фактор' },
]

// ── Парсер данных ─────────────────────────────────────────────────────────────
function parseBowtieData(result) {
  const tree = result.causal_tree || []
  const by = (cat) => tree.filter(n => n.category?.toUpperCase().includes(cat))

  let hazards      = by('HAZARD')
  let topEvents    = by('TOP_EVENT')
  let threats      = by('THREAT')
  let prevention   = by('PREVENTION')
  let consequences = by('CONSEQUENCE')
  let mitigation   = by('MITIGATION')

  // Фаллбэк
  if (!threats.length)      threats      = result.root_causes || []
  if (!consequences.length) consequences = (result.immediate_causes || []).slice(1)
  if (!topEvents.length)    topEvents    = (result.immediate_causes || []).slice(0, 1)
  if (!prevention.length || !mitigation.length) {
    const contrib = result.contributing_causes || []
    if (!prevention.length)  prevention  = contrib.filter((_, i) => i % 2 === 0)
    if (!mitigation.length)  mitigation  = contrib.filter((_, i) => i % 2 !== 0)
  }

  return { hazards, topEvents, threats, prevention, consequences, mitigation }
}

// ── Главный компонент ─────────────────────────────────────────────────────────
export default function BowtieDiagram({ result }) {
  const data = parseBowtieData(result)
  const { hazards, topEvents, threats, prevention, consequences, mitigation } = data

  const topEvent = topEvents[0]
  const hazard   = hazards[0]

  // Refs для измерения DOM-позиций карточек
  const colRefs = {
    threats:      useRef([]),
    prevention:   useRef([]),
    topEvent:     useRef(null),
    mitigation:   useRef([]),
    consequences: useRef([]),
  }

  const svgRef    = useRef(null)
  const wrapRef   = useRef(null)
  const [paths, setPaths]   = useState([])
  const [tooltip, setTooltip] = useState(null)

  // Пересчёт SVG-путей после рендера
  const calcPaths = useCallback(() => {
    if (!svgRef.current || !wrapRef.current) return
    const wrap = wrapRef.current.getBoundingClientRect()

    function midRight(el) {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { x: r.right - wrap.left, y: r.top + r.height / 2 - wrap.top }
    }
    function midLeft(el) {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { x: r.left - wrap.left, y: r.top + r.height / 2 - wrap.top }
    }

    const topEl = colRefs.topEvent.current
    if (!topEl) return
    const topLeft  = midLeft(topEl)
    const topRight = midRight(topEl)

    const newPaths = []

    // Threats → Prevention → Top Event
    threats.forEach((_, i) => {
      const tEl = colRefs.threats.current[i]
      const pEl = colRefs.prevention.current[i] || colRefs.prevention.current[0]
      if (!tEl) return
      const tR = midRight(tEl)
      if (pEl) {
        const pL = midLeft(pEl)
        const pR = midRight(pEl)
        if (tR && pL) newPaths.push(bezier(tR, pL, 'left'))
        if (pR && topLeft) newPaths.push(bezier(pR, topLeft, 'left'))
      } else {
        if (tR && topLeft) newPaths.push(bezier(tR, topLeft, 'left'))
      }
    })
    // Лишние prevention без пары
    prevention.forEach((_, i) => {
      if (i >= threats.length) {
        const pEl = colRefs.prevention.current[i]
        if (!pEl) return
        const pR = midRight(pEl)
        if (pR && topLeft) newPaths.push(bezier(pR, topLeft, 'left'))
      }
    })

    // Top Event → Mitigation → Consequences
    consequences.forEach((_, i) => {
      const cEl = colRefs.consequences.current[i]
      const mEl = colRefs.mitigation.current[i] || colRefs.mitigation.current[0]
      if (!cEl) return
      const cL = midLeft(cEl)
      if (mEl) {
        const mR = midRight(mEl)
        const mL = midLeft(mEl)
        if (topRight && mL) newPaths.push(bezier(topRight, mL, 'right'))
        if (mR && cL) newPaths.push(bezier(mR, cL, 'right'))
      } else {
        if (topRight && cL) newPaths.push(bezier(topRight, cL, 'right'))
      }
    })
    prevention.forEach((_, i) => {
      if (i >= consequences.length) {
        const mEl = colRefs.mitigation.current[i]
        if (!mEl) return
        const mL = midLeft(mEl)
        if (topRight && mL) newPaths.push(bezier(topRight, mL, 'right'))
      }
    })

    setPaths(newPaths)
  }, [threats, prevention, consequences, mitigation])

  useLayoutEffect(() => {
    calcPaths()
    const ro = new ResizeObserver(calcPaths)
    if (wrapRef.current) ro.observe(wrapRef.current)
    return () => ro.disconnect()
  }, [calcPaths])

  function showTip(e, node) {
    setTooltip({ text: node.text, conf: node.confidence, x: e.clientX, y: e.clientY })
  }

  return (
    <div className="bt-shell">

      {/* Легенда */}
      <div className="bt-legend">
        {LEGEND.map(({ key, label }) => (
          <span key={key} className="bt-legend-item">
            <span className="bt-legend-dot" style={{ background: PALETTE[key].dot }} />
            {label}
          </span>
        ))}
      </div>

      {/* Диаграмма */}
      <div className="bt-diagram" ref={wrapRef}>

        {/* SVG-слой связей */}
        <svg ref={svgRef} className="bt-svg-layer" aria-hidden="true">
          <defs>
            <marker id="arr-l" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
              <path d="M0,0 L0,7 L7,3.5 z" fill="rgba(160,180,255,0.35)" />
            </marker>
            <marker id="arr-r" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
              <path d="M0,0 L0,7 L7,3.5 z" fill="rgba(160,255,200,0.30)" />
            </marker>
          </defs>
          {paths.map((d, i) => (
            <path
              key={i}
              d={d.path}
              fill="none"
              stroke={d.side === 'left' ? 'rgba(160,180,255,0.22)' : 'rgba(100,220,180,0.22)'}
              strokeWidth={1.5}
              markerEnd={d.side === 'left' ? 'url(#arr-l)' : 'url(#arr-r)'}
            />
          ))}
        </svg>

        {/* Колонки */}
        <div className="bt-col bt-col--threats">
          {hazard && (
            <Card
              node={hazard}
              palette={PALETTE.hazard}
              isHazard
              onHover={showTip}
              onLeave={() => setTooltip(null)}
            />
          )}
          {threats.map((n, i) => (
            <Card
              key={n?.id || i}
              node={n}
              palette={PALETTE.threat}
              ref={el => colRefs.threats.current[i] = el}
              onHover={showTip}
              onLeave={() => setTooltip(null)}
            />
          ))}
        </div>

        <div className="bt-col bt-col--prevention">
          {prevention.map((n, i) => (
            <Card
              key={n?.id || i}
              node={n}
              palette={PALETTE.prevention}
              isBarrier
              ref={el => colRefs.prevention.current[i] = el}
              onHover={showTip}
              onLeave={() => setTooltip(null)}
            />
          ))}
        </div>

        <div className="bt-col bt-col--center">
          <Card
            node={topEvent || { text: 'Топ-событие', confidence: 1 }}
            palette={PALETTE.topEvent}
            isCenter
            ref={colRefs.topEvent}
            onHover={showTip}
            onLeave={() => setTooltip(null)}
          />
        </div>

        <div className="bt-col bt-col--mitigation">
          {mitigation.map((n, i) => (
            <Card
              key={n?.id || i}
              node={n}
              palette={PALETTE.mitigation}
              isBarrier
              ref={el => colRefs.mitigation.current[i] = el}
              onHover={showTip}
              onLeave={() => setTooltip(null)}
            />
          ))}
        </div>

        <div className="bt-col bt-col--consequences">
          {consequences.map((n, i) => (
            <Card
              key={n?.id || i}
              node={n}
              palette={PALETTE.consequence}
              ref={el => colRefs.consequences.current[i] = el}
              onHover={showTip}
              onLeave={() => setTooltip(null)}
            />
          ))}
        </div>
      </div>

      {/* Тултип */}
      {tooltip && (
        <div
          className="bt-tooltip"
          style={{ left: tooltip.x + 12, top: tooltip.y - 40 }}
        >
          <div className="bt-tooltip-text">{tooltip.text}</div>
          {tooltip.conf != null && (
            <div className="bt-tooltip-conf">
              Уверенность: {(tooltip.conf * 100).toFixed(0)}%
              <span
                className="bt-tooltip-bar"
                style={{ width: `${tooltip.conf * 100}%`,
                  background: tooltip.conf > 0.6 ? '#34d399' : tooltip.conf > 0.3 ? '#facc15' : '#f87171' }}
              />
            </div>
          )}
        </div>
      )}

      {/* Список узлов (детали) */}
      <details className="bt-raw">
        <summary>▸ Список узлов</summary>
        <div className="bt-raw-grid">
          {[
            { label: 'Угрозы',           nodes: threats,      key: 'threat' },
            { label: 'Барьеры предотвр.', nodes: prevention,   key: 'prevention' },
            { label: 'Топ-событие',       nodes: topEvents,    key: 'topEvent' },
            { label: 'Барьеры смягч.',    nodes: mitigation,   key: 'mitigation' },
            { label: 'Последствия',       nodes: consequences,  key: 'consequence' },
          ].map(col => (
            <div key={col.label}>
              <div className="bt-raw-label" style={{ color: PALETTE[col.key].dot }}>{col.label}</div>
              {col.nodes.map((n, i) => (
                <div key={n?.id || i} className="bt-raw-node">
                  <span>{n?.text}</span>
                  <span className="bt-raw-conf">{n ? (n.confidence * 100).toFixed(0) + '%' : ''}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}

// ── Card (React.forwardRef) ────────────────────────────────────────────────────
const Card = React.forwardRef(function Card(
  { node, palette, isCenter, isBarrier, isHazard, onHover, onLeave },
  ref
) {
  const degraded = node?.confidence != null && node.confidence < 0.3
  const text = node?.text || ''

  return (
    <div
      ref={ref}
      className={[
        'bt-card',
        isCenter  ? 'bt-card--center'  : '',
        isBarrier ? 'bt-card--barrier' : '',
        isHazard  ? 'bt-card--hazard'  : '',
        degraded  ? 'bt-card--degraded': '',
      ].join(' ').trim()}
      style={{
        background:   palette.bg,
        borderColor:  degraded ? 'rgba(248,113,113,0.5)' : palette.border,
      }}
      onMouseEnter={e => node && onHover(e, node)}
      onMouseLeave={onLeave}
    >
      {isBarrier && <div className="bt-card-shield" style={{ background: palette.dot }} />}
      <span className="bt-card-text" style={{ color: palette.text }}>{text}</span>
      {degraded && <span className="bt-card-degraded-mark" title="Низкая уверенность">⚠</span>}
    </div>
  )
})

// ── Bezier-путь между двумя точками ───────────────────────────────────────────
function bezier(from, to, side) {
  const dx = Math.abs(to.x - from.x) * 0.5
  const c1x = from.x + dx
  const c2x = to.x - dx
  return {
    path: `M ${from.x} ${from.y} C ${c1x} ${from.y}, ${c2x} ${to.y}, ${to.x} ${to.y}`,
    side,
  }
}
