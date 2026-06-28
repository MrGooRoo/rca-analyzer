import React, { useRef, useEffect } from 'react'
import { cn } from '../../utils/cn'
import './Field.css'

/**
 * Обёртка поля с label, hint, error.
 */
export function FieldWrapper({ label, hint, required, error, children, className }) {
  return (
    <div className={cn('ui-field', className)}>
      {label && (
        <label className="ui-field__label">
          {label} {required && <span className="ui-field__required">*</span>}
        </label>
      )}
      {children}
      {error ? (
        <div className="ui-field__error">{error}</div>
      ) : hint ? (
        <div className="ui-field__hint">{hint}</div>
      ) : null}
    </div>
  )
}

/**
 * Input — текстовое поле.
 */
export function Input(props) {
  const { label, hint, error, required, className, ...rest } = props
  return (
    <FieldWrapper label={label} hint={hint} error={error} required={required}>
      <input className={cn('ui-input', className)} {...rest} />
    </FieldWrapper>
  )
}

/**
 * Textarea — многострочное поле.
 */
export function Textarea(props) {
  const { label, hint, error, required, className, ...rest } = props
  const textareaRef = useRef(null)

  const resize = () => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = el.scrollHeight + 2 + 'px'
    }
  }

  useEffect(() => { resize() }, [rest.value])

  return (
    <FieldWrapper label={label} hint={hint} error={error} required={required}>
      <textarea
        ref={textareaRef}
        className={cn('ui-textarea', className)}
        onInput={resize}
        {...rest}
      />
    </FieldWrapper>
  )
}

/**
 * Select — выпадающий список.
 */
export function Select(props) {
  const { label, hint, error, required, className, children, ...rest } = props
  return (
    <FieldWrapper label={label} hint={hint} error={error} required={required}>
      <select className={cn('ui-select', className)} {...rest}>{children}</select>
    </FieldWrapper>
  )
}
