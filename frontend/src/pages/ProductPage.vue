<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { productApi, orderApi } from '@/api'
import { errorMessage } from '@/api/client'
import { formatPrice } from '@/utils/helpers'
import type { Product } from '@/types'
const route = useRoute(), router = useRouter()
const product = ref<Product | null>(null), loading = ref(true), busy = ref(false), error = ref('')
const slug = String(route.params.slug)
const requestKey = `order-request-${slug}`
let key = sessionStorage.getItem(requestKey) || crypto.randomUUID()
sessionStorage.setItem(requestKey, key)
async function load() { loading.value = true; error.value = ''; try { product.value = (await productApi.get(slug)).data } catch(e) { error.value = errorMessage(e) } finally { loading.value = false } }
async function start() { if (busy.value || !product.value?.canPurchase) return; busy.value = true; error.value = ''; try { const order = (await orderApi.create(slug, key)).data; sessionStorage.removeItem(requestKey); key = crypto.randomUUID(); await router.push(`/checkout/${order.id}`) } catch(e) { error.value = errorMessage(e) } finally { busy.value = false } }
onMounted(load)
</script>
<template><div class="container page"><router-link class="back-link" to="/">← 所有测评</router-link><div v-if="loading" class="center"><span class="loading"></span></div><article v-else-if="product" class="card stack"><span class="product-icon" aria-hidden="true">{{ product.slug === 'city-quiz' ? '🏙️' : '🧠' }}</span><p class="eyebrow">日常选择里的自我探索</p><h1>{{ product.title }}</h1><p class="muted">{{ product.description }}</p><div class="meta"><span>{{ product.questionCount }} 道题</span><span>约 {{ product.estimatedMinutes }} 分钟</span><span>可保存进度</span></div><div class="notice"><p>按第一感觉选择即可，没有标准答案。提交前可以修改；提交后可反复查看报告。</p><p>这是娱乐性体验，结果用于自我观察。</p></div><div class="price-line"><strong class="price">{{ formatPrice(product.price) }}</strong><span v-if="product.testMode" class="badge">客户测试 · 免费</span></div><p v-if="product.testMode" class="muted">下一页点击「免付款进入答题」，无需扫描收款码。</p><p v-else-if="!product.canPurchase" class="muted">该测评正在内容审核中，暂未开放购买。</p><button class="btn btn-primary" :disabled="busy || !product.canPurchase" @click="start">{{ busy ? '正在准备…' : product.testMode ? '开始免费体验' : '购买测评' }}</button></article><p v-if="error" class="error-message" role="alert">{{ error }}</p><button v-if="error && !product" class="btn btn-secondary" @click="load">重试</button></div></template>
