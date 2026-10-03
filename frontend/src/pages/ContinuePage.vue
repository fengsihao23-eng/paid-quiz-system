<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { orderApi } from '@/api'
import { errorMessage } from '@/api/client'
const route = useRoute(), router = useRouter(), error = ref('')
onMounted(async () => { const token = new URLSearchParams(route.hash.slice(1)).get('token'); await router.replace('/continue'); if (!token) { error.value = '继续链接不完整或已失效。请使用专属密码。'; return }; try { const data = (await orderApi.exchange(token)).data; await router.replace(data.canClaim ? `/claim/${data.orderId}` : `/checkout/${data.orderId}`) } catch(e) { error.value = errorMessage(e) } })
</script>
<template><div class="container page"><article class="card stack"><h1>恢复你的测评</h1><p v-if="error" class="error-message" role="alert">{{ error }}</p><p v-else>正在验证一次性继续链接…</p><router-link v-if="error" class="btn btn-primary" to="/access">使用专属密码继续</router-link></article></div></template>
