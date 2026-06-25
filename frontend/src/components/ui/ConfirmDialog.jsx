import React from 'react'
import { AlertTriangle, Trash2 } from 'lucide-react'
import { Button } from './Button.jsx'
import './ConfirmDialog.css'

/**
 * Apple-style confirmation dialog for destructive actions.
 *
 * Usage:
 *   const [confirm, setConfirm] = useState(null)  // { message, action, label? }
 *   ...
 *   {confirm && (
 *     <ConfirmDialog
 *       message={confirm.message}
 *       label={confirm.label}
 *       onConfirm={() => { confirm.action(); setConfirm(null) }}
 *       onCancel={() => setConfirm(null)}
 *     />
 *   )}
 */
export default function ConfirmDialog({ message, label = 'Удалить', onConfirm, onCancel, icon = 'danger' }) {
  return (
    <div className="confirm-overlay" onClick={onCancel}>
      <div className="confirm-modal" onClick={e => e.stopPropagation()}>
        <div className="confirm-modal__icon">
          {icon === 'danger' ? <Trash2 size={24} /> : <AlertTriangle size={24} />}
        </div>
        <p className="confirm-modal__message">{message}</p>
        <div className="confirm-modal__actions">
          <Button variant="secondary" onClick={onCancel}>Отмена</Button>
          <Button variant="danger" onClick={onConfirm}>{label}</Button>
        </div>
      </div>
    </div>
  )
}
