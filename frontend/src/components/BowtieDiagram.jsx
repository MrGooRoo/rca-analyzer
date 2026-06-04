/**
 * BowtieDiagram — Apple-style glass UI.
 *
 * Архитектура DOM:
 *   .bt-shell
 *     .bt-legend
 *     .bt-outer          ← position:relative, overflow:visible
 *       .bt-diagram      ← grid (5 колонок), z-index:1
 *       svg.bt-svg-layer ← position:absolute, inset:0, z-index:2, pointer-events:none
 *     .bt-raw
 *
 * SVG позиционируется относительно .bt-outer, а не внутри grid —
 * поэтому линии не попадают в grid-ячейку.
 */

import React, { useRef, useCallback, useState, useEffect } from 'react'
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

  if (!threats.length)      threats      = result.root_causes      || []
  if (!consequences.length) consequences = (result.immediate_causes || []).slice(1)
  if (!topEvents.length)    topEvents    = (result.immediate_causes || []).slice(0, 1)
  if (!prevention.length || !mitigation.length) {
    const contrib = result.contributing_causes || []
    if (!prevention.length) prevention = contrib.filter((_, i) => i % 2 === 0)
    if (!mitigation.length) mitigation = contrib.filter((_, i) => i % 2 !== 0)
  }

  return { hazards, topEvents, threats, prevention, consequences, mitigation }
}

function bezier(x1, y1, x2, y2) {
  const dx = Math.abs(x2 - x1) * 0.5
  return `M${x1} ${y1} C${x1+dx} ${y1} ${x2-dx} ${y2} ${x2} ${y2}`
}

