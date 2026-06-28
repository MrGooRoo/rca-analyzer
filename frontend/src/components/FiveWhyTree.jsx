/**
 * FiveWhyTree v2 — SVG визуализация дерева причин
 *
 * Исправления:
 *   - Линии идут от фактических краёв узлов (учёт динамической высоты)
 *   - Узлы не наезжают друг на друга (spacing >= реальная ширина)
 *   - Корректное соединение при разном количестве узлов в ярусах
 */
import React, { useMemo } from 'react'

const TIERS = [
  { key: 'problem',     label: 'Проблема / Инцидент',        color: '#8E8E93' },
  { key: 'immediate',   label: 'Непосредственные причины',   color: '#6366f1' },
  { key: 'contributing',label: 'Способствующие факторы',     color: '#f59e0b' },
  { key: 'root',        label: 'Корневые причины',           color: '#f43f5e' },
]

function useThemeColors() {
  if (typeof document === 'undefined') return { bg: '#000000', text: '#ffffff', spine: '#48484A' }
  const theme = document.documentElement.getAttribute('data-theme') || 'dark'
  const isDark = theme === 'dark'
  return {
    bg:    isDark ? '#1C1C1E' : '#FFFFFF',
    text:  isDark ? '#ffffff' : '#000000',
    spine: isDark ? '#48484A' : '#C6C6C8',
    muted: isDark ? '#8E8E93' : '#3C3C43',
    card:  isDark ? '#2C2C2E' : '#F2F2F7',
  }
}

/** Рассчитывает размеры узла по тексту */
function calcNodeDims(text, compact = false) {
  const pad = compact ? 6 : 10
  const fontSize = compact ? 11 : 12
  const lineH = compact ? 14 : 16
  const estWidth = Math.min(text.length * (fontSize * 0.55) + pad * 2, 200)
  const boxW = Math.max(estWidth, 120)
  const words = text.split(' ')
  const lines = []
  let cur = ''
  const maxChars = Math.floor((boxW - pad * 2) / (fontSize * 0.55))
  words.forEach(w => {
    if ((cur + ' ' + w).length > maxChars) { lines.push(cur); cur = w }
    else cur = cur ? cur + ' ' + w : w
  })
  if (cur) lines.push(cur)
  const textBlockH = lines.length * lineH
  const boxH = Math.max(compact ? 40 : 54, textBlockH + (compact ? 12 : 16))
  return { boxW, boxH, lines }
}

function NodeBox({ x, y, text, boxW, boxH, color, colors }) {
  const pad = 10
  return (
    <g>
      <rect
        x={x - boxW / 2} y={y - boxH / 2}
        width={boxW} height={boxH}
        rx="10"
        fill={colors.card}
        stroke={color}
        strokeWidth="1.5"
        strokeOpacity="0.4"
      />
      <rect
        x={x - boxW / 2} y={y - boxH / 2 + 4}
        width="3" height={boxH - 8}
        rx="1.5"
        fill={color}
      />
      <foreignObject x={x - boxW / 2 + pad} y={y - boxH / 2 + 6} width={boxW - pad * 2} height={boxH - 12}>
        <div style={{
          fontSize: '12px',
          lineHeight: '16px',
          color: colors.text,
          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
          fontWeight: 500,
        }}>
          {text}
        </div>
      </foreignObject>
    </g>
  )
}

