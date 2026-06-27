import React, { useRef } from 'react'
import { Button } from '../ui/Button.jsx'

function CardToggle(active, disabled) {
  return `incident-choice ${
    active ? 'incident-choice--active' : 'incident-choice--hoverable'
  } ${disabled ? 'is-disabled' : ''}`
}

export default function InputModeSelector({
  inputMode, uploadedFile, uploading, uploadMessage, uploadError, busy, dragOver,
  onModeChange, onFileSelect, onDrop, onDragOver, onDragLeave, onClear, fileInputRef,
}) {
  const localRef = useRef(null)
  const ref = fileInputRef || localRef

  return (
    <div className="incident-section">
      <div className="incident-input-mode-intro">
        <div className="incident-input-mode-kicker">Способ заполнения</div>
        <div className="incident-input-mode-help">Выберите, с чего начать ввод исходных данных</div>
      </div>
      <div className="incident-choice-grid" role="tablist" aria-label="Способ заполнения исходных данных">
        {/* Вручную */}
        <button key="manual" type="button" disabled={busy}
          className={CardToggle(inputMode === 'manual' && !uploadedFile, busy)}
          onClick={() => { onClear?.(); onModeChange?.('manual') }}
          aria-pressed={inputMode === 'manual' && !uploadedFile}>
          <div className="incident-choice__content">
            <span className="incident-choice__icon">⌨️</span>
            <div className="incident-choice__text-wrap">
              <div className="incident-choice__title">Вручную</div>
              <div className="incident-choice__text">Сразу заполнить поля формы самостоятельно.</div>
            </div>
          </div>
        </button>

        {/* DOCX загрузка */}
        <div key="docx"
          className={`incident-choice incident-upload-zone ${
            inputMode === 'docx' || uploadedFile ? 'incident-choice--active' : ''
          } ${
            inputMode === 'manual' && !uploadedFile ? 'incident-upload-zone--idle' : ''
          } ${
            dragOver ? 'incident-upload-zone--dragging' : ''
          } ${
            uploading ? 'incident-upload-zone--uploading' : ''
          } ${busy ? 'is-disabled' : ''}`}
          onDrop={onDrop} onDragOver={onDragOver} onDragLeave={onDragLeave}
          onClick={() => {
            if (busy || uploading) return
            if (!uploadedFile) onModeChange?.('docx')
            ref.current?.click()
          }}>
          <input ref={ref} type="file" accept=".docx" onChange={onFileSelect} className="incident-file-input" disabled={busy} />

          {uploading ? (
            <div className="incident-choice__content">
              <svg className="incident-spinner" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25"/><path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg>
              <div className="incident-choice__text-wrap">
                <div className="incident-choice__title">{uploadMessage}</div>
              </div>
            </div>
          ) : uploadedFile ? (
            <div className="incident-choice__content">
              <span className="incident-choice__icon">✅</span>
              <div className="incident-choice__text-wrap">
                <div className="incident-choice__title">Загружен: «{uploadedFile}»</div>
                <div className="incident-choice__text">Нажмите, чтобы заменить файл, или используйте ✕ для сброса</div>
                <Button type="button" variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); onClear?.() }} disabled={busy}>✕ Сбросить</Button>
              </div>
            </div>
          ) : (
            <div className="incident-choice__content">
              <svg className="incident-choice__upload-icon" width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3" y="18" width="22" height="7" rx="2" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                <path d="M14 2V17M14 2L8 8M14 2L20 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <div className="incident-choice__text-wrap">
                <div className="incident-choice__title">Из DOCX-отчёта</div>
                <div className="incident-choice__text">Нажмите или перетащите .docx сюда — найденные поля подставятся в форму.</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
