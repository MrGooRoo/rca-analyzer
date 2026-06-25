import React, { useMemo } from 'react'

/**
 * 5 Why Tree — SVG визуализация дерева причин
 *
 * Layout:
 *   Vertical tree from top to bottom.
 *   Problem → Immediate Causes → Contributing Causes → Root Causes
 *   Each level is a colored tier with connecting lines.
 */

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

function NodeBox({ x, y, text, category, confidence, color, colors, compact }) {
  const pad = compact ? 6 : 10
  const fontSize = compact ? 11 : 12
  const lineH = compact ? 14 : 16
  const estWidth = Math.min(text.length * (fontSize * 0.55) + pad * 2, 200)
  const boxW = Math.max(estWidth, 120)
  const boxH = compact ? 40 : 54

  // Multi-line text wrapping approximation
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

  return (
    <g>
      {/* Card background */}
      <rect
        x={x - boxW / 2} y={y - boxH / 2}
        width={boxW} height={boxH}
        rx="10"
        fill={colors.card}
        stroke={color}
        strokeWidth="1.5"
        strokeOpacity="0.4"
      />
      {/* Left accent bar */}
      <rect
        x={x - boxW / 2} y={y - boxH / 2 + 4}
        width="3" height={boxH - 8}
        rx="1.5"
        fill={color}
      />
      {/* Text */}
      <foreignObject x={x - boxW / 2 + pad + 6} y={y - textBlockH / 2} width={boxW - pad * 2 - 6} height={textBlockH}>
        <div style={{
          fontSize: `${fontSize}px`,
          lineHeight: `${lineH}px`,
          color: colors.text,
          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
          fontWeight: 500,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: '-webkit-box',
          WebkitLineClamp: 3,
          WebkitBoxOrient: 'vertical',
        }}>
          {text}
        </div>
      </foreignObject>

      {/* Category + confidence footer */}
      {category && (
        <text
          x={x - boxW / 2 + pad + 6}
          y={y + boxH / 2 - 6}
          fill={color}
          fontSize="9"
          fontFamily="-apple-system, BlinkMacSystemFont, sans-serif"
          fontWeight="600"
          opacity="0.8"
        >
          {category}
        </text>
      )}
      <text
        x={x + boxW / 2 - pad}
        y={y + boxH / 2 - 6}
        fill={colors.muted}
        fontSize="9"
        fontFamily="-apple-system, BlinkMacSystemFont, sans-serif"
        textAnchor="end"
      >
        {confidence ? `${(confidence * 100).toFixed(0)}%` : ''}
      </text>
    </g>
  )
}

