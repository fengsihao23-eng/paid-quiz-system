<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { productApi } from '@/api'
import { errorMessage } from '@/api/client'
import { formatPrice } from '@/utils/helpers'
import type { Product } from '@/types'
const products = ref<Product[]>([]), loading = ref(true), error = ref('')
async function load() { loading.value = true; error.value = ''; try { products.value = (await productApi.list()).data } catch(e) { error.value = errorMessage(e) } finally { loading.value = false } }
onMounted(load)
</script>
<template>
  <div class="container container-wide page">
    <section class="hero"><p class="eyebrow">一点好奇 · 一次自我发现</p><h1>给你的生活，<br>换一个视角。</h1><p class="muted">从日常的选择出发，探索你的城市偏好与心理年龄风格。</p></section>
    <div v-if="loading" class="center"><span class="loading"></span></div>
    <div v-else-if="error" class="card stack"><p class="error-message" role="alert">{{ error }}</p><button class="btn btn-secondary" @click="load">重试</button></div>
    <section v-else class="products-grid">
      <article v-for="p in products" :key="p.slug" class="card product-card"><span class="product-icon" aria-hidden="true">{{ p.slug === 'city-quiz' ? '🏙️' : '🧠' }}</span><h2>{{ p.title }}</h2><p class="muted">{{ p.description }}</p><div class="meta"><span>{{ p.questionCount }} 道题</span><span>约 {{ p.estimatedMinutes }} 分钟</span></div><div class="price-line"><strong class="price">{{ formatPrice(p.price) }}</strong><span v-if="p.testMode" class="badge">本次测试免费</span></div><router-link class="btn btn-primary" :to="`/p/${p.slug}`">{{ p.testMode ? '开始免费体验' : '查看测评' }}</router-link></article>
    </section>
    <section class="card resume-card"><div><h3>已有专属密码？</h3><p class="muted">继续未完成的答题，或重新查看你的报告。</p></div><router-link class="btn btn-secondary" to="/access">输入密码继续</router-link></section>
  </div>
</template>
