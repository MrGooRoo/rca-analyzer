import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api } from '../api.js'

const AuthContext = createContext(undefined)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const u = await api.auth.me()
      setUser(u)
    } catch {
      setUser(null)
    }
  }, [])

  useEffect(() => {
    ;(async () => {
      await refresh()
      setLoading(false)
    })()
  }, [refresh])

  const login = async (email, password) => {
    const u = await api.auth.login(email, password)
    setUser(u)
    return u
  }

  const register = async (email, name, password) => {
    const u = await api.auth.register(email, name, password)
    setUser(u)
    return u
  }

  const logout = async () => {
    try {
      await api.auth.logout()
    } finally {
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
