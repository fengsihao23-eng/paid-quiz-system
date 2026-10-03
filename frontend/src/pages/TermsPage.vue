<script setup lang="ts">
import { sessionInfo } from '@/api/client'
</script>
<template>
  <div class="container page"><article class="card stack prose">
    <h1>服务说明</h1>
    <p>本网站提供城市偏好和心理年龄娱乐测评。每个专属密码对应一份答卷，提交后可反复查看同一份报告。</p>
    <p>结果用于自我观察，不具有科学预测、医疗诊断或专业心理评估效力。</p>
    <p v-if="sessionInfo?.testMode">当前客户测试免费，无需扫码付款。</p>
    <p v-else>每套测评 ¥9.90，分别购买。微信固定收款码付款后，须提供订单号与付款凭证，由运营方核对并开通权限。</p>
    <p>涉及已付款订单的开通、退款或访问问题，请联系提供测评链接的人。妥善保存付款凭证与订单号。</p>
    <p>答题过程中可修改并保存答案；提交后不能修改，可使用同一密码重复查看报告。分享密码意味着分享同一份答卷的访问权。</p>
    <p>服务由本机临时服务器运行，维护、网络中断或主机关机可能导致暂时无法访问。</p>
    <router-link to="/">返回首页</router-link>
  </article></div>
</template>
