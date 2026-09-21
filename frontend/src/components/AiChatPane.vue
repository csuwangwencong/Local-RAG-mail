<template>
  <section class="ai-chat-pane">
    <div class="ai-chat-scroll">
      <div v-if="ai.loadingConversation" class="chat-loading">
        <el-skeleton :rows="6" animated />
      </div>
      <div v-else-if="ai.messages.length === 0" class="chat-empty">
        <h2>开始邮件问答</h2>
      </div>
      <template v-else>
        <template v-for="message in ai.messages" :key="message.message_id">
          <div v-if="message.role === 'user'" class="chat-bubble user-bubble">{{ message.content }}</div>
          <article v-else-if="message.role === 'assistant'" class="chat-bubble assistant-bubble">
            <header>
              <span class="ai-mark">AI</span>
              <strong>思考完成</strong>
            </header>
            <section v-if="message.sources.length || ai.ragStatus?.status === 'ready'" class="source-panel">
              <div class="source-title">
                <strong>参考相关{{ message.sources.length }}条邮件信息来源</strong>
                <el-button
                  v-if="message.sources.length > 3"
                  size="small"
                  type="primary"
                  @click="toggleSources(message.message_id)"
                >
                  {{ expandedSourceIds.has(message.message_id) ? '收起' : '查看全部' }}
                </el-button>
              </div>
              <button
                v-for="source in visibleSources(message)"
                :key="`${source.uid}-${source.title}`"
                class="source-row"
                type="button"
                @click="openSource(source.uid)"
              >
                <span>
                  <strong>{{ source.title }}</strong>
                  <small>{{ source.sender_name || source.sender_address }} · {{ source.snippet }}</small>
                </span>
                <el-icon><TopRight /></el-icon>
              </button>
            </section>
            <section v-else class="source-placeholder">邮件知识库尚未接入，暂无参考邮件来源。</section>
            <p class="assistant-answer">{{ message.content }}</p>
            <footer class="answer-tools">
              <el-button text :icon="RefreshRight">重新生成</el-button>
              <span />
              <el-button text :icon="DocumentCopy" aria-label="复制回答" title="复制回答" />
              <el-button text aria-label="点赞" title="点赞">
                <svg class="thumb-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M7 10v10H4a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h3Zm2 10V9.5l4.4-6.7a1.8 1.8 0 0 1 3.3 1.1l-.6 4.1H20a2 2 0 0 1 2 2.3l-1.2 7.7a2.3 2.3 0 0 1-2.3 2H9Z"
                  />
                </svg>
              </el-button>
              <el-button text aria-label="点踩" title="点踩">
                <svg class="thumb-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M7 14V4H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h3Zm2-10v10.5l4.4 6.7a1.8 1.8 0 0 0 3.3-1.1l-.6-4.1H20a2 2 0 0 0 2-2.3L20.8 6a2.3 2.3 0 0 0-2.3-2H9Z"
                  />
                </svg>
              </el-button>
            </footer>
          </article>
        </template>
        <div v-if="ai.sending" class="chat-bubble assistant-bubble">
          <header>
            <span class="ai-mark">AI</span>
            <strong>正在思考</strong>
          </header>
          <el-skeleton :rows="3" animated />
        </div>
      </template>
    </div>

    <form class="chat-composer" @submit.prevent="submitQuestion">
      <el-input
        v-model="question"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 5 }"
        resize="none"
        placeholder="请在这里提问邮件助手"
        :disabled="ai.sending"
      />
      <div class="composer-footer">
        <el-select v-model="ai.selectedModel" class="model-select" size="small" :disabled="ai.sending">
          <el-option v-for="model in ai.models" :key="model.id" :label="model.name" :value="model.id" />
        </el-select>
        <span class="model-ready">{{ ai.sending ? '生成中' : '已就绪' }}</span>
        <el-button type="primary" circle :icon="Promotion" native-type="submit" :loading="ai.sending" />
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { DocumentCopy, Promotion, RefreshRight, TopRight } from '@element-plus/icons-vue'

import type { AiMessage, AiSource } from '../types/ai'
import { useAiStore } from '../stores/ai'
import { useMailStore } from '../stores/mail'

const question = ref('')
const expandedSourceIds = ref(new Set<string>())
const ai = useAiStore()
const mail = useMailStore()

function submitQuestion() {
  void ai.submit(question.value)
  question.value = ''
}

function openSource(uid: string | null) {
  if (!uid) return
  mail.openInbox()
  void mail.selectMessage(uid)
}

function visibleSources(message: AiMessage): AiSource[] {
  if (expandedSourceIds.value.has(message.message_id)) {
    return message.sources
  }
  return message.sources.slice(0, 3)
}

function toggleSources(messageId: string) {
  const next = new Set(expandedSourceIds.value)
  if (next.has(messageId)) {
    next.delete(messageId)
  } else {
    next.add(messageId)
  }
  expandedSourceIds.value = next
}
</script>
