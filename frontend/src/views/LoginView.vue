<template>
  <main class="login-view">
    <form class="login-panel" @submit.prevent="submit">
      <h1>localmail</h1>
      <el-alert v-if="mail.loginError" :title="mail.loginError" type="error" show-icon :closable="false" />
      <el-form label-position="top">
        <el-form-item label="QQ 邮箱" :error="emailError">
          <el-input v-model.trim="email" :disabled="loading" placeholder="123456@qq.com" autocomplete="username" />
        </el-form-item>
        <el-form-item label="授权码" :error="authError">
          <el-input
            v-model="authCode"
            :disabled="loading"
            type="password"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
      </el-form>
      <el-button type="primary" native-type="submit" :loading="loading" :disabled="loading" class="login-button">
        连接邮箱
      </el-button>
      <p class="login-tip">请使用 QQ 邮箱授权码，不是 QQ 登录密码。</p>
    </form>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { useMailStore } from '../stores/mail'

const mail = useMailStore()
const email = ref('')
const authCode = ref('')
const loading = ref(false)
const emailError = ref('')
const authError = ref('')

async function submit() {
  if (loading.value) return
  mail.clearErrors()
  emailError.value = ''
  authError.value = ''
  if (!email.value) emailError.value = '请输入 QQ 邮箱。'
  else if (!/^[^\s@]+@qq\.com$/i.test(email.value)) emailError.value = '请输入有效的 @qq.com 邮箱。'
  if (!authCode.value.trim()) authError.value = '请输入授权码。'
  if (emailError.value || authError.value) return
  loading.value = true
  try {
    await mail.connect(email.value, authCode.value)
  } catch {
    authCode.value = ''
  } finally {
    loading.value = false
  }
}
</script>
