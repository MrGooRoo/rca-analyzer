import { cn } from '../../utils/cn'
import './Button.css'

/**
 * Кнопка с вариантами стиля.
 * variant: "primary" | "secondary" | "ghost" | "danger" | "outline"
 * size: "sm" | "md" | "lg"
 * loading: показывать спиннер
 */
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
        'ui-btn',
        `ui-btn--${variant}`,
        `ui-btn--${size}`,
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <span className="ui-btn__spinner" /> : leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  )
}
