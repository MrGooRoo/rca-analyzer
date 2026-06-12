import { cn } from '../../utils/cn'
import './Card.css'

export function Card({ children, className }) {
  return <div className={cn('ui-card', className)}>{children}</div>
}

export function CardHeader({ children, className }) {
  return <div className={cn('ui-card__header', className)}>{children}</div>
}

export function CardBody({ children, className }) {
  return <div className={cn('ui-card__body', className)}>{children}</div>
}

/**
 * Badge — цветная метка.
 * tone: "slate" | "indigo" | "emerald" | "amber" | "rose" | "sky" | "violet"
 */
export function Badge({ children, tone = 'slate', className }) {
  return <span className={cn('ui-badge', `ui-badge--${tone}`, className)}>{children}</span>
}
