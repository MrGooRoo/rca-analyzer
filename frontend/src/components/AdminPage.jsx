import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import './AdminPage.css'

const ROLE_LABELS = {
  admin: { label: 'Admin', color: '#f7b955', bg: 'rgba(247,185,85,0.12)' },
  user:  { label: 'User',  color: '#4f8ef7', bg: 'rgba(79,142,247,0.12)' },
}

export default function AdminPage({ currentUser }) {
  const [users, setUsers]       = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [busy, setBusy]         = useState(null) // user_id в процессе

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.admin.listUsers()
      setUsers(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function toggleRole(user) {
    const newRole = user.role === 'admin' ? 'user' : 'admin'
    const action = newRole === 'admin' ? 'назначить администратором' : 'снять права администратора'
    if (!confirm(`${action} для ${user.email}?`)) return

    setBusy(user.user_id)
    setError(null)
    try {
      await api.admin.setRole(user.user_id, newRole)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="admin">
      <div className="admin-toolbar">
        <h2 className="admin-title">👥 Управление пользователями</h2>
        <button className="btn-refresh" onClick={load} disabled={loading}>
          {loading ? '…' : '↻ Обновить'}
        </button>
      </div>

      {error && (
        <div className="admin-error">{error}</div>
      )}

      {!loading && !error && users.length === 0 && (
        <div className="admin-empty">Пользователей нет</div>
      )}

      <div className="admin-table-wrap">
        {users.length > 0 && (
          <table className="admin-table">
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Email</th>
                <th>Роль</th>
                <th>Статус</th>
                <th>Действие</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => {
                const r = ROLE_LABELS[u.role] || ROLE_LABELS.user
                const isSelf = u.user_id === currentUser.user_id
                return (
                  <tr key={u.user_id} className={isSelf ? 'admin-row--self' : ''}>
                    <td className="admin-cell-name">
                      {u.display_name}
                      {isSelf && <span className="admin-you">(вы)</span>}
                    </td>
                    <td className="admin-cell-email">{u.email}</td>
                    <td>
                      <span
                        className="admin-badge"
                        style={{ background: r.bg, color: r.color }}
                      >
                        {r.label}
                      </span>
                    </td>
                    <td>
                      <span className={`admin-status ${u.is_active ? 'admin-status--active' : 'admin-status--disabled'}`}>
                        {u.is_active ? 'Активен' : 'Отключён'}
                      </span>
                    </td>
                    <td>
                      {isSelf ? (
                        <span className="admin-no-action">—</span>
                      ) : (
                        <button
                          className={`admin-btn-role ${u.role === 'admin' ? 'admin-btn-role--demote' : 'admin-btn-role--promote'}`}
                          onClick={() => toggleRole(u)}
                          disabled={busy === u.user_id}
                        >
                          {busy === u.user_id
                            ? '…'
                            : u.role === 'admin'
                              ? '↓ Снять admin'
                              : '↑ Сделать admin'
                          }
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
