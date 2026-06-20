import { cn } from '../../utils/cn'

const variantClasses = {
  primary:
    'bg-gradient-to-r from-indigo-500 to-violet-600 text-white shadow-lg shadow-indigo-900/40 hover:from-indigo-400 hover:to-violet-500 active:scale-[0.98]',
  secondary:
    'bg-slate-800 text-slate-100 ring-1 ring-slate-700 hover:bg-slate-700 hover:ring-slate-600',
  ghost:
    'bg-transparent text-slate-300 hover:bg-slate-800/60 hover:text-white',
  danger:
    'bg-rose-600 text-white hover:bg-rose-500 active:scale-[0.98]',
  outline:
    'bg-transparent text-slate-200 ring-1 ring-slate-600 hover:ring-indigo-400 hover:text-white',
}

const sizeClasses = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
  lg: 'h-12 px-6 text-base gap-2',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  leftIcon,
  rightIcon,
  children,
  className,
  disabled,
  ...rest
}) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-xl font-semibold transition-all duration-150',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && (
        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
      )}
      {!loading && leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  )
}