export default function FiveWhyTree({ result }) {
  const colors = useThemeColors()

  const sections = useMemo(() => {
    const immed = (result.immediate_causes || []).map(n => ({ ...n, tier: 'immediate' }))
    const cont  = (result.contributing_causes || []).map(n => ({ ...n, tier: 'contributing' }))
    const root  = (result.root_causes || []).map(n => ({ ...n, tier: 'root' }))
    return { immed, cont, root, all: [...immed, ...cont, ...root] }
  }, [result])

  if (sections.all.length === 0) {
    return <div className="result-section-empty">Нет данных для дерева причин</div>
  }

  const W = 800
  const TIER_GAP = 100
  const PROBLEM_HEIGHT = 70
  const TIER_HEADER_H = 30

  // Рассчитываем размеры проблемного узла
  const probDims = calcNodeDims(result.summary || 'Инцидент', true)
  const problemNode = {
    x: W / 2,
    y: PROBLEM_HEIGHT - 20,
    text: result.summary || 'Инцидент',
    boxW: probDims.boxW,
    boxH: probDims.boxH,
    color: '#8E8E93',
  }

  /** Позиционирует узлы яруса с учётом их реальной ширины */
  function nodePositions(nodes, tierIndex) {
    if (nodes.length === 0) return []
    const y = PROBLEM_HEIGHT + TIER_GAP * (tierIndex + 1) + TIER_HEADER_H
    // Рассчитываем ширину каждого узла
    const withDims = nodes.map(n => {
      const d = calcNodeDims(n.text || '', false)
      return { ...n, ...d }
    })
    // Суммарная ширина всех узлов
    const totalW = withDims.reduce((sum, n) => sum + n.boxW, 0)
    // Минимальный зазор между узлами
    const gap = 24
    const fullW = totalW + gap * (nodes.length - 1)
    // Если не влезает — уменьшаем до ширины контейнера
    const maxW = W - 60
    const scale = fullW > maxW ? maxW / fullW : 1
    const adjustedGap = gap * scale
    const adjustedTotalW = totalW * scale + adjustedGap * (nodes.length - 1)
    const firstX = (W - adjustedTotalW) / 2
    let cursor = firstX
    return withDims.map((n, i) => {
      const boxW = n.boxW * scale
      const x = cursor + boxW / 2
      cursor += boxW + adjustedGap
      return { ...n, x, y, boxW, boxH: n.boxH }
    })
  }

  const immedNodes = nodePositions(sections.immed, 0)
  const contNodes  = nodePositions(sections.cont, 1)
  const rootNodes  = nodePositions(sections.root, 2)

  // Высота SVG: динамическая, чтобы вместить все ярусы + запасы
  const maxNodes = Math.max(immedNodes.length, contNodes.length, rootNodes.length)
  const maxBoxH = maxNodes > 0 ? Math.max(...[...immedNodes, ...contNodes, ...rootNodes].map(n => n.boxH)) : 80
  const H = PROBLEM_HEIGHT + TIER_GAP * 3 + TIER_HEADER_H * 3 + maxBoxH * 2 + 80

  /** Соединяет узлы от края parent → к краю child */
  function ConnLine({ from, to, color, key: lineKey }) {
    if (!from || !to) return null
    const x1 = from.x
    const y1 = from.y + from.boxH / 2          // низ parent
    const x2 = to.x
    const y2 = to.y - to.boxH / 2               // верх child
    return (
      <line
        key={lineKey}
        x1={x1} y1={y1}
        x2={x2} y2={y2}
        stroke={color} strokeWidth="1.5" strokeDasharray="4,3" opacity="0.5"
        markerEnd="url(#tree-arrow)"
      />
    )
  }

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: '100%', maxHeight: `${H}px`, background: 'transparent' }}
      role="img"
      aria-label="5 Why — дерево причин"
    >
      <defs>
        <marker id="tree-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill={colors.spine} />
        </marker>
      </defs>

      <rect x="0" y="0" width={W} height={H} fill={colors.bg} rx="12" opacity="0.95" />

      {/* Problem node */}
      <NodeBox {...problemNode} colors={colors} />

      {/* Immediate tier */}
      {sections.immed.length > 0 && (
        <>
          <text x={W / 2} y={PROBLEM_HEIGHT + 18}
            fill={TIERS[1].color}
            fontSize="11" fontFamily="-apple-system, BlinkMacSystemFont, sans-serif"
            fontWeight="600" textAnchor="middle" opacity="0.7">
            Почему? — {TIERS[1].label}
          </text>

          {/* problem → immediate */}
          {immedNodes.map(n => (
            <ConnLine key={`im-line-${n.id || n.text.slice(0, 10)}`}
              from={problemNode} to={n} color={TIERS[1].color} />
          ))}

          {immedNodes.map(n => <NodeBox key={n.id || n.text.slice(0, 10)} {...n} color={TIERS[1].color} colors={colors} />)}
        </>
      )}

      {/* Contributing tier */}
      {sections.cont.length > 0 && (
        <>
          <text x={W / 2} y={PROBLEM_HEIGHT + TIER_GAP + TIER_HEADER_H + 18}
            fill={TIERS[2].color}
            fontSize="11" fontFamily="-apple-system, BlinkMacSystemFont, sans-serif"
            fontWeight="600" textAnchor="middle" opacity="0.7">
            Почему? — {TIERS[2].label}
          </text>

          {immedNodes.length > 0
            ? contNodes.map((n, i) => {
                // Назначаем родителя пропорционально позиции: ближайший immediate
                const pct = i / Math.max(contNodes.length - 1, 1)
                const pIdx = Math.round(pct * (immedNodes.length - 1))
                const parent = immedNodes[Math.min(pIdx, immedNodes.length - 1)]
                return parent
                  ? <ConnLine key={`ct-line-${n.id || n.text.slice(0, 10)}`}
                      from={parent} to={n} color={TIERS[2].color} />
                  : null
              })
            : contNodes.map(n => (
                <ConnLine key={`ct-line-${n.id || n.text.slice(0, 10)}`}
                  from={problemNode} to={n} color={TIERS[2].color} />
              ))}

          {contNodes.map(n => <NodeBox key={n.id || n.text.slice(0, 10)} {...n} color={TIERS[2].color} colors={colors} />)}
        </>
      )}

      {/* Root causes tier */}
      {sections.root.length > 0 && (
        <>
          <text x={W / 2} y={PROBLEM_HEIGHT + TIER_GAP * 2 + TIER_HEADER_H * 2 + 18}
            fill={TIERS[3].color}
            fontSize="11" fontFamily="-apple-system, BlinkMacSystemFont, sans-serif"
            fontWeight="600" textAnchor="middle" opacity="0.7">
            Почему? — {TIERS[3].label}
          </text>

          {contNodes.length > 0
            ? rootNodes.map((n, i) => {
                const pct = i / Math.max(rootNodes.length - 1, 1)
                const pIdx = Math.round(pct * (contNodes.length - 1))
                const parent = contNodes[Math.min(pIdx, contNodes.length - 1)]
                return parent
                  ? <ConnLine key={`rt-line-${n.id || n.text.slice(0, 10)}`}
                      from={parent} to={n} color={TIERS[3].color} />
                  : null
              })
            : rootNodes.map(n => (
                <ConnLine key={`rt-line-${n.id || n.text.slice(0, 10)}`}
                  from={problemNode} to={n} color={TIERS[3].color} />
              ))}

          {rootNodes.map(n => <NodeBox key={n.id || n.text.slice(0, 10)} {...n} color={TIERS[3].color} colors={colors} />)}
        </>
      )}
    </svg>
  )
}
