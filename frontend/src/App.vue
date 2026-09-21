<template>
  <main v-if="mail.bootstrapping" class="boot-screen">
    <el-skeleton :rows="5" animated />
  </main>
  <MailView v-else-if="mail.connected" />
  <LoginView v-else />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import LoginView from './views/LoginView.vue'
import MailView from './views/MailView.vue'
import { useMailStore } from './stores/mail'

const mail = useMailStore()

onMounted(() => {
  void mail.restoreSession()
})
</script>