export default function BowtieDiagram({ result }) {
  const { hazards, topEvents, threats, prevention, consequences, mitigation } = parseBowtieData(result)
  const topEvent = topEvents[0]
  const hazard   = hazards[0]

  // outerRef — относительно него считается SVG
  const outerRef  = useRef(null)
  const [paths,   setPaths]   = useState([])
  const [svgSize, setSvgSize] = useState({ w: 0, h: 0 })
  const [tooltip, setTooltip] = useState(null)

  const recalc = useCallback(() => {
    const outer = outerRef.current
    if (!outer) return
    const oRect = outer.getBoundingClientRect()
    if (oRect.width === 0) return

    setSvgSize({ w: oRect.width, h: oRect.height })

    function mid(el, side) {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return {
        x: (side === 'right' ? r.right : r.left) - oRect.left,
        y: r.top + r.height / 2 - oRect.top,
      }
    }

    const topEl = outer.querySelector('[data-bt="top"]')
    if (!topEl) return
    const topL = mid(topEl, 'left')
    const topR = mid(topEl, 'right')

    const np = []

    // Левая: угроза → барьер → центр
    threats.forEach((_, i) => {
      const tEl = outer.querySelector(`[data-bt="threat-${i}"]`)
      if (!tEl) return
      const tR  = mid(tEl, 'right')
      // каждой угрозе ищем свой барьер, иначе берём первый
      const pEl = outer.querySelector(`[data-bt="prev-${i}"]`) ||
                  outer.querySelector('[data-bt^="prev-"]')
      if (pEl) {
        const pL = mid(pEl, 'left'), pR = mid(pEl, 'right')
        if (tR && pL)   np.push({ d: bezier(tR.x,tR.y, pL.x,pL.y), side:'L' })
        if (pR && topL) np.push({ d: bezier(pR.x,pR.y, topL.x,topL.y), side:'L' })
      } else {
        if (tR && topL) np.push({ d: bezier(tR.x,tR.y, topL.x,topL.y), side:'L' })
      }
    })

    // Правая: центр → барьер → последствие
    consequences.forEach((_, i) => {
      const cEl = outer.querySelector(`[data-bt="cons-${i}"]`)
      if (!cEl) return
      const cL  = mid(cEl, 'left')
      const mEl = outer.querySelector(`[data-bt="miti-${i}"]`) ||
                  outer.querySelector('[data-bt^="miti-"]')
      if (mEl) {
        const mL = mid(mEl, 'left'), mR = mid(mEl, 'right')
        if (topR && mL) np.push({ d: bezier(topR.x,topR.y, mL.x,mL.y), side:'R' })
        if (mR && cL)   np.push({ d: bezier(mR.x,mR.y, cL.x,cL.y), side:'R' })
      } else {
        if (topR && cL) np.push({ d: bezier(topR.x,topR.y, cL.x,cL.y), side:'R' })
      }
    })

    setPaths(np)
  }, [threats.length, prevention.length, consequences.length, mitigation.length])

  useEffect(() => {
    // double-rAF: grid settled → paint → замер
    let r1, r2
    r1 = requestAnimationFrame(() => { r2 = requestAnimationFrame(recalc) })
    const ro = new ResizeObserver(recalc)
    if (outerRef.current) ro.observe(outerRef.current)
    return () => { cancelAnimationFrame(r1); cancelAnimationFrame(r2); ro.disconnect() }
  }, [recalc])

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

      {/* outer: position:relative — относительно него позиционируется SVG */}
      <div className="bt-outer" ref={outerRef}>

        <div className="bt-diagram">
          {/* Кол. 1: Угрозы */}
          <div className="bt-col">
            {hazard && (
              <Card node={hazard} palette={PALETTE.hazard} isHazard
                onHover={setTooltip} onLeave={() => setTooltip(null)} />
            )}
            {threats.map((n, i) => (
              <Card key={n?.id ?? i} node={n} palette={PALETTE.threat}
                dataId={`threat-${i}`}
                onHover={setTooltip} onLeave={() => setTooltip(null)} />
            ))}
          </div>

          {/* Кол. 2: Барьеры предотвр. */}
          <div className="bt-col bt-col--barriers">
            {prevention.map((n, i) => (
              <Card key={n?.id ?? i} node={n} palette={PALETTE.prevention} isBarrier
                dataId={`prev-${i}`}
                onHover={setTooltip} onLeave={() => setTooltip(null)} />
            ))}
          </div>

          {/* Кол. 3: Топ-событие */}
          <div className="bt-col bt-col--center">
            <Card
              node={topEvent || { text: 'Топ-событие', confidence: 1 }}
              palette={PALETTE.topEvent} isCenter dataId="top"
              onHover={setTooltip} onLeave={() => setTooltip(null)}
            />
          </div>

          {/* Кол. 4: Барьеры смягч. */}
          <div className="bt-col bt-col--barriers">
            {mitigation.map((n, i) => (
              <Card key={n?.id ?? i} node={n} palette={PALETTE.mitigation} isBarrier
                dataId={`miti-${i}`}
                onHover={setTooltip} onLeave={() => setTooltip(null)} />
            ))}
          </div>

          {/* Кол. 5: Последствия */}
          <div className="bt-col">
            {consequences.map((n, i) => (
              <Card key={n?.id ?? i} node={n} palette={PALETTE.consequence}
                dataId={`cons-${i}`}
                onHover={setTooltip} onLeave={() => setTooltip(null)} />
            ))}
          </div>
        </div>

        {/* SVG поверх grid, позиционируется относительно .bt-outer */}
        <svg
          className="bt-svg-layer"
          aria-hidden="true"
          width={svgSize.w}
          height={svgSize.h}
        >
          <defs>
            <filter id="bt-glow-l" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="bt-glow-r" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          {paths.map((p, i) => (
            <path key={i} d={p.d} fill="none"
              stroke={p.side==='L' ? 'rgba(160,180,255,0.45)' : 'rgba(80,220,170,0.45)'}
              strokeWidth={2}
              filter={`url(#bt-glow-${p.side==='L'?'l':'r'})`}
            />
          ))}
        </svg>
      </div>

      {tooltip && (
        <div className="bt-tooltip"
          style={{ left: tooltip.x + 14, top: tooltip.y - 48 }}>
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
            { label: 'Угрозы',           nodes: threats,      key: 'threat' },
            { label: 'Барьеры предотвр.', nodes: prevention,   key: 'prevention' },
            { label: 'Топ-событие',     nodes: topEvents,    key: 'topEvent' },
            { label: 'Барьеры смягч.',    nodes: mitigation,   key: 'mitigation' },
            { label: 'Последствия',     nodes: consequences, key: 'consequence' },
          ].map(col => (
            <div key={col.label}>
              <div className="bt-raw-label" style={{ color: PALETTE[col.key].dot }}>{col.label}</div>
              {col.nodes.map((n, i) => (
                <div key={n?.id ?? i} className="bt-raw-node">
                  <span>{n?.text}</span>
                  <span className="bt-raw-conf">{n ? (n.confidence*100).toFixed(0)+'%' : ''}</span>
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
        isCenter  ? 'bt-card--center'  : '',
        isBarrier ? 'bt-card--barrier' : '',
        isHazard  ? 'bt-card--hazard'  : '',
        degraded  ? 'bt-card--degraded': '',
      ].filter(Boolean).join(' ')}
      style={{
        background:  palette.bg,
        borderColor: degraded ? 'rgba(248,113,113,0.5)' : palette.border,
      }}
      onMouseEnter={e => node && onHover({ text: node.text, conf: node.confidence, x: e.clientX, y: e.clientY })}
      onMouseLeave={onLeave}
    >
      {isBarrier && <div className="bt-card-shield" style={{ background: palette.dot }} />}
      <span className="bt-card-text" style={{ color: palette.text }}>
        {node?.text || ''}
        {degraded && <span className="bt-card-degraded-mark" title="Низкая уверенность"> ⚠</span>}
      </span>
    </div>
  )
}
