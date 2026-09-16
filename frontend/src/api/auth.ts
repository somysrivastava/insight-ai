import { apiClient } from './client'
import type { TokenResponse } from '../types/api'

export async function signup(email: string, password: string): Promise<{ message: string; user_id: number }> {
  const { data } = await apiClient.post('/auth/signup', { email, password })
  return data
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  // /auth/login is an OAuth2PasswordRequestForm endpoint — form-encoded
  // fields named "username"/"password", not JSON, and not "email"
  // despite what's actually being sent being an email address.
  const body = new URLSearchParams()
  body.set('username', email)
  body.set('password', password)

  const { data } = await apiClient.post('/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}
