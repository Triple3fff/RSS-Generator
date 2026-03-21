import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { getToken, setToken, clearToken } from '../api/client'
import { authApi } from '../api/auth'

interface AuthContextValue {
  username: string | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = getToken()
    if (!token) { setIsLoading(false); return }
    authApi.me()
      .then(data => setUsername(data.username))
      .catch(() => clearToken())
      .finally(() => setIsLoading(false))
  }, [])

  const login = async (u: string, p: string) => {
    const res = await authApi.login(u, p)
    setToken(res.access_token)
    setUsername(u)
  }

  const logout = () => {
    clearToken()
    setUsername(null)
    window.location.href = '/login'
  }

  return (
    <AuthContext.Provider value={{ username, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
