<template>
  <main class="mail-shell">
    <FolderPane />
    <template v-if="mail.activeView === 'inbox'">
      <MessageListPane />
      <MessageReaderPane />
    </template>
    <template v-else>
      <AiConversationListPane />
      <AiChatPane />
    </template>
  </main>
</template>

<script setup lang="ts">
import AiChatPane from '../components/AiChatPane.vue'
import AiConversationListPane from '../components/AiConversationListPane.vue'
import FolderPane from '../components/FolderPane.vue'
import MessageListPane from '../components/MessageListPane.vue'
import MessageReaderPane from '../components/MessageReaderPane.vue'
import { useMailStore } from '../stores/mail'

const mail = useMailStore()
</script>
