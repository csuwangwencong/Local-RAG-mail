<template>
  <section class="ai-list-pane">
    <header class="ai-side-header">
      <div>
        <h2>AI问答</h2>
        <p>{{ ai.loadingConversations ? '正在加载...' : aiStatusText }}</p>
      </div>
    </header>

    <div class="ai-actions">
      <el-button type="primary" :icon="Plus" :loading="ai.loadingConversations" @click="ai.newConversation">
        新建对话
      </el-button>
      <el-button :loading="ai.indexing" @click="ai.buildKnowledgeBase">构建知识库</el-button>
      <p class="rag-status">{{ ragStatusText }}</p>
    </div>

    <div class="ai-history">
      <el-alert v-if="ai.error" :title="ai.error" type="error" show-icon :closable="false" class="ai-error" />
      <button
        v-for="item in ai.conversations"
        :key="item.conversation_id"
        class="conversation-item"
        :class="{ 'is-active': ai.selectedConversationId === item.conversation_id }"
        type="button"
        @click="ai.selectConversation(item.conversation_id)"
      >
        <span>{{ item.title }}</span>
        <small>{{ formatMailDate(item.updated_at) }}</small>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'

import { useAiStore } from '../stores/ai'
import { formatMailDate } from '../utils/date'

const ai = useAiStore()
const aiStatusText = computed(() => `共 ${ai.conversations.length} 个历史会话`)
const ragStatusText = computed(() => {
  if (ai.indexing) return '正在索引最近 50 封邮件...'
  if (!ai.ragStatus || ai.ragStatus.status === 'not_built') return '知识库未构建'
  if (ai.ragStatus.status === 'ready') return `知识库已构建：${ai.ragStatus.indexed_messages} 封邮件`
  if (ai.ragStatus.status === 'error') return ai.ragStatus.error ?? '知识库构建失败'
  return '知识库状态更新中'
})

onMounted(() => {
  void ai.bootstrap()
})
</script>
