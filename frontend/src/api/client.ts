import axios from 'axios'
import { shallowRef } from 'vue'
import type { SessionInfo } from '@/types'
export const sessionInfo = shallowRef<SessionInfo | null>(null)
const api = axios.create({ baseURL: '/api', timeout: 20000, withCredentials: true })
let bootstrap: Promise<SessionInfo> | null = null
export async function ensureSession(): Promise<SessionInfo> {
  if (sessionInfo.value) return sessionInfo.value
  if (!bootstrap) bootstrap = api.get<SessionInfo>('/session/').then(response => {
    sessionInfo.value = response.data
    return response.data
  }).finally(() => { bootstrap = null })
  return bootstrap
}
api.interceptors.request.use(async config => {
  if (!['get', 'head', 'options'].includes(config.method || 'get')) {
    const session = await ensureSession()
    config.headers.set('X-CSRFToken', session.csrfToken)
  }
  return config
})
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) return error.response?.data?.error || (error.code === 'ECONNABORTED' ? '网络超时，请重试。已保存的答案会保留。' : '连接失败，请检查网络后重试。')
  return error instanceof Error ? error.message : '操作失败，请重试。'
}
export default api
