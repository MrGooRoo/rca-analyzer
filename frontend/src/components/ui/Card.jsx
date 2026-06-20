import { cn } from '../../utils/cn'

export function Card({ children, className, ...rest }) {
  return (
    <div
      className={cn(
        'rounded-2xl bg-slate-900/60 ring-1 ring-slate-800 backdrop-blur-sm shadow-xl shadow-black/20',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className, ...rest }) {
  return (
    <div className={cn('px-6 py-5 border-b border-slate-800', className)} {...rest}>
      {children}
    </div>
  )
}

export function CardBody({ children, className, ...rest }) {
  return (
    <div className={cn('px-6 py-5', className)} {...rest}>
      {children}
    </div>
  )
}

export function CardFooter({ children, className, ...rest }) {
  return (
    <div className={cn('px-6 py-4 border-t border-slate-800', className)} {...rest}>
      {children}
    </div>
  )
}

const toneMap = {
  sky: 'bg-sky-500/15 text-sky-300 ring-sky-500/30',
  rose: 'bg-rose-500/15 text-rose-300 ring-rose-500/30',
  emerald: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  amber: 'bg-amber-500/15 text-amber-300 ring-amber-500/30',
  violet: 'bg-violet-500/15 text-violet-300 ring-violet-500/30',
  slate: 'bg-slate-500/15 text-slate-300 ring-slate-500/30',
  indigo: 'bg-indigo-500/15 text-indigo-300 ring-indigo-500/30',
}

export function Badge({ children, tone = 'slate', className }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        toneMap[tone] ?? toneMap.slate,
        className,
      )}
    >
      {children}
    </span>
  )
}
