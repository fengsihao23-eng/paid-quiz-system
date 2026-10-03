import { createRouter, createWebHistory } from 'vue-router'
const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', component: () => import('@/pages/HomePage.vue') },
  { path: '/p/:slug', component: () => import('@/pages/ProductPage.vue') },
  { path: '/checkout/:orderId', component: () => import('@/pages/CheckoutPage.vue') },
  { path: '/claim/:orderId', component: () => import('@/pages/ClaimPage.vue') },
  { path: '/access', component: () => import('@/pages/AccessPage.vue') },
  { path: '/continue', component: () => import('@/pages/ContinuePage.vue') },
  { path: '/quiz/:grantId/intro', component: () => import('@/pages/QuizIntroPage.vue') },
  { path: '/quiz/:attemptId', component: () => import('@/pages/QuizPage.vue') },
  { path: '/result/:attemptId', component: () => import('@/pages/ResultPage.vue') },
  { path: '/help', component: () => import('@/pages/HelpPage.vue') },
  { path: '/terms', component: () => import('@/pages/TermsPage.vue') },
  { path: '/privacy', component: () => import('@/pages/PrivacyPage.vue') },
  { path: '/:pathMatch(.*)*', component: () => import('@/pages/NotFoundPage.vue') }
], scrollBehavior(_to, _from, saved) { return saved || { top: 0 } } })
export default router
