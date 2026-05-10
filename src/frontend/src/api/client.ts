import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  timeout: 600_000, // 解析/索引可能很慢
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg = err?.response?.data?.detail || err?.message || '请求失败'
    console.error('[API]', msg, err)
    return Promise.reject(new Error(msg))
  }
)
