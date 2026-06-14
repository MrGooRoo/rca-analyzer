import { cn } from '../../utils/cn'
import './Card.css'

export function Card({ children, className, ...rest }) {
  return <div className={cn('ui-card', className)} {...rest}>{children}</div>
}

export function CardHeader({ children, className, ...rest }) {
  return <div className={cn('ui-card__header', className)} {...rest}>{children}</div>
}

export function CardBody({ children, className, ...rest }) {
  return <div className={cn('ui-card__body', className)} {...rest}>{children}</div>
}

/**
 * Badge — цветная метка.
 * tone: "slate" | "indigo" | "emerald" | "amber" | "rose" | "sky" | "violet"
 */
export function Badge({ children, tone = 'slate', className }) {
  return <span className={cn('ui-badge', `ui-badge--${tone}`, className)}>{children}</span>
}
