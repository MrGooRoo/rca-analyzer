/**
 * BowtieDiagram — Apple-style glass UI.
 * Фикс: double-rAF для гарантированного замера домъ после layout,
 * align-items:stretch + justify-content:center для выравнивания колонок.
 */

import React, { useRef, useState, useEffect } from 'react'
import './BowtieDiagram.css'

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

function parseBowtieData(result) {
  const tree = result.causal_tree || []
  const by = (cat) => tree.filter(n => n.category?.toUpperCase().includes(cat))

  let hazards      = by('HAZARD')
  let topEvents    = by('TOP_EVENT')
  let threats      = by('THREAT')
  let prevention   = by('PREVENTION')
  let consequences = by('CONSEQUENCE')
  let mitigation   = by('MITIGATION')

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

function bezierPath(x1, y1, x2, y2) {
  const dx = Math.abs(x2 - x1) * 0.5
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`
}

export default function BowtieDiagram({ result }) {
  const data = parseBowtieData(result)
  const { hazards, topEvents, threats, prevention, consequences, mitigation } = data
  const topEvent = topEvents[0]
  const hazard   = hazards[0]

  const wrapRef = useRef(null)
  const [paths, setPaths] = useState([])
  const [tooltip, setTooltip] = useState(null)

  function recalc() {
    const wrap = wrapRef.current
    if (!wrap) return
    const wRect = wrap.getBoundingClientRect()
    if (wRect.width === 0) return   // ещё не отрисовано

    function mid(el, side) {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return {
        x: (side === 'right' ? r.right : r.left) - wRect.left,
        y: r.top + r.height / 2 - wRect.top,
      }
    }

    function byId(role, idx) {
      return wrap.querySelector(`[data-bt="${role}-${idx}"]`)
    }
    const topEl = wrap.querySelector('[data-bt="top"]')
    if (!topEl) return

    const topL = mid(topEl, 'left')
    const topR = mid(topEl, 'right')
    const newPaths = []

    // Левая сторона: угроза → [барьер] → топ-событие
    threats.forEach((_, i) => {
      const tEl = byId('threat', i)
      if (!tEl) return
      const tR = mid(tEl, 'right')
      const pEl = byId('prev', i) ?? byId('prev', 0)
      if (pEl) {
        const pL = mid(pEl, 'left')
        const pR = mid(pEl, 'right')
        if (tR && pL)   newPaths.push({ d: bezierPath(tR.x, tR.y, pL.x, pL.y), side: 'L' })
        if (pR && topL) newPaths.push({ d: bezierPath(pR.x, pR.y, topL.x, topL.y), side: 'L' })
      } else if (tR && topL) {
        newPaths.push({ d: bezierPath(tR.x, tR.y, topL.x, topL.y), side: 'L' })
      }
    })

    // Правая сторона: топ-событие → [барьер] → последствие
    consequences.forEach((_, i) => {
      const cEl = byId('cons', i)
      if (!cEl) return
      const cL = mid(cEl, 'left')
      const mEl = byId('miti', i) ?? byId('miti', 0)
      if (mEl) {
        const mL = mid(mEl, 'left')
        const mR = mid(mEl, 'right')
        if (topR && mL) newPaths.push({ d: bezierPath(topR.x, topR.y, mL.x, mL.y), side: 'R' })
        if (mR && cL)   newPaths.push({ d: bezierPath(mR.x, mR.y, cL.x, cL.y), side: 'R' })
      } else if (topR && cL) {
        newPaths.push({ d: bezierPath(topR.x, topR.y, cL.x, cL.y), side: 'R' })
      }
    })

    setPaths(newPaths)
  }

  useEffect(() => {
    // double-rAF: ждём два фрейма — grid-layout + paint гарантированно завершён
    let id1, id2
    id1 = requestAnimationFrame(() => {
      id2 = requestAnimationFrame(() => recalc())
    })
    const ro = new ResizeObserver(() => recalc())
    if (wrapRef.current) ro.observe(wrapRef.current)
    return () => {
      cancelAnimationFrame(id1)
      cancelAnimationFrame(id2)
      ro.disconnect()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threats.length, prevention.length, consequences.length, mitigation.length])

  function showTip(e, node) {
    setTooltip({ text: node.text, conf: node.confidence, x: e.clientX, y: e.clientY })
  }

  return (
    <div className="bt-shell">

      <div className="bt-legend">
        {LEGEND.map(({ key, label }) => (
          <span key={key} className="bt-legend-item">
            <span className="bt-legend-dot" style={{ background: PALETTE[key].dot }} />
            {label}
          </span>
        ))}
      </div>

      <div className="bt-diagram" ref={wrapRef}>

        {/* SVG-слой */}
        <svg className="bt-svg-layer" aria-hidden="true">
          <defs>
            <filter id="bt-glow-l">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="bt-glow-r">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          {paths.map((p, i) => (
            <path
              key={i}
              d={p.d}
              fill="none"
              stroke={p.side === 'L' ? 'rgba(160,180,255,0.35)' : 'rgba(80,220,170,0.35)'}
              strokeWidth={1.8}
              filter={`url(#bt-glow-${p.side === 'L' ? 'l' : 'r'})`}
            />
          ))}
        </svg>

        {/* Кол. 1: Угрозы + Hazard */}
        <div className="bt-col">
          {hazard && (
            <Card node={hazard} palette={PALETTE.hazard} isHazard
              onHover={showTip} onLeave={() => setTooltip(null)} />
          )}
          {threats.map((n, i) => (
            <Card key={n?.id ?? i} node={n} palette={PALETTE.threat}
              dataId={`threat-${i}`}
              onHover={showTip} onLeave={() => setTooltip(null)} />
          ))}
        </div>

        {/* Кол. 2: Барьеры предотвр. */}
        <div className="bt-col">
          {prevention.map((n, i) => (
            <Card key={n?.id ?? i} node={n} palette={PALETTE.prevention} isBarrier
              dataId={`prev-${i}`}
              onHover={showTip} onLeave={() => setTooltip(null)} />
          ))}
        </div>

        {/* Кол. 3: Топ-событие */}
        <div className="bt-col bt-col--center">
          <Card
            node={topEvent || { text: 'Топ-событие', confidence: 1 }}
            palette={PALETTE.topEvent}
            isCenter
            dataId="top"
            onHover={showTip}
            onLeave={() => setTooltip(null)}
          />
        </div>

        {/* Кол. 4: Барьеры смягч. */}
        <div className="bt-col">
          {mitigation.map((n, i) => (
            <Card key={n?.id ?? i} node={n} palette={PALETTE.mitigation} isBarrier
              dataId={`miti-${i}`}
              onHover={showTip} onLeave={() => setTooltip(null)} />
          ))}
        </div>

        {/* Кол. 5: Последствия */}
        <div className="bt-col">
          {consequences.map((n, i) => (
            <Card key={n?.id ?? i} node={n} palette={PALETTE.consequence}
              dataId={`cons-${i}`}
              onHover={showTip} onLeave={() => setTooltip(null)} />
          ))}
        </div>
      </div>

      {tooltip && (
        <div className="bt-tooltip" style={{ left: tooltip.x + 14, top: tooltip.y - 48 }}>
          <div className="bt-tooltip-text">{tooltip.text}</div>
          {tooltip.conf != null && (
            <div className="bt-tooltip-conf">
              Уверенность: {(tooltip.conf * 100).toFixed(0)}%
              <span className="bt-tooltip-bar" style={{
                width: `${tooltip.conf * 100}%`,
                background: tooltip.conf > 0.6 ? '#34d399' : tooltip.conf > 0.3 ? '#facc15' : '#f87171',
              }} />
            </div>
          )}
        </div>
      )}

      <details className="bt-raw">
        <summary>▸ Список узлов</summary>
        <div className="bt-raw-grid">
          {[
            { label: 'Угрозы',              nodes: threats,      key: 'threat' },
            { label: 'Барьеры предотвр.',    nodes: prevention,   key: 'prevention' },
            { label: 'Топ-событие',          nodes: topEvents,    key: 'topEvent' },
            { label: 'Барьеры смягч.',       nodes: mitigation,   key: 'mitigation' },
            { label: 'Последствия',          nodes: consequences, key: 'consequence' },
          ].map(col => (
            <div key={col.label}>
              <div className="bt-raw-label" style={{ color: PALETTE[col.key].dot }}>{col.label}</div>
              {col.nodes.map((n, i) => (
                <div key={n?.id ?? i} className="bt-raw-node">
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

function Card({ node, palette, isCenter, isBarrier, isHazard, dataId, onHover, onLeave }) {
  const degraded = node?.confidence != null && node.confidence < 0.3
  return (
    <div
      data-bt={dataId}
      className={[
        'bt-card',
        isCenter  ? 'bt-card--center'   : '',
        isBarrier ? 'bt-card--barrier'  : '',
        isHazard  ? 'bt-card--hazard'   : '',
        degraded  ? 'bt-card--degraded' : '',
      ].filter(Boolean).join(' ')}
      style={{
        background:  palette.bg,
        borderColor: degraded ? 'rgba(248,113,113,0.5)' : palette.border,
      }}
      onMouseEnter={e => node && onHover(e, node)}
      onMouseLeave={onLeave}
    >
      {isBarrier && <div className="bt-card-shield" style={{ background: palette.dot }} />}
      <span className="bt-card-text" style={{ color: palette.text }}>{node?.text || ''}</span>
      {degraded && <span className="bt-card-degraded-mark" title="Низкая уверенность">⚠</span>}
    </div>
  )
}
