<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { orderApi, accessApi } from '@/api'
import { errorMessage } from '@/api/client'
import { formatAccessCode, rememberCode, copyToClipboard } from '@/utils/helpers'
import type { AccessCode } from '@/types'
const route = useRoute(), router = useRouter(), id = String(route.params.orderId)
const data = ref<AccessCode | null>(null), busy = ref(false), error = ref(''), note = ref('')
async function load() { busy.value = true; error.value = ''; try { data.value = (await orderApi.claimAccess(id)).data; rememberCode(data.value.grantId, data.value.code) } catch(e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function enter() { if (!data.value || busy.value) return; busy.value = true; error.value = ''; try { const grant = (await accessApi.verify(data.value.code)).data; await router.push(`/quiz/${grant.id}/intro`) } catch(e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function copy() { try { await copyToClipboard(data.value!.code); note.value = '密码已复制，请妥善保存。' } catch(e) { error.value = errorMessage(e) } }
onMounted(load)
</script>
<template><div class="container page"><article class="card stack"><p class="eyebrow">专属测评权限</p><h1>保存你的专属密码</h1><template v-if="data"><p class="muted">{{ data.productTitle }} · 使用同一密码可续答和查看报告。</p><code class="access-code">{{ formatAccessCode(data.code) }}</code><button class="btn btn-secondary" @click="copy">复制密码</button><p class="notice">每个密码对应一份答卷。分享密码会让对方访问同一份答案和结果，请妥善保存。</p><button class="btn btn-primary" :disabled="busy" @click="enter">{{ busy ? '正在进入…' : '进入答题' }}</button></template><span v-else-if="busy" class="loading"></span><p v-if="error" class="error-message" role="alert">{{ error }}</p><p v-if="note" role="status">{{ note }}</p><router-link :to="`/checkout/${id}`">返回订单</router-link><button v-if="error && !data" class="btn btn-secondary" @click="load">重试领取</button></article></div></template>
