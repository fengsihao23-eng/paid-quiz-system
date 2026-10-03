<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { accessApi, quizApi } from '@/api'
import { errorMessage } from '@/api/client'
import { formatAccessCode, copyToClipboard } from '@/utils/helpers'
import type { QuizGrant } from '@/types'
const route = useRoute(), router = useRouter(), id = String(route.params.grantId)
const grant = ref<QuizGrant | null>(null), busy = ref(false), loading = ref(true), error = ref(''), note = ref('')
const code = sessionStorage.getItem(`quiz-code-${id}`) || ''
async function load() { loading.value = true; error.value = ''; try { grant.value = (await accessApi.getGrant(id)).data } catch(e) { error.value = errorMessage(e) } finally { loading.value = false } }
async function start() { if (!grant.value || busy.value) return; busy.value = true; error.value = ''; try { const attempt = (await quizApi.startAttempt(id)).data; await router.push(attempt.status === 'submitted' ? `/result/${attempt.id}` : `/quiz/${attempt.id}`) } catch(e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function copy() { try { await copyToClipboard(code); note.value = '密码已复制。换设备时可用它继续。' } catch(e) { error.value = errorMessage(e) } }
onMounted(load)
</script>
<template><div class="container page"><div v-if="loading" class="center"><span class="loading"></span></div><article v-else-if="grant" class="card stack"><p class="eyebrow">{{ grant.isTest ? '免费客户体验' : '准备开始' }}</p><h1>{{ grant.productTitle }}</h1><div class="meta"><span>{{ grant.questionCount }} 道题</span><span>约 {{ grant.estimatedMinutes }} 分钟</span></div><div class="notice"><p>请选择最接近你当前感受的选项。每题保存成功后可进入下一题，途中退出也能续答。</p><p>提交前可修改，提交后保存报告。每个密码对应一份答卷。</p></div><details v-if="code" open><summary>保存专属密码，方便续答</summary><code class="access-code">{{ formatAccessCode(code) }}</code><button class="btn btn-secondary" @click="copy">复制专属密码</button><p class="muted">请勿公开分享密码。</p></details><button class="btn btn-primary" :disabled="busy" @click="start">{{ busy ? '正在准备…' : grant.attemptStatus === 'submitted' ? '查看已有报告' : grant.attemptStatus === 'in_progress' ? '继续答题' : '开始答题' }}</button><p v-if="note" role="status">{{ note }}</p></article><p v-if="error" class="error-message" role="alert">{{ error }}</p><router-link v-if="error" class="btn btn-secondary" to="/access">重新输入密码</router-link></div></template>
