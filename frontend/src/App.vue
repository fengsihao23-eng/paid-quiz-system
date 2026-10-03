<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ensureSession, sessionInfo, errorMessage } from '@/api/client'
const route = useRoute(), error = ref('')
async function init() { error.value = ''; try { await ensureSession() } catch (e) { error.value = errorMessage(e) } }
onMounted(init)
</script>
<template>
  <header class="site-header"><router-link to="/" class="brand">自我探索 <span>QUIZ</span></router-link><nav><router-link to="/access">输入密码</router-link><router-link to="/help">帮助</router-link></nav></header>
  <div v-if="sessionInfo?.testMode" class="test-banner">客户测试版 · 免费答题，无需付款</div>
  <main v-if="error" class="container page"><div class="card stack"><p role="alert" class="error-message">{{ error }}</p><button class="btn btn-primary" @click="init">重新连接</button></div></main>
  <RouterView v-else-if="sessionInfo" :key="route.path" />
  <div v-else class="container page center"><span class="loading"></span><p>正在连接测评服务…</p></div>
  <footer class="site-footer"><span>娱乐测评，给生活多一个视角</span><div><router-link to="/terms">服务说明</router-link><router-link to="/privacy">隐私说明</router-link></div></footer>
</template>
