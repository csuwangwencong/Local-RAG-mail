<template>
  <section class="reader-pane">
    <div v-if="!mail.selectedUid" class="reader-empty">请选择一封邮件</div>
    <LoadingState v-else-if="mail.detailLoading" />
    <ErrorState v-else-if="mail.detailError" :message="mail.detailError" @retry="mail.reloadSelectedMessage" />
    <article v-else-if="mail.selectedMessage" class="reader-content">
      <header class="reader-header">
        <h1>{{ mail.selectedMessage.subject || '无主题' }}</h1>
        <p>{{ formatAddressList(mail.selectedMessage.from) }}</p>
        <p>{{ formatFullDate(mail.selectedMessage.received_at) }}</p>
        <p>收件人：{{ formatAddressList(mail.selectedMessage.to) }}</p>
        <p v-if="mail.selectedMessage.cc.length">抄送人：{{ formatAddressList(mail.selectedMessage.cc) }}</p>
      </header>
      <div class="reader-body">
        <MailBodyFrame :body="mail.selectedMessage.body" />
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import MailBodyFrame from './MailBodyFrame.vue'
import LoadingState from './LoadingState.vue'
import ErrorState from './ErrorState.vue'
import type { MailAddress } from '../types/common'
import { useMailStore } from '../stores/mail'
import { formatFullDate } from '../utils/date'

const mail = useMailStore()

function formatAddressList(items: MailAddress[]) {
  return items.map((item) => (item.name ? `${item.name} <${item.address}>` : item.address)).join(', ')
}
</script>
