import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

interface AuthContextValue {
  token: string | null
  isAuthenticated: boolean
  setToken: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  // Sourced straight from localStorage on first render — the axios
  // interceptor (api/client.ts) reads the same key independently, so
  // this context is only for React's own render tree to know whether
  // to show the app shell or redirect to /login, not the source of
  // truth for what gets sent on the wire.
  const [token, setTokenState] = useState<string | null>(() => localStorage.getItem('token'))

  const setToken = useCallback((newToken: string) => {
    localStorage.setItem('token', newToken)
    setTokenState(newToken)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    setTokenState(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, isAuthenticated: !!token, setToken, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
