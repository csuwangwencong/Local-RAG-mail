<template>
  <aside class="folder-pane">
    <div>
      <h2>Local Mail</h2>
      <p class="account">{{ mail.accountEmail }}</p>
      <p class="status">已连接</p>
      <button
        class="folder-item"
        :class="{ 'is-active': mail.activeView === 'inbox' }"
        type="button"
        @click="mail.openInbox"
      >
        <span>收件箱</span>
        <strong>{{ mail.inboxUnread }}</strong>
      </button>
      <button
        class="folder-item sub-item"
        :class="{ 'is-active': mail.activeView === 'ai' }"
        type="button"
        @click="mail.openAiAssistant"
      >
        <span>AI问答</span>
      </button>
    </div>
    <el-button text @click="mail.disconnect">退出邮箱</el-button>
  </aside>
</template>

<script setup lang="ts">
import { useMailStore } from '../stores/mail'

const mail = useMailStore()
</script>