export default function FiveWhyTree({ result }) {
  const colors = useThemeColors()

  const sections = useMemo(() => {
    const immed = (result.immediate_causes || []).map(n => ({ ...n, tier: 'immediate' }))
    const cont  = (result.contributing_causes || []).map(n => ({ ...n, tier: 'contributing' }))
    const root  = (result.root_causes || []).map(n => ({ ...n, tier: 'root' }))
    const all = [...immed, ...cont, ...root]
    return { immed, cont, root, all }
  }, [result])

  if (sections.all.length === 0) {
    return <div className="result-section-empty">Нет данных для дерева причин</div>
  }

  const W = 800
  const TIER_GAP = 100
  const PROBLEM_HEIGHT = 70
  const NODE_HEIGHT = 54
  const NODE_GAP = 20
  const TIER_HEADER_H = 30

  // Calculate how many rows per tier
  const maxNodesPerTier = Math.max(
    sections.immed.length,
    sections.cont.length,
    sections.root.length,
    1
  )
  const gridW = Math.min(W - 40, 160 * maxNodesPerTier + (maxNodesPerTier - 1) * NODE_GAP)
  const startX = W / 2
  // Actually let's space nodes evenly per tier
  function nodePositions(nodes, tierIndex) {
    const y = PROBLEM_HEIGHT + TIER_GAP * (tierIndex + 1) + TIER_HEADER_H
    if (nodes.length === 0) return []
    const totalW = Math.min(W - 60, nodes.length * 180)
    const spacing = nodes.length > 1 ? totalW / (nodes.length - 1) : 0
    const firstX = (W - totalW) / 2
    return nodes.map((n, i) => ({
      ...n,
      x: nodes.length > 1 ? firstX + spacing * i : W / 2,
      y,
    }))
  }

  const problemNode = {
    x: W / 2,
    y: PROBLEM_HEIGHT - 20,
    text: result.summary,
    category: result.methodology,
    confidence: result.confidence_avg,
    color: '#8E8E93',
  }

  const immedNodes = nodePositions(sections.immed, 0)
  const contNodes  = nodePositions(sections.cont, 1)
  const rootNodes  = nodePositions(sections.root, 2)

  const H = PROBLEM_HEIGHT + TIER_GAP * 4 + TIER_HEADER_H * 3 + 60

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

      {/* Background */}
      <rect x="0" y="0" width={W} height={H} fill={colors.bg} rx="12" opacity="0.95" />

      {/* Problem node */}
      {NodeBox({
        ...problemNode,
        colors,
        compact: true,
      })}

      {/* Tier headers */}
      {/* Immediate header */}
      {sections.immed.length > 0 && (
        <text x={W / 2} y={PROBLEM_HEIGHT + 18} fill={TIERS[1].color} fontSize="11" fontFamily="-apple-system, BlinkMacSystemFont, sans-serif" fontWeight="600" textAnchor="middle" opacity="0.7">
          Почему? — {TIERS[1].label}
        </text>
      )}

      {/* Connecting lines: problem → immediate */}
      {sections.immed.length > 0 && immedNodes.map(n => (
        <line key={n.id || `im-${n.text.slice(0, 10)}`}
          x1={problemNode.x} y1={problemNode.y + 30}
          x2={n.x} y2={n.y - NODE_HEIGHT / 2}
          stroke={TIERS[1].color} strokeWidth="1.5" strokeDasharray="4,3" opacity="0.5"
          markerEnd="url(#tree-arrow)"
        />
      ))}

      {immedNodes.map(n => NodeBox({ ...n, color: TIERS[1].color, colors }))}

      {/* Contributing header + lines */}
      {sections.cont.length > 0 && (
        <>
          <text x={W / 2} y={PROBLEM_HEIGHT + TIER_GAP + TIER_HEADER_H + 18} fill={TIERS[2].color} fontSize="11" fontFamily="-apple-system, BlinkMacSystemFont, sans-serif" fontWeight="600" textAnchor="middle" opacity="0.7">
            Почему? — {TIERS[2].label}
          </text>
          {sections.cont.length > 0 && sections.immed.length > 0 ? (
            // Connect each contributing to closest immediate
            contNodes.map((n, i) => {
              const parent = immedNodes[Math.min(i, immedNodes.length - 1)] || immedNodes[0]
              return (
                <line key={n.id || `ct-${n.text.slice(0, 10)}`}
                  x1={parent.x} y1={parent.y + NODE_HEIGHT / 2}
                  x2={n.x} y2={n.y - NODE_HEIGHT / 2}
                  stroke={TIERS[2].color} strokeWidth="1.5" strokeDasharray="4,3" opacity="0.5"
                  markerEnd="url(#tree-arrow)"
                />
              )
            })
          ) : sections.cont.length > 0 ? (
            // Connect from problem when no immediate
            contNodes.map(n => (
              <line key={n.id || `ct-${n.text.slice(0, 10)}`}
                x1={problemNode.x} y1={problemNode.y + 30}
                x2={n.x} y2={n.y - NODE_HEIGHT / 2}
                stroke={TIERS[2].color} strokeWidth="1.5" strokeDasharray="4,3" opacity="0.5"
                markerEnd="url(#tree-arrow)"
              />
            ))
          ) : null}
          {contNodes.map(n => NodeBox({ ...n, color: TIERS[2].color, colors }))}
        </>
      )}

      {/* Root causes header + lines */}
      {sections.root.length > 0 && (
        <>
          <text x={W / 2} y={PROBLEM_HEIGHT + TIER_GAP * 2 + TIER_HEADER_H * 2 + 18} fill={TIERS[3].color} fontSize="11" fontFamily="-apple-system, BlinkMacSystemFont, sans-serif" fontWeight="600" textAnchor="middle" opacity="0.7">
            Почему? — {TIERS[3].label}
          </text>
          {sections.root.length > 0 && sections.cont.length > 0 ? (
            rootNodes.map((n, i) => {
              const parent = contNodes[Math.min(i, contNodes.length - 1)] || contNodes[0]
              if (!parent) return null
              return (
                <line key={n.id || `rt-${n.text.slice(0, 10)}`}
                  x1={parent.x} y1={parent.y + NODE_HEIGHT / 2}
                  x2={n.x} y2={n.y - NODE_HEIGHT / 2}
                  stroke={TIERS[3].color} strokeWidth="1.5" strokeDasharray="4,3" opacity="0.5"
                  markerEnd="url(#tree-arrow)"
                />
              )
            })
          ) : sections.root.length > 0 ? (
            rootNodes.map(n => (
              <line key={n.id || `rt-${n.text.slice(0, 10)}`}
                x1={problemNode.x} y1={problemNode.y + 30}
                x2={n.x} y2={n.y - NODE_HEIGHT / 2}
                stroke={TIERS[3].color} strokeWidth="1.5" strokeDasharray="4,3" opacity="0.5"
                markerEnd="url(#tree-arrow)"
              />
            ))
          ) : null}
          {rootNodes.map(n => NodeBox({ ...n, color: TIERS[3].color, colors }))}
        </>
      )}
    </svg>
  )
}
