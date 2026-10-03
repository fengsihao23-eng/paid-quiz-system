<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QRCode from 'qrcode'
import { orderApi } from '@/api'
import { errorMessage, sessionInfo } from '@/api/client'
import { formatPrice, rememberCode, copyToClipboard } from '@/utils/helpers'
import type { Order } from '@/types'
const route = useRoute(), router = useRouter(), id = String(route.params.orderId)
const order = ref<Order | null>(null), loading = ref(true), busy = ref(false), error = ref(''), note = ref(''), qr = ref(''), remaining = ref('')
let timer: ReturnType<typeof setInterval> | undefined
let paymentTimer: ReturnType<typeof setInterval> | undefined
let polling = false
function countdown() { if (!order.value) return; const seconds = Math.max(0, Math.floor((new Date(order.value.expiresAt).getTime() - Date.now()) / 1000)); remaining.value = seconds ? `${Math.floor(seconds / 60)}分${seconds % 60}秒` : '已过期' }
async function load() { loading.value = true; error.value = ''; try { order.value = (await orderApi.get(id)).data; countdown(); if (order.value.status === 'pending') { const payment = (await orderApi.getPaymentQR(id)).data; qr.value = payment.imageUrl || (payment.codeUrl ? await QRCode.toDataURL(payment.codeUrl, { width: 360, margin: 3 }) : '') } } catch(e) { error.value = errorMessage(e) } finally { loading.value = false } }
async function freeStart() { if (busy.value) return; busy.value = true; error.value = ''; try { const data = (await orderApi.testAccess(id)).data; rememberCode(data.grant.id, data.code); await router.push(`/quiz/${data.grant.id}/intro`) } catch(e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function check() { if (busy.value) return; busy.value = true; error.value = ''; try { const data = (await orderApi.checkPayment(id)).data; if (data.canClaim) await router.push(`/claim/${id}`); else { note.value = sessionInfo.value?.paymentMode === 'manual' ? '尚未收到人工确认。请联系提供测评链接的人，并附订单号与付款凭证。' : data.message; order.value = (await orderApi.get(id)).data } } catch(e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function copyContinue() { if (busy.value) return; busy.value = true; error.value = ''; try { const ticket = (await orderApi.continue(id)).data; await copyToClipboard(ticket.url); note.value = '继续链接已复制，仅可使用一次，5 分钟内有效。请勿公开分享。' } catch(e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function copyOrder() { try { await copyToClipboard(id); note.value = '订单号已复制，请与付款凭证一起发送给商家。' } catch(e) { error.value = errorMessage(e) } }
async function pollPayment() {
  if (polling || busy.value || !order.value || order.value.isTest || !['pending', 'expired'].includes(order.value.status)) return
  polling = true
  try {
    order.value = (await orderApi.get(id)).data
    countdown()
    if (order.value.status === 'paid' && !['pending', 'success'].includes(order.value.refundState)) await router.replace(`/claim/${id}`)
  } catch { /* 保留当前页面，用户仍可手动查询。 */ }
  finally { polling = false }
}
onMounted(() => { load(); timer = setInterval(countdown, 1000); paymentTimer = setInterval(pollPayment, 10000) })
onUnmounted(() => { clearInterval(timer); clearInterval(paymentTimer) })
</script>
<template><div class="container page"><router-link class="back-link" to="/">← 返回首页</router-link><div v-if="loading" class="center"><span class="loading"></span></div><article v-else-if="order" class="card stack"><p class="eyebrow">{{ order.isTest ? '客户体验' : '测评订单' }}</p><h1>{{ order.productTitle }}</h1><div class="price-line"><strong class="price">{{ formatPrice(order.amount) }}</strong><span v-if="order.isTest" class="badge">本次测试免费</span></div><div class="notice stack"><span class="muted small">订单号</span><code class="break-word">{{ order.id }}</code><button class="btn btn-secondary" @click="copyOrder">复制订单号</button></div><template v-if="['pending', 'success'].includes(order.refundState)"><p class="notice">该订单的测评权限已撤销。退款或付款凭证问题请联系商家。</p></template><template v-else-if="order.isTest && ['pending', 'testing'].includes(order.status)"><div class="notice"><strong>直接进入答题，无需付款</strong><p>测试内容与结果仍在完善中，欢迎体验完整流程。</p></div><button class="btn btn-primary" :disabled="busy" @click="freeStart">{{ busy ? '正在开通…' : '免付款进入答题' }}</button><details class="payment-preview"><summary>查看固定收款码（测试无需支付）</summary><img :src="qr || sessionInfo?.paymentQR" class="payment-image" alt="微信固定收款码，金额9.90元"><p class="muted">正式收款将使用此二维码；当前客户测试无需扫码或付款。</p></details></template><template v-else-if="order.status === 'paid' || order.status === 'testing'"><p class="notice">{{ order.isTest ? '测试权限已开通' : '付款已确认' }}</p><router-link class="btn btn-primary" :to="`/claim/${order.id}`">查看专属密码并进入答题</router-link></template><template v-else-if="order.status === 'pending'"><p>请使用微信扫描或识别二维码，支付 {{ formatPrice(order.amount) }}。</p><img v-if="qr" :src="qr" class="payment-image" alt="微信支付二维码"><p v-if="sessionInfo?.paymentMode === 'manual'" class="notice">付款后请联系提供测评链接的人，发送订单号与付款凭证。核对后会开通答题权限。</p><p class="muted">订单有效期剩余：{{ remaining }}</p><button class="btn btn-primary" :disabled="busy" @click="check">{{ busy ? '正在查询…' : '我已付款，查询开通' }}</button></template><template v-else><p class="notice">{{ order.status === 'expired' ? '订单已过期，请重新创建测评。已经付款的客户请联系提供测评链接的人核对。' : '该订单的测评权限已撤销。' }}</p><router-link class="btn btn-secondary" :to="`/p/${order.productSlug}`">重新创建测评</router-link></template><details><summary>换浏览器继续</summary><button class="btn btn-secondary" :disabled="busy" @click="copyContinue">复制一次性继续链接</button></details><p v-if="note" class="notice" role="status">{{ note }}</p></article><p v-if="error" class="error-message" role="alert">{{ error }}</p><button v-if="error && !order" class="btn btn-secondary" @click="load">重试加载</button></div></template>
