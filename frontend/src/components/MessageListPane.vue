<template>
  <section class="message-list-pane">
    <header class="list-header">
      <div>
        <h2>收件箱</h2>
        <p>共有 {{ mail.inboxTotal }} 封，{{ mail.inboxUnread }} 封未读</p>
      </div>
      <el-button :icon="Refresh" :loading="mail.refreshLoading" circle @click="mail.refreshInbox" />
    </header>

    <div class="list-body" @scroll.passive="onScroll">
      <LoadingState v-if="mail.listLoading && mail.messages.length === 0" />
      <ErrorState v-else-if="mail.listError" :message="mail.listError" @retry="mail.loadFirstPage" />
      <el-empty v-else-if="mail.messages.length === 0" description="收件箱为空" />
      <template v-else>
        <MessageListItem
          v-for="message in mail.messages"
          :key="message.uid"
          :message="message"
          :active="mail.selectedUid === message.uid"
          @select="mail.selectMessage(message.uid)"
        />
        <div class="load-more">
          <el-button v-if="mail.hasMore" :loading="mail.moreLoading" @click="mail.loadMore">加载更多</el-button>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'

import ErrorState from './ErrorState.vue'
import LoadingState from './LoadingState.vue'
import MessageListItem from './MessageListItem.vue'
import { useMailStore } from '../stores/mail'

const mail = useMailStore()

function onScroll(event: Event) {
  const target = event.target as HTMLElement
  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 80) {
    void mail.loadMore()
  }
}
</script>
