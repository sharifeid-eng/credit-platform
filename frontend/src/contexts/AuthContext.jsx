import { createContext, useContext, useState, useEffect } from 'react'
import api from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // On mount, check if user is authenticated via Cloudflare
    api.get('/auth/me')
      .then(r => setUser(r.data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const logout = async () => {
    try {
      const r = await api.get('/auth/logout-url')
      window.location.href = r.data.url
    } catch {
      window.location.href = '/'
    }
  }

  const refreshUser = async () => {
    try {
      const r = await api.get('/auth/me')
      setUser(r.data)
    } catch {
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      isAdmin: user?.role === 'admin',
      logout,
      refreshUser,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
