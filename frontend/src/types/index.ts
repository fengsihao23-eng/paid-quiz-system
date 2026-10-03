export interface SessionInfo { csrfToken: string; testMode: boolean; paymentMode: 'manual' | 'wechat'; paymentQR: string }
export interface Product { slug: string; title: string; description: string; questionCount: number; estimatedMinutes: string; price: number; currency: string; status: string; currentVersion: string; canPurchase: boolean; testMode: boolean; contentPreview: boolean }
export interface Order { id: string; productSlug: string; productTitle: string; amount: number; currency: string; status: 'pending' | 'paid' | 'testing' | 'expired' | 'refunded'; createdAt: string; expiresAt: string; paidAt: string | null; isTest: boolean; refundState: string; contentVersion: string }
export interface QuizGrant { id: string; productSlug: string; productTitle: string; productVersion: string; questionCount: number; estimatedMinutes: string; status: string; attemptId: string | null; attemptStatus: 'not_started' | 'in_progress' | 'submitted'; isTest: boolean }
export interface AccessCode { code: string; orderId: string; productSlug: string; productTitle: string; grantId: string; isTest: boolean }
export interface Question { id: string; sequence: number; dimension: string; dimensionName: string; text: string; options: { id: string; sequence: number; text: string }[] }
export interface QuizAttempt { id: string; grantId: string; productSlug: string; totalQuestions: number; answeredCount: number; status: 'in_progress' | 'submitted'; currentQuestion: number; revision: number; submittedAt: string | null; isTest: boolean }
export interface Answer { questionId: string; optionId: string; savedAt: string }
export interface SavedAnswers { answers: Answer[]; revision: number }
export interface ResultMeta { attemptId: string; generatedAt: string; isTest: boolean; contentPreview: boolean; contentVersion: string; scoringHash: string }
export interface CityCandidate { cityCode: string; cityName: string; score: number; emoji?: string; tags?: string[]; matchReasons?: string[] }
export interface CityResult extends ResultMeta { type: 'city'; bestMatch: CityCandidate; matchIndex: number; topCandidates: CityCandidate[]; dimensions: { key: string; name: string; score: number; description: string; preference: string }[] }
export interface MentalAgeResult extends ResultMeta { type: 'mental-age'; mentalAge: number; typeName: string; typeDescription: string; insights: string[]; totalScore: number }
export type QuizResult = CityResult | MentalAgeResult
export interface PaymentStatus { orderId: string; status: Order['status']; canClaim: boolean; message: string }
