import api from './client'
import type { Product, Order, PaymentStatus, AccessCode, QuizGrant, QuizAttempt, Question, Answer, SavedAnswers, QuizResult } from '@/types'
export const productApi = {
  list: () => api.get<Product[]>('/products/'),
  get: (slug: string) => api.get<Product>(`/products/${encodeURIComponent(slug)}/`)
}
export const orderApi = {
  create: (slug: string, key: string, source = '') => api.post<Order>('/orders/', { product_slug: slug, source }, { headers: { 'X-Idempotency-Key': key } }),
  get: (id: string) => api.get<Order>(`/orders/${id}/`),
  checkPayment: (id: string) => api.post<PaymentStatus>(`/orders/${id}/check-payment/`),
  getPaymentQR: (id: string) => api.get<{ imageUrl?: string; codeUrl?: string; method: string }>(`/orders/${id}/payment-qr/`),
  claimAccess: (id: string) => api.post<AccessCode>(`/orders/${id}/claim/`),
  testAccess: (id: string) => api.post<{ grant: QuizGrant; code: string }>(`/orders/${id}/test-access/`),
  continue: (id: string) => api.post<{ url: string; expiresIn: number }>(`/orders/${id}/continue/`),
  exchange: (token: string) => api.post<{ orderId: string; canClaim: boolean }>('/continue/exchange/', { token })
}
export const accessApi = {
  verify: (code: string) => api.post<QuizGrant>('/access/verify/', { code }),
  getGrant: (id: string) => api.get<QuizGrant>(`/access/grants/${id}/`)
}
export const quizApi = {
  startAttempt: (id: string) => api.post<QuizAttempt>(`/quiz/grants/${id}/start/`),
  getAttempt: (id: string) => api.get<QuizAttempt>(`/quiz/attempts/${id}/`),
  getQuestions: (id: string) => api.get<Question[]>(`/quiz/attempts/${id}/questions/`),
  getAnswers: (id: string) => api.get<SavedAnswers>(`/quiz/attempts/${id}/answers/`),
  saveAnswer: (id: string, question: string, option: string, revision: number) => api.post<{ answer: Answer; revision: number }>(`/quiz/attempts/${id}/answers/`, { question_id: question, option_id: option, revision }),
  submit: (id: string, revision: number) => api.post<QuizAttempt>(`/quiz/attempts/${id}/submit/`, { revision })
}
export const resultApi = { get: (id: string) => api.get<QuizResult>(`/quiz/results/${id}/`) }
