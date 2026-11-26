import { ref } from 'vue'
import { toast } from './toast'

export interface SessionUser {
  id: string
  phone: string
  nickname: string
  avatar: string
}
const user = ref<SessionUser | null>(null)
const loading = ref(true)
let initialized = false

export function useSession() {
  async function restore() {
    if (initialized) return
    initialized = true
    try { localStorage.removeItem('skill-plaza:user') } catch { /* storage may be disabled */ }
    const url = new URL(location.href)
    if (url.searchParams.has('login_error')) {
      url.searchParams.delete('login_error')
      history.replaceState(history.state, '', url.pathname + url.search + url.hash)
      toast('登录未成功，请重试')
    }
    try {
      const response = await fetch('/api/auth/me', { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(20_000) })
      if (response.status === 401) { user.value = null; return }
      if (!response.ok) throw new Error()
      const data = await response.json()
      user.value = data.user
    } catch { toast('暂时无法获取用户信息，请稍后刷新') }
    finally { loading.value = false }
  }
  function openLogin() {
    const params = new URLSearchParams({ origin: location.origin, returnTo: location.pathname + location.search + location.hash })
    location.assign(`/api/auth/login?${params}`)
  }
  async function logout() {
    try {
      const response = await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin', signal: AbortSignal.timeout(20_000), headers: { 'X-Plaza-Auth': '1' } })
      if (!response.ok) throw new Error()
      const data = await response.json()
      user.value = null
      location.assign(data.url)
    } catch { toast('退出未成功，请重试') }
  }
  return { user, loading, restore, openLogin, logout }
}
