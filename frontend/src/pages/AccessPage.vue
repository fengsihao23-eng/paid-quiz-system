<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { accessApi } from '@/api'
import { errorMessage } from '@/api/client'
import { rememberCode } from '@/utils/helpers'
const router = useRouter(), code = ref(''), busy = ref(false), error = ref('')
async function enter() { if (busy.value) return; busy.value = true; error.value = ''; try { const grant = (await accessApi.verify(code.value)).data; rememberCode(grant.id, code.value); code.value = ''; await router.push(`/quiz/${grant.id}/intro`) } catch(e) { error.value = errorMessage(e) } finally { busy.value = false } }
</script>
<template><div class="container page"><form class="card stack" @submit.prevent="enter"><p class="eyebrow">欢迎回来</p><h1>继续你的探索</h1><p class="muted">输入领取的专属密码，可接着答题或查看已完成的报告。</p><label for="access-code">专属密码</label><input id="access-code" v-model="code" class="input code-input" placeholder="XXXX-XXXX-XXXX-XXXX" maxlength="43" autocomplete="off" autocapitalize="characters" spellcheck="false" required><p v-if="error" class="error-message" role="alert">{{ error }}</p><button class="btn btn-primary" :disabled="busy || !code.trim()">{{ busy ? '正在验证…' : '验证并继续' }}</button><router-link to="/help">找不到密码或遇到问题？</router-link></form></div></template>
