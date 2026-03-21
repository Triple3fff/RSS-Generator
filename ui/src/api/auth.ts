import { apiFetch } from './client'

export const authApi = {
  login: (username: string, password: string) => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    return fetch('/api/auth/login', {
      method: 'POST',
      body: form,
    }).then(async res => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? 'Login failed')
      }
      return res.json() as Promise<{ access_token: string; token_type: string }>
    })
  },

  me: () => apiFetch<{ username: string }>('/auth/me'),

  changeCredentials: (data: {
    current_password: string
    new_username?: string
    new_password?: string
  }) =>
    apiFetch<{ access_token: string }>('/auth/credentials', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
}
