import { cn } from '../../utils/cn'

const baseInput =
  'w-full rounded-xl bg-slate-950/60 ring-1 ring-slate-700 px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-400/60 focus:bg-slate-950/80'

export function FieldWrapper({ label, hint, required, error, children, className }) {
  return (
    <div className={cn('block', className)}>
      {label && (
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-sm font-medium text-slate-200">
            {label}
            {required && <span className="ml-1 text-rose-400">*</span>}
          </span>
          {hint && !error && <span className="text-xs text-slate-500">{hint}</span>}
        </div>
      )}
      {children}
      {error && (
        <div className="mt-1 text-xs text-rose-400">{error}</div>
      )}
    </div>
  )
}

export function Input(props) {
  const { label, hint, error, required, className, ...rest } = props
  return (
    <FieldWrapper label={label} hint={hint} error={error} required={required}>
      <input className={cn(baseInput, className)} {...rest} />
    </FieldWrapper>
  )
}

export function Textarea(props) {
  const { label, hint, error, required, className, ...rest } = props
  return (
    <FieldWrapper label={label} hint={hint} error={error} required={required}>
      <textarea className={cn(baseInput, 'min-h-[110px] resize-y leading-relaxed', className)} {...rest} />
    </FieldWrapper>
  )
}

export function Select(props) {
  const { label, hint, error, required, className, children, ...rest } = props
  return (
    <FieldWrapper label={label} hint={hint} error={error} required={required}>
      <select className={cn(baseInput, 'pr-8 appearance-none', className)} {...rest}>
        {children}
      </select>
    </FieldWrapper>
  )
}
